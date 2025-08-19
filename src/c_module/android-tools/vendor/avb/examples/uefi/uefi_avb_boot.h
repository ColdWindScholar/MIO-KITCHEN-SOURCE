/*
 * Copyright (C) 2017 The Android Open Source Project
 *
 * Permission is hereby granted, free of charge, to any person
 * obtaining a copy of this software and associated documentation
 * files (the "Software"), to deal in the Software without
 * restriction, including without limitation the rights to use, copy,
 * modify, merge, publish, distribute, sublicense, and/or sell copies
 * of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be
 * included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 * EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
 * NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
 * BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
 * ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

#ifndef UEFI_AVB_BOOT_H_
#define UEFI_AVB_BOOT_H_

#include <efi.h>
#include <libavb/libavb.h>

/* Return codes used in uefi_avb_boot_kernel().
 *
 * Use uefi_avb_boot_kernel_result_to_string to get a textual
 * representation usable for error/debug output.
 */
typedef enum {
  UEFI_AVB_BOOT_KERNEL_RESULT_OK,
  UEFI_AVB_BOOT_KERNEL_RESULT_ERROR_OOM,
  UEFI_AVB_BOOT_KERNEL_RESULT_ERROR_IO,
  UEFI_AVB_BOOT_KERNEL_RESULT_ERROR_PARTITION_INVALID_FORMAT,
  UEFI_AVB_BOOT_KERNEL_RESULT_ERROR_KERNEL_INVALID_FORMAT,
  UEFI_AVB_BOOT_KERNEL_RESULT_ERROR_START_KERNEL
} UEFIAvbBootKernelResult;

/* Jumps to the Linux kernel embedded in the Android boot image which
 * has been loaded in |slot_data|. This also supports setting up the
 * initramfs from the boot image. The command-line to be passed to the
 * kernel will be the concatenation of
 *
 *  1. the cmdline in the Android boot image; and
 *  2. the cmdline in |slot_data|; and
 *  3. |cmdline_extra| if not NULL
 *
 * in that order with spaces inserted as necessary.
 *
 * This function only returns if an error occurs.
 */
UEFIAvbBootKernelResult uefi_avb_boot_kernel(EFI_HANDLE efi_image_handle,
                                             AvbSlotVerifyData* slot_data,
                                             const char* cmdline_extra);

/* Get a textual representation of |result|. */
const char* uefi_avb_boot_kernel_result_to_string(
    UEFIAvbBootKernelResult result);

#endif /* UEFI_AVB_BOOT_H_ */
