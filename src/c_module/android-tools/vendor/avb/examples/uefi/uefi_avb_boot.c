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

#include "bootimg.h"

#include "uefi_avb_boot.h"
#include "uefi_avb_util.h"

/* See Documentation/x86/boot.txt for this struct and more information
 * about the boot/handover protocol.
 */

#define SETUP_MAGIC 0x53726448 /* "HdrS" */

struct SetupHeader {
  UINT8 boot_sector[0x01f1];
  UINT8 setup_secs;
  UINT16 root_flags;
  UINT32 sys_size;
  UINT16 ram_size;
  UINT16 video_mode;
  UINT16 root_dev;
  UINT16 signature;
  UINT16 jump;
  UINT32 header;
  UINT16 version;
  UINT16 su_switch;
  UINT16 setup_seg;
  UINT16 start_sys;
  UINT16 kernel_ver;
  UINT8 loader_id;
  UINT8 load_flags;
  UINT16 movesize;
  UINT32 code32_start;
  UINT32 ramdisk_start;
  UINT32 ramdisk_len;
  UINT32 bootsect_kludge;
  UINT16 heap_end;
  UINT8 ext_loader_ver;
  UINT8 ext_loader_type;
  UINT32 cmd_line_ptr;
  UINT32 ramdisk_max;
  UINT32 kernel_alignment;
  UINT8 relocatable_kernel;
  UINT8 min_alignment;
  UINT16 xloadflags;
  UINT32 cmdline_size;
  UINT32 hardware_subarch;
  UINT64 hardware_subarch_data;
  UINT32 payload_offset;
  UINT32 payload_length;
  UINT64 setup_data;
  UINT64 pref_address;
  UINT32 init_size;
  UINT32 handover_offset;
} __attribute__((packed));

#ifdef __x86_64__
typedef VOID (*handover_f)(VOID* image,
                           EFI_SYSTEM_TABLE* table,
                           struct SetupHeader* setup);
static inline VOID linux_efi_handover(EFI_HANDLE image,
                                      struct SetupHeader* setup) {
  handover_f handover;

  asm volatile("cli");
  handover =
      (handover_f)((UINTN)setup->code32_start + 512 + setup->handover_offset);
  handover(image, ST, setup);
}
#else
typedef VOID (*handover_f)(VOID* image,
                           EFI_SYSTEM_TABLE* table,
                           struct SetupHeader* setup)
    __attribute__((regparm(0)));
static inline VOID linux_efi_handover(EFI_HANDLE image,
                                      struct SetupHeader* setup) {
  handover_f handover;

  handover = (handover_f)((UINTN)setup->code32_start + setup->handover_offset);
  handover(image, ST, setup);
}
#endif

static size_t round_up(size_t value, size_t size) {
  size_t ret = value + size - 1;
  ret /= size;
  ret *= size;
  return ret;
}

