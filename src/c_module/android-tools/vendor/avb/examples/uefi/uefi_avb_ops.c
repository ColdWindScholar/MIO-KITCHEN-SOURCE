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

#include "uefi_avb_ops.h"
#include "uefi_avb_util.h"

#include <efi.h>
#include <efilib.h>

/* GPT related constants. */
#define GPT_REVISION 0x00010000
#define GPT_MAGIC "EFI PART"
#define GPT_MIN_SIZE 92
#define GPT_ENTRIES_LBA 2
#define AVB_BLOCK_SIZE 512
#define ENTRIES_PER_BLOCK 4
#define ENTRY_NAME_LEN 36
#define MAX_GPT_ENTRIES 128

typedef struct {
  uint8_t signature[8];
  uint32_t revision;
  uint32_t header_size;
  uint32_t header_crc32;
  uint32_t reserved;
  uint64_t header_lba;
  uint64_t alternate_header_lba;
  uint64_t first_usable_lba;
  uint64_t last_usable_lba;
  uint8_t disk_guid[16];
  uint64_t entry_lba;
  uint32_t entry_count;
  uint32_t entry_size;
  uint32_t entry_crc32;
  uint8_t reserved2[420];
} GPTHeader;

typedef struct {
  uint8_t type_GUID[16];
  uint8_t unique_GUID[16];
  uint64_t first_lba;
  uint64_t last_lba;
  uint64_t flags;
  uint16_t name[ENTRY_NAME_LEN];
} GPTEntry;

static EFI_STATUS find_partition_entry_by_name(IN EFI_BLOCK_IO* block_io,
                                               const char* partition_name,
                                               GPTEntry** entry_buf) {
  EFI_STATUS err;
  GPTHeader* gpt_header = NULL;
  GPTEntry all_gpt_entries[MAX_GPT_ENTRIES];
  uint16_t* partition_name_ucs2 = NULL;
  size_t partition_name_bytes;
  size_t partition_name_ucs2_capacity;
  size_t partition_name_ucs2_len;

  gpt_header = (GPTHeader*)avb_malloc(sizeof(GPTHeader));
  if (gpt_header == NULL) {
    avb_error("Could not allocate for GPT header\n");
    return EFI_NOT_FOUND;
  }

  *entry_buf = (GPTEntry*)avb_malloc(sizeof(GPTEntry) * ENTRIES_PER_BLOCK);
  if (entry_buf == NULL) {
    avb_error("Could not allocate for partition entry\n");
    avb_free(gpt_header);
    return EFI_NOT_FOUND;
  }

  err = uefi_call_wrapper(block_io->ReadBlocks,
                          NUM_ARGS_READ_BLOCKS,
                          block_io,
                          block_io->Media->MediaId,
                          1,
                          sizeof(GPTHeader),
                          gpt_header);
  if (EFI_ERROR(err)) {
    avb_error("Could not ReadBlocks for gpt header\n");
    avb_free(gpt_header);
    avb_free(*entry_buf);
    *entry_buf = NULL;
    return EFI_NOT_FOUND;
  }

  partition_name_bytes = avb_strlen(partition_name);
  partition_name_ucs2_capacity = sizeof(uint16_t) * (partition_name_bytes + 1);
  partition_name_ucs2 = avb_calloc(partition_name_ucs2_capacity);
  if (partition_name_ucs2 == NULL) {
    avb_error("Could not allocate for ucs2 partition name\n");
    avb_free(gpt_header);
    avb_free(*entry_buf);
    *entry_buf = NULL;
    return EFI_NOT_FOUND;
  }
  if (!uefi_avb_utf8_to_ucs2((const uint8_t*)partition_name,
                             partition_name_bytes,
                             partition_name_ucs2,
                             partition_name_ucs2_capacity,
                             NULL)) {
    avb_error("Could not convert partition name to UCS-2\n");
    avb_free(gpt_header);
    avb_free(partition_name_ucs2);
    avb_free(*entry_buf);
    *entry_buf = NULL;
    return EFI_NOT_FOUND;
  }
  partition_name_ucs2_len = StrLen(partition_name_ucs2);

  /* Block-aligned bytes for entries. */
  UINTN entries_num_bytes =
      block_io->Media->BlockSize * (MAX_GPT_ENTRIES / ENTRIES_PER_BLOCK);

  err = uefi_call_wrapper(block_io->ReadBlocks,
                          NUM_ARGS_READ_BLOCKS,
                          block_io,
                          block_io->Media->MediaId,
                          GPT_ENTRIES_LBA,
                          entries_num_bytes,
                          &all_gpt_entries);
  if (EFI_ERROR(err)) {
    avb_error("Could not ReadBlocks for GPT header\n");
    avb_free(gpt_header);
    avb_free(partition_name_ucs2);
    avb_free(*entry_buf);
    *entry_buf = NULL;
    return EFI_NOT_FOUND;
  }

  /* Find matching partition name. */
  for (int n = 0; n < gpt_header->entry_count; n++) {
    if ((partition_name_ucs2_len == StrLen(all_gpt_entries[n].name)) &&
        avb_memcmp(all_gpt_entries[n].name,
                   partition_name_ucs2,
                   partition_name_ucs2_len * 2) == 0) {
      avb_memcpy((*entry_buf), &all_gpt_entries[n], sizeof(GPTEntry));
      avb_free(partition_name_ucs2);
      avb_free(gpt_header);
      return EFI_SUCCESS;
    }
  }

  avb_free(partition_name_ucs2);
  avb_free(gpt_header);
  avb_free(*entry_buf);
  *entry_buf = NULL;
  return EFI_NOT_FOUND;
}

