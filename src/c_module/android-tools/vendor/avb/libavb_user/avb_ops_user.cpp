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

#include "avb_ops_user.h"

#include <errno.h>
#include <fcntl.h>
#include <linux/fs.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#include <cutils/properties.h>
#include <fs_mgr.h>

#include <libavb_ab/libavb_ab.h>

using android::fs_mgr::Fstab;
using android::fs_mgr::GetEntryForMountPoint;
using android::fs_mgr::ReadDefaultFstab;
using android::fs_mgr::ReadFstabFromFile;

/* Open the appropriate fstab file and fallback to /fstab.device if
 * that's what's being used.
 */
static bool open_fstab(Fstab* fstab) {
  return ReadDefaultFstab(fstab) || ReadFstabFromFile("/fstab.device", fstab);
}

static int open_partition(const char* name, int flags) {
  char* path;
  int fd;

  /* Per https://android-review.googlesource.com/c/platform/system/core/+/674989
   * Android now supports /dev/block/by-name/<partition_name> ... try that
   * first.
   */
  path = avb_strdupv("/dev/block/by-name/", name, NULL);
  if (path != NULL) {
    fd = open(path, flags);
    avb_free(path);
    if (fd != -1) {
      return fd;
    }
  }

  /* OK, so /dev/block/by-name/<partition_name> didn't work... so we're
   * falling back to what we used to do before that:
   *
   * We can't use fs_mgr to look up |name| because fstab doesn't list
   * every slot partition (it uses the slotselect option to mask the
   * suffix) and |slot| is expected to be of that form, e.g. boot_a.
   *
   * We can however assume that there's an entry for the /misc mount
   * point and use that to get the device file for the misc
   * partition. From there we'll assume that a by-name scheme is used
   * so we can just replace the trailing "misc" by the given |name|,
   * e.g.
   *
   *   /dev/block/platform/soc.0/7824900.sdhci/by-name/misc ->
   *   /dev/block/platform/soc.0/7824900.sdhci/by-name/boot_a
   *
   * If needed, it's possible to relax this assumption in the future
   * by trawling /sys/block looking for the appropriate sibling of
   * misc and then finding an entry in /dev matching the sysfs entry.
   */

  Fstab fstab;
  if (!open_fstab(&fstab)) {
    return -1;
  }
  auto record = GetEntryForMountPoint(&fstab, "/misc");
  if (record == nullptr) {
    return -1;
  }
  if (strcmp(name, "misc") == 0) {
    path = strdup(record->blk_device.c_str());
  } else {
    size_t trimmed_len, name_len;
    const char* end_slash = strrchr(record->blk_device.c_str(), '/');
    if (end_slash == NULL) {
      return -1;
    }
    trimmed_len = end_slash - record->blk_device.c_str() + 1;
    name_len = strlen(name);
    path = static_cast<char*>(calloc(trimmed_len + name_len + 1, 1));
    strncpy(path, record->blk_device.c_str(), trimmed_len);
    strncpy(path + trimmed_len, name, name_len);
  }

  fd = open(path, flags);
  free(path);

  return fd;
}

static AvbIOResult read_from_partition(AvbOps* ops,
                                       const char* partition,
                                       int64_t offset,
                                       size_t num_bytes,
                                       void* buffer,
                                       size_t* out_num_read) {
  int fd;
  off_t where;
  ssize_t num_read;
  AvbIOResult ret;

  fd = open_partition(partition, O_RDONLY);
  if (fd == -1) {
    ret = AVB_IO_RESULT_ERROR_NO_SUCH_PARTITION;
    goto out;
  }

  if (offset < 0) {
    uint64_t partition_size;
    if (ioctl(fd, BLKGETSIZE64, &partition_size) != 0) {
      avb_error("Error getting size of \"", partition, "\" partition.\n");
      ret = AVB_IO_RESULT_ERROR_IO;
      goto out;
    }
    offset = partition_size - (-offset);
  }

  where = lseek(fd, offset, SEEK_SET);
  if (where == -1) {
    avb_error("Error seeking to offset.\n");
    ret = AVB_IO_RESULT_ERROR_IO;
    goto out;
  }
  if (where != offset) {
    avb_error("Error seeking to offset.\n");
    ret = AVB_IO_RESULT_ERROR_RANGE_OUTSIDE_PARTITION;
    goto out;
  }

  /* On Linux, we never get partial reads from block devices (except
   * for EOF).
   */
  num_read = read(fd, buffer, num_bytes);
  if (num_read == -1) {
    avb_error("Error reading data.\n");
    ret = AVB_IO_RESULT_ERROR_IO;
    goto out;
  }
  if (out_num_read != NULL) {
    *out_num_read = num_read;
  }

  ret = AVB_IO_RESULT_OK;

out:
  if (fd != -1) {
    if (close(fd) != 0) {
      avb_error("Error closing file descriptor.\n");
    }
  }
  return ret;
}