UEFIAvbBootKernelResult uefi_avb_boot_kernel(EFI_HANDLE efi_image_handle,
                                             AvbSlotVerifyData* slot_data,
                                             const char* cmdline_extra) {
  UEFIAvbBootKernelResult ret;
  const boot_img_hdr* header;
  EFI_STATUS err;
  UINT8* kernel_buf = NULL;
  UINT8* initramfs_buf = NULL;
  UINT8* cmdline_utf8 = NULL;
  AvbPartitionData* boot;
  size_t offset;
  uint64_t total_size;
  size_t initramfs_size;
  size_t cmdline_first_len;
  size_t cmdline_second_len;
  size_t cmdline_extra_len;
  size_t cmdline_utf8_len;
  struct SetupHeader* image_setup;
  struct SetupHeader* setup;
  EFI_PHYSICAL_ADDRESS addr;

  if (slot_data->num_loaded_partitions != 1) {
    avb_error("No boot partition.\n");
    ret = UEFI_AVB_BOOT_KERNEL_RESULT_ERROR_PARTITION_INVALID_FORMAT;
    goto out;
  }

  boot = &slot_data->loaded_partitions[0];
  if (avb_strcmp(boot->partition_name, "boot") != 0) {
    avb_error("Unexpected partition name '", boot->partition_name, "'.\n");
    ret = UEFI_AVB_BOOT_KERNEL_RESULT_ERROR_PARTITION_INVALID_FORMAT;
    goto out;
  }

  header = (const boot_img_hdr*)boot->data;

  /* Check boot image header magic field. */
  if (avb_memcmp(BOOT_MAGIC, header->magic, BOOT_MAGIC_SIZE)) {
    avb_error("Wrong boot image header magic.\n");
    ret = UEFI_AVB_BOOT_KERNEL_RESULT_ERROR_PARTITION_INVALID_FORMAT;
    goto out;
  }

  /* Sanity check header. */
  total_size = header->kernel_size;
  if (!avb_safe_add_to(&total_size, header->ramdisk_size) ||
      !avb_safe_add_to(&total_size, header->second_size)) {
    avb_error("Overflow while adding sizes of kernel and initramfs.\n");
    ret = UEFI_AVB_BOOT_KERNEL_RESULT_ERROR_PARTITION_INVALID_FORMAT;
    goto out;
  }
  if (total_size > boot->data_size) {
    avb_error("Invalid kernel/initramfs sizes.\n");
    ret = UEFI_AVB_BOOT_KERNEL_RESULT_ERROR_PARTITION_INVALID_FORMAT;
    goto out;
  }

  /* The kernel has to be in its own specific memory pool. */
  err = uefi_call_wrapper(BS->AllocatePool,
                          NUM_ARGS_ALLOCATE_POOL,
                          EfiLoaderCode,
                          header->kernel_size,
                          &kernel_buf);
  if (EFI_ERROR(err)) {
    avb_error("Could not allocate kernel buffer.\n");
    ret = UEFI_AVB_BOOT_KERNEL_RESULT_ERROR_OOM;
    goto out;
  }
  avb_memcpy(kernel_buf, boot->data + header->page_size, header->kernel_size);

  /* Ditto for the initrd. */
  initramfs_buf = NULL;
  initramfs_size = header->ramdisk_size + header->second_size;
  if (initramfs_size > 0) {
    err = uefi_call_wrapper(BS->AllocatePool,
                            NUM_ARGS_ALLOCATE_POOL,
                            EfiLoaderCode,
                            initramfs_size,
                            &initramfs_buf);
    if (EFI_ERROR(err)) {
      avb_error("Could not allocate initrd buffer.\n");
      ret = UEFI_AVB_BOOT_KERNEL_RESULT_ERROR_OOM;
      goto out;
    }
    /* Concatente the first and second initramfs. */
    offset = header->page_size;
    offset += round_up(header->kernel_size, header->page_size);
    avb_memcpy(initramfs_buf, boot->data + offset, header->ramdisk_size);
    offset += round_up(header->ramdisk_size, header->page_size);
    avb_memcpy(initramfs_buf, boot->data + offset, header->second_size);
  }

  /* Prepare the command-line. */
  cmdline_first_len = avb_strlen((const char*)header->cmdline);
  cmdline_second_len = avb_strlen(slot_data->cmdline);
  cmdline_extra_len = cmdline_extra != NULL ? avb_strlen(cmdline_extra) : 0;
  if (cmdline_extra_len > 0) {
    cmdline_extra_len += 1;
  }
  cmdline_utf8_len =
      cmdline_first_len + 1 + cmdline_second_len + 1 + cmdline_extra_len;
  err = uefi_call_wrapper(BS->AllocatePool,
                          NUM_ARGS_ALLOCATE_POOL,
                          EfiLoaderCode,
                          cmdline_utf8_len,
                          &cmdline_utf8);
  if (EFI_ERROR(err)) {
    avb_error("Could not allocate kernel cmdline.\n");
    ret = UEFI_AVB_BOOT_KERNEL_RESULT_ERROR_OOM;
    goto out;
  }
  offset = 0;
  avb_memcpy(cmdline_utf8, header->cmdline, cmdline_first_len);
  offset += cmdline_first_len;
  cmdline_utf8[offset] = ' ';
  offset += 1;
  avb_memcpy(cmdline_utf8 + offset, slot_data->cmdline, cmdline_second_len);
  offset += cmdline_second_len;
  if (cmdline_extra_len > 0) {
    cmdline_utf8[offset] = ' ';
    avb_memcpy(cmdline_utf8 + offset + 1, cmdline_extra, cmdline_extra_len - 1);
    offset += cmdline_extra_len;
  }
  cmdline_utf8[offset] = '\0';
  offset += 1;
  avb_assert(offset == cmdline_utf8_len);

  /* Now set up the EFI handover. */
  image_setup = (struct SetupHeader*)kernel_buf;
  if (image_setup->signature != 0xAA55 || image_setup->header != SETUP_MAGIC) {
    avb_error("Wrong kernel header magic.\n");
    ret = UEFI_AVB_BOOT_KERNEL_RESULT_ERROR_KERNEL_INVALID_FORMAT;
    goto out;
  }

  if (image_setup->version < 0x20b) {
    avb_error("Wrong version.\n");
    ret = UEFI_AVB_BOOT_KERNEL_RESULT_ERROR_KERNEL_INVALID_FORMAT;
    goto out;
  }

  if (!image_setup->relocatable_kernel) {
    avb_error("Kernel is not relocatable.\n");
    ret = UEFI_AVB_BOOT_KERNEL_RESULT_ERROR_KERNEL_INVALID_FORMAT;
    goto out;
  }

  addr = 0x3fffffff;
  err = uefi_call_wrapper(BS->AllocatePages,
                          4,
                          AllocateMaxAddress,
                          EfiLoaderData,
                          EFI_SIZE_TO_PAGES(0x4000),
                          &addr);
  if (EFI_ERROR(err)) {
    avb_error("Could not allocate setup buffer.\n");
    ret = UEFI_AVB_BOOT_KERNEL_RESULT_ERROR_OOM;
    goto out;
  }
  setup = (struct SetupHeader*)(UINTN)addr;
  avb_memset(setup, '\0', 0x4000);
  avb_memcpy(setup, image_setup, sizeof(struct SetupHeader));
  setup->loader_id = 0xff;
  setup->code32_start =
      ((uintptr_t)kernel_buf) + (image_setup->setup_secs + 1) * 512;
  setup->cmd_line_ptr = (uintptr_t)cmdline_utf8;

  setup->ramdisk_start = (uintptr_t)initramfs_buf;
  setup->ramdisk_len = (uintptr_t)initramfs_size;

  /* Jump to the kernel. */
  linux_efi_handover(efi_image_handle, setup);

  ret = UEFI_AVB_BOOT_KERNEL_RESULT_ERROR_START_KERNEL;
out:
  return ret;
}

