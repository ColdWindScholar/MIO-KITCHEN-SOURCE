enable_language(C CXX)
include(CheckSymbolExists)

# Use C11 with GNU extensions.
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_EXTENSIONS ON)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Use C++20 with GNU extensions.
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_EXTENSIONS ON)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(APPLE)
	set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -D_DARWIN_C_SOURCE -D__DARWIN_C_LEVEL=__DARWIN_C_FULL")
	set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -D_DARWIN_C_SOURCE -D__DARWIN_C_LEVEL=__DARWIN_C_FULL")
endif()
set(PREFER_STATIC_LINKING "build statically" ON)
if(PREFER_STATIC_LINKING)
	list(INSERT CMAKE_FIND_LIBRARY_PREFIXES 0 ${CMAKE_STATIC_LIBRARY_PREFIX})
	list(INSERT CMAKE_FIND_LIBRARY_SUFFIXES 0 ${CMAKE_STATIC_LIBRARY_SUFFIX})
	set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -static -fPIC")
	set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -static -fPIC")
	set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -static -fPIC")
endif()
# Different versions of clang require a different set of flags for -ftrivial-auto-var-init
# Simplify this contruct once old clang version support is dropped
include(CheckCXXCompilerFlag)
check_cxx_compiler_flag("-ftrivial-auto-var-init=zero" COMPILER_SUPPORTS_TRIVIAL_ZERO_INIT)
if(COMPILER_SUPPORTS_TRIVIAL_ZERO_INIT)
	set(VAR_ZERO_INIT_FLAGS "-ftrivial-auto-var-init=zero")
else()
	check_cxx_compiler_flag("-ftrivial-auto-var-init=zero -enable-trivial-auto-var-init-zero-knowing-it-will-be-removed-from-clang"
				COMPILER_REQUIRES_ENABLE_TRIVIAL_ZERO_INIT)
	if(COMPILER_REQUIRES_ENABLE_TRIVIAL_ZERO_INIT)
		set(VAR_ZERO_INIT_FLAGS "-ftrivial-auto-var-init=zero -enable-trivial-auto-var-init-zero-knowing-it-will-be-removed-from-clang")
	endif()
endif()
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} ${VAR_ZERO_INIT_FLAGS}")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${VAR_ZERO_INIT_FLAGS}")

# Android seems to use various attributes supported by clang but not by
# GCC which causes it to emit lots of warnings. Since these attributes
# don't seem to effect runtime behaviour simply disable the warnings.
add_compile_options(-Wno-attributes)
add_compile_options(-static)

# libfsmgr (required by fastboot) requires a 64-bit off_t for lseek. On
# 32-bit glibc platforms this is not the case by default.
add_compile_definitions(_FILE_OFFSET_BITS=64 _LARGEFILE64_SOURCE)

set(android-vendored
	avb
	core
	extras
	libbase
	libufdt
	libziparchive
	logging
	mkbootimg
	selinux
	f2fs-tools
	e2fsprogs
	fmtlib
	boringssl)

# XXX: Consider using https://cmake.org/cmake/help/v3.0/module/ExternalProject.html
if(ANDROID_TOOLS_PATCH_VENDOR AND EXISTS "${ANDROID_PATCH_DIR}/")
	execute_process(COMMAND git submodule --quiet update)
	foreach(v ${android-vendored})
		file(GLOB patches ${ANDROID_PATCH_DIR}/${v}/*.patch)
		if(patches)
			message(STATUS "Applying patches for: ${v}")
			execute_process(COMMAND git -C
				${CMAKE_CURRENT_SOURCE_DIR}/${v} am ${patches}
				RESULT_VARIABLE ret)
			if(NOT "${ret}" STREQUAL "0")
				message(FATAL_ERROR "Couldn't apply patches for ${v}")
			endif()
		endif(patches)
	endforeach(v)
endif()

add_subdirectory(boringssl EXCLUDE_FROM_ALL)

if(ANDROID_TOOLS_USE_BUNDLED_FMT)
	add_subdirectory(fmtlib EXCLUDE_FROM_ALL)
else()
	find_package(fmt CONFIG REQUIRED)
	message(STATUS "Found fmt: ${fmt_DIR} (version ${fmt_VERSION})")
endif()

find_package(PkgConfig REQUIRED)
pkg_check_modules(libbrotlicommon REQUIRED IMPORTED_TARGET libbrotlicommon)
pkg_check_modules(libbrotlidec REQUIRED IMPORTED_TARGET libbrotlidec)
pkg_check_modules(libbrotlienc REQUIRED IMPORTED_TARGET libbrotlienc)
pkg_check_modules(liblz4 REQUIRED IMPORTED_TARGET liblz4)
pkg_check_modules(libpcre2-8 REQUIRED IMPORTED_TARGET libpcre2-8)
if(ANDROID_TOOLS_USE_BUNDLED_LIBUSB)
	include(CMakeLists.libusb.txt)
	if(ANDROID_TOOLS_LIBUSB_ENABLE_UDEV)
		pkg_check_modules(libudev REQUIRED IMPORTED_TARGET libudev)
	endif()
else()
	pkg_check_modules(libusb-1.0 REQUIRED IMPORTED_TARGET libusb-1.0)
endif()
pkg_check_modules(libzstd REQUIRED IMPORTED_TARGET libzstd)
find_package(PkgConfig REQUIRED)
list(APPEND PKG_CONFIG_EXECUTABLE "--static")
find_package(Protobuf CONFIG)
find_package(Protobuf REQUIRED)
set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)
find_package(ZLIB REQUIRED)

check_symbol_exists(strlcpy "string.h" HAVE_STRLCPY)
check_symbol_exists(reallocarray "stdlib.h" HAVE_REALLOCARRAY)

include_directories(${PROTOBUF_INCLUDE_DIRS})
include_directories(${CMAKE_CURRENT_BINARY_DIR})

include(CMakeLists.libbase.txt)
include(CMakeLists.adb.txt)
include(CMakeLists.sparse.txt)
include(CMakeLists.fastboot.txt)
include(CMakeLists.f2fstools.txt)
include(CMakeLists.mke2fs.txt)
include(CMakeLists.partition.txt)
include(CMakeLists.mkbootimg.txt)
include(CMakeLists.libufdt.txt)
include(CMakeLists.avb.txt)

# Targets which should be installed by `make install`.
install(TARGETS
	"${ANDROID_MKE2FS_NAME}"
	append2simg
	img2simg
	lpadd
	lpdump
	lpflash
	lpmake
	lpunpack
	make_f2fs
	sload_f2fs
	simg2img
	ext2simg
	DESTINATION bin)

if(NOT APPLE)
	install(TARGETS
		e2fsdroid
		DESTINATION bin)
endif()

# Install common completion files.
install(FILES adb/adb.bash RENAME adb DESTINATION "${COMPLETION_COMMON_DIR}")

# Install license files.
# Disabled for now, see https://github.com/nmeum/android-tools/issues/30#issuecomment-855365636
#set(LICENSE_DIR "${CMAKE_INSTALL_FULL_DATADIR}/licenses/android-tools")
#install(FILES core/NOTICE RENAME AOSP_LICENSE DESTINATION "${LICENSE_DIR}")
