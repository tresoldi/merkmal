#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "merkmal.h"

/* The registry every module-level call uses when the caller names none. It is
 * built once and never mutated, which is what makes sharing it safe: adding a
 * model requires an explicit Registry, so no call can change what another
 * caller sees.
 *
 * It is a file static, and the module declares m_size = -1 accordingly. The
 * wheel is built abi3, which is about binary compatibility across CPython
 * versions and not about subinterpreters; this module does not support those. */
static mk_registry *default_registry = NULL;
static PyObject *mk_py_error = NULL;
static const char *registry_capsule_name = "merkmal.registry";

/* The system used when a call names none. One definition: this string used to
 * be written out four times, three in this file and once in __init__.py. */
static const char *const default_system_name = "descriptive";

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

/* Holds the PyBytes behind every borrowed UTF-8 pointer a call takes, so one
 * clear at the end releases them all. Each function used to unwind its own
 * ladder of py_utf8_clear calls at every early return -- four of them in
 * distance alone, each an independent chance to leak one. */
#define PY_UTF8_SLOTS 4

typedef struct py_utf8_args {
    py_utf8 slots[PY_UTF8_SLOTS];
    size_t count;
} py_utf8_args;

static void py_utf8_args_clear(py_utf8_args *bag)
{
    size_t i;

    for (i = 0; i < bag->count; i++) {
        py_utf8_clear(&bag->slots[i]);
    }
    bag->count = 0;
}

static int py_utf8_take(py_utf8_args *bag, PyObject *obj, const char *name, const char **out)
{
    if (bag->count >= PY_UTF8_SLOTS) {
        PyErr_SetString(PyExc_SystemError, "merkmal: too many string arguments");
        return -1;
    }
    if (py_utf8_from_unicode(obj, name, &bag->slots[bag->count]) < 0) {
        return -1;
    }
    *out = bag->slots[bag->count].value;
    bag->count++;
    return 0;
}

/* An absent or None argument leaves *out at the default the caller seeded. */
static int py_utf8_take_optional(py_utf8_args *bag, PyObject *obj, const char *name, const char **out)
{
    if (obj == NULL || obj == Py_None) {
        return 0;
    }
    return py_utf8_take(bag, obj, name, out);
}

/* A Python sequence of str as the borrowed `const char **` the C library
 * takes, with the backing bytes objects kept alive until clear. */
typedef struct py_str_array {
    PyObject *sequence;
    py_utf8 *slots;
    const char **items;
    Py_ssize_t count;
} py_str_array;

static void py_str_array_clear(py_str_array *arr)
{
    Py_ssize_t i;

    for (i = 0; i < arr->count; i++) {
        py_utf8_clear(&arr->slots[i]);
    }
    PyMem_Free(arr->slots);
    PyMem_Free(arr->items);
    Py_XDECREF(arr->sequence);
    arr->slots = NULL;
    arr->items = NULL;
    arr->sequence = NULL;
    arr->count = 0;
}

static int py_str_array_init(py_str_array *arr, PyObject *obj, const char *name)
{
    Py_ssize_t i;

    arr->sequence = NULL;
    arr->slots = NULL;
    arr->items = NULL;
    arr->count = 0;

    arr->sequence = PySequence_List(obj);
    if (arr->sequence == NULL) {
        PyErr_Format(PyExc_TypeError, "%s must be an iterable of str", name);
        return -1;
    }
    arr->count = PySequence_Size(arr->sequence);
    if (arr->count < 0) {
        py_str_array_clear(arr);
        return -1;
    }
    /* PyMem_Calloc(0, ...) may return NULL without an error, which would be
     * indistinguishable from failure; an empty sequence is legitimate here. */
    arr->slots = (py_utf8 *)PyMem_Calloc((size_t)arr->count + 1, sizeof(*arr->slots));
    arr->items = (const char **)PyMem_Calloc((size_t)arr->count + 1, sizeof(*arr->items));
    if (arr->slots == NULL || arr->items == NULL) {
        py_str_array_clear(arr);
        PyErr_NoMemory();
        return -1;
    }
    for (i = 0; i < arr->count; i++) {
        PyObject *item = PySequence_GetItem(arr->sequence, i);

        if (item == NULL) {
            py_str_array_clear(arr);
            return -1;
        }
        if (py_utf8_from_unicode(item, name, &arr->slots[i]) < 0) {
            Py_DECREF(item);
            py_str_array_clear(arr);
            return -1;
        }
        Py_DECREF(item);
        arr->items[i] = arr->slots[i].value;
    }
    return 0;
}

