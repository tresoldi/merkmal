#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "merkmal.h"

static mk_registry *default_registry = NULL;
static PyObject *mk_py_error = NULL;
static const char *registry_capsule_name = "merkmal.registry";

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

static void registry_capsule_destructor(PyObject *capsule)
{
    mk_registry *registry = PyCapsule_GetPointer(capsule, registry_capsule_name);
    if (registry != NULL) {
        mk_registry_free(registry);
    }
}

static mk_registry *registry_from_capsule(PyObject *obj, const char *context)
{
    mk_registry *registry = PyCapsule_GetPointer(obj, registry_capsule_name);
    if (registry == NULL) {
        PyErr_Format(PyExc_TypeError, "%s: invalid registry handle", context);
        return NULL;
    }
    return registry;
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

static const mk_system *get_system_from_registry_or_error(
    mk_registry *registry,
    const char *name,
    const char *context
)
{
    const mk_system *system = NULL;
    mk_status status = mk_registry_get_system(registry, name == NULL ? "descriptive" : name, &system);
    if (status != MK_OK) {
        status_error(status, context);
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

static PyObject *py_string_list_to_list(mk_string_list *strings)
{
    PyObject *result;
    size_t i;

    result = PyList_New((Py_ssize_t)mk_string_list_size(strings));
    if (result == NULL) {
        return NULL;
    }
    for (i = 0; i < mk_string_list_size(strings); i++) {
        PyObject *item = PyUnicode_FromString(mk_string_list_get(strings, i));
        if (item == NULL || py_list_set_steal(result, (Py_ssize_t)i, item) < 0) {
            Py_DECREF(result);
            return NULL;
        }
    }
    return result;
}

/* Converts an owned C feature set into the immutable Python result type. */
static PyObject *py_feature_set_to_frozenset(const mk_feature_set *features)
{
    PyObject *result = PyFrozenSet_New(NULL);
    size_t i;

    if (result == NULL) {
        return NULL;
    }
    for (i = 0; i < mk_feature_set_size(features); i++) {
        PyObject *item = PyUnicode_FromString(mk_feature_set_get(features, i));
        if (item == NULL) {
            Py_DECREF(result);
            return NULL;
        }
        if (PySet_Add(result, item) < 0) {
            Py_DECREF(item);
            Py_DECREF(result);
            return NULL;
        }
        Py_DECREF(item);
    }
    return result;
}

static PyObject *py_list_systems(PyObject *self, PyObject *args)
{
    mk_string_list *systems = NULL;
    PyObject *result;
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

    result = py_string_list_to_list(systems);
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

    result = py_feature_set_to_frozenset(features);
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
    static char *keywords[] = {"a", "b", "system", "node_weights", NULL};
    PyObject *a_obj;
    PyObject *b_obj;
    PyObject *system_obj = Py_None;
    PyObject *node_weights_obj = Py_None;
    py_utf8 a_arg = {NULL, NULL};
    py_utf8 b_arg = {NULL, NULL};
    py_utf8 system_arg = {NULL, NULL};
    py_utf8 node_weights_arg = {NULL, NULL};
    const char *system_name;
    const char *node_weights = NULL;
    const mk_system *system;
    double distance = 0.0;
    mk_status status;

    (void)self;

    if (!PyArg_ParseTupleAndKeywords(
            args, kwargs, "OO|OO:distance", keywords,
            &a_obj, &b_obj, &system_obj, &node_weights_obj
        )) {
        return NULL;
    }
    if (py_utf8_from_unicode(a_obj, "a", &a_arg) < 0 ||
        py_utf8_from_unicode(b_obj, "b", &b_arg) < 0 ||
        parse_system_kw(system_obj, &system_arg, &system_name) < 0) {
        py_utf8_clear(&a_arg);
        py_utf8_clear(&b_arg);
        return NULL;
    }
    if (node_weights_obj != NULL && node_weights_obj != Py_None) {
        if (py_utf8_from_unicode(node_weights_obj, "node_weights", &node_weights_arg) < 0) {
            py_utf8_clear(&a_arg);
            py_utf8_clear(&b_arg);
            py_utf8_clear(&system_arg);
            return NULL;
        }
        node_weights = node_weights_arg.value;
    }
    system = get_system_or_error(system_name);
    if (system == NULL) {
        py_utf8_clear(&a_arg);
        py_utf8_clear(&b_arg);
        py_utf8_clear(&system_arg);
        py_utf8_clear(&node_weights_arg);
        return NULL;
    }

    status = mk_system_segment_distance_with_weights(
        system,
        a_arg.value,
        b_arg.value,
        node_weights,
        &distance
    );
    py_utf8_clear(&a_arg);
    py_utf8_clear(&b_arg);
    py_utf8_clear(&system_arg);
    py_utf8_clear(&node_weights_arg);
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

    result = py_string_list_to_list(segments);
    mk_string_list_free(segments);
    return result;
}

static PyObject *py_segment_ipa_merged(PyObject *self, PyObject *args)
{
    PyObject *ipa_obj;
    py_utf8 ipa_arg = {NULL, NULL};
    mk_string_list *segments = NULL;
    PyObject *result;
    mk_status status;

    (void)self;

    if (!PyArg_ParseTuple(args, "O:segment_ipa_merged", &ipa_obj)) {
        return NULL;
    }
    if (py_utf8_from_unicode(ipa_obj, "ipa", &ipa_arg) < 0) {
        return NULL;
    }
    status = mk_segment_ipa_merged(ipa_arg.value, &segments);
    py_utf8_clear(&ipa_arg);
    if (status != MK_OK) {
        return status_error(status, "segment_ipa_merged");
    }

    result = py_string_list_to_list(segments);
    mk_string_list_free(segments);
    return result;
}

static PyObject *py_system_segment_ipa(PyObject *self, PyObject *args, PyObject *kwargs)
{
    static char *keywords[] = {"ipa", "system", NULL};
    PyObject *ipa_obj;
    PyObject *system_obj = Py_None;
    py_utf8 ipa_arg = {NULL, NULL};
    py_utf8 system_arg = {NULL, NULL};
    const char *system_name;
    const mk_system *system;
    mk_string_list *segments = NULL;
    PyObject *result;
    mk_status status;

    (void)self;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|O:system_segment_ipa", keywords, &ipa_obj, &system_obj)) {
        return NULL;
    }
    if (py_utf8_from_unicode(ipa_obj, "ipa", &ipa_arg) < 0 ||
        parse_system_kw(system_obj, &system_arg, &system_name) < 0) {
        py_utf8_clear(&ipa_arg);
        return NULL;
    }
    system = get_system_or_error(system_name);
    if (system == NULL) {
        py_utf8_clear(&ipa_arg);
        py_utf8_clear(&system_arg);
        return NULL;
    }

    status = mk_system_segment_ipa(system, ipa_arg.value, &segments);
    py_utf8_clear(&ipa_arg);
    py_utf8_clear(&system_arg);
    if (status != MK_OK) {
        return status_error(status, "system_segment_ipa");
    }

    result = py_string_list_to_list(segments);
    mk_string_list_free(segments);
    return result;
}

static PyObject *py_split_tone(PyObject *self, PyObject *args)
{
    PyObject *segment_obj;
    py_utf8 segment_arg = {NULL, NULL};
    char *base = NULL;
    char *tone = NULL;
    PyObject *result;
    mk_status status;

    (void)self;

    if (!PyArg_ParseTuple(args, "O:split_tone", &segment_obj)) {
        return NULL;
    }
    if (py_utf8_from_unicode(segment_obj, "segment", &segment_arg) < 0) {
        return NULL;
    }
    status = mk_split_tone(segment_arg.value, &base, &tone);
    py_utf8_clear(&segment_arg);
    if (status != MK_OK) {
        return status_error(status, "split_tone");
    }
    /* An untoned segment yields None for the tone, not an empty string, so
     * "has no tone" and "has an empty tone" cannot be confused. */
    result = Py_BuildValue("(sz)", base, tone);
    mk_free_string(base);
    mk_free_string(tone);
    return result;
}

static PyObject *py_merge_tone_digits(PyObject *self, PyObject *args)
{
    PyObject *segments_obj;
    PyObject *sequence = NULL;
    Py_ssize_t count;
    py_utf8 *segment_args;
    const char **items;
    mk_string_list *segments = NULL;
    mk_string_list *merged = NULL;
    PyObject *result = NULL;
    Py_ssize_t i;
    mk_status status;

    (void)self;

    if (!PyArg_ParseTuple(args, "O:merge_tone_digits", &segments_obj)) {
        return NULL;
    }
    sequence = PySequence_List(segments_obj);
    if (sequence == NULL) {
        PyErr_SetString(PyExc_TypeError, "segments must be an iterable of str");
        return NULL;
    }
    count = PySequence_Size(sequence);
    if (count < 0) {
        Py_DECREF(sequence);
        return NULL;
    }
    segment_args = (py_utf8 *)PyMem_Calloc((size_t)count, sizeof(*segment_args));
    items = (const char **)PyMem_Calloc((size_t)count, sizeof(*items));
    if (segment_args == NULL || items == NULL) {
        PyMem_Free(segment_args);
        PyMem_Free(items);
        Py_DECREF(sequence);
        return PyErr_NoMemory();
    }

    for (i = 0; i < count; i++) {
        PyObject *item = PySequence_GetItem(sequence, i);
        if (item == NULL) {
            goto cleanup;
        }
        if (py_utf8_from_unicode(item, "segment", &segment_args[i]) < 0) {
            Py_DECREF(item);
            goto cleanup;
        }
        Py_DECREF(item);
        items[i] = segment_args[i].value;
    }

    status = mk_string_list_new(items, (size_t)count, &segments);
    if (status != MK_OK) {
        status_error(status, "merge_tone_digits");
        goto cleanup;
    }
    status = mk_merge_tone_digits(segments, &merged);
    if (status != MK_OK) {
        status_error(status, "merge_tone_digits");
        goto cleanup;
    }

    result = py_string_list_to_list(merged);

cleanup:
    for (i = 0; i < count; i++) {
        py_utf8_clear(&segment_args[i]);
    }
    mk_string_list_free(segments);
    mk_string_list_free(merged);
    PyMem_Free(segment_args);
    PyMem_Free(items);
    Py_DECREF(sequence);
    return result;
}

static PyObject *py_registry_new(PyObject *self, PyObject *args)
{
    mk_registry *registry = NULL;
    mk_status status;

    (void)self;
    (void)args;

    status = mk_registry_new_builtin(&registry);
    if (status != MK_OK) {
        return status_error(status, "Registry");
    }
    return PyCapsule_New(registry, registry_capsule_name, registry_capsule_destructor);
}

static PyObject *py_registry_add_model_text(PyObject *self, PyObject *args)
{
    PyObject *capsule;
    PyObject *text_obj;
    mk_registry *registry;
    py_utf8 text_arg = {NULL, NULL};
    mk_status status;

    (void)self;

    if (!PyArg_ParseTuple(args, "OO:registry_add_model_text", &capsule, &text_obj)) {
        return NULL;
    }
    registry = registry_from_capsule(capsule, "registry_add_model_text");
    if (registry == NULL) {
        return NULL;
    }
    if (py_utf8_from_unicode(text_obj, "model_text", &text_arg) < 0) {
        return NULL;
    }
    {
        char *diagnostic = NULL;

        status = mk_registry_add_model_text_ex(registry, text_arg.value, &diagnostic);
        py_utf8_clear(&text_arg);
        if (status != MK_OK) {
            /* The diagnostic names the offending line and token; without it the
             * caller only learns that something in the model was wrong. */
            if (diagnostic != NULL) {
                PyErr_Format(mk_py_error, "registry_add_model_text: %s", diagnostic);
                mk_free_string(diagnostic);
                return NULL;
            }
            return status_error(status, "registry_add_model_text");
        }
        mk_free_string(diagnostic);
    }
    Py_RETURN_NONE;
}

static PyObject *py_registry_list_systems(PyObject *self, PyObject *args)
{
    PyObject *capsule;
    mk_registry *registry;
    mk_string_list *systems = NULL;
    PyObject *result;
    mk_status status;

    (void)self;

    if (!PyArg_ParseTuple(args, "O:registry_list_systems", &capsule)) {
        return NULL;
    }
    registry = registry_from_capsule(capsule, "registry_list_systems");
    if (registry == NULL) {
        return NULL;
    }
    status = mk_registry_list_systems(registry, &systems);
    if (status != MK_OK) {
        return status_error(status, "registry_list_systems");
    }
    result = py_string_list_to_list(systems);
    mk_string_list_free(systems);
    return result;
}

static PyObject *py_registry_get_features(PyObject *self, PyObject *args)
{
    PyObject *capsule;
    PyObject *system_obj;
    PyObject *grapheme_obj;
    mk_registry *registry;
    py_utf8 system_arg = {NULL, NULL};
    py_utf8 grapheme_arg = {NULL, NULL};
    const mk_system *system;
    mk_feature_set *features = NULL;
    PyObject *result;
    mk_status status;

    (void)self;

    if (!PyArg_ParseTuple(args, "OOO:registry_get_features", &capsule, &system_obj, &grapheme_obj)) {
        return NULL;
    }
    registry = registry_from_capsule(capsule, "registry_get_features");
    if (registry == NULL) {
        return NULL;
    }
    if (py_utf8_from_unicode(system_obj, "system", &system_arg) < 0 ||
        py_utf8_from_unicode(grapheme_obj, "grapheme", &grapheme_arg) < 0) {
        py_utf8_clear(&system_arg);
        return NULL;
    }
    system = get_system_from_registry_or_error(registry, system_arg.value, "registry_get_features");
    if (system == NULL) {
        py_utf8_clear(&system_arg);
        py_utf8_clear(&grapheme_arg);
        return NULL;
    }
    status = mk_system_grapheme_features(system, grapheme_arg.value, &features);
    py_utf8_clear(&system_arg);
    py_utf8_clear(&grapheme_arg);
    if (status != MK_OK) {
        return status_error(status, "registry_get_features");
    }
    result = py_feature_set_to_frozenset(features);
    mk_feature_set_free(features);
    return result;
}

static PyObject *py_registry_is_segment(PyObject *self, PyObject *args)
{
    PyObject *capsule;
    PyObject *system_obj;
    PyObject *grapheme_obj;
    mk_registry *registry;
    py_utf8 system_arg = {NULL, NULL};
    py_utf8 grapheme_arg = {NULL, NULL};
    const mk_system *system;
    int is_segment = 0;
    mk_status status;

    (void)self;

    if (!PyArg_ParseTuple(args, "OOO:registry_is_segment", &capsule, &system_obj, &grapheme_obj)) {
        return NULL;
    }
    registry = registry_from_capsule(capsule, "registry_is_segment");
    if (registry == NULL) {
        return NULL;
    }
    if (py_utf8_from_unicode(system_obj, "system", &system_arg) < 0 ||
        py_utf8_from_unicode(grapheme_obj, "grapheme", &grapheme_arg) < 0) {
        py_utf8_clear(&system_arg);
        return NULL;
    }
    system = get_system_from_registry_or_error(registry, system_arg.value, "registry_is_segment");
    if (system == NULL) {
        py_utf8_clear(&system_arg);
        py_utf8_clear(&grapheme_arg);
        return NULL;
    }
    status = mk_system_is_segment(system, grapheme_arg.value, &is_segment);
    py_utf8_clear(&system_arg);
    py_utf8_clear(&grapheme_arg);
    if (status != MK_OK) {
        return status_error(status, "registry_is_segment");
    }
    if (is_segment) {
        Py_RETURN_TRUE;
    }
    Py_RETURN_FALSE;
}

static PyObject *py_registry_distance(PyObject *self, PyObject *args)
{
    PyObject *capsule;
    PyObject *system_obj;
    PyObject *a_obj;
    PyObject *b_obj;
    PyObject *node_weights_obj = Py_None;
    mk_registry *registry;
    py_utf8 system_arg = {NULL, NULL};
    py_utf8 a_arg = {NULL, NULL};
    py_utf8 b_arg = {NULL, NULL};
    py_utf8 node_weights_arg = {NULL, NULL};
    const char *node_weights = NULL;
    const mk_system *system;
    double distance = 0.0;
    mk_status status;

    (void)self;

    if (!PyArg_ParseTuple(args, "OOOO|O:registry_distance", &capsule, &system_obj, &a_obj, &b_obj, &node_weights_obj)) {
        return NULL;
    }
    registry = registry_from_capsule(capsule, "registry_distance");
    if (registry == NULL) {
        return NULL;
    }
    if (py_utf8_from_unicode(system_obj, "system", &system_arg) < 0 ||
        py_utf8_from_unicode(a_obj, "a", &a_arg) < 0 ||
        py_utf8_from_unicode(b_obj, "b", &b_arg) < 0) {
        py_utf8_clear(&system_arg);
        py_utf8_clear(&a_arg);
        return NULL;
    }
    if (node_weights_obj != NULL && node_weights_obj != Py_None) {
        if (py_utf8_from_unicode(node_weights_obj, "node_weights", &node_weights_arg) < 0) {
            py_utf8_clear(&system_arg);
            py_utf8_clear(&a_arg);
            py_utf8_clear(&b_arg);
            return NULL;
        }
        node_weights = node_weights_arg.value;
    }
    system = get_system_from_registry_or_error(registry, system_arg.value, "registry_distance");
    if (system == NULL) {
        py_utf8_clear(&system_arg);
        py_utf8_clear(&a_arg);
        py_utf8_clear(&b_arg);
        py_utf8_clear(&node_weights_arg);
        return NULL;
    }
    status = mk_system_segment_distance_with_weights(system, a_arg.value, b_arg.value, node_weights, &distance);
    py_utf8_clear(&system_arg);
    py_utf8_clear(&a_arg);
    py_utf8_clear(&b_arg);
    py_utf8_clear(&node_weights_arg);
    if (status != MK_OK) {
        return status_error(status, "registry_distance");
    }
    return PyFloat_FromDouble(distance);
}

static PyMethodDef methods[] = {
    {"list_systems", py_list_systems, METH_NOARGS, "List built-in feature systems."},
    {"get_features", (PyCFunction)py_get_features, METH_VARARGS | METH_KEYWORDS, "Return features for a grapheme."},
    {"is_segment", (PyCFunction)py_is_segment, METH_VARARGS | METH_KEYWORDS, "Return whether a grapheme is known."},
    {"distance", (PyCFunction)py_distance, METH_VARARGS | METH_KEYWORDS, "Return segment distance."},
    {"feature_distance", (PyCFunction)py_feature_distance, METH_VARARGS | METH_KEYWORDS, "Return geometry feature distance."},
    {"normalize", py_normalize, METH_VARARGS, "Normalize an IPA grapheme."},
    {"segment_ipa", py_segment_ipa, METH_VARARGS, "Segment an IPA string orthographically."},
    {"system_segment_ipa", (PyCFunction)py_system_segment_ipa, METH_VARARGS | METH_KEYWORDS, "Segment an IPA string by longest match against a system's inventory."},
    {"merge_tone_digits", py_merge_tone_digits, METH_VARARGS, "Attach Chao tone digit segments to nuclei."},
    {"split_tone", py_split_tone, METH_VARARGS, "Split a merged segment into (base, tone); tone is None when absent."},
    {"segment_ipa_merged", py_segment_ipa_merged, METH_VARARGS, "Segment IPA and attach Chao tone digits to nuclei."},
    {"_registry_new", py_registry_new, METH_NOARGS, "Create a native registry capsule."},
    {"_registry_add_model_text", py_registry_add_model_text, METH_VARARGS, "Add runtime model text to a native registry."},
    {"_registry_list_systems", py_registry_list_systems, METH_VARARGS, "List systems in a native registry."},
    {"_registry_get_features", py_registry_get_features, METH_VARARGS, "Return features from a native registry."},
    {"_registry_is_segment", py_registry_is_segment, METH_VARARGS, "Return segment validity from a native registry."},
    {"_registry_distance", py_registry_distance, METH_VARARGS, "Return segment distance from a native registry."},
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