const char* uefi_avb_boot_kernel_result_to_string(
    UEFIAvbBootKernelResult result) {
  const char* ret = NULL;

  switch (result) {
    case UEFI_AVB_BOOT_KERNEL_RESULT_OK:
      ret = "OK";
      break;
    case UEFI_AVB_BOOT_KERNEL_RESULT_ERROR_OOM:
      ret = "ERROR_OEM";
      break;
    case UEFI_AVB_BOOT_KERNEL_RESULT_ERROR_IO:
      ret = "ERROR_IO";
      break;
    case UEFI_AVB_BOOT_KERNEL_RESULT_ERROR_PARTITION_INVALID_FORMAT:
      ret = "ERROR_PARTITION_INVALID_FORMAT";
      break;
    case UEFI_AVB_BOOT_KERNEL_RESULT_ERROR_KERNEL_INVALID_FORMAT:
      ret = "ERROR_KERNEL_INVALID_FORMAT";
      break;
    case UEFI_AVB_BOOT_KERNEL_RESULT_ERROR_START_KERNEL:
      ret = "ERROR_START_KERNEL";
      break;
      /* Do not add a 'default:' case here because of -Wswitch. */
  }

  if (ret == NULL) {
    avb_error("Unknown UEFIAvbBootKernelResult value.\n");
    ret = "(unknown)";
  }

  return ret;
}
