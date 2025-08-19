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

#ifndef BOOTINFO_H_
#define BOOTINFO_H_

#include <stdbool.h>
#include <stdint.h>

typedef struct BrilloSlotInfo {
  uint8_t bootable : 1;
  uint8_t reserved[3];
} BrilloSlotInfo;

typedef struct BrilloBootInfo {
  // Used by fs_mgr. Must be NUL terminated.
  char bootctrl_suffix[4];

  // Magic for identification - must be 'B', 'C', 'c' (short for
  // "boot_control copy" implementation).
  uint8_t magic[3];

  // Version of BrilloBootInfo struct, must be 0 or larger.
  uint8_t version;

  // Currently active slot.
  uint8_t active_slot;

  // Information about each slot.
  BrilloSlotInfo slot_info[2];

  uint8_t reserved[15];
} BrilloBootInfo;

// Loading and saving BrillBootInfo instances.
bool boot_info_load(BrilloBootInfo* out_info);
bool boot_info_save(BrilloBootInfo* info);

// Returns non-zero if valid.
bool boot_info_validate(BrilloBootInfo* info);
void boot_info_reset(BrilloBootInfo* info);

// Opens partition by |name|, e.g. "misc" or "boot_a" with |flags|
// (e.g. O_RDONLY or O_RDWR) passed directly to open(2). Returns fd on
// success and -1 on error.
int boot_info_open_partition(const char* name, uint64_t* out_size, int flags);

#if defined(__GNUC__) && __GNUC__ >= 4 && __GNUC_MINOR__ >= 6
_Static_assert(sizeof(BrilloBootInfo) == 32, "BrilloBootInfo has wrong size");
#endif

#endif  // BOOTINFO_H
