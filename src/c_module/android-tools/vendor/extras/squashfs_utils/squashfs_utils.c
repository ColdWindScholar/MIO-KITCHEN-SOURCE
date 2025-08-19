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

#include "squashfs_utils.h"

#include <cutils/fs.h>
#include <cutils/klog.h>
#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "squashfs_fs.h"

#ifdef SQUASHFS_NO_KLOG
#include <stdio.h>
#define ERROR(x...)   fprintf(stderr, x)
#else
#define ERROR(x...)   KLOG_ERROR("squashfs_utils", x)
#endif

size_t squashfs_get_sb_size()
{
    return sizeof(struct squashfs_super_block);
}

int squashfs_parse_sb_buffer(const void *buf, struct squashfs_info *info)
{
    const struct squashfs_super_block *sb =
        (const struct squashfs_super_block *)buf;

    if (sb->s_magic != SQUASHFS_MAGIC) {
        return -1;
    }

    info->block_size = sb->block_size;
    info->inodes = sb->inodes;
    info->bytes_used = sb->bytes_used;
    // by default mksquashfs pads the filesystem to 4K blocks
    info->bytes_used_4K_padded =
        sb->bytes_used + (4096 - (sb->bytes_used & (4096 - 1)));

    return 0;
}

int squashfs_parse_sb(const char *blk_device, struct squashfs_info *info)
{
    int ret = 0;
    struct squashfs_super_block sb;
    int data_device;

    data_device = TEMP_FAILURE_RETRY(open(blk_device, O_RDONLY | O_CLOEXEC));
    if (data_device == -1) {
        ERROR("Error opening block device (%s)\n", strerror(errno));
        return -1;
    }

    if (TEMP_FAILURE_RETRY(read(data_device, &sb, sizeof(sb)))
            != sizeof(sb)) {
        ERROR("Error reading superblock\n");
        ret = -1;
        goto cleanup;
    }

    if (squashfs_parse_sb_buffer(&sb, info) == -1) {
        ERROR("Not a valid squashfs filesystem\n");
        ret = -1;
        goto cleanup;
    }

cleanup:
    close(data_device);
    return ret;
}
