cmake_minimum_required(VERSION 3.20)

project(merkmal
    VERSION 0.10.0
    DESCRIPTION "C99 phonological feature library"
    LANGUAGES C
)

find_package(Python3 COMPONENTS Interpreter QUIET)

include(CMakePackageConfigHelpers)
include(GNUInstallDirs)

option(MERKMAL_BUILD_TESTS "Build merkmal C tests" ON)
# utf8proc is no longer a dependency of the library: NFC and NFD are compiled
# in from the Unicode tables, identically in every build. It is used only as
# an independent oracle by the `unicode` test. USE decides whether to look for
# it; REQUIRE makes its absence fatal, for CI jobs that must run the oracle.
option(MERKMAL_REQUIRE_UTF8PROC "Fail configuration if utf8proc (the test oracle) is missing" OFF)
option(MERKMAL_USE_UTF8PROC "Use system utf8proc as a normalization test oracle when available" ON)
option(MERKMAL_WERROR "Treat compiler warnings as errors (intended for CI)" OFF)
option(MERKMAL_BUILD_FUZZERS "Build the libFuzzer harnesses (Clang only)" OFF)
option(MERKMAL_BUILD_EXAMPLES "Build the examples" ON)
# Which built-in systems the library carries. `full` is every bundled table.
# `cc-by` carries only the tables without share-alike or non-commercial terms
# (descriptive and distinctive, CC-BY-4.0), dropping PHOIBLE (CC-BY-SA-3.0)
# and the four P-base systems (CC-BY-NC-SA-4.0). See NOTICE.
set(MERKMAL_DATA_PROFILE "full" CACHE STRING "Built-in data profile: full or cc-by")
set_property(CACHE MERKMAL_DATA_PROFILE PROPERTY STRINGS full cc-by)
if(MERKMAL_DATA_PROFILE STREQUAL "full")
    set(MERKMAL_BUILTIN_DATA src/generated/builtin_data.c)
elseif(MERKMAL_DATA_PROFILE STREQUAL "cc-by")
    set(MERKMAL_BUILTIN_DATA src/generated/cc-by/builtin_data.c)
else()
    message(FATAL_ERROR "MERKMAL_DATA_PROFILE must be full or cc-by")
endif()
set(MERKMAL_ENABLE_SANITIZER "" CACHE STRING "Enable sanitizer: address or undefined")
set_property(CACHE MERKMAL_ENABLE_SANITIZER PROPERTY STRINGS "" address undefined)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

if(MERKMAL_USE_UTF8PROC)
    find_package(PkgConfig QUIET)
    if(PkgConfig_FOUND)
        pkg_check_modules(UTF8PROC QUIET IMPORTED_TARGET libutf8proc)
    endif()
else()
    set(UTF8PROC_FOUND FALSE)
endif()

if(MERKMAL_REQUIRE_UTF8PROC AND NOT MERKMAL_USE_UTF8PROC)
    message(FATAL_ERROR "MERKMAL_REQUIRE_UTF8PROC and MERKMAL_USE_UTF8PROC=OFF contradict each other.")
endif()

if(MERKMAL_REQUIRE_UTF8PROC AND NOT UTF8PROC_FOUND)
    message(FATAL_ERROR "libutf8proc was not found. It is only needed for the normalization oracle test; install it or disable MERKMAL_REQUIRE_UTF8PROC.")
endif()

set(MERKMAL_SOURCES
    src/array.c
    src/bundle.c
    src/classes.c
    src/cluster.c
    src/diagnose.c
    src/fingerprint.c
    src/geometry.c
    src/inventory.c
    src/ipa.c
    src/model_text.c
    src/normalize.c
    src/registry.c
    src/resolver.c
    src/status.c
    src/string_list.c
    src/strings.c
    src/system.c
    src/vector.c
    src/version.c
    src/tokenize.c
    src/tone.c
    src/unicode_norm.c
    src/utf8.c
    ${MERKMAL_BUILTIN_DATA}
    src/generated/unicode_data.c
)

add_library(merkmal ${MERKMAL_SOURCES})

add_library(merkmal::merkmal ALIAS merkmal)

