#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "merkmal.h"

static mk_registry *default_registry = NULL;
static PyObject *mk_py_error = NULL;

typedef struct py_utf8 {
    PyObject *bytes;
    const char *value;
} py_utf8;

static void py_utf8_clear(py_utf8 *arg)
{
    Py_XDECREF(arg->bytes);
    arg->bytes = NULL;
    arg->value = NULL;
}

static int py_utf8_from_unicode(PyObject *obj, const char *name, py_utf8 *out)
{
    out->bytes = NULL;
    out->value = NULL;
    if (!PyUnicode_Check(obj)) {
        PyErr_Format(PyExc_TypeError, "%s must be str", name);
        return -1;
    }
    out->bytes = PyUnicode_AsEncodedString(obj, "utf-8", "strict");
    if (out->bytes == NULL) {
        return -1;
    }
    out->value = PyBytes_AsString(out->bytes);
    if (out->value == NULL) {
        py_utf8_clear(out);
        return -1;
    }
    return 0;
}

static int ensure_registry(void)
{
    if (default_registry != NULL) {
        return 0;
    }
    if (mk_registry_new_builtin(&default_registry) != MK_OK) {
        PyErr_SetString(PyExc_MemoryError, "failed to create merkmal registry");
        return -1;
    }
    return 0;
}

static PyObject *status_error(mk_status status, const char *context)
{
    switch (status) {
    case MK_ERR_UNKNOWN_SYSTEM:
        PyErr_Format(PyExc_KeyError, "%s: unknown system", context);
        break;
    case MK_ERR_UNKNOWN_GRAPHEME:
        PyErr_Format(PyExc_ValueError, "%s: unknown grapheme", context);
        break;
    case MK_ERR_INVALID_ARGUMENT:
        PyErr_Format(PyExc_ValueError, "%s: invalid argument", context);
        break;
    case MK_ERR_UNSUPPORTED_MODEL:
        PyErr_Format(PyExc_NotImplementedError, "%s: unsupported model", context);
        break;
    case MK_ERR_PARSE:
        PyErr_Format(mk_py_error, "%s: parse error", context);
        break;
    case MK_ERR_OOM:
        PyErr_NoMemory();
        break;
    case MK_OK:
        Py_RETURN_NONE;
    default:
        PyErr_Format(mk_py_error, "%s: merkmal error %d", context, (int)status);
        break;
    }
    return NULL;
}

static int parse_system_kw(PyObject *system_obj, py_utf8 *system_arg, const char **system)
{
    system_arg->bytes = NULL;
    system_arg->value = NULL;
    *system = "descriptive";
    if (system_obj != NULL && system_obj != Py_None) {
        if (py_utf8_from_unicode(system_obj, "system", system_arg) < 0) {
            return -1;
        }
        *system = system_arg->value;
    }
    return 0;
}

static const mk_system *get_system_or_error(const char *name)
{
    const mk_system *system = NULL;
    mk_status status;

    if (ensure_registry() < 0) {
        return NULL;
    }
    status = mk_registry_get_system(default_registry, name == NULL ? "descriptive" : name, &system);
    if (status != MK_OK) {
        status_error(status, "get_system");
        return NULL;
    }
    return system;
}

static int py_list_set_steal(PyObject *list, Py_ssize_t index, PyObject *item)
{
    if (PyList_SetItem(list, index, item) < 0) {
        Py_DECREF(item);
        return -1;
    }
    return 0;
}

static PyObject *py_list_systems(PyObject *self, PyObject *args)
{
    mk_string_list *systems = NULL;
    PyObject *result;
    size_t i;
    mk_status status;

    (void)self;
    (void)args;

    if (ensure_registry() < 0) {
        return NULL;
    }
    status = mk_registry_list_systems(default_registry, &systems);
    if (status != MK_OK) {
        return status_error(status, "list_systems");
    }

    result = PyList_New((Py_ssize_t)mk_string_list_size(systems));
    if (result == NULL) {
        mk_string_list_free(systems);
        return NULL;
    }
    for (i = 0; i < mk_string_list_size(systems); i++) {
        PyObject *item = PyUnicode_FromString(mk_string_list_get(systems, i));
        if (item == NULL || py_list_set_steal(result, (Py_ssize_t)i, item) < 0) {
            mk_string_list_free(systems);
            Py_DECREF(result);
            return NULL;
        }
    }
    mk_string_list_free(systems);
    return result;
}

