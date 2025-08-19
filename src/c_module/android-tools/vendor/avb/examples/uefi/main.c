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

#include <efi.h>
#include <efilib.h>

#include <libavb_ab/libavb_ab.h>

#include "uefi_avb_boot.h"
#include "uefi_avb_ops.h"

EFI_STATUS EFIAPI efi_main(EFI_HANDLE ImageHandle,
                           EFI_SYSTEM_TABLE* SystemTable) {
  AvbOps* ops;
  AvbABFlowResult ab_result;
  AvbSlotVerifyData* slot_data;
  UEFIAvbBootKernelResult boot_result;
  const char* requested_partitions[] = {"boot", NULL};
  bool unlocked = true;
  char* additional_cmdline = NULL;
  AvbSlotVerifyFlags flags;

  InitializeLib(ImageHandle, SystemTable);

  avb_printv("UEFI AVB-based bootloader using libavb version ",
             avb_version_string(),
             "\n",
             NULL);

  ops = uefi_avb_ops_new(ImageHandle);
  if (ops == NULL) {
    avb_fatal("Error allocating AvbOps.\n");
  }

  if (ops->read_is_device_unlocked(ops, &unlocked) != AVB_IO_RESULT_OK) {
    avb_fatal("Error determining whether device is unlocked.\n");
  }
  avb_printv("read_is_device_unlocked() ops returned that device is ",
             unlocked ? "UNLOCKED" : "LOCKED",
             "\n",
             NULL);

  flags = AVB_SLOT_VERIFY_FLAGS_NONE;
  if (unlocked) {
    flags |= AVB_SLOT_VERIFY_FLAGS_ALLOW_VERIFICATION_ERROR;
  }

  ab_result = avb_ab_flow(ops->ab_ops,
                          requested_partitions,
                          flags,
                          AVB_HASHTREE_ERROR_MODE_RESTART_AND_INVALIDATE,
                          &slot_data);
  avb_printv("avb_ab_flow() returned ",
             avb_ab_flow_result_to_string(ab_result),
             "\n",
             NULL);
  switch (ab_result) {
    case AVB_AB_FLOW_RESULT_OK:
    case AVB_AB_FLOW_RESULT_OK_WITH_VERIFICATION_ERROR:
      avb_printv("slot_suffix:    ", slot_data->ab_suffix, "\n", NULL);
      avb_printv("cmdline:        ", slot_data->cmdline, "\n", NULL);
      avb_printv(
          "release string: ",
          (const char*)((((AvbVBMetaImageHeader*)(slot_data->vbmeta_images[0]
                                                      .vbmeta_data)))
                            ->release_string),
          "\n",
          NULL);
      /* Pass 'skip_initramfs' since we're not booting into recovery
       * mode. Also pass the selected slot in androidboot.slot and the
       * suffix in androidboot.slot_suffix.
       */
      additional_cmdline = avb_strdupv("skip_initramfs ",
                                       "androidboot.slot=",
                                       slot_data->ab_suffix + 1,
                                       " ",
                                       "androidboot.slot_suffix=",
                                       slot_data->ab_suffix,
                                       NULL);
      if (additional_cmdline == NULL) {
        avb_fatal("Error allocating additional_cmdline.\n");
      }
      boot_result =
          uefi_avb_boot_kernel(ImageHandle, slot_data, additional_cmdline);
      avb_fatal("uefi_avb_boot_kernel() failed with error ",
                uefi_avb_boot_kernel_result_to_string(boot_result),
                "\n");
      avb_slot_verify_data_free(slot_data);
      avb_free(additional_cmdline);
      break;
    case AVB_AB_FLOW_RESULT_ERROR_OOM:
      avb_fatal("OOM error while doing A/B select flow.\n");
      break;
    case AVB_AB_FLOW_RESULT_ERROR_IO:
      avb_fatal("I/O error while doing A/B select flow.\n");
      break;
    case AVB_AB_FLOW_RESULT_ERROR_NO_BOOTABLE_SLOTS:
      avb_fatal("No bootable slots - enter repair mode\n");
      break;
    case AVB_AB_FLOW_RESULT_ERROR_INVALID_ARGUMENT:
      avb_fatal("Invalid arguments passed\n");
      break;
  }
  uefi_avb_ops_free(ops);

  return EFI_SUCCESS;
}