# The scorers call fabs from <math.h>. Where the C library keeps it in a
# separate libm, the library links it, and a static consumer is told to: the
# exported CMake target carries it as a link-only dependency, and merkmal.pc
# lists it in Libs.private.
find_library(MERKMAL_LIBM m)
set(MERKMAL_PC_LIBS_PRIVATE "")
if(MERKMAL_LIBM)
    target_link_libraries(merkmal PRIVATE m)
    set(MERKMAL_PC_LIBS_PRIVATE "-lm")
endif()

set_target_properties(merkmal PROPERTIES
    VERSION ${PROJECT_VERSION}
    SOVERSION ${PROJECT_VERSION_MAJOR}
    C_VISIBILITY_PRESET hidden
    VISIBILITY_INLINES_HIDDEN YES
)

target_compile_definitions(merkmal
    PRIVATE
        MERKMAL_BUILDING_LIBRARY
    PUBLIC
        $<$<BOOL:${BUILD_SHARED_LIBS}>:MERKMAL_SHARED>
)

target_include_directories(merkmal
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src
)

# The first-party sources are clean at this set; it is enforced rather than
# aspirational. -Werror is opt-in so that CI can gate on it without imposing it
# on downstream consumers building from source.
if(MSVC)
    set(MERKMAL_C_WARNINGS /W4)
    if(MERKMAL_WERROR)
        list(APPEND MERKMAL_C_WARNINGS /WX)
    endif()
else()
    set(MERKMAL_C_WARNINGS
        -Wall
        -Wextra
        -Wpedantic
        -Wshadow
        -Wconversion
        -Wstrict-prototypes
        -Wmissing-prototypes
        # The five below were each measured at zero findings against the tree
        # before being added, so none of them cost a cleanup. They are here to
        # keep properties the code already has rather than to report news:
        -Wvla                # stack growth that depends on untrusted input
        -Wformat=2           # a diagnostic built with a non-literal format
        -Wdouble-promotion   # a float sneaking into the double scorers
        -Wswitch-enum        # an mk_status arm forgotten when the enum grows
        -Wwrite-strings      # a string literal bound to a mutable char *
        # -Wcast-qual is the one that cost something. It found 28 sites where a
        # destructor cast const away to free storage it owned, because
        # mki_builtin_entry declared owned pointers const. Nothing was wrong at
        # any of the 28 -- the cast was load-bearing and correct -- but a type
        # that needs a cast to be freed cannot be checked, and the next reader
        # to free the wrong branch of that union of lifetimes would have found
        # out at runtime. The type now says which pointers it owns.
        -Wcast-qual
    )
    if(MERKMAL_WERROR)
        list(APPEND MERKMAL_C_WARNINGS -Werror)
    endif()
endif()

target_compile_options(merkmal PRIVATE ${MERKMAL_C_WARNINGS})

if(MERKMAL_ENABLE_SANITIZER)
    if(MSVC)
        message(FATAL_ERROR "MERKMAL_ENABLE_SANITIZER is not supported with MSVC yet")
    endif()
    if(NOT MERKMAL_ENABLE_SANITIZER MATCHES "^(address|undefined)$")
        message(FATAL_ERROR "MERKMAL_ENABLE_SANITIZER must be empty, address, or undefined")
    endif()
    # Defined once: the library and merkmal_internal (the tests' copy of it)
    # must be instrumented identically.
    set(MERKMAL_SANITIZER_COMPILE_OPTIONS
        -fsanitize=${MERKMAL_ENABLE_SANITIZER} -fno-omit-frame-pointer)
    set(MERKMAL_SANITIZER_LINK_OPTIONS -fsanitize=${MERKMAL_ENABLE_SANITIZER})
    target_compile_options(merkmal PRIVATE ${MERKMAL_SANITIZER_COMPILE_OPTIONS})
    target_link_options(merkmal PUBLIC ${MERKMAL_SANITIZER_LINK_OPTIONS})
endif()