static PyObject *py_get_features(PyObject *self, PyObject *args, PyObject *kwargs)
{
    static char *keywords[] = {"grapheme", "system", NULL};
    PyObject *grapheme_obj;
    PyObject *system_obj = Py_None;
    py_utf8 grapheme_arg = {NULL, NULL};
    py_utf8 system_arg = {NULL, NULL};
    const char *system_name;
    const mk_system *system;
    mk_feature_set *features = NULL;
    PyObject *result;
    size_t i;
    mk_status status;

    (void)self;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|O:get_features", keywords, &grapheme_obj, &system_obj)) {
        return NULL;
    }
    if (py_utf8_from_unicode(grapheme_obj, "grapheme", &grapheme_arg) < 0 ||
        parse_system_kw(system_obj, &system_arg, &system_name) < 0) {
        py_utf8_clear(&grapheme_arg);
        return NULL;
    }
    system = get_system_or_error(system_name);
    if (system == NULL) {
        py_utf8_clear(&grapheme_arg);
        py_utf8_clear(&system_arg);
        return NULL;
    }

    status = mk_system_grapheme_features(system, grapheme_arg.value, &features);
    py_utf8_clear(&grapheme_arg);
    py_utf8_clear(&system_arg);
    if (status != MK_OK) {
        return status_error(status, "get_features");
    }

    result = PyFrozenSet_New(NULL);
    if (result == NULL) {
        mk_feature_set_free(features);
        return NULL;
    }
    for (i = 0; i < mk_feature_set_size(features); i++) {
        PyObject *item = PyUnicode_FromString(mk_feature_set_get(features, i));
        int add_status;
        if (item == NULL) {
            mk_feature_set_free(features);
            Py_DECREF(result);
            return NULL;
        }
        add_status = PySet_Add(result, item);
        Py_DECREF(item);
        if (add_status < 0) {
            mk_feature_set_free(features);
            Py_DECREF(result);
            return NULL;
        }
    }
    mk_feature_set_free(features);
    return result;
}

static PyObject *py_is_segment(PyObject *self, PyObject *args, PyObject *kwargs)
{
    static char *keywords[] = {"grapheme", "system", NULL};
    PyObject *grapheme_obj;
    PyObject *system_obj = Py_None;
    py_utf8 grapheme_arg = {NULL, NULL};
    py_utf8 system_arg = {NULL, NULL};
    const char *system_name;
    const mk_system *system;
    int is_segment = 0;
    mk_status status;

    (void)self;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|O:is_segment", keywords, &grapheme_obj, &system_obj)) {
        return NULL;
    }
    if (py_utf8_from_unicode(grapheme_obj, "grapheme", &grapheme_arg) < 0 ||
        parse_system_kw(system_obj, &system_arg, &system_name) < 0) {
        py_utf8_clear(&grapheme_arg);
        return NULL;
    }
    system = get_system_or_error(system_name);
    if (system == NULL) {
        py_utf8_clear(&grapheme_arg);
        py_utf8_clear(&system_arg);
        return NULL;
    }

    status = mk_system_is_segment(system, grapheme_arg.value, &is_segment);
    py_utf8_clear(&grapheme_arg);
    py_utf8_clear(&system_arg);
    if (status != MK_OK) {
        return status_error(status, "is_segment");
    }
    if (is_segment) {
        Py_RETURN_TRUE;
    }
    Py_RETURN_FALSE;
}

static PyObject *py_distance(PyObject *self, PyObject *args, PyObject *kwargs)
{
    static char *keywords[] = {"a", "b", "system", NULL};
    PyObject *a_obj;
    PyObject *b_obj;
    PyObject *system_obj = Py_None;
    py_utf8 a_arg = {NULL, NULL};
    py_utf8 b_arg = {NULL, NULL};
    py_utf8 system_arg = {NULL, NULL};
    const char *system_name;
    const mk_system *system;
    double distance = 0.0;
    mk_status status;

    (void)self;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO|O:distance", keywords, &a_obj, &b_obj, &system_obj)) {
        return NULL;
    }
    if (py_utf8_from_unicode(a_obj, "a", &a_arg) < 0 ||
        py_utf8_from_unicode(b_obj, "b", &b_arg) < 0 ||
        parse_system_kw(system_obj, &system_arg, &system_name) < 0) {
        py_utf8_clear(&a_arg);
        py_utf8_clear(&b_arg);
        return NULL;
    }
    system = get_system_or_error(system_name);
    if (system == NULL) {
        py_utf8_clear(&a_arg);
        py_utf8_clear(&b_arg);
        py_utf8_clear(&system_arg);
        return NULL;
    }

    status = mk_system_segment_distance(system, a_arg.value, b_arg.value, &distance);
    py_utf8_clear(&a_arg);
    py_utf8_clear(&b_arg);
    py_utf8_clear(&system_arg);
    if (status != MK_OK) {
        return status_error(status, "distance");
    }
    return PyFloat_FromDouble(distance);
}

