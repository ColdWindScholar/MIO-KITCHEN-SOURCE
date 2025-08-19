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

#ifndef _SQUASHFS_UTILS_H_
#define _SQUASHFS_UTILS_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

struct squashfs_info {
    uint32_t block_size;
    uint32_t inodes;
    uint64_t bytes_used;
    uint64_t bytes_used_4K_padded;
};

size_t squashfs_get_sb_size();
int squashfs_parse_sb_buffer(const void *data, struct squashfs_info *info);
int squashfs_parse_sb(const char *blk_device, struct squashfs_info *info);

#ifdef __cplusplus
}
#endif

#endif