if(MERKMAL_BUILD_TESTS)
    enable_testing()

    add_executable(test_smoke tests/c/test_smoke.c)
    target_link_libraries(test_smoke PRIVATE merkmal)
    # The header's MK_VERSION_* are written by hand; this is what holds them to
    # the project version, so a release that bumps one and not the other fails.
    target_compile_definitions(test_smoke PRIVATE MERKMAL_PROJECT_VERSION="${PROJECT_VERSION}")
    add_test(NAME smoke COMMAND test_smoke)

    add_executable(test_inventory tests/c/test_inventory.c)
    target_link_libraries(test_inventory PRIVATE merkmal)
    add_test(NAME inventory COMMAND test_inventory)

    add_executable(test_bundle tests/c/test_bundle.c)
    target_link_libraries(test_bundle PRIVATE merkmal)
    add_test(NAME bundle COMMAND test_bundle)

    # The WebAssembly adapter builds natively too; this checks its JSON.
    add_executable(test_wasm_adapter tests/c/test_wasm_adapter.c web/merkmal_wasm.c)
    target_link_libraries(test_wasm_adapter PRIVATE merkmal)
    add_test(NAME wasm_adapter COMMAND test_wasm_adapter)
    # The check needs PHOIBLE, which the cc-by profile does not carry.
    if(MERKMAL_DATA_PROFILE STREQUAL "cc-by")
        target_compile_definitions(test_wasm_adapter PRIVATE MERKMAL_TEST_DATA_PROFILE_CC_BY)
    endif()
    set_tests_properties(wasm_adapter PROPERTIES SKIP_RETURN_CODE 77)

    # Compiling the header alone is the test: one that needs the caller to
    # have included <stddef.h> first passes everywhere inside this project and
    # fails for the first consumer who includes it before anything else.
    add_executable(test_header tests/c/header/header_only.c)
    target_link_libraries(test_header PRIVATE merkmal)
    add_test(NAME header COMMAND test_header)

    add_executable(test_malformed tests/c/test_malformed.c)
    target_link_libraries(test_malformed PRIVATE merkmal)
    add_test(NAME malformed COMMAND test_malformed)

    add_executable(test_golden_distances tests/c/test_golden_distances.c tests/c/golden_support.c)
    target_compile_definitions(test_golden_distances
        PRIVATE MERKMAL_SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}"
    )
    target_include_directories(test_golden_distances PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/tests/c)
    target_link_libraries(test_golden_distances PRIVATE merkmal)
    add_test(NAME golden_distances COMMAND test_golden_distances)

    add_executable(test_golden_features tests/c/test_golden_features.c tests/c/golden_support.c)
    target_compile_definitions(test_golden_features
        PRIVATE MERKMAL_SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}"
    )
    target_include_directories(test_golden_features PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/tests/c)
    target_link_libraries(test_golden_features PRIVATE merkmal)
    add_test(NAME golden_features COMMAND test_golden_features)

    add_executable(test_geometry tests/c/test_geometry.c tests/c/golden_support.c)
    target_compile_definitions(test_geometry
        PRIVATE MERKMAL_SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}"
    )
    target_include_directories(test_geometry PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/tests/c)
    target_link_libraries(test_geometry PRIVATE merkmal)
    add_test(NAME geometry COMMAND test_geometry)

    # Tests of internal modules link this rather than the merkmal target. A
    # shared merkmal exports only the public API (hidden visibility), so the
    # mki_ symbols these tests call exist only in a static build of the same
    # sources. Built only for the tests and never installed. It carries the
    # warning set and the sanitizer, so a test linking it is checked exactly
    # as the library is. This replaced six executables each recompiling the
    # sources with their own copy of the sanitizer flags.
    add_library(merkmal_internal STATIC EXCLUDE_FROM_ALL ${MERKMAL_SOURCES})
    target_include_directories(merkmal_internal
        PUBLIC
            ${CMAKE_CURRENT_SOURCE_DIR}/include
            ${CMAKE_CURRENT_SOURCE_DIR}/src
    )
    if(MERKMAL_LIBM)
        target_link_libraries(merkmal_internal PUBLIC m)
    endif()
    target_compile_options(merkmal_internal
        PRIVATE ${MERKMAL_C_WARNINGS}
        PUBLIC ${MERKMAL_SANITIZER_COMPILE_OPTIONS}
    )
    target_link_options(merkmal_internal PUBLIC ${MERKMAL_SANITIZER_LINK_OPTIONS})

    # The resolution seam: which path resolved a grapheme is part of the answer
    # and only visible internally.
    add_executable(test_resolution tests/c/test_resolution.c)
    target_link_libraries(test_resolution PRIVATE merkmal_internal)
    add_test(NAME resolution COMMAND test_resolution)

    # The scoring seam: which scorer a system selects is what this asserts.
    add_executable(test_scoring tests/c/test_scoring.c)
    target_link_libraries(test_scoring PRIVATE merkmal_internal)
    add_test(NAME scoring COMMAND test_scoring)

    # The cluster seam: a resolved cluster carries its parts rather than only
    # their spellings.
    add_executable(test_cluster tests/c/test_cluster.c)
    target_link_libraries(test_cluster PRIVATE merkmal_internal)
    add_test(NAME cluster COMMAND test_cluster)

    # The checked growth helper, on its own: its overflow paths cannot be
    # reached through the public API with any input that fits in memory.
    add_executable(test_array tests/c/test_array.c)
    target_link_libraries(test_array PRIVATE merkmal_internal)
    add_test(NAME array COMMAND test_array)

    # Fails every allocation in turn inside the entry points whose cleanup
    # paths no ordinary input reaches. Wrapping malloc needs the GNU or LLVM
    # linker's --wrap, which applies to the archive members linked in, so it
    # links merkmal_internal rather than a possibly shared merkmal.
    if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
        add_executable(test_alloc_failure tests/c/test_alloc_failure.c)
        target_link_libraries(test_alloc_failure PRIVATE merkmal_internal)
        target_link_options(test_alloc_failure
            PRIVATE -Wl,--wrap=malloc,--wrap=calloc,--wrap=realloc
        )
        add_test(NAME alloc_failure COMMAND test_alloc_failure)
    endif()

    # The built-in NFC and NFD. With utf8proc found, the test also compares
    # every code point and generated mark sequences against it; utf8proc is a
    # test oracle here, never a dependency of the library.
    add_executable(test_unicode tests/c/test_unicode.c)
    target_link_libraries(test_unicode PRIVATE merkmal_internal)
    if(UTF8PROC_FOUND)
        target_compile_definitions(test_unicode PRIVATE MK_HAVE_UTF8PROC=1)
        target_link_libraries(test_unicode PRIVATE PkgConfig::UTF8PROC)
    else()
        target_compile_definitions(test_unicode PRIVATE MK_HAVE_UTF8PROC=0)
    endif()
    # With MERKMAL_REQUIRE_UTF8PROC the oracle must run, so a utf8proc of
    # another Unicode version is a failure. Otherwise it cannot serve as the
    # oracle and the test exits 77, which ctest reports as a skip.
    if(MERKMAL_REQUIRE_UTF8PROC)
        target_compile_definitions(test_unicode PRIVATE MK_REQUIRE_ORACLE=1)
    else()
        target_compile_definitions(test_unicode PRIVATE MK_REQUIRE_ORACLE=0)
    endif()
    add_test(NAME unicode COMMAND test_unicode)
    set_tests_properties(unicode PROPERTIES SKIP_RETURN_CODE 77)

    # The tests are first-party sources and compile under the library's warning
    # set too. Previously only test_header and test_resolution did, which meant
    # the golden and malformed tests -- the ones that handle hostile input and
    # do the most pointer arithmetic -- were the least checked code in the tree.
    foreach(target
        test_smoke
        test_inventory
        test_bundle
        test_alloc_failure
        test_header
        test_malformed
        test_golden_distances
        test_golden_features
        test_geometry
        test_resolution
        test_scoring
        test_cluster
        test_array
        test_unicode
    )
        if(NOT TARGET ${target})
            continue()  # test_alloc_failure exists only on Linux
        endif()
        target_compile_options(${target} PRIVATE ${MERKMAL_C_WARNINGS})
        if(MERKMAL_DATA_PROFILE STREQUAL "cc-by")
            target_compile_definitions(${target} PRIVATE MERKMAL_TEST_DATA_PROFILE_CC_BY)
        endif()
    endforeach()

    # That the archive exports the public symbols and no more. Needs nm and a
    # static archive to read, so it is skipped rather than failed elsewhere; the
    # script exits 0 when nm is absent, and a shared build hides internals by
    # visibility anyway.
    if(UNIX AND NOT BUILD_SHARED_LIBS)
        add_test(
            NAME public_symbols
            COMMAND ${CMAKE_CURRENT_SOURCE_DIR}/tools/check_public_symbols.sh
                    $<TARGET_FILE:merkmal>
        )
    endif()
