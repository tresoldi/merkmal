/* Registry lifecycle: holding systems, handing them out, and installing a
 * model parsed from caller-supplied text. The parser itself is model_text.c. */

#include "registry.h"

#include "merkmal.h"
#include "model_text.h"
#include "string_list.h"
#include "strings.h"

#include <stdlib.h>
#include <string.h>

static void mk_free_owned_system(mk_system *system)
{
    size_t i;

    if (system == NULL || !system->owns) {
        return;
    }
    free(system->owned_name);
    for (i = 0; i < system->owned.entry_count; i++) {
        mk_builtin_entry *entry = &system->owned.entries[i];
        size_t j;

        free(entry->grapheme);
        for (j = 0; j < entry->feature_count; j++) {
            free(entry->features[j]);
        }
        free(entry->features);
    }
    free(system->owned.entries);
    system->builtin = NULL;
    system->owned_name = NULL;
    memset(&system->owned, 0, sizeof(system->owned));
    system->owns = 0;
}

/*
 * Allocates each system separately. The registry array may be reallocated
 * when a runtime model is added, but a system returned to the caller must not
 * move as a result of that operation.
 */
mk_status mk_registry_new_builtin(mk_registry **out)
{
    mk_registry *registry;
    size_t i;

    if (out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = NULL;

    registry = (mk_registry *)calloc(1, sizeof(*registry));
    if (registry == NULL) {
        return MK_ERR_OOM;
    }

    registry->systems = (mk_system **)calloc(
        mki_builtin_system_count,
        sizeof(*registry->systems)
    );
    if (registry->systems == NULL) {
        free(registry);
        return MK_ERR_OOM;
    }
    registry->system_count = mki_builtin_system_count;

    for (i = 0; i < mki_builtin_system_count; i++) {
        registry->systems[i] = (mk_system *)calloc(1, sizeof(*registry->systems[i]));
        if (registry->systems[i] == NULL) {
            while (i > 0) {
                i--;
                free(registry->systems[i]);
            }
            free(registry->systems);
            free(registry);
            return MK_ERR_OOM;
        }
        registry->systems[i]->builtin = &mki_builtin_systems[i];
    }

    *out = registry;
    return MK_OK;
}

void mk_registry_free(mk_registry *registry)
{
    size_t i;

    if (registry == NULL) {
        return;
    }
    for (i = 0; i < registry->system_count; i++) {
        mk_free_owned_system(registry->systems[i]);
        free(registry->systems[i]);
    }
    free(registry->systems);
    free(registry);
}

mk_status mk_registry_list_systems(
    const mk_registry *registry,
    mk_string_list **out
)
{
    const char **names;
    size_t i;
    mk_status status;

    if (registry == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }

    names = (const char **)calloc(registry->system_count, sizeof(*names));
    if (names == NULL) {
        return MK_ERR_OOM;
    }
    for (i = 0; i < registry->system_count; i++) {
        names[i] = registry->systems[i]->builtin->name;
    }

    status = mki_string_list_from_borrowed(names, registry->system_count, out);
    free(names);
    return status;
}

mk_status mk_registry_get_system(
    const mk_registry *registry,
    const char *name,
    const mk_system **out
)
{
    size_t i;

    if (registry == NULL || name == NULL || out == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    *out = NULL;

    for (i = 0; i < registry->system_count; i++) {
        if (mki_streq(registry->systems[i]->builtin->name, name)) {
            *out = registry->systems[i];
            return MK_OK;
        }
    }

    return MK_ERR_UNKNOWN_SYSTEM;
}

mk_status mk_registry_add_model_text(
    mk_registry *registry,
    const char *model_text
)
{
    return mk_registry_add_model_text_ex(registry, model_text, NULL);
}

/* The two NUL-terminated forms measure the string and hand off to the one that
 * takes a length, so there is a single install path to keep correct. */
mk_status mk_registry_add_model_text_ex(
    mk_registry *registry,
    const char *model_text,
    char **diagnostic_out
)
{
    if (diagnostic_out != NULL) {
        *diagnostic_out = NULL;
    }
    if (registry == NULL || model_text == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }
    return mk_registry_add_model_text_n(
        registry, model_text, strlen(model_text), diagnostic_out
    );
}

mk_status mk_registry_add_model_text_n(
    mk_registry *registry,
    const char *model_text,
    size_t model_text_length,
    char **diagnostic_out
)
{
    mk_parsed_model model;
    mk_system **next_systems;
    mk_system *slot;
    mk_status status;

    if (diagnostic_out != NULL) {
        *diagnostic_out = NULL;
    }
    if (registry == NULL || model_text == NULL) {
        return MK_ERR_INVALID_ARGUMENT;
    }

    status = mki_parse_model_text_n(model_text, model_text_length, &model, diagnostic_out);
    if (status != MK_OK) {
        return status;
    }

    next_systems = (mk_system **)realloc(
        registry->systems,
        (registry->system_count + 1) * sizeof(*registry->systems)
    );
    if (next_systems == NULL) {
        mki_parsed_model_clear(&model);
        return MK_ERR_OOM;
    }
    registry->systems = next_systems;

    slot = (mk_system *)calloc(1, sizeof(*slot));
    if (slot == NULL) {
        mki_parsed_model_clear(&model);
        return MK_ERR_OOM;
    }
    registry->systems[registry->system_count] = slot;

    /* The registry takes over what the parser produced, so the model must not
     * be cleared on this path. The name is held twice on purpose: owned_name is
     * the allocation this struct frees, owned.name is the borrowed view of it
     * that every reader sees. */
    slot->owned_name = model.name;
    slot->owned.name = model.name;
    slot->owned.kind = MK_SYSTEM_CATEGORICAL;
    slot->owned.entries = model.entries;
    slot->owned.entry_count = model.entry_count;
    slot->builtin = &slot->owned;
    slot->owns = 1;
    registry->system_count++;
    return MK_OK;
}
