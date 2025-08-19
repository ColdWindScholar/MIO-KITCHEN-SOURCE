# android-tools

Git repository to make it easier to package certain command line
utilities provided by [android-tools][android-tools].

# Motivation

[Many][void-linux] [Linux][arch-linux] [distributions][alpine-linux] have
[a package called android-tools][repology] which ships essential android command
line tools like adb or fastboot. Sadly the upstream build system for
those tools is rather complex and doesn't allow building the command
line tools only.

Linux Distribution therefore mostly ship their own build systems for
building the command line utilities. This repository aims to make
packaging of android command utilities easier by providing a simple
CMake based build system and a ready-to-use tarball which doesn't
require cloning all of the required git repositories manually. Besides
this makes it easy to collect all patches required to build standalone
android command line utilities in a central place.

# Status

Currently the following tools are supported:

* adb
* fastboot
* mke2fs.android (required by fastboot)
* simg2img, img2simg, append2simg
* lpdump, lpmake, lpadd, lpflash, lpunpack
* mkbootimg, unpack_bootimg, repack_bootimg, avbtool
* mkdtboimg

The build system itself works quite well and is already being used for
the Alpine Linux [android-tools package][alpine-linux] which I maintain.

I personally don't use any android-tools except adb and fastboot. Thus
my motivation to add support for additional tools is rather low at the
moment. However, patches adding support for new tools in a clean way are
welcome. Additionally, patches needed to make the software compile on
other Linux distributions are welcome as well. Please create new patches
using `git format-patch --no-numbered --no-signature …`.

# Dependencies

The following libraries are required by android-tools:

1. [libusb][libusb]
2. [PCRE][PCRE]
3. [Google Test][gtest]
4. [protobuf][protobuf]
5. [brotli][brotli]
6. [zstd][zstd]
7. [lz4][lz4]

Python 3 is optionally needed as a run-time dependency in order to use
the `mkbootimg`, `unpack_bootimg`, and `repack_bootimg` scripts which
are all written in Python.

Additionally the following software is required at compile-time:

1. A C and C++ compiler (either [GCC][gcc] >= 10.X or [clang][clang])
2. The [Go compiler][golang]
3. [CMake][cmake]
4. [Perl][perl]

*Currently the build system doesn't check whether all of these are installed.*

# Installation

Source tarballs containing an already patched version of all vendored
dependencies are available on the [GitHub Release Page][release-page].

These tarballs should be used for packaging and general installation.
After the tarball was downloaded and extracted android-tools can be
build and installed as follows:

	$ mkdir build && cd build
	$ cmake ..
	$ make
	$ make install

# Generating tarballs

New source tarballs can be created from the Git repository using:

	$ mkdir build && cd build
	$ cmake ..
	$ make package_source

Before a new release is uploaded a new `git-tag(1)` should be created
for the release. Afterwards the tarball can be uploaded to the [GitHub
Release Page][release-page].

# See also

[The build script][android-tools-legacy] for android platform tools by [Anatol Pomozov][anatol.pomozov]
which inspired this project. Most definitions in the `CMakeLists.txt`
have been copied from Anatol's ruby script.

[android-tools]: https://developer.android.com/tools/releases/platform-tools
[void-linux]: https://github.com/void-linux/void-packages/tree/master/srcpkgs/android-tools
[arch-linux]: https://archlinux.org/packages/extra/x86_64/android-tools/
[alpine-linux]: https://pkgs.alpinelinux.org/package/edge/community/x86_64/android-tools
[repology]: https://repology.org/project/android-tools/versions
[release-page]: https://github.com/nmeum/android-tools/releases
[libusb]: https://libusb.info/
[PCRE]: https://pcre.sourceforge.net/
[gtest]: https://github.com/google/googletest
[gcc]: https://gcc.gnu.org/
[clang]: https://clang.llvm.org/
[golang]: https://go.dev/
[cmake]: https://cmake.org/
[perl]: https://www.perl.org/
[protobuf]: https://github.com/protocolbuffers/protobuf
[brotli]: https://github.com/google/brotli
[zstd]: https://facebook.github.io/zstd/
[lz4]: https://github.com/lz4/lz4
[android-tools-legacy]: https://github.com/anatol/android-platform-tools-build
[anatol.pomozov]: https://github.com/anatol