endif()

# The examples link the library the way a consumer does, through the public
# header only. They are built and run as tests rather than merely shipped,
# because an example nobody compiles is an example that stops working.
if(MERKMAL_BUILD_EXAMPLES)
    add_executable(example_transcribe examples/transcribe.c)
    target_link_libraries(example_transcribe PRIVATE merkmal)
    target_compile_options(example_transcribe PRIVATE ${MERKMAL_C_WARNINGS})
    if(MERKMAL_BUILD_TESTS)
        add_test(NAME example COMMAND example_transcribe)
    endif()
endif()

# libFuzzer, so Clang only. Off by default: the harnesses are a development and
# CI tool, not something a downstream build should have to have a fuzzing
# runtime for.
if(MERKMAL_BUILD_FUZZERS)
    if(NOT CMAKE_C_COMPILER_ID MATCHES "Clang")
        message(FATAL_ERROR "MERKMAL_BUILD_FUZZERS needs Clang for libFuzzer")
    endif()
    foreach(target model_text segment resolve)
        add_executable(fuzz_${target} tests/fuzz/fuzz_${target}.c ${MERKMAL_SOURCES})
        target_include_directories(fuzz_${target}
            PRIVATE
                ${CMAKE_CURRENT_SOURCE_DIR}/include
                ${CMAKE_CURRENT_SOURCE_DIR}/src
        )
        # The harnesses call the core directly, including the internal parser
        # seam, so they compile the sources rather than link the library.
        target_compile_options(fuzz_${target}
            PRIVATE -fsanitize=fuzzer,address,undefined -fno-omit-frame-pointer -g
        )
        target_link_options(fuzz_${target} PRIVATE -fsanitize=fuzzer,address,undefined)
    endforeach()