/* Always returns NULL, with a Python exception set, so callers can `return
 * status_error(...)` directly. The exception type is this binding's contract;
 * the message comes from the C library, so the two cannot drift. */
static PyObject *status_error(mk_status status, const char *context)
{
    const char *message = mk_status_string(status);

    switch (status) {
    case MK_ERR_UNKNOWN_SYSTEM:
        PyErr_Format(PyExc_KeyError, "%s: %s", context, message);
        break;
    case MK_ERR_UNKNOWN_GRAPHEME:
    case MK_ERR_INVALID_ARGUMENT:
        PyErr_Format(PyExc_ValueError, "%s: %s", context, message);
        break;
    case MK_ERR_UNSUPPORTED_MODEL:
        PyErr_Format(PyExc_NotImplementedError, "%s: %s", context, message);
        break;
    case MK_ERR_OOM:
        PyErr_NoMemory();
        break;
    case MK_OK:
        /* A bug in this file: nothing should report success as a failure. */
        PyErr_Format(mk_py_error, "%s: reported success as an error", context);
        break;
    default:
        PyErr_Format(mk_py_error, "%s: %s", context, message);
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

/* The registry a call should use: the capsule the caller passed, or the
 * process default, built on first use. */
static mk_registry *resolve_registry(PyObject *registry_obj, const char *context)
{
    if (registry_obj != NULL && registry_obj != Py_None) {
        mk_registry *registry = PyCapsule_GetPointer(registry_obj, registry_capsule_name);

        if (registry == NULL) {
            PyErr_Format(PyExc_TypeError, "%s: invalid registry handle", context);
            return NULL;
        }
        return registry;
    }
    if (default_registry == NULL) {
        if (mk_registry_new_builtin(&default_registry) != MK_OK) {
            PyErr_SetString(PyExc_MemoryError, "failed to create merkmal registry");
            return NULL;
        }
    }
    return default_registry;
}

static const mk_system *resolve_system(
    mk_registry *registry,
    const char *name,
    const char *context
)
{
    const mk_system *system = NULL;
    mk_status status = mk_registry_get_system(registry, name, &system);

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

static PyObject *py_list_systems(PyObject *self, PyObject *args, PyObject *kwargs)
{
    static char *keywords[] = {"registry", NULL};
    PyObject *registry_obj = Py_None;
    mk_registry *registry;
    mk_string_list *systems = NULL;
    PyObject *result;
    mk_status status;

    (void)self;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "|O:list_systems", keywords, &registry_obj)) {
        return NULL;
    }
    registry = resolve_registry(registry_obj, "list_systems");
    if (registry == NULL) {
        return NULL;
    }
    status = mk_registry_list_systems(registry, &systems);
    if (status != MK_OK) {
        return status_error(status, "list_systems");
    }
    result = py_string_list_to_list(systems);
    mk_string_list_free(systems);
    return result;
}

static PyObject *py_get_features(PyObject *self, PyObject *args, PyObject *kwargs)
{
    static char *keywords[] = {"grapheme", "system", "registry", NULL};
    PyObject *grapheme_obj;
    PyObject *system_obj = Py_None;
    PyObject *registry_obj = Py_None;
    py_utf8_args bag = {{{NULL, NULL}}, 0};
    const char *grapheme = NULL;
    const char *system_name = default_system_name;
    mk_registry *registry;
    const mk_system *system;
    mk_feature_set *features = NULL;
    PyObject *result = NULL;
    mk_status status;

    (void)self;

    if (!PyArg_ParseTupleAndKeywords(
            args, kwargs, "O|OO:get_features", keywords,
            &grapheme_obj, &system_obj, &registry_obj
        )) {
        return NULL;
    }
    if (py_utf8_take(&bag, grapheme_obj, "grapheme", &grapheme) < 0 ||
        py_utf8_take_optional(&bag, system_obj, "system", &system_name) < 0) {
        goto done;
    }
    registry = resolve_registry(registry_obj, "get_features");
    if (registry == NULL) {
        goto done;
    }
    system = resolve_system(registry, system_name, "get_features");
    if (system == NULL) {
        goto done;
    }
    status = mk_system_grapheme_features(system, grapheme, &features);
    if (status != MK_OK) {
        status_error(status, "get_features");
        goto done;
    }
    result = py_feature_set_to_frozenset(features);
    mk_feature_set_free(features);

done:
    py_utf8_args_clear(&bag);
    return result;
}

static PyObject *py_is_segment(PyObject *self, PyObject *args, PyObject *kwargs)
{
    static char *keywords[] = {"grapheme", "system", "registry", NULL};
    PyObject *grapheme_obj;
    PyObject *system_obj = Py_None;
    PyObject *registry_obj = Py_None;
    py_utf8_args bag = {{{NULL, NULL}}, 0};
    const char *grapheme = NULL;
    const char *system_name = default_system_name;
    mk_registry *registry;
    const mk_system *system;
    int is_segment = 0;
    PyObject *result = NULL;
    mk_status status;

    (void)self;

    if (!PyArg_ParseTupleAndKeywords(
            args, kwargs, "O|OO:is_segment", keywords,
            &grapheme_obj, &system_obj, &registry_obj
        )) {
        return NULL;
    }
    if (py_utf8_take(&bag, grapheme_obj, "grapheme", &grapheme) < 0 ||
        py_utf8_take_optional(&bag, system_obj, "system", &system_name) < 0) {
        goto done;
    }
    registry = resolve_registry(registry_obj, "is_segment");
    if (registry == NULL) {
        goto done;
    }
    system = resolve_system(registry, system_name, "is_segment");
    if (system == NULL) {
        goto done;
    }
    status = mk_system_is_segment(system, grapheme, &is_segment);
    if (status != MK_OK) {
        status_error(status, "is_segment");
        goto done;
    }
    result = PyBool_FromLong(is_segment);

done:
    py_utf8_args_clear(&bag);
    return result;
}

static PyObject *py_distance(PyObject *self, PyObject *args, PyObject *kwargs)
{
    static char *keywords[] = {"a", "b", "system", "node_weights", "registry", NULL};
    PyObject *a_obj;
    PyObject *b_obj;
    PyObject *system_obj = Py_None;
    PyObject *node_weights_obj = Py_None;
    PyObject *registry_obj = Py_None;
    py_utf8_args bag = {{{NULL, NULL}}, 0};
    const char *a = NULL;
    const char *b = NULL;
    const char *system_name = default_system_name;
    const char *node_weights = NULL;
    mk_registry *registry;
    const mk_system *system;
    double distance = 0.0;
    PyObject *result = NULL;
    mk_status status;

    (void)self;

    if (!PyArg_ParseTupleAndKeywords(
            args, kwargs, "OO|OOO:distance", keywords,
            &a_obj, &b_obj, &system_obj, &node_weights_obj, &registry_obj
        )) {
        return NULL;
    }
    if (py_utf8_take(&bag, a_obj, "a", &a) < 0 ||
        py_utf8_take(&bag, b_obj, "b", &b) < 0 ||
        py_utf8_take_optional(&bag, system_obj, "system", &system_name) < 0 ||
        py_utf8_take_optional(&bag, node_weights_obj, "node_weights", &node_weights) < 0) {
        goto done;
    }
    registry = resolve_registry(registry_obj, "distance");
    if (registry == NULL) {
        goto done;
    }
    system = resolve_system(registry, system_name, "distance");
    if (system == NULL) {
        goto done;
    }
    status = mk_system_segment_distance_with_weights(system, a, b, node_weights, &distance);
    if (status != MK_OK) {
        status_error(status, "distance");
        goto done;
    }
    result = PyFloat_FromDouble(distance);

done:
    py_utf8_args_clear(&bag);
    return result;
}

/* Feature distance is a property of the compiled geometry, which every system
 * shares. It takes no system: the argument it used to accept was validated and
 * then discarded, so a caller passing system="phoible" was told nothing about
 * having been given clements-hume numbers. */
static PyObject *py_feature_distance(PyObject *self, PyObject *args)
{
    PyObject *a_obj;
    PyObject *b_obj;
    py_utf8_args bag = {{{NULL, NULL}}, 0};
    const char *a = NULL;
    const char *b = NULL;
    int distance = 0;
    PyObject *result = NULL;
    mk_status status;

    (void)self;

    if (!PyArg_ParseTuple(args, "OO:feature_distance", &a_obj, &b_obj)) {
        return NULL;
    }
    if (py_utf8_take(&bag, a_obj, "feat_a", &a) < 0 ||
        py_utf8_take(&bag, b_obj, "feat_b", &b) < 0) {
        goto done;
    }
    status = mk_feature_distance(a, b, &distance);
    if (status != MK_OK) {
        status_error(status, "feature_distance");
        goto done;
    }
    result = PyLong_FromLong(distance);

done:
    py_utf8_args_clear(&bag);
    return result;
}

/* Scores two caller-supplied feature sets against the compiled geometry,
 * without a system, a registry, or a grapheme that has to resolve. It is the
 * only way to exercise a scoring rule in isolation, which is why the geometry
 * fixtures are keyed by feature sets rather than by segments. */
static PyObject *py_sound_distance(PyObject *self, PyObject *args, PyObject *kwargs)
{
    static char *keywords[] = {"features_a", "features_b", "node_weights", NULL};
    PyObject *a_obj;
    PyObject *b_obj;
    PyObject *node_weights_obj = Py_None;
    py_str_array a = {NULL, NULL, NULL, 0};
    py_str_array b = {NULL, NULL, NULL, 0};
    py_utf8_args bag = {{{NULL, NULL}}, 0};
    const char *node_weights = NULL;
    double distance = 0.0;
    PyObject *result = NULL;
    mk_status status;

    (void)self;

    if (!PyArg_ParseTupleAndKeywords(
            args, kwargs, "OO|O:sound_distance", keywords,
            &a_obj, &b_obj, &node_weights_obj
        )) {
        return NULL;
    }
    if (py_utf8_take_optional(&bag, node_weights_obj, "node_weights", &node_weights) < 0) {
        goto done;
    }
    if (py_str_array_init(&a, a_obj, "features_a") < 0 ||
        py_str_array_init(&b, b_obj, "features_b") < 0) {
        goto done;
    }
    status = mk_sound_distance(
        a.items, (size_t)a.count,
        b.items, (size_t)b.count,
        node_weights,
        &distance
    );
    if (status != MK_OK) {
        status_error(status, "sound_distance");
        goto done;
    }
    result = PyFloat_FromDouble(distance);

done:
    py_str_array_clear(&a);
    py_str_array_clear(&b);
    py_utf8_args_clear(&bag);
    return result;
}

static PyObject *py_normalize(PyObject *self, PyObject *args)
{
    PyObject *grapheme_obj;
    py_utf8_args bag = {{{NULL, NULL}}, 0};
    const char *grapheme = NULL;
    char *normalized = NULL;
    PyObject *result = NULL;
    mk_status status;

    (void)self;

    if (!PyArg_ParseTuple(args, "O:normalize", &grapheme_obj)) {
        return NULL;
    }
    if (py_utf8_take(&bag, grapheme_obj, "grapheme", &grapheme) < 0) {
        goto done;
    }
    status = mk_normalize_grapheme(grapheme, &normalized);
    if (status != MK_OK) {
        status_error(status, "normalize");
        goto done;
    }
    result = PyUnicode_FromString(normalized);
    mk_free_string(normalized);

done:
    py_utf8_args_clear(&bag);
    return result;
}

/* mk_segment_ipa and mk_segment_ipa_merged have the same shape, so one body
 * serves both; which one runs is the caller's choice. */
static PyObject *py_segment_with(
    PyObject *args,
    mk_status (*segment)(const char *, mk_string_list **),
    const char *context
)
{
    PyObject *ipa_obj;
    py_utf8_args bag = {{{NULL, NULL}}, 0};
    const char *ipa = NULL;
    mk_string_list *segments = NULL;
    PyObject *result = NULL;
    mk_status status;

    if (!PyArg_ParseTuple(args, "O", &ipa_obj)) {
        return NULL;
    }
    if (py_utf8_take(&bag, ipa_obj, "ipa", &ipa) < 0) {
        goto done;
    }
    status = segment(ipa, &segments);
    if (status != MK_OK) {
        status_error(status, context);
        goto done;
    }
    result = py_string_list_to_list(segments);
    mk_string_list_free(segments);

done:
    py_utf8_args_clear(&bag);
    return result;
}

static PyObject *py_segment_ipa(PyObject *self, PyObject *args)
{
    (void)self;
    return py_segment_with(args, mk_segment_ipa, "segment_ipa");
}

static PyObject *py_segment_ipa_merged(PyObject *self, PyObject *args)
{
    (void)self;
    return py_segment_with(args, mk_segment_ipa_merged, "segment_ipa_merged");
}

static PyObject *py_system_segment_ipa(PyObject *self, PyObject *args, PyObject *kwargs)
{
    static char *keywords[] = {"ipa", "system", "registry", NULL};
    PyObject *ipa_obj;
    PyObject *system_obj = Py_None;
    PyObject *registry_obj = Py_None;
    py_utf8_args bag = {{{NULL, NULL}}, 0};
    const char *ipa = NULL;
    const char *system_name = default_system_name;
    mk_registry *registry;
    const mk_system *system;
    mk_string_list *segments = NULL;
    PyObject *result = NULL;
    mk_status status;

    (void)self;

    if (!PyArg_ParseTupleAndKeywords(
            args, kwargs, "O|OO:system_segment_ipa", keywords,
            &ipa_obj, &system_obj, &registry_obj
        )) {
        return NULL;
    }
    if (py_utf8_take(&bag, ipa_obj, "ipa", &ipa) < 0 ||
        py_utf8_take_optional(&bag, system_obj, "system", &system_name) < 0) {
        goto done;
    }
    registry = resolve_registry(registry_obj, "system_segment_ipa");
    if (registry == NULL) {
        goto done;
    }
    system = resolve_system(registry, system_name, "system_segment_ipa");
    if (system == NULL) {
        goto done;
    }
    status = mk_system_segment_ipa(system, ipa, &segments);
    if (status != MK_OK) {
        status_error(status, "system_segment_ipa");
        goto done;
    }
    result = py_string_list_to_list(segments);
    mk_string_list_free(segments);

done:
    py_utf8_args_clear(&bag);
    return result;
}

static PyObject *py_split_tone(PyObject *self, PyObject *args)
{
    PyObject *segment_obj;
    py_utf8_args bag = {{{NULL, NULL}}, 0};
    const char *segment = NULL;
    char *base = NULL;
    char *tone = NULL;
    PyObject *result = NULL;
    mk_status status;

    (void)self;

    if (!PyArg_ParseTuple(args, "O:split_tone", &segment_obj)) {
        return NULL;
    }
    if (py_utf8_take(&bag, segment_obj, "segment", &segment) < 0) {
        goto done;
    }
    status = mk_split_tone(segment, &base, &tone);
    if (status != MK_OK) {
        status_error(status, "split_tone");
        goto done;
    }
    /* An untoned segment yields None for the tone, not an empty string, so
     * "has no tone" and "has an empty tone" cannot be confused. */
    result = Py_BuildValue("(sz)", base, tone);
    mk_free_string(base);
    mk_free_string(tone);

done:
    py_utf8_args_clear(&bag);
    return result;
}

static PyObject *py_merge_tone_digits(PyObject *self, PyObject *args)
{
    PyObject *segments_obj;
    py_str_array input = {NULL, NULL, NULL, 0};
    mk_string_list *segments = NULL;
    mk_string_list *merged = NULL;
    PyObject *result = NULL;
    mk_status status;

    (void)self;

    if (!PyArg_ParseTuple(args, "O:merge_tone_digits", &segments_obj)) {
        return NULL;
    }
    if (py_str_array_init(&input, segments_obj, "segments") < 0) {
        return NULL;
    }
    status = mk_string_list_new(input.items, (size_t)input.count, &segments);
    if (status != MK_OK) {
        status_error(status, "merge_tone_digits");
        goto done;
    }
    status = mk_merge_tone_digits(segments, &merged);
    if (status != MK_OK) {
        status_error(status, "merge_tone_digits");
        goto done;
    }
    result = py_string_list_to_list(merged);

done:
    mk_string_list_free(segments);
    mk_string_list_free(merged);
    py_str_array_clear(&input);
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

static PyObject *py_add_model_text(PyObject *self, PyObject *args, PyObject *kwargs)
{
    static char *keywords[] = {"model_text", "registry", NULL};
    PyObject *text_obj;
    PyObject *registry_obj = Py_None;
    py_utf8_args bag = {{{NULL, NULL}}, 0};
    const char *text = NULL;
    mk_registry *registry;
    char *diagnostic = NULL;
    PyObject *result = NULL;
    mk_status status;

    (void)self;

    if (!PyArg_ParseTupleAndKeywords(
            args, kwargs, "O|O:add_model_text", keywords, &text_obj, &registry_obj
        )) {
        return NULL;
    }
    /* Deliberately no default. Every other call may fall back to the shared
     * registry because none of them change it; this one would, and every other
     * caller in the process would see the new system appear. */
    if (registry_obj == Py_None) {
        PyErr_SetString(
            PyExc_ValueError,
            "add_model_text requires an explicit registry, because the default one is "
            "shared process-wide; construct a merkmal.Registry()"
        );
        return NULL;
    }
    if (py_utf8_take(&bag, text_obj, "model_text", &text) < 0) {
        goto done;
    }
    registry = resolve_registry(registry_obj, "add_model_text");
    if (registry == NULL) {
        goto done;
    }
    status = mk_registry_add_model_text_ex(registry, text, &diagnostic);
    if (status != MK_OK) {
        /* The diagnostic names the offending line and token; without it the
         * caller only learns that something in the model was wrong. */
        if (diagnostic != NULL) {
            PyErr_Format(mk_py_error, "add_model_text: %s", diagnostic);
            mk_free_string(diagnostic);
        } else {
            status_error(status, "add_model_text");
        }
        goto done;
    }
    mk_free_string(diagnostic);
    result = Py_NewRef(Py_None);

done:
    py_utf8_args_clear(&bag);
    return result;
}

static PyMethodDef methods[] = {
    {"list_systems", (PyCFunction)py_list_systems, METH_VARARGS | METH_KEYWORDS,
     "List the systems in a registry."},
    {"get_features", (PyCFunction)py_get_features, METH_VARARGS | METH_KEYWORDS,
     "Return features for a grapheme."},
    {"is_segment", (PyCFunction)py_is_segment, METH_VARARGS | METH_KEYWORDS,
     "Return whether a grapheme is known."},
    {"distance", (PyCFunction)py_distance, METH_VARARGS | METH_KEYWORDS,
     "Return segment distance."},
    {"feature_distance", py_feature_distance, METH_VARARGS,
     "Return geometry feature distance."},
    {"sound_distance", (PyCFunction)py_sound_distance, METH_VARARGS | METH_KEYWORDS,
     "Return the geometry distance between two feature sets."},
    {"normalize", py_normalize, METH_VARARGS, "Normalize an IPA grapheme."},
    {"segment_ipa", py_segment_ipa, METH_VARARGS, "Segment an IPA string orthographically."},
    {"system_segment_ipa", (PyCFunction)py_system_segment_ipa, METH_VARARGS | METH_KEYWORDS,
     "Segment an IPA string by longest match against a system's inventory."},
    {"merge_tone_digits", py_merge_tone_digits, METH_VARARGS,
     "Attach Chao tone digit segments to nuclei."},
    {"split_tone", py_split_tone, METH_VARARGS,
     "Split a merged segment into (base, tone); tone is None when absent."},
    {"segment_ipa_merged", py_segment_ipa_merged, METH_VARARGS,
     "Segment IPA and attach Chao tone digits to nuclei."},
    {"registry_new", py_registry_new, METH_NOARGS, "Create a native registry capsule."},
    {"add_model_text", (PyCFunction)py_add_model_text, METH_VARARGS | METH_KEYWORDS,
     "Add runtime model text to a registry."},
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