static AvbIOResult read_from_partition(AvbOps* ops,
                                       const char* partition_name,
                                       int64_t offset_from_partition,
                                       size_t num_bytes,
                                       void* buf,
                                       size_t* out_num_read) {
  EFI_STATUS err;
  GPTEntry* partition_entry;
  uint64_t partition_size;
  UEFIAvbOpsData* data = (UEFIAvbOpsData*)ops->user_data;

  avb_assert(partition_name != NULL);
  avb_assert(buf != NULL);
  avb_assert(out_num_read != NULL);

  err = find_partition_entry_by_name(
      data->block_io, partition_name, &partition_entry);
  if (EFI_ERROR(err)) {
    return AVB_IO_RESULT_ERROR_NO_SUCH_PARTITION;
  }

  partition_size =
      (partition_entry->last_lba - partition_entry->first_lba + 1) *
      data->block_io->Media->BlockSize;

  if (offset_from_partition < 0) {
    if ((-offset_from_partition) > partition_size) {
      avb_error("Offset outside range.\n");
      avb_free(partition_entry);
      return AVB_IO_RESULT_ERROR_RANGE_OUTSIDE_PARTITION;
    }
    offset_from_partition = partition_size - (-offset_from_partition);
  }

  /* Check if num_bytes goes beyond partition end. If so, don't read beyond
   * this boundary -- do a partial I/O instead.
   */
  if (num_bytes > partition_size - offset_from_partition)
    *out_num_read = partition_size - offset_from_partition;
  else
    *out_num_read = num_bytes;

  err = uefi_call_wrapper(
      data->disk_io->ReadDisk,
      5,
      data->disk_io,
      data->block_io->Media->MediaId,
      (partition_entry->first_lba * data->block_io->Media->BlockSize) +
          offset_from_partition,
      *out_num_read,
      buf);
  if (EFI_ERROR(err)) {
    avb_error("Could not read from Disk.\n");
    *out_num_read = 0;
    avb_free(partition_entry);
    return AVB_IO_RESULT_ERROR_IO;
  }

  avb_free(partition_entry);
  return AVB_IO_RESULT_OK;
}

