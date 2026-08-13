cmake_minimum_required(VERSION 3.20)

project(merkmal
    VERSION 1.0.0
    DESCRIPTION "C99 phonological feature library"
    LANGUAGES C
)

find_package(Python3 COMPONENTS Interpreter QUIET)

include(CMakePackageConfigHelpers)
include(GNUInstallDirs)

option(MERKMAL_BUILD_TESTS "Build merkmal C tests" ON)
option(MERKMAL_REQUIRE_UTF8PROC "Fail configuration if system utf8proc is missing" OFF)
# REQUIRE only decides what happens when utf8proc is absent. USE decides whether
# to look for it at all, so that the fallback profile -- the one WebAssembly
# ships -- can be selected and tested on a machine that has utf8proc installed.
option(MERKMAL_USE_UTF8PROC "Use system utf8proc when available" ON)
option(MERKMAL_WERROR "Treat compiler warnings as errors (intended for CI)" OFF)
option(MERKMAL_BUILD_FUZZERS "Build the libFuzzer harnesses (Clang only)" OFF)
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
    message(FATAL_ERROR "libutf8proc was not found. Install it or disable MERKMAL_REQUIRE_UTF8PROC for development builds.")
endif()

set(MERKMAL_SOURCES
    src/diagnose.c
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
    src/tokenize.c
    src/tone.c
    src/utf8.c
    src/generated/builtin_data.c
)

add_library(merkmal ${MERKMAL_SOURCES})

add_library(merkmal::merkmal ALIAS merkmal)

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

if(UTF8PROC_FOUND)
    target_compile_definitions(merkmal PRIVATE MK_HAVE_UTF8PROC=1)
    target_link_libraries(merkmal PUBLIC PkgConfig::UTF8PROC)
else()
    target_compile_definitions(merkmal PRIVATE MK_HAVE_UTF8PROC=0)
endif()

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
    target_compile_options(merkmal PRIVATE -fsanitize=${MERKMAL_ENABLE_SANITIZER} -fno-omit-frame-pointer)
    target_link_options(merkmal PUBLIC -fsanitize=${MERKMAL_ENABLE_SANITIZER})
endif()

if(MERKMAL_BUILD_TESTS)
    enable_testing()

    add_executable(test_smoke tests/c/test_smoke.c)
    target_link_libraries(test_smoke PRIVATE merkmal)
    add_test(NAME smoke COMMAND test_smoke)

    # Compiling the header alone is the test: one that needs the caller to
    # have included <stddef.h> first passes everywhere inside this project and
    # fails for the first consumer who includes it before anything else.
    add_executable(test_header tests/c/header/header_only.c)
    target_link_libraries(test_header PRIVATE merkmal)
    target_compile_options(test_header PRIVATE ${MERKMAL_C_WARNINGS})
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

    # The resolution seam is internal and a shared build does not export it, so
    # this test compiles the library sources rather than linking the target.
    # That keeps it running in every configuration, including BUILD_SHARED_LIBS.
    add_executable(test_resolution tests/c/test_resolution.c ${MERKMAL_SOURCES})
    target_include_directories(test_resolution
        PRIVATE
            ${CMAKE_CURRENT_SOURCE_DIR}/include
            ${CMAKE_CURRENT_SOURCE_DIR}/src
    )
    target_compile_options(test_resolution PRIVATE ${MERKMAL_C_WARNINGS})
    if(UTF8PROC_FOUND)
        target_compile_definitions(test_resolution PRIVATE MK_HAVE_UTF8PROC=1)
        target_link_libraries(test_resolution PRIVATE PkgConfig::UTF8PROC)
    else()
        target_compile_definitions(test_resolution PRIVATE MK_HAVE_UTF8PROC=0)
    endif()
    if(MERKMAL_ENABLE_SANITIZER)
        target_compile_options(test_resolution
            PRIVATE -fsanitize=${MERKMAL_ENABLE_SANITIZER} -fno-omit-frame-pointer
        )
        target_link_options(test_resolution PRIVATE -fsanitize=${MERKMAL_ENABLE_SANITIZER})
    endif()
    add_test(NAME resolution COMMAND test_resolution)
endif()

# libFuzzer, so Clang only. Off by default: the harnesses are a development and
# CI tool, not something a downstream build should have to have a fuzzing
# runtime for.
if(MERKMAL_BUILD_FUZZERS)
    if(NOT CMAKE_C_COMPILER_ID MATCHES "Clang")
        message(FATAL_ERROR "MERKMAL_BUILD_FUZZERS needs Clang for libFuzzer")
    endif()
    foreach(target model_text segment resolve)
        add_executable(fuzz_${target} fuzz/fuzz_${target}.c ${MERKMAL_SOURCES})
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
        if(UTF8PROC_FOUND)
            target_compile_definitions(fuzz_${target} PRIVATE MK_HAVE_UTF8PROC=1)
            target_link_libraries(fuzz_${target} PRIVATE PkgConfig::UTF8PROC)
        else()
            target_compile_definitions(fuzz_${target} PRIVATE MK_HAVE_UTF8PROC=0)
        endif()
    endforeach()
endif()

if(Python3_Interpreter_FOUND)
    add_custom_target(check-generated-data
        COMMAND Python3::Interpreter
            "${CMAKE_CURRENT_SOURCE_DIR}/scripts/check_generated_data.py"
        WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
        COMMENT "Checking generated C data"
    )
endif()

if(UTF8PROC_FOUND)
    set(MERKMAL_PC_REQUIRES_PRIVATE "libutf8proc")
    set(MERKMAL_CONFIG_UTF8PROC
"include(CMakeFindDependencyMacro)
find_dependency(PkgConfig)
pkg_check_modules(UTF8PROC REQUIRED IMPORTED_TARGET libutf8proc)")
else()
    set(MERKMAL_PC_REQUIRES_PRIVATE "")
    set(MERKMAL_CONFIG_UTF8PROC "")
endif()

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
