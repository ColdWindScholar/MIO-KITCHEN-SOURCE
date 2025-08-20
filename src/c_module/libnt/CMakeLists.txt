cmake_minimum_required(VERSION 3.10)

project(libnt)

add_library(nt STATIC fnmatch.c mman.c libnt.c)
add_executable(test test.c)
target_link_libraries(test libnt -static)
include_directories(include)