static AvbIOResult write_to_partition(AvbOps* ops,
                                      const char* partition_name,
                                      int64_t offset_from_partition,
                                      size_t num_bytes,
                                      const void* buf) {
  EFI_STATUS err;
  GPTEntry* partition_entry;
  uint64_t partition_size;
  UEFIAvbOpsData* data = (UEFIAvbOpsData*)ops->user_data;

  avb_assert(partition_name != NULL);
  avb_assert(buf != NULL);

  err = find_partition_entry_by_name(
      data->block_io, partition_name, &partition_entry);
  if (EFI_ERROR(err)) {
    return AVB_IO_RESULT_ERROR_NO_SUCH_PARTITION;
  }

  partition_size = (partition_entry->last_lba - partition_entry->first_lba) *
                   data->block_io->Media->BlockSize;

  if (offset_from_partition < 0) {
    if ((-offset_from_partition) > partition_size) {
      avb_error("Offset outside range.\n");
      avb_free(partition_entry);
      return AVB_IO_RESULT_ERROR_RANGE_OUTSIDE_PARTITION;
    }
    offset_from_partition = partition_size - (-offset_from_partition);
  }

  /* Check if num_bytes goes beyond partition end. If so, error out -- no
   * partial I/O.
   */
  if (num_bytes > partition_size - offset_from_partition) {
    avb_error("Cannot write beyond partition boundary.\n");
    avb_free(partition_entry);
    return AVB_IO_RESULT_ERROR_RANGE_OUTSIDE_PARTITION;
  }

  err = uefi_call_wrapper(
      data->disk_io->WriteDisk,
      5,
      data->disk_io,
      data->block_io->Media->MediaId,
      (partition_entry->first_lba * data->block_io->Media->BlockSize) +
          offset_from_partition,
      num_bytes,
      buf);

  if (EFI_ERROR(err)) {
    avb_error("Could not write to Disk.\n");
    avb_free(partition_entry);
    return AVB_IO_RESULT_ERROR_IO;
  }

  avb_free(partition_entry);
  return AVB_IO_RESULT_OK;
}

static AvbIOResult get_size_of_partition(AvbOps* ops,
                                         const char* partition_name,
                                         uint64_t* out_size) {
  EFI_STATUS err;
  GPTEntry* partition_entry;
  uint64_t partition_size;
  UEFIAvbOpsData* data = (UEFIAvbOpsData*)ops->user_data;

  avb_assert(partition_name != NULL);

  err = find_partition_entry_by_name(
      data->block_io, partition_name, &partition_entry);
  if (EFI_ERROR(err)) {
    return AVB_IO_RESULT_ERROR_NO_SUCH_PARTITION;
  }

  partition_size =
      (partition_entry->last_lba - partition_entry->first_lba + 1) *
      data->block_io->Media->BlockSize;

  if (out_size != NULL) {
    *out_size = partition_size;
  }

  avb_free(partition_entry);
  return AVB_IO_RESULT_OK;
}

/* Helper method to get the parent path to the current |walker| path
 * given the initial path, |init|. Resulting path is stored in |next|.
 * Caller is responsible for freeing |next|. Stores allocated bytes
 * for |next| in |out_bytes|. Returns EFI_SUCCESS on success.
 */
static EFI_STATUS walk_path(IN EFI_DEVICE_PATH* init,
                            IN EFI_DEVICE_PATH* walker,
                            OUT EFI_DEVICE_PATH** next,
                            OUT UINTN* out_bytes) {
  /* Number of bytes from initial path to current walker. */
  UINTN walker_bytes = (uint8_t*)NextDevicePathNode(walker) - (uint8_t*)init;
  *out_bytes = sizeof(EFI_DEVICE_PATH) + walker_bytes;

  *next = (EFI_DEVICE_PATH*)avb_malloc(*out_bytes);
  if (*next == NULL) {
    *out_bytes = 0;
    return EFI_NOT_FOUND;
  }

  /* Copy in the previous paths. */
  avb_memcpy((*next), init, walker_bytes);
  /* Copy in the new ending of the path. */
  avb_memcpy(
      (uint8_t*)(*next) + walker_bytes, EndDevicePath, sizeof(EFI_DEVICE_PATH));
  return EFI_SUCCESS;
}

/* Helper method to validate a GPT header, |gpth|.
 *
 * @return EFI_STATUS EFI_SUCCESS on success.
 */
