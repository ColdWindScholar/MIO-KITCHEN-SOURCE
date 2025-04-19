#!/usr/bin/env python3
#------------------------
# Author: Kamenta
# Modified by ColdWindScholar
#------------------------
# pylint: disable=line-too-long, missing-class-docstring, missing-function-docstring
# Copyright (C) 2022-2025 The MIO-KITCHEN-SOURCE Project
#
# Licensed under the GNU AFFERO GENERAL PUBLIC LICENSE, Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.gnu.org/licenses/agpl-3.0.en.html#license-text
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging as logger
import os
import re
import struct
import threading
from ctypes import sizeof
from time import time
from zlib import crc32

from ext4 import (
    ext4_superblock, ext4_group_descriptor, Volume
)



class ResizeError(Exception):
    pass


class Ext4Resizer:
    def __init__(self, file_path):
        self.file_path = file_path
        self.vol = None
        self.stream = None
        self.original_size = 0
        self._lock = threading.RLock()

    def __enter__(self):
        if os.path.exists(self.file_path):
            self.stream = open(self.file_path, 'r+b')
            self.vol = Volume(self.stream)
            self.original_size = self.vol.get_block_count * self.vol.block_size
            return self
        else:
            raise ResizeError(f"NO Such File: {self.file_path}")

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.stream:
            self.stream.close()
            self.stream = None

    def read_data(self, offset, size):
        with self._stream_lock():
            self.stream.seek(offset)
            return self.stream.read(size)

    def write_data(self, offset, data):
        with self._stream_lock():
            self.stream.seek(offset)
            self.stream.write(data)
            self.stream.flush()

    def parse_size(self, size_str):
        match = re.match(r'^(\d+)([KMGT]?)$', size_str.upper())
        if not match:
            raise ResizeError(f"Invalid Size Format: {size_str}")

        value, unit = match.groups()
        value = int(value)

        if unit == 'K':
            bytes_count = value * 1024
        elif unit == 'M':
            bytes_count = value * 1024 * 1024
        elif unit == 'G':
            bytes_count = value * 1024 * 1024 * 1024
        elif unit == 'T':
            bytes_count = value * 1024 * 1024 * 1024 * 1024
        else:
            bytes_count = value * self.vol.block_size

        return bytes_count

    def calculate_new_fs_parameters(self, new_size_bytes):
        block_size = self.vol.block_size
        new_blocks_count = new_size_bytes // block_size

        blocks_per_group = self.vol.superblock.s_blocks_per_group
        groups_count = (new_blocks_count + blocks_per_group - 1) // blocks_per_group

        return new_blocks_count, groups_count

    def check_resize_constraints(self, new_blocks_count):
        min_blocks = self.vol.superblock.s_first_data_block + 100
        if new_blocks_count < min_blocks:
            raise ResizeError(f"Need {min_blocks} Blocks at least.")

        used_blocks = self.vol.get_block_count - self.vol.get_free_blocks_count
        if new_blocks_count < used_blocks:
            raise ResizeError(f"Block Count Must > Used {used_blocks} Blocks.")

        if self.vol.superblock.s_state != 1:
            logger.warning("Run Fsck First.")

        return True

    def update_superblock(self, new_blocks_count, groups_count):
        sb_data = self.read_data(0x400, sizeof(ext4_superblock))

        old_free_blocks = self.vol.get_free_blocks_count
        size_diff_blocks = new_blocks_count - self.vol.get_block_count
        new_free_blocks = old_free_blocks + size_diff_blocks

        new_sb = ext4_superblock.from_buffer_copy(sb_data)

        if self.vol.platform64:
            new_sb.s_blocks_count_lo = new_blocks_count & 0xFFFFFFFF
            new_sb.s_blocks_count_hi = (new_blocks_count >> 32) & 0xFFFFFFFF
        else:
            new_sb.s_blocks_count_lo = new_blocks_count

        if self.vol.platform64:
            new_sb.s_free_blocks_count_lo = new_free_blocks & 0xFFFFFFFF
            new_sb.s_free_blocks_count_hi = (new_free_blocks >> 32) & 0xFFFFFFFF
        else:
            new_sb.s_free_blocks_count_lo = new_free_blocks

        current_time = int(time())
        new_sb.s_wtime = current_time

        self._update_superblock_checksum(new_sb)

        self.write_data(0x400, bytes(new_sb))

        self.vol.superblock = new_sb

    def _update_superblock_checksum(self, sb):
        checksum = crc32(bytes(sb)) & 0xFFFFFFFF
        sb.s_checksum = checksum

    def update_block_group_descriptors(self, new_blocks_count, groups_count):
        blocks_per_group = self.vol.superblock.s_blocks_per_group
        old_groups_count = len(self.vol.group_descriptors)

        if groups_count < old_groups_count:
            self.vol.group_descriptors = self.vol.group_descriptors[:groups_count]

        elif groups_count > old_groups_count:
            template_gd = self.vol.group_descriptors[-1]

            for i in range(old_groups_count, groups_count):
                first_block_in_group = i * blocks_per_group

                if i == groups_count - 1:
                    blocks_in_last_group = new_blocks_count - first_block_in_group
                    free_blocks = blocks_in_last_group
                else:
                    free_blocks = blocks_per_group

                new_gd = ext4_group_descriptor()

                new_gd.bg_flags = template_gd.bg_flags

                bitmap_block = first_block_in_group + 1
                new_gd.bg_block_bitmap_lo = bitmap_block
                new_gd.bg_inode_bitmap_lo = bitmap_block + 1
                new_gd.bg_inode_table_lo = bitmap_block + 2

                new_gd.bg_free_blocks_count_lo = free_blocks - 3
                new_gd.bg_free_inodes_count_lo = self.vol.superblock.s_inodes_per_group
                new_gd.bg_used_dirs_count_lo = 0
                new_gd.bg_itable_unused_lo = self.vol.superblock.s_inodes_per_group

                self._update_group_descriptor_checksum(new_gd, i)

                self.vol.group_descriptors.append(new_gd)

                self._initialize_block_bitmap(i, new_blocks_count)
                self._initialize_inode_bitmap(i)

        last_group_idx = groups_count - 1
        last_group_first_block = last_group_idx * blocks_per_group
        blocks_in_last_group = new_blocks_count - last_group_first_block

        if blocks_in_last_group > blocks_per_group:
            blocks_in_last_group = blocks_per_group

        last_gd = self.vol.group_descriptors[last_group_idx]
        free_blocks_in_last_group = blocks_in_last_group - (blocks_per_group - last_gd.bg_free_blocks_count_lo)
        last_gd.bg_free_blocks_count_lo = free_blocks_in_last_group

        self._update_last_group_bitmap(last_group_idx, new_blocks_count)

        self._write_group_descriptors()

    def _initialize_block_bitmap(self, group_idx, new_blocks_count):
        blocks_per_group = self.vol.superblock.s_blocks_per_group

        first_block_in_group = group_idx * blocks_per_group

        block_bitmap_block = self.vol.group_descriptors[group_idx].bg_block_bitmap_lo
        inode_bitmap_block = self.vol.group_descriptors[group_idx].bg_inode_bitmap_lo
        inode_table_block = self.vol.group_descriptors[group_idx].bg_inode_table_lo

        if group_idx == len(self.vol.group_descriptors) - 1:
            blocks_in_group = new_blocks_count - first_block_in_group
        else:
            blocks_in_group = blocks_per_group

        bitmap_size = self.vol.block_size
        bitmap = bytearray(bitmap_size)

        used_blocks = [block_bitmap_block, inode_bitmap_block, inode_table_block]
        inode_table_size = (
                                       self.vol.superblock.s_inodes_per_group * self.vol.superblock.s_inode_size + self.vol.block_size - 1) // self.vol.block_size

        for i in range(inode_table_size):
            used_blocks.append(inode_table_block + i)

        for block in used_blocks:
            if first_block_in_group <= block < first_block_in_group + blocks_in_group:
                relative_block = block - first_block_in_group
                byte_index = relative_block // 8
                bit_index = relative_block % 8
                bitmap[byte_index] |= (1 << bit_index)

        bitmap_offset = block_bitmap_block * self.vol.block_size
        self.write_data(bitmap_offset, bitmap)

    def _initialize_inode_bitmap(self, group_idx):
        inode_bitmap_block = self.vol.group_descriptors[group_idx].bg_inode_bitmap_lo

        bitmap_size = self.vol.block_size
        bitmap = bytearray(bitmap_size)

        bitmap_offset = inode_bitmap_block * self.vol.block_size
        self.write_data(bitmap_offset, bitmap)

    def _update_last_group_bitmap(self, last_group_idx, new_blocks_count):
        blocks_per_group = self.vol.superblock.s_blocks_per_group

        first_block_in_group = last_group_idx * blocks_per_group

        blocks_in_last_group = new_blocks_count - first_block_in_group

        block_bitmap_block = self.vol.group_descriptors[last_group_idx].bg_block_bitmap_lo

        bitmap_offset = block_bitmap_block * self.vol.block_size
        current_bitmap = bytearray(self.read_data(bitmap_offset, self.vol.block_size))

        for i in range(blocks_in_last_group, blocks_per_group):
            byte_index = i // 8
            bit_index = i % 8
            if byte_index < len(current_bitmap):
                current_bitmap[byte_index] |= (1 << bit_index)

        self.write_data(bitmap_offset, current_bitmap)

    def _update_group_descriptor_checksum(self, gd, group_idx):
        gd.bg_checksum = crc32(bytes(gd) + struct.pack("<I", group_idx)) & 0xFFFF

    def _write_group_descriptors(self):
        group_desc_table_offset = (0x400 // self.vol.block_size + 1) * self.vol.block_size

        for group_idx, gd in enumerate(self.vol.group_descriptors):
            offset = group_desc_table_offset + group_idx * self.vol.superblock.s_desc_size
            self.write_data(offset, bytes(gd))

    def _stream_lock(self):
        class StreamLock:
            def __init__(self, lock):
                self.lock = lock

            def __enter__(self):
                self.lock.acquire()
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                self.lock.release()

        return StreamLock(self._lock)

    def physical_resize(self, new_size_bytes):
        if os.path.isfile(self.file_path):
            if self.stream:
                self.stream.close()
                self.stream = None

            if os.name == 'nt':
                with open(self.file_path, 'r+b') as f:
                    f.truncate(new_size_bytes)
            else:
                os.truncate(self.file_path, new_size_bytes)

            self.stream = open(self.file_path, 'r+b')
            self.vol = Volume(self.stream)
        else:
            print('Cannot adjust the size of block device,please use Linux utils')

    def resize(self, new_size):
        if isinstance(new_size, str):
            new_size_bytes = self.parse_size(new_size)
        else:
            new_size_bytes = new_size

        new_blocks_count, groups_count = self.calculate_new_fs_parameters(new_size_bytes)
        current_size_bytes = self.vol.get_block_count * self.vol.block_size
        used_blocks = self.vol.get_block_count - self.vol.get_free_blocks_count

        min_required_blocks = used_blocks + 100
        if new_blocks_count < min_required_blocks:
            raise ResizeError(f"Need {min_required_blocks} Block(s) at least.")

        self.check_resize_constraints(new_blocks_count)

        print(f"Total Size: {get_human_readable_size(current_size_bytes)} -> {get_human_readable_size(new_size_bytes)}")
        print(f"Total blocks: {self.vol.get_block_count} -> {new_blocks_count}")
        print(f"Used blocks: {used_blocks} -> {used_blocks}")
        print(f"Free blocks: {self.vol.get_free_blocks_count} -> {new_blocks_count - used_blocks}")

        if current_size_bytes == new_size_bytes:
            return True

        try:
            if new_size_bytes > current_size_bytes:
                self.physical_resize(new_size_bytes)

            self.update_superblock(new_blocks_count, groups_count)
            self.update_block_group_descriptors(new_blocks_count, groups_count)

            if new_size_bytes < current_size_bytes:
                self.physical_resize(new_size_bytes)
            return True
        except Exception as e:
            logger.error(f"Fail to adjust size: {str(e)}")
            raise


def get_human_readable_size(size_bytes):
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    size = size_bytes
    unit_index = 0

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    return f"{size:.2f} {units[unit_index]}"


def is_ext4_filesystem(file_path):
    try:
        with open(file_path, 'rb') as f:
            f.seek(0x400)
            superblock_data = f.read(1024)
            magic = int.from_bytes(superblock_data[0x38:0x3A], byteorder='little')
            return magic == 0xEF53
    except Exception:
        return False


def main(file_path, new_size):
    if not os.path.exists(file_path):
        logger.error(f"No Such File: {file_path}")
        return 1

    if not is_ext4_filesystem(file_path):
        logger.error(f"Invalid ext4 file:{file_path}")
        return 1
    try:
        with Ext4Resizer(file_path) as resizer:
            if not new_size:
                used_blocks = resizer.vol.get_block_count - resizer.vol.get_free_blocks_count
                buffer_blocks = max(int(used_blocks * 0.01), int(1024 * 1024 / resizer.vol.block_size))
                new_blocks = used_blocks + buffer_blocks
                new_size_bytes = new_blocks * resizer.vol.block_size
                print(f"Used Space: Add {buffer_blocks} Blocks Buffering.")
                resizer.resize(new_size_bytes)
            else:
                resizer.resize(new_size)
            return 0

    except (Exception, ResizeError):
        logger.exception('Resize')
        return 1

if __name__ == '__main__':
    import sys
    main(sys.argv[1], int(sys.argv[2]))