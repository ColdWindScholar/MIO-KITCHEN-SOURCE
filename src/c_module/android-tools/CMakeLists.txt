cmake_minimum_required(VERSION 3.12.0)
project(android-tools)

# To ease installation of utility files such as bash completions, etc.
# See: https://cmake.org/cmake/help/latest/module/GNUInstallDirs.html
include(GNUInstallDirs)

# Option to enable or disable patching vendor projects using patches directory.
# This helps to build vendor projects with or without any patching. Also if any
# files are changed in vendor projects those can be retained with this option.
option(ANDROID_TOOLS_PATCH_VENDOR "Patch vendor projects using patches directory" ON)
option(ANDROID_TOOLS_USE_BUNDLED_FMT "Use bundled fmt library instead of system provided one" OFF)
option(ANDROID_TOOLS_USE_BUNDLED_LIBUSB "Use bundled libusb library instead of system provided one" OFF)
option(ANDROID_TOOLS_LIBUSB_ENABLE_UDEV "Enable udev for device enumeration and hotplug support" OFF)

# Install bash/zsh completion files.
set(COMPLETION_COMMON_DIR "${CMAKE_INSTALL_FULL_DATADIR}/android-tools/completions")
add_subdirectory(completions)

# Android provides it's own version of mke2fs which is incompatible with
# the version shipped by e2fsprogs. To prevent a name clash we install
# androids version of mke2fs under a different name. This name can be
# configured here.
#
# See also: https://bugs.archlinux.org/task/56955
set(ANDROID_MKE2FS_NAME "mke2fs")

# Version of android-tools and the version of boringssl being used.
# See: https://android.googlesource.com/platform/external/boringssl/+/platform-tools-${ANDROID_VERSION}/BORINGSSL_REVISION
set(ANDROID_VERSION 35.0.2)
set(BORINGSSL_VERSION 9cffd74fdb65c69506a0ce1b19420a67ad0cb19e)

# Vendor string used in version outputs.
set(ANDROID_VENDOR android-tools)

configure_file(version.h.in vendor/build/version.h @ONLY)
configure_file(platform_tools_version.h.in vendor/platform_tools_version.h @ONLY)

# The CMakeLists.txt in the vendor subdirectory is responsible for
# patching, building and installing the software.
set(ANDROID_PATCH_DIR ${CMAKE_CURRENT_SOURCE_DIR}/patches)
add_subdirectory(vendor)

# CPack configuration for creating source tarballs which already include
# patched versions of the vendored dependencies.
set(CPACK_SOURCE_GENERATOR "TXZ")
set(CPACK_SOURCE_PACKAGE_FILE_NAME "${PROJECT_NAME}-${ANDROID_VERSION}")
set(CPACK_SOURCE_IGNORE_FILES "/patches/" "/build/" "/.git/" "/.github/" "/tests/"
	"/testdata/" "/extras/simpleperf/scripts/" "/extras/simpleperf/demo/"
	"aes_128_gcm.txt" "aes_256_gcm.txt"
	"/fuzz/"
	"/wycheproof_testvectors/"
	"\\\\.apk$"
	"\\\\.bz2$"
	"\\\\.clang-format$"
	"\\\\.data$"
	"\\\\.git$"
	"\\\\.html$"
	"\\\\.orig$"
	"\\\\.pdf$"
	"\\\\.pem$"
	"\\\\.png$"
	"\\\\.rej$"
	"\\\\.so$"
	"\\\\.tar$"
	"\\\\.tar\\\\..*$"
	"\\\\.tgz$"
	"\\\\.zip$"
)
include(CPack)
