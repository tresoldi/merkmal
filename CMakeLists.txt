cmake_minimum_required(VERSION 3.20)

project(merkmal
    VERSION 0.7.0
    DESCRIPTION "C99 phonological feature library"
    LANGUAGES C
)

option(MERKMAL_BUILD_TESTS "Build merkmal C tests" ON)
option(MERKMAL_REQUIRE_UTF8PROC "Require system utf8proc" OFF)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

find_package(PkgConfig QUIET)
if(PkgConfig_FOUND)
    pkg_check_modules(UTF8PROC QUIET IMPORTED_TARGET libutf8proc)
endif()

if(MERKMAL_REQUIRE_UTF8PROC AND NOT UTF8PROC_FOUND)
    message(FATAL_ERROR "libutf8proc was not found. Install it or disable MERKMAL_REQUIRE_UTF8PROC for development builds.")
endif()

add_library(merkmal
    src/feature_set.c
    src/geometry.c
    src/registry.c
    src/string_list.c
    src/system.c
    src/unicode.c
    src/generated/builtin_data.c
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
    target_link_libraries(merkmal PRIVATE PkgConfig::UTF8PROC)
else()
    target_compile_definitions(merkmal PRIVATE MK_HAVE_UTF8PROC=0)
endif()

if(MSVC)
    target_compile_options(merkmal PRIVATE /W4)
else()
    target_compile_options(merkmal PRIVATE -Wall -Wextra -Wpedantic)
endif()

if(MERKMAL_BUILD_TESTS)
    enable_testing()

    add_executable(test_smoke tests/c/test_smoke.c)
    target_link_libraries(test_smoke PRIVATE merkmal)
    add_test(NAME smoke COMMAND test_smoke)

    add_executable(test_golden_distances tests/c/test_golden_distances.c)
    target_compile_definitions(test_golden_distances
        PRIVATE MERKMAL_SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}"
    )
    target_link_libraries(test_golden_distances PRIVATE merkmal)
    add_test(NAME golden_distances COMMAND test_golden_distances)

    add_executable(test_golden_features tests/c/test_golden_features.c)
    target_compile_definitions(test_golden_features
        PRIVATE MERKMAL_SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}"
    )
    target_link_libraries(test_golden_features PRIVATE merkmal)
    add_test(NAME golden_features COMMAND test_golden_features)

    add_executable(test_geometry tests/c/test_geometry.c)
    target_compile_definitions(test_geometry
        PRIVATE MERKMAL_SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}"
    )
    target_link_libraries(test_geometry PRIVATE merkmal)
    add_test(NAME geometry COMMAND test_geometry)
endif()
