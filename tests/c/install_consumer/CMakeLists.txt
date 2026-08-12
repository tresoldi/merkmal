cmake_minimum_required(VERSION 3.20)

project(merkmal_install_consumer LANGUAGES C)

find_package(merkmal CONFIG REQUIRED)

add_executable(merkmal_install_consumer main.c)
target_link_libraries(merkmal_install_consumer PRIVATE merkmal::merkmal)

enable_testing()
add_test(NAME installed_consumer COMMAND merkmal_install_consumer)