static PyObject *py_feature_distance(PyObject *self, PyObject *args, PyObject *kwargs)
{
    static char *keywords[] = {"feat_a", "feat_b", "system", NULL};
    PyObject *a_obj;
    PyObject *b_obj;
    PyObject *system_obj = Py_None;
    py_utf8 a_arg = {NULL, NULL};
    py_utf8 b_arg = {NULL, NULL};
    py_utf8 system_arg = {NULL, NULL};
    const char *system_name;
    int distance = 0;
    mk_status status;

    (void)self;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO|O:feature_distance", keywords, &a_obj, &b_obj, &system_obj)) {
        return NULL;
    }
    if (py_utf8_from_unicode(a_obj, "feat_a", &a_arg) < 0 ||
        py_utf8_from_unicode(b_obj, "feat_b", &b_arg) < 0 ||
        parse_system_kw(system_obj, &system_arg, &system_name) < 0) {
        py_utf8_clear(&a_arg);
        py_utf8_clear(&b_arg);
        return NULL;
    }
    if (get_system_or_error(system_name) == NULL) {
        py_utf8_clear(&a_arg);
        py_utf8_clear(&b_arg);
        py_utf8_clear(&system_arg);
        return NULL;
    }

    status = mk_feature_distance(a_arg.value, b_arg.value, &distance);
    py_utf8_clear(&a_arg);
    py_utf8_clear(&b_arg);
    py_utf8_clear(&system_arg);
    if (status != MK_OK) {
        return status_error(status, "feature_distance");
    }
    return PyLong_FromLong(distance);
}

static PyObject *py_normalize(PyObject *self, PyObject *args)
{
    PyObject *grapheme_obj;
    py_utf8 grapheme_arg = {NULL, NULL};
    char *normalized = NULL;
    PyObject *result;
    mk_status status;

    (void)self;

    if (!PyArg_ParseTuple(args, "O:normalize", &grapheme_obj)) {
        return NULL;
    }
    if (py_utf8_from_unicode(grapheme_obj, "grapheme", &grapheme_arg) < 0) {
        return NULL;
    }
    status = mk_normalize_grapheme(grapheme_arg.value, &normalized);
    py_utf8_clear(&grapheme_arg);
    if (status != MK_OK) {
        return status_error(status, "normalize");
    }
    result = PyUnicode_FromString(normalized);
    mk_free_string(normalized);
    return result;
}

static PyObject *py_segment_ipa(PyObject *self, PyObject *args)
{
    PyObject *ipa_obj;
    py_utf8 ipa_arg = {NULL, NULL};
    mk_string_list *segments = NULL;
    PyObject *result;
    size_t i;
    mk_status status;

    (void)self;

    if (!PyArg_ParseTuple(args, "O:segment_ipa", &ipa_obj)) {
        return NULL;
    }
    if (py_utf8_from_unicode(ipa_obj, "ipa", &ipa_arg) < 0) {
        return NULL;
    }
    status = mk_segment_ipa(ipa_arg.value, &segments);
    py_utf8_clear(&ipa_arg);
    if (status != MK_OK) {
        return status_error(status, "segment_ipa");
    }

    result = PyList_New((Py_ssize_t)mk_string_list_size(segments));
    if (result == NULL) {
        mk_string_list_free(segments);
        return NULL;
    }
    for (i = 0; i < mk_string_list_size(segments); i++) {
        PyObject *item = PyUnicode_FromString(mk_string_list_get(segments, i));
        if (item == NULL || py_list_set_steal(result, (Py_ssize_t)i, item) < 0) {
            mk_string_list_free(segments);
            Py_DECREF(result);
            return NULL;
        }
    }
    mk_string_list_free(segments);
    return result;
}

static PyMethodDef methods[] = {
    {"list_systems", py_list_systems, METH_NOARGS, "List built-in feature systems."},
    {"get_features", (PyCFunction)py_get_features, METH_VARARGS | METH_KEYWORDS, "Return features for a grapheme."},
    {"is_segment", (PyCFunction)py_is_segment, METH_VARARGS | METH_KEYWORDS, "Return whether a grapheme is known."},
    {"distance", (PyCFunction)py_distance, METH_VARARGS | METH_KEYWORDS, "Return segment distance."},
    {"feature_distance", (PyCFunction)py_feature_distance, METH_VARARGS | METH_KEYWORDS, "Return geometry feature distance."},
    {"normalize", py_normalize, METH_VARARGS, "Normalize an IPA grapheme."},
    {"segment_ipa", py_segment_ipa, METH_VARARGS, "Segment an IPA string."},
    {NULL, NULL, 0, NULL}
};

static void module_free(void *module)
{
    (void)module;
    mk_registry_free(default_registry);
    default_registry = NULL;
}

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "merkmal._native",
    "Native merkmal wrapper.",
    -1,
    methods,
    NULL,
    NULL,
    NULL,
    module_free
};

PyMODINIT_FUNC PyInit__native(void)
{
    PyObject *module = PyModule_Create(&moduledef);
    if (module == NULL) {
        return NULL;
    }
    mk_py_error = PyErr_NewException("merkmal.NativeError", NULL, NULL);
    if (mk_py_error == NULL) {
        Py_DECREF(module);
        return NULL;
    }
    Py_INCREF(mk_py_error);
    if (PyModule_AddObject(module, "NativeError", mk_py_error) < 0) {
        Py_DECREF(mk_py_error);
        Py_DECREF(module);
        return NULL;
    }
    return module;
}
