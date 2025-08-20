cmake_minimum_required(VERSION 3.10)

project(libnt)

add_library(nt STATIC fnmatch.c mman.c libnt.c)
target_include_directories(nt include)
add_executable(test test.c)
target_link_libraries(test libnt -static)
target_include_directories(test include)
include_directories(include)