static EFI_STATUS validate_gpt(const IN GPTHeader* gpth) {
  if (avb_memcmp(gpth->signature, GPT_MAGIC, sizeof(gpth->signature)) != 0) {
    avb_error("GPT signature does not match.\n");
    return EFI_NOT_FOUND;
  }
  /* Make sure GPT header bytes are within minimun and block size. */
  if (gpth->header_size < GPT_MIN_SIZE) {
    avb_error("GPT header too small.\n");
    return EFI_NOT_FOUND;
  }
  if (gpth->header_size > AVB_BLOCK_SIZE) {
    avb_error("GPT header too big.\n");
    return EFI_NOT_FOUND;
  }

  GPTHeader gpth_tmp = {{0}};
  avb_memcpy(&gpth_tmp, gpth, sizeof(GPTHeader));
  uint32_t gpt_header_crc = gpth_tmp.header_crc32;
  gpth_tmp.header_crc32 = 0;
  uint32_t gpt_header_crc_calc =
      CalculateCrc((uint8_t*)&gpth_tmp, gpth_tmp.header_size);

  if (gpt_header_crc != gpt_header_crc_calc) {
    avb_error("GPT header crc invalid.\n");
    return EFI_NOT_FOUND;
  }

  if (gpth->revision != GPT_REVISION) {
    avb_error("GPT header wrong revision.\n");
    return EFI_NOT_FOUND;
  }

  return EFI_SUCCESS;
}

/* Queries |disk_handle| for a |block_io| device and the corresponding
 * path, |block_path|.  The |block_io| device is found by iteratively
 * querying parent devices and checking for a GPT Header.  This
 * ensures the resulting |block_io| device is the top level block
 * device having access to partition entries. Returns EFI_STATUS
 * EFI_NOT_FOUND on failure, EFI_SUCCESS otherwise.
 */
static EFI_STATUS get_disk_block_io(IN EFI_HANDLE* block_handle,
                                    OUT EFI_BLOCK_IO** block_io,
                                    OUT EFI_DISK_IO** disk_io,
                                    OUT EFI_DEVICE_PATH** io_path) {
  EFI_STATUS err;
  EFI_HANDLE disk_handle;
  UINTN path_bytes;
  EFI_DEVICE_PATH* disk_path;
  EFI_DEVICE_PATH* walker_path;
  EFI_DEVICE_PATH* init_path;
  GPTHeader gpt_header = {{0}};
  init_path = DevicePathFromHandle(block_handle);

  if (!init_path) {
    return EFI_NOT_FOUND;
  }

  walker_path = init_path;
  while (!IsDevicePathEnd(walker_path)) {
    walker_path = NextDevicePathNode(walker_path);

    err = walk_path(init_path, walker_path, &(*io_path), &path_bytes);
    if (EFI_ERROR(err)) {
      avb_error("Cannot walk device path.\n");
      return EFI_NOT_FOUND;
    }

    disk_path = (EFI_DEVICE_PATH*)avb_malloc(path_bytes);
    avb_memcpy(disk_path, *io_path, path_bytes);
    err = uefi_call_wrapper(BS->LocateDevicePath,
                            NUM_ARGS_LOCATE_DEVICE_PATH,
                            &BlockIoProtocol,
                            &(*io_path),
                            &block_handle);
    if (EFI_ERROR(err)) {
      avb_free(*io_path);
      avb_free(disk_path);
      continue;
    }
    err = uefi_call_wrapper(BS->LocateDevicePath,
                            NUM_ARGS_LOCATE_DEVICE_PATH,
                            &DiskIoProtocol,
                            &disk_path,
                            &disk_handle);
    if (EFI_ERROR(err)) {
      avb_error("LocateDevicePath, DISK_IO_PROTOCOL.\n");
      avb_free(*io_path);
      avb_free(disk_path);
      continue;
    }

    /* Handle Block and Disk I/O. Attempt to get handle on device,
     * must be Block/Disk Io type.
     */
    err = uefi_call_wrapper(BS->HandleProtocol,
                            NUM_ARGS_HANDLE_PROTOCOL,
                            block_handle,
                            &BlockIoProtocol,
                            (VOID**)&(*block_io));
    if (EFI_ERROR(err)) {
      avb_error("Cannot get handle on block device.\n");
      avb_free(*io_path);
      avb_free(disk_path);
      continue;
    }
    err = uefi_call_wrapper(BS->HandleProtocol,
                            NUM_ARGS_HANDLE_PROTOCOL,
                            disk_handle,
                            &DiskIoProtocol,
                            (VOID**)&(*disk_io));
    if (EFI_ERROR(err)) {
      avb_error("Cannot get handle on disk device.\n");
      avb_free(*io_path);
      avb_free(disk_path);
      continue;
    }

    if ((*block_io)->Media->LogicalPartition ||
        !(*block_io)->Media->MediaPresent) {
      avb_error("Logical partion or No Media Present, continue...\n");
      avb_free(*io_path);
      avb_free(disk_path);
      continue;
    }

    err = uefi_call_wrapper((*block_io)->ReadBlocks,
                            NUM_ARGS_READ_BLOCKS,
                            (*block_io),
                            (*block_io)->Media->MediaId,
                            1,
                            sizeof(GPTHeader),
                            &gpt_header);

    if (EFI_ERROR(err)) {
      avb_error("ReadBlocks, Block Media error.\n");
      avb_free(*io_path);
      avb_free(disk_path);
      continue;
    }

    err = validate_gpt(&gpt_header);
    if (EFI_ERROR(err)) {
      avb_error("Invalid GPTHeader\n");
      avb_free(*io_path);
      avb_free(disk_path);
      continue;
    }

    return EFI_SUCCESS;
  }

  (*block_io) = NULL;
  return EFI_NOT_FOUND;
}

