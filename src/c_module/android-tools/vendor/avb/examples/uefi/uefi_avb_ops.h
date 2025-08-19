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

#ifndef UEFI_AVB_OPS_H_
#define UEFI_AVB_OPS_H_

#include <efi.h>
#include <libavb_ab/libavb_ab.h>

/* The |user_data| member of AvbOps points to a struct of this type. */
typedef struct UEFIAvbOpsData {
  AvbOps ops;
  AvbABOps ab_ops;

  EFI_HANDLE efi_image_handle;
  EFI_DEVICE_PATH* path;
  EFI_BLOCK_IO* block_io;
  EFI_DISK_IO* disk_io;
} UEFIAvbOpsData;

/* Returns an AvbOps for use with UEFI. */
AvbOps* uefi_avb_ops_new(EFI_HANDLE app_image);

/* Frees the AvbOps allocated with uefi_avb_ops_new(). */
void uefi_avb_ops_free(AvbOps* ops);

#endif /* UEFI_AVB_OPS_H_ */