static AvbIOResult write_to_partition(AvbOps* ops,
                                      const char* partition,
                                      int64_t offset,
                                      size_t num_bytes,
                                      const void* buffer) {
  int fd;
  off_t where;
  ssize_t num_written;
  AvbIOResult ret;

  fd = open_partition(partition, O_WRONLY);
  if (fd == -1) {
    avb_error("Error opening \"", partition, "\" partition.\n");
    ret = AVB_IO_RESULT_ERROR_IO;
    goto out;
  }

  where = lseek(fd, offset, SEEK_SET);
  if (where == -1) {
    avb_error("Error seeking to offset.\n");
    ret = AVB_IO_RESULT_ERROR_IO;
    goto out;
  }
  if (where != offset) {
    avb_error("Error seeking to offset.\n");
    ret = AVB_IO_RESULT_ERROR_RANGE_OUTSIDE_PARTITION;
    goto out;
  }

  /* On Linux, we never get partial writes on block devices. */
  num_written = write(fd, buffer, num_bytes);
  if (num_written == -1) {
    avb_error("Error writing data.\n");
    ret = AVB_IO_RESULT_ERROR_IO;
    goto out;
  }

  ret = AVB_IO_RESULT_OK;

out:
  if (fd != -1) {
    if (close(fd) != 0) {
      avb_error("Error closing file descriptor.\n");
    }
  }
  return ret;
}

static AvbIOResult validate_vbmeta_public_key(
    AvbOps* ops,
    const uint8_t* public_key_data,
    size_t public_key_length,
    const uint8_t* public_key_metadata,
    size_t public_key_metadata_length,
    bool* out_is_trusted) {
  if (out_is_trusted != NULL) {
    *out_is_trusted = true;
  }
  return AVB_IO_RESULT_OK;
}

static AvbIOResult read_rollback_index(AvbOps* ops,
                                       size_t rollback_index_location,
                                       uint64_t* out_rollback_index) {
  if (out_rollback_index != NULL) {
    *out_rollback_index = 0;
  }
  return AVB_IO_RESULT_OK;
}

static AvbIOResult write_rollback_index(AvbOps* ops,
                                        size_t rollback_index_location,
                                        uint64_t rollback_index) {
  return AVB_IO_RESULT_OK;
}

static AvbIOResult read_is_device_unlocked(AvbOps* ops, bool* out_is_unlocked) {
  if (out_is_unlocked != NULL) {
    *out_is_unlocked = true;
  }
  return AVB_IO_RESULT_OK;
}

static AvbIOResult get_size_of_partition(AvbOps* ops,
                                         const char* partition,
                                         uint64_t* out_size_in_bytes) {
  int fd;
  AvbIOResult ret;

  fd = open_partition(partition, O_RDONLY);
  if (fd == -1) {
    avb_error("Error opening \"", partition, "\" partition.\n");
    ret = AVB_IO_RESULT_ERROR_IO;
    goto out;
  }

  if (out_size_in_bytes != NULL) {
    if (ioctl(fd, BLKGETSIZE64, out_size_in_bytes) != 0) {
      avb_error("Error getting size of \"", partition, "\" partition.\n");
      ret = AVB_IO_RESULT_ERROR_IO;
      goto out;
    }
  }

  ret = AVB_IO_RESULT_OK;

out:
  if (fd != -1) {
    if (close(fd) != 0) {
      avb_error("Error closing file descriptor.\n");
    }
  }
  return ret;
}

static AvbIOResult get_unique_guid_for_partition(AvbOps* ops,
                                                 const char* partition,
                                                 char* guid_buf,
                                                 size_t guid_buf_size) {
  if (guid_buf != NULL && guid_buf_size > 0) {
    guid_buf[0] = '\0';
  }
  return AVB_IO_RESULT_OK;
}

AvbOps* avb_ops_user_new(void) {
  AvbOps* ops;

  ops = static_cast<AvbOps*>(calloc(1, sizeof(AvbOps)));
  if (ops == NULL) {
    avb_error("Error allocating memory for AvbOps.\n");
    goto out;
  }

  ops->ab_ops = static_cast<AvbABOps*>(calloc(1, sizeof(AvbABOps)));
  if (ops->ab_ops == NULL) {
    avb_error("Error allocating memory for AvbABOps.\n");
    free(ops);
    goto out;
  }
  ops->ab_ops->ops = ops;

  ops->read_from_partition = read_from_partition;
  ops->write_to_partition = write_to_partition;
  ops->validate_vbmeta_public_key = validate_vbmeta_public_key;
  ops->read_rollback_index = read_rollback_index;
  ops->write_rollback_index = write_rollback_index;
  ops->read_is_device_unlocked = read_is_device_unlocked;
  ops->get_unique_guid_for_partition = get_unique_guid_for_partition;
  ops->get_size_of_partition = get_size_of_partition;
  ops->ab_ops->read_ab_metadata = avb_ab_data_read;
  ops->ab_ops->write_ab_metadata = avb_ab_data_write;

out:
  return ops;
}

void avb_ops_user_free(AvbOps* ops) {
  free(ops->ab_ops);
  free(ops);
}