static AvbIOResult validate_vbmeta_public_key(
    AvbOps* ops,
    const uint8_t* public_key_data,
    size_t public_key_length,
    const uint8_t* public_key_metadata,
    size_t public_key_metadata_length,
    bool* out_key_is_trusted) {
  /* For now we just allow any key. */
  if (out_key_is_trusted != NULL) {
    *out_key_is_trusted = true;
  }
  avb_debug("TODO: implement validate_vbmeta_public_key().\n");
  return AVB_IO_RESULT_OK;
}

static AvbIOResult read_rollback_index(AvbOps* ops,
                                       size_t rollback_index_slot,
                                       uint64_t* out_rollback_index) {
  /* For now we always return 0 as the stored rollback index. */
  avb_debug("TODO: implement read_rollback_index().\n");
  if (out_rollback_index != NULL) {
    *out_rollback_index = 0;
  }
  return AVB_IO_RESULT_OK;
}

static AvbIOResult write_rollback_index(AvbOps* ops,
                                        size_t rollback_index_slot,
                                        uint64_t rollback_index) {
  /* For now this is a no-op. */
  avb_debug("TODO: implement write_rollback_index().\n");
  return AVB_IO_RESULT_OK;
}

static AvbIOResult read_is_device_unlocked(AvbOps* ops, bool* out_is_unlocked) {
  /* For now we always return that the device is unlocked. */
  avb_debug("TODO: implement read_is_device_unlocked().\n");
  *out_is_unlocked = true;
  return AVB_IO_RESULT_OK;
}

static void set_hex(char* buf, uint8_t value) {
  char hex_digits[17] = "0123456789abcdef";
  buf[0] = hex_digits[value >> 4];
  buf[1] = hex_digits[value & 0x0f];
}

