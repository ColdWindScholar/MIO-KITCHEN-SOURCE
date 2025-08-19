/*
 * Copyright (C) 2015 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include <fcntl.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <sys/types.h>
#include <unistd.h>

#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#include <fs_mgr.h>
#include <hardware/boot_control.h>
#include <hardware/hardware.h>

#include "bootinfo.h"

void module_init(boot_control_module_t* module) {}

unsigned module_getNumberSlots(boot_control_module_t* module) {
  return 2;
}

static bool get_dev_t_for_partition(const char* name, dev_t* out_device) {
  int fd;
  struct stat statbuf;

  fd = boot_info_open_partition(name, NULL, O_RDONLY);
  if (fd == -1) return false;
  if (fstat(fd, &statbuf) != 0) {
    fprintf(stderr, "WARNING: Error getting information about part %s: %s\n", name,
            strerror(errno));
    close(fd);
    return false;
  }
  close(fd);
  *out_device = statbuf.st_rdev;
  return true;
}

unsigned module_getCurrentSlot(boot_control_module_t* module) {
  struct stat statbuf;
  dev_t system_a_dev, system_b_dev;

  if (stat("/system", &statbuf) != 0) {
    fprintf(stderr, "WARNING: Error getting information about /system: %s\n", strerror(errno));
    return 0;
  }

  if (!get_dev_t_for_partition("system_a", &system_a_dev) ||
      !get_dev_t_for_partition("system_b", &system_b_dev))
    return 0;

  if (statbuf.st_dev == system_a_dev) {
    return 0;
  } else if (statbuf.st_dev == system_b_dev) {
    return 1;
  } else {
    fprintf(stderr,
            "WARNING: Error determining current slot "
            "(/system dev_t of %d:%d does not match a=%d:%d or b=%d:%d)\n",
            major(statbuf.st_dev), minor(statbuf.st_dev), major(system_a_dev), minor(system_a_dev),
            major(system_b_dev), minor(system_b_dev));
    return 0;
  }
}

int module_markBootSuccessful(boot_control_module_t* module) {
  return 0;
}

#define COPY_BUF_SIZE (1024 * 1024)

static bool copy_data(int src_fd, int dst_fd, size_t num_bytes) {
  char copy_buf[COPY_BUF_SIZE];
  size_t remaining;

  remaining = num_bytes;
  while (remaining > 0) {
    size_t num_to_read = remaining > COPY_BUF_SIZE ? COPY_BUF_SIZE : remaining;
    ssize_t num_read;
    do {
      num_read = read(src_fd, copy_buf, num_to_read);
    } while (num_read == -1 && errno == EINTR);
    if (num_read <= 0) {
      fprintf(stderr, "Error reading %zd bytes from source: %s\n", num_to_read, strerror(errno));
      return false;
    }
    size_t num_to_write = num_read;
    while (num_to_write > 0) {
      size_t offset = num_read - num_to_write;
      ssize_t num_written;
      do {
        num_written = write(dst_fd, copy_buf + offset, num_to_write);
      } while (num_written == -1 && errno == EINTR);
      if (num_written <= 0) {
        fprintf(stderr, "Error writing %zd bytes to destination: %s\n", num_to_write,
                strerror(errno));
        return false;
      }
      num_to_write -= num_written;
    }
    remaining -= num_read;
  }

  return true;
}

int module_setActiveBootSlot(boot_control_module_t* module, unsigned slot) {
  BrilloBootInfo info;
  int src_fd, dst_fd;
  uint64_t src_size, dst_size;
  char src_name[32];

  if (slot >= 2) return -EINVAL;

  if (!boot_info_load(&info)) {
    fprintf(stderr, "WARNING: Error loading boot-info. Resetting.\n");
    boot_info_reset(&info);
  } else {
    if (!boot_info_validate(&info)) {
      fprintf(stderr, "WARNING: boot-info is invalid. Resetting.\n");
      boot_info_reset(&info);
    }
  }

  info.active_slot = slot;
  info.slot_info[slot].bootable = true;
  snprintf(info.bootctrl_suffix, sizeof(info.bootctrl_suffix), "_%c", slot + 'a');

  if (!boot_info_save(&info)) {
    fprintf(stderr, "Error saving boot-info.\n");
    return -errno;
  }

  // Finally copy the contents of boot_X into boot.
  snprintf(src_name, sizeof(src_name), "boot_%c", slot + 'a');
  src_fd = boot_info_open_partition(src_name, &src_size, O_RDONLY);
  if (src_fd == -1) {
    fprintf(stderr, "Error opening \"%s\" partition.\n", src_name);
    return -errno;
  }

  dst_fd = boot_info_open_partition("boot", &dst_size, O_RDWR);
  if (dst_fd == -1) {
    fprintf(stderr, "Error opening \"boot\" partition.\n");
    close(src_fd);
    return -errno;
  }

  if (src_size != dst_size) {
    fprintf(stderr,
            "src (%" PRIu64 " bytes) and dst (%" PRIu64
            " bytes) "
            "have different sizes.\n",
            src_size, dst_size);
    close(src_fd);
    close(dst_fd);
    return -EINVAL;
  }

  if (!copy_data(src_fd, dst_fd, src_size)) {
    close(src_fd);
    close(dst_fd);
    return -errno;
  }

  if (fsync(dst_fd) != 0) {
    fprintf(stderr, "Error calling fsync on destination: %s\n", strerror(errno));
    return -errno;
  }

  close(src_fd);
  close(dst_fd);
  return 0;
}

int module_setSlotAsUnbootable(struct boot_control_module* module, unsigned slot) {
  BrilloBootInfo info;

  if (slot >= 2) return -EINVAL;

  if (!boot_info_load(&info)) {
    fprintf(stderr, "WARNING: Error loading boot-info. Resetting.\n");
    boot_info_reset(&info);
  } else {
    if (!boot_info_validate(&info)) {
      fprintf(stderr, "WARNING: boot-info is invalid. Resetting.\n");
      boot_info_reset(&info);
    }
  }

  info.slot_info[slot].bootable = false;

  if (!boot_info_save(&info)) {
    fprintf(stderr, "Error saving boot-info.\n");
    return -errno;
  }

  return 0;
}

int module_isSlotBootable(struct boot_control_module* module, unsigned slot) {
  BrilloBootInfo info;

  if (slot >= 2) return -EINVAL;

  if (!boot_info_load(&info)) {
    fprintf(stderr, "WARNING: Error loading boot-info. Resetting.\n");
    boot_info_reset(&info);
  } else {
    if (!boot_info_validate(&info)) {
      fprintf(stderr, "WARNING: boot-info is invalid. Resetting.\n");
      boot_info_reset(&info);
    }
  }

  return info.slot_info[slot].bootable;
}

const char* module_getSuffix(boot_control_module_t* module, unsigned slot) {
  static const char* suffix[2] = {"_a", "_b"};
  if (slot >= 2) return NULL;
  return suffix[slot];
}

static struct hw_module_methods_t module_methods = {
    .open = NULL,
};

/* This boot_control HAL implementation emulates A/B by copying the
 * contents of the boot partition of the requested slot to the boot
 * partition. It hence works with bootloaders that are not yet aware
 * of A/B. This code is only intended to be used for development.
 */

boot_control_module_t HAL_MODULE_INFO_SYM = {
    .common =
        {
            .tag = HARDWARE_MODULE_TAG,
            .module_api_version = BOOT_CONTROL_MODULE_API_VERSION_0_1,
            .hal_api_version = HARDWARE_HAL_API_VERSION,
            .id = BOOT_CONTROL_HARDWARE_MODULE_ID,
            .name = "Copy Implementation of boot_control HAL",
            .author = "The Android Open Source Project",
            .methods = &module_methods,
        },
    .init = module_init,
    .getNumberSlots = module_getNumberSlots,
    .getCurrentSlot = module_getCurrentSlot,
    .markBootSuccessful = module_markBootSuccessful,
    .setActiveBootSlot = module_setActiveBootSlot,
    .setSlotAsUnbootable = module_setSlotAsUnbootable,
    .isSlotBootable = module_isSlotBootable,
    .getSuffix = module_getSuffix,
};
