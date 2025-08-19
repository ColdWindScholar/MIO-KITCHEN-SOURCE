cmake_minimum_required(VERSION 3.10)

project(c_module)

set(BUILD_SHARED_LIBS ON)
execute_process(
        COMMAND bash -c "python3-config --cflags"
        OUTPUT_VARIABLE C_FLAGS
        OUTPUT_STRIP_TRAILING_WHITESPACE
)
execute_process(
        COMMAND bash -c "python3-config --ldflags"
        OUTPUT_VARIABLE LD_FLAGS
        OUTPUT_STRIP_TRAILING_WHITESPACE
)
set(Python_ADDITIONAL_VERSIONS 3.13)
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} ${C_FLAGS}")
set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} ${LD_FLAGS}")
add_library(utils utils.c)
target_include_directories(utils PUBLIC include)

add_subdirectory(android-tools)