endif()

if(Python3_Interpreter_FOUND)
    add_custom_target(check-generated-data
        COMMAND Python3::Interpreter
            "${CMAKE_CURRENT_SOURCE_DIR}/tools/check_generated_data.py"
        WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
        COMMENT "Checking generated C data"
    )
endif()

# The library has no external dependency: normalization is compiled in.
set(MERKMAL_PC_REQUIRES_PRIVATE "")

configure_package_config_file(
    cmake/merkmal-config.cmake.in
    "${CMAKE_CURRENT_BINARY_DIR}/merkmal-config.cmake"
    INSTALL_DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/merkmal"
)

write_basic_package_version_file(
    "${CMAKE_CURRENT_BINARY_DIR}/merkmal-config-version.cmake"
    VERSION ${PROJECT_VERSION}
    COMPATIBILITY SameMajorVersion
)

# merkmal.pc locates the prefix from its own directory, so that an installed
# tree can be moved. The number of levels depends on CMAKE_INSTALL_LIBDIR
# (lib, lib64 or a multiarch lib/x86_64-linux-gnu), so it is computed here.
file(RELATIVE_PATH MERKMAL_PC_PREFIX_FROM_PCFILEDIR
    "${CMAKE_INSTALL_FULL_LIBDIR}/pkgconfig" "${CMAKE_INSTALL_PREFIX}")
string(REGEX REPLACE "/$" "" MERKMAL_PC_PREFIX_FROM_PCFILEDIR "${MERKMAL_PC_PREFIX_FROM_PCFILEDIR}")
configure_file(
    cmake/merkmal.pc.in
    "${CMAKE_CURRENT_BINARY_DIR}/merkmal.pc"
    @ONLY
)

install(TARGETS merkmal
    EXPORT merkmal-targets
    ARCHIVE DESTINATION "${CMAKE_INSTALL_LIBDIR}"
    LIBRARY DESTINATION "${CMAKE_INSTALL_LIBDIR}"
    RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}"
)

install(FILES include/merkmal.h DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}")

install(EXPORT merkmal-targets
    FILE merkmal-targets.cmake
    NAMESPACE merkmal::
    DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/merkmal"
)

install(FILES
    "${CMAKE_CURRENT_BINARY_DIR}/merkmal-config.cmake"
    "${CMAKE_CURRENT_BINARY_DIR}/merkmal-config-version.cmake"
    DESTINATION "${CMAKE_INSTALL_LIBDIR}/cmake/merkmal"
)

install(FILES
    "${CMAKE_CURRENT_BINARY_DIR}/merkmal.pc"
    DESTINATION "${CMAKE_INSTALL_LIBDIR}/pkgconfig"
)
