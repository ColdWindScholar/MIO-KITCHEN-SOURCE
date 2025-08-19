#
# Copyright (C) 2017 The Android Open Source Project
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use, copy,
# modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

# TODO(zeuthen): This is not invoked by Android build system and is
# intended to aid users to locally build the EFI application. It would
# be nice to add gnu-efi/ to external and rewrite this as an
# Android.mk file.

EFI_CC      = gcc
EFI_LD      = ld
EFI_OBJCOPY = objcopy
AVB         = ../..
GNUEFI      = /usr/include/efi

EFI_SRC_FILES = \
    main.c \
    uefi_avb_sysdeps.c \
    uefi_avb_ops.c \
    uefi_avb_util.c \
    uefi_avb_boot.c \
	$(AVB)/libavb/avb_chain_partition_descriptor.c \
    $(AVB)/libavb/avb_crc32.c \
    $(AVB)/libavb/avb_crypto.c \
    $(AVB)/libavb/avb_descriptor.c \
    $(AVB)/libavb/avb_footer.c \
    $(AVB)/libavb/avb_hash_descriptor.c \
    $(AVB)/libavb/avb_hashtree_descriptor.c \
    $(AVB)/libavb/avb_kernel_cmdline_descriptor.c \
    $(AVB)/libavb/avb_property_descriptor.c \
    $(AVB)/libavb/avb_rsa.c \
    $(AVB)/libavb/avb_sha256.c \
    $(AVB)/libavb/avb_sha512.c \
    $(AVB)/libavb/avb_slot_verify.c \
    $(AVB)/libavb/avb_util.c \
    $(AVB)/libavb/avb_vbmeta_image.c \
    $(AVB)/libavb/avb_version.c \
    $(AVB)/libavb_ab/avb_ab_flow.c

EFI_OBJ_FILES   = $(notdir $(patsubst %.S,%.o,$(patsubst %.c,%.o,$(EFI_SRC_FILES))))
EFI_TARGET      = avb_bootloader.efi
EFI_SHARED_OBJ  = $(patsubst %.efi,%.so,$(EFI_TARGET))

EFI_CFLAGS = \
    -DAVB_COMPILATION -DAVB_ENABLE_DEBUG \
    -DAVB_AB_I_UNDERSTAND_LIBAVB_AB_IS_DEPRECATED \
    -std=gnu99 \
	-I$(ANDROID_BUILD_TOP)/system/core/mkbootimg/ \
    -I$(AVB) \
    -I$(GNUEFI) \
    -I$(GNUEFI)/x86_64 \
    -I$(GNUEFI)/protocol \
    -fno-stack-protector -fpic \
    -fshort-wchar -mno-red-zone -Wall \
    -DEFI_FUNCTION_WRAPPER

EFI_LDFLAGS = \
    -nostdlib -znocombreloc -T /usr/lib/elf_x86_64_efi.lds -shared \
    -Bsymbolic -L /usr/lib/ /usr/lib/crt0-efi-x86_64.o \
    /usr/lib/elf_x86_64_efi.lds

EFI_LDLIBS  = -lefi -lgnuefi

EFI_OBJCOPY_SECTIONS    = -j .text -j .sdata -j .data -j .dynamic \
                            -j .dynsym  -j .rel -j .rela -j .reloc

EFI_OBJCOPY_TARGET      = --target=efi-app-x86_64

all: $(EFI_TARGET)

$(EFI_OBJ_FILES): $(EFI_SRC_FILES)
	$(EFI_CC) $(EFI_CFLAGS) -c $(EFI_SRC_FILES)

$(EFI_SHARED_OBJ): $(EFI_OBJ_FILES)
	$(EFI_LD) $(EFI_LDFLAGS) $(EFI_OBJ_FILES) -o $@ $(EFI_LDLIBS)

$(EFI_TARGET): $(EFI_SHARED_OBJ)
	$(EFI_OBJCOPY) $(EFI_OBJCOPY_SECTIONS) $(EFI_OBJCOPY_TARGET) $^ $@

clean:
	rm -f  $(EFI_OBJ_FILES) $(EFI_SHARED_OBJ) $(EFI_TARGET) *~
