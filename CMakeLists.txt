cmake_minimum_required(VERSION 3.20)

project(merkmal
    VERSION 0.7.0
    DESCRIPTION "C99 phonological feature library"
    LANGUAGES C
)

find_package(Python3 COMPONENTS Interpreter QUIET)

include(CMakePackageConfigHelpers)
include(GNUInstallDirs)

option(MERKMAL_BUILD_TESTS "Build merkmal C tests" ON)
option(MERKMAL_REQUIRE_UTF8PROC "Require system utf8proc" OFF)
set(MERKMAL_ENABLE_SANITIZER "" CACHE STRING "Enable sanitizer: address or undefined")
set_property(CACHE MERKMAL_ENABLE_SANITIZER PROPERTY STRINGS "" address undefined)

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
    src/status.c
    src/string_list.c
    src/system.c
    src/unicode.c
    src/generated/builtin_data.c
)

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

if(MSVC)
    target_compile_options(merkmal PRIVATE /W4)
else()
    target_compile_options(merkmal PRIVATE -Wall -Wextra -Wpedantic)
endif()

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