static AvbIOResult get_unique_guid_for_partition(AvbOps* ops,
                                                 const char* partition,
                                                 char* guid_buf,
                                                 size_t guid_buf_size) {
  EFI_STATUS err;
  GPTEntry* partition_entry;
  UEFIAvbOpsData* data = (UEFIAvbOpsData*)ops->user_data;

  avb_assert(partition != NULL);
  avb_assert(guid_buf != NULL);

  err =
      find_partition_entry_by_name(data->block_io, partition, &partition_entry);
  if (EFI_ERROR(err)) {
    avb_error("Error getting unique GUID for partition.\n");
    return AVB_IO_RESULT_ERROR_IO;
  }

  if (guid_buf_size < 37) {
    avb_error("GUID buffer size too small.\n");
    return AVB_IO_RESULT_ERROR_IO;
  }

  /* The GUID encoding is somewhat peculiar in terms of byte order. It
   * is what it is.
   */
  set_hex(guid_buf + 0, partition_entry->unique_GUID[3]);
  set_hex(guid_buf + 2, partition_entry->unique_GUID[2]);
  set_hex(guid_buf + 4, partition_entry->unique_GUID[1]);
  set_hex(guid_buf + 6, partition_entry->unique_GUID[0]);
  guid_buf[8] = '-';
  set_hex(guid_buf + 9, partition_entry->unique_GUID[5]);
  set_hex(guid_buf + 11, partition_entry->unique_GUID[4]);
  guid_buf[13] = '-';
  set_hex(guid_buf + 14, partition_entry->unique_GUID[7]);
  set_hex(guid_buf + 16, partition_entry->unique_GUID[6]);
  guid_buf[18] = '-';
  set_hex(guid_buf + 19, partition_entry->unique_GUID[8]);
  set_hex(guid_buf + 21, partition_entry->unique_GUID[9]);
  guid_buf[23] = '-';
  set_hex(guid_buf + 24, partition_entry->unique_GUID[10]);
  set_hex(guid_buf + 26, partition_entry->unique_GUID[11]);
  set_hex(guid_buf + 28, partition_entry->unique_GUID[12]);
  set_hex(guid_buf + 30, partition_entry->unique_GUID[13]);
  set_hex(guid_buf + 32, partition_entry->unique_GUID[14]);
  set_hex(guid_buf + 34, partition_entry->unique_GUID[15]);
  guid_buf[36] = '\0';
  return AVB_IO_RESULT_OK;
}

AvbOps* uefi_avb_ops_new(EFI_HANDLE app_image) {
  UEFIAvbOpsData* data;
  EFI_STATUS err;
  EFI_LOADED_IMAGE* loaded_app_image = NULL;
  EFI_GUID loaded_image_protocol = LOADED_IMAGE_PROTOCOL;

  data = avb_calloc(sizeof(UEFIAvbOpsData));
  data->ops.user_data = data;

  data->efi_image_handle = app_image;
  err = uefi_call_wrapper(BS->HandleProtocol,
                          NUM_ARGS_HANDLE_PROTOCOL,
                          app_image,
                          &loaded_image_protocol,
                          (VOID**)&loaded_app_image);
  if (EFI_ERROR(err)) {
    avb_error("HandleProtocol, LOADED_IMAGE_PROTOCOL.\n");
    return 0;
  }

  /* Get parent device disk and block I/O. */
  err = get_disk_block_io(loaded_app_image->DeviceHandle,
                          &data->block_io,
                          &data->disk_io,
                          &data->path);
  if (EFI_ERROR(err)) {
    avb_error("Could not acquire block or disk device handle.\n");
    return 0;
  }

  data->ops.ab_ops = &data->ab_ops;
  data->ops.read_from_partition = read_from_partition;
  data->ops.write_to_partition = write_to_partition;
  data->ops.validate_vbmeta_public_key = validate_vbmeta_public_key;
  data->ops.read_rollback_index = read_rollback_index;
  data->ops.write_rollback_index = write_rollback_index;
  data->ops.read_is_device_unlocked = read_is_device_unlocked;
  data->ops.get_unique_guid_for_partition = get_unique_guid_for_partition;
  data->ops.get_size_of_partition = get_size_of_partition;

  data->ab_ops.ops = &data->ops;
  data->ab_ops.read_ab_metadata = avb_ab_data_read;
  data->ab_ops.write_ab_metadata = avb_ab_data_write;

  return &data->ops;
}

void uefi_avb_ops_free(AvbOps* ops) {
  UEFIAvbOpsData* data = ops->user_data;
  avb_free(data);
}
