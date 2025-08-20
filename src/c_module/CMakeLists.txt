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
list(INSERT CMAKE_FIND_LIBRARY_PREFIXES 0 ${CMAKE_STATIC_LIBRARY_PREFIX})
list(INSERT CMAKE_FIND_LIBRARY_SUFFIXES 0 ${CMAKE_STATIC_LIBRARY_SUFFIX})
set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -static-libgcc")
set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -static-libstdc++")
# and after find_package(PkgConfig REQUIRED)
list(APPEND PKG_CONFIG_EXECUTABLE "--static")

set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} ${C_FLAGS} -static")
set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} ${LD_FLAGS} -static")
add_library(utils SHARED utils.c
        utils.h)
target_link_libraries(utils e2fstool libext2fs libsparse libzip libcutils liblog libutil
        libbase libselinux libsepol z pcre2-8 m pthread -static)
target_include_directories(utils PRIVATE
        android-tools/vendor/e2fsprogs/lib android-tools/vendor/e2fsprogs/lib/ext2fs android-tools/vendor/selinux/libselinux/include
        android-tools/vendor/core/libcutils/include android-tools/vendor/e2fsprogs/misc)
target_include_directories(utils PUBLIC include)
include_directories(.)
add_subdirectory(android-tools)
