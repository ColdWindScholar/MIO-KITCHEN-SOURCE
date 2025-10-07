#!/usr/bin/env python3

import logging as logger
import os
import re
import struct
import threading
from ctypes import sizeof
from time import time

from ext4 import ext4_superblock, ext4_group_descriptor, Volume

CRC32C_POLY = 0x82F63B78
EXT4_FEATURE_RO_COMPAT_GDT_CSUM = 0x0010
EXT4_FEATURE_RO_COMPAT_METADATA_CSUM = 0x0400
EXT4_FEATURE_COMPAT_SPARSE_SUPER = 0x0001

_crc32c_table = None

def _init_crc32c_table():
    global _crc32c_table
    if _crc32c_table is not None:
        return
    
    _crc32c_table = []
    for i in range(256):
        crc = i
        for _ in range(8):
            crc = (crc >> 1) ^ CRC32C_POLY if crc & 1 else crc >> 1
        _crc32c_table.append(crc)

def crc32c(data, crc=0xFFFFFFFF):
    """Compute CRC32C checksum as required by ext4 metadata_csum feature"""
    if _crc32c_table is None:
        _init_crc32c_table()
    
    for byte in data:
        crc = _crc32c_table[(crc ^ byte) & 0xFF] ^ (crc >> 8)
    
    return crc ^ 0xFFFFFFFF


class ResizeError(Exception):
    pass


class Ext4Resizer:
    def __init__(self, file_path):
        self.file_path = file_path
        self.vol = None
        self.stream = None
        self.original_size = 0
        self._lock = threading.RLock()
        self._cached_params = {}

    def __enter__(self):
        if not os.path.exists(self.file_path):
            raise ResizeError(f"File not found: {self.file_path}")
        
        self.stream = open(self.file_path, 'r+b')
        self.vol = Volume(self.stream)
        self.original_size = self.vol.get_block_count * self.vol.block_size
        
        self._cache_common_params()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.stream:
            self.stream.close()
            self.stream = None
    
    def _cache_common_params(self):
        """Cache frequently accessed parameters to reduce repeated property access"""
        sb = self.vol.superblock
        self._cached_params = {
            'block_size': self.vol.block_size,
            'blocks_per_group': sb.s_blocks_per_group,
            'inodes_per_group': sb.s_inodes_per_group,
            'inode_size': sb.s_inode_size,
            'desc_size': sb.s_desc_size,
            'reserved_gdt_blocks': sb.s_reserved_gdt_blocks,
            'inode_table_blocks': (sb.s_inodes_per_group * sb.s_inode_size + self.vol.block_size - 1) // self.vol.block_size,
        }

    def read_data(self, offset, size):
        with self._lock:
            self.stream.seek(offset)
            return self.stream.read(size)

    def write_data(self, offset, data):
        with self._lock:
            self.stream.seek(offset)
            self.stream.write(data)
            self.stream.flush()

    def parse_size(self, size_str):
        """Parse size string like '100M', '2G', or '1000' (blocks)"""
        match = re.match(r'^(\d+)([KMGT]?)$', size_str.upper())
        if not match:
            raise ResizeError(f"Invalid size format: {size_str}")

        value = int(match.group(1))
        unit = match.group(2)
        
        multipliers = {'K': 1024, 'M': 1024**2, 'G': 1024**3, 'T': 1024**4}
        
        if unit:
            return value * multipliers[unit]
        else:
            return value * self._cached_params['block_size']

    def calculate_new_fs_parameters(self, new_size_bytes):
        block_size = self._cached_params['block_size']
        blocks_per_group = self._cached_params['blocks_per_group']
        new_blocks_count = new_size_bytes // block_size
        groups_count = (new_blocks_count + blocks_per_group - 1) // blocks_per_group
        return new_blocks_count, groups_count

    def check_resize_constraints(self, new_blocks_count):
        min_blocks = self.vol.superblock.s_first_data_block + 100
        if new_blocks_count < min_blocks:
            raise ResizeError(f"Minimum {min_blocks} blocks required")

        used_blocks = self.vol.get_block_count - self.vol.get_free_blocks_count
        if new_blocks_count < used_blocks:
            raise ResizeError(f"New size must accommodate {used_blocks} used blocks")

        if self.vol.superblock.s_state != 1:
            logger.warning("Filesystem not cleanly unmounted. Run fsck first.")
        
        return True

    def update_superblock(self, new_blocks_count, groups_count):
        """Update superblock: adjust block counts, timestamp, checksum; write primary + backups"""
        sb = ext4_superblock.from_buffer_copy(self.read_data(0x400, sizeof(ext4_superblock)))
        
        size_diff_blocks = new_blocks_count - self.vol.get_block_count
        new_free_blocks = self.vol.get_free_blocks_count + size_diff_blocks

        if self.vol.platform64:
            sb.s_blocks_count_lo = new_blocks_count & 0xFFFFFFFF
            sb.s_blocks_count_hi = (new_blocks_count >> 32) & 0xFFFFFFFF
            sb.s_free_blocks_count_lo = new_free_blocks & 0xFFFFFFFF
            sb.s_free_blocks_count_hi = (new_free_blocks >> 32) & 0xFFFFFFFF
        else:
            sb.s_blocks_count_lo = new_blocks_count
            sb.s_free_blocks_count_lo = new_free_blocks

        sb.s_wtime = int(time())
        self._update_superblock_checksum(sb)
        
        self.write_data(0x400, bytes(sb))
        self._write_superblock_backups(sb, groups_count)
        
        self.vol.superblock = sb
    
    def _write_superblock_backups(self, sb, groups_count):
        """Write superblock to backup locations (groups 0,1,3^n,5^n,7^n if sparse_super enabled)"""
        blocks_per_group = self._cached_params['blocks_per_group']
        block_size = self._cached_params['block_size']
        
        for group_idx in range(1, groups_count):
            if not self._group_has_super_backup(group_idx):
                continue
            
            sb_copy = ext4_superblock.from_buffer_copy(bytes(sb))
            sb_copy.s_block_group_nr = group_idx
            self._update_superblock_checksum(sb_copy)
            
            sb_offset = group_idx * blocks_per_group * block_size
            self.write_data(sb_offset, bytes(sb_copy))

    def _has_metadata_csum(self):
        return (self.vol.superblock.s_feature_ro_compat & EXT4_FEATURE_RO_COMPAT_METADATA_CSUM) != 0
    
    def _has_gdt_csum(self):
        return (self.vol.superblock.s_feature_ro_compat & EXT4_FEATURE_RO_COMPAT_GDT_CSUM) != 0
    
    def _update_superblock_checksum(self, sb):
        """Compute CRC32C checksum over entire superblock structure"""
        if not self._has_metadata_csum():
            sb.s_checksum = 0
            return
        
        sb.s_checksum = 0
        sb.s_checksum = crc32c(bytes(sb)) & 0xFFFFFFFF

    def update_block_group_descriptors(self, new_blocks_count, groups_count):
        """Add/remove groups; initialize bitmaps and inode tables; update checksums"""
        blocks_per_group = self._cached_params['blocks_per_group']
        old_groups_count = len(self.vol.group_descriptors)

        if groups_count < old_groups_count:
            self.vol.group_descriptors = self.vol.group_descriptors[:groups_count]
        elif groups_count > old_groups_count:
            self._add_new_groups(old_groups_count, groups_count, new_blocks_count)

        self._update_last_group_bitmap(groups_count - 1, new_blocks_count)
        self._update_group_descriptor_checksum(self.vol.group_descriptors[-1], groups_count - 1)
        self._write_group_descriptors()

    def _add_new_groups(self, start_idx, end_idx, new_blocks_count):
        """Create and initialize new block groups with proper metadata layout"""
        params = self._cached_params
        blocks_per_group = params['blocks_per_group']
        desc_size = params['desc_size']
        
        gdt_blocks = (end_idx * desc_size + params['block_size'] - 1) // params['block_size']
        inode_table_blocks = params['inode_table_blocks']

        for i in range(start_idx, end_idx):
            first_block = i * blocks_per_group
            blocks_in_group = min(blocks_per_group, new_blocks_count - first_block)

            metadata_offset = (1 + gdt_blocks + params['reserved_gdt_blocks']) if self._group_has_super_backup(i) else 0
            
            block_bitmap_block = first_block + metadata_offset
            inode_bitmap_block = block_bitmap_block + 1
            inode_table_block = inode_bitmap_block + 1
            
            metadata_blocks = metadata_offset + 2 + inode_table_blocks
            free_blocks = blocks_in_group - metadata_blocks

            gd = ext4_group_descriptor()
            
            if self.vol.platform64:
                gd.bg_block_bitmap_lo = block_bitmap_block & 0xFFFFFFFF
                gd.bg_block_bitmap_hi = (block_bitmap_block >> 32) & 0xFFFFFFFF
                gd.bg_inode_bitmap_lo = inode_bitmap_block & 0xFFFFFFFF
                gd.bg_inode_bitmap_hi = (inode_bitmap_block >> 32) & 0xFFFFFFFF
                gd.bg_inode_table_lo = inode_table_block & 0xFFFFFFFF
                gd.bg_inode_table_hi = (inode_table_block >> 32) & 0xFFFFFFFF
                gd.bg_free_blocks_count_lo = free_blocks & 0xFFFF
                gd.bg_free_blocks_count_hi = (free_blocks >> 16) & 0xFFFF
            else:
                gd.bg_block_bitmap_lo = block_bitmap_block
                gd.bg_inode_bitmap_lo = inode_bitmap_block
                gd.bg_inode_table_lo = inode_table_block
                gd.bg_free_blocks_count_lo = free_blocks

            gd.bg_free_inodes_count_lo = params['inodes_per_group']
            gd.bg_used_dirs_count_lo = 0
            gd.bg_itable_unused_lo = params['inodes_per_group']
            gd.bg_flags = 0
            gd.bg_exclude_bitmap_lo = 0

            self._update_group_descriptor_checksum(gd, i)
            self.vol.group_descriptors.append(gd)

            self._initialize_block_bitmap(i, new_blocks_count)
            self._initialize_inode_bitmap(i)
            self._initialize_inode_table(i)

    def _initialize_block_bitmap(self, group_idx, new_blocks_count):
        """Mark metadata blocks as used; mark out-of-range blocks as unavailable"""
        params = self._cached_params
        blocks_per_group = params['blocks_per_group']
        block_size = params['block_size']
        first_block = group_idx * blocks_per_group
        
        gd = self.vol.group_descriptors[group_idx]
        blocks_in_group = min(blocks_per_group, new_blocks_count - first_block)

        bitmap = bytearray(block_size)
        used_blocks = {gd.bg_block_bitmap, gd.bg_inode_bitmap}
        
        if self._group_has_super_backup(group_idx):
            desc_size = params['desc_size']
            gdt_blocks = (len(self.vol.group_descriptors) * desc_size + block_size - 1) // block_size
            
            used_blocks.add(first_block)
            used_blocks.update(range(first_block + 1, first_block + 1 + gdt_blocks + params['reserved_gdt_blocks']))
        
        inode_table_start = gd.bg_inode_table
        used_blocks.update(range(inode_table_start, inode_table_start + params['inode_table_blocks']))

        for block in used_blocks:
            if first_block <= block < first_block + blocks_in_group:
                rel_block = block - first_block
                bitmap[rel_block >> 3] |= (1 << (rel_block & 7))
        
        for i in range(blocks_in_group, blocks_per_group):
            bitmap[i >> 3] |= (1 << (i & 7))

        self.write_data(gd.bg_block_bitmap * block_size, bitmap)

    def _initialize_inode_bitmap(self, group_idx):
        """Mark all inodes as free; mark padding bits beyond inodes_per_group as used"""
        params = self._cached_params
        gd = self.vol.group_descriptors[group_idx]
        
        bitmap = bytearray(params['block_size'])
        
        inodes_per_group = params['inodes_per_group']
        for i in range(inodes_per_group, params['block_size'] * 8):
            bitmap[i >> 3] |= (1 << (i & 7))

        self.write_data(gd.bg_inode_bitmap * params['block_size'], bitmap)
    
    def _initialize_inode_table(self, group_idx):
        """Zero out inode table using efficient block-sized writes"""
        params = self._cached_params
        gd = self.vol.group_descriptors[group_idx]
        
        inode_table_bytes = params['inodes_per_group'] * params['inode_size']
        block_size = params['block_size']
        offset = gd.bg_inode_table * block_size
        
        zero_block = bytes(block_size)
        for i in range(0, inode_table_bytes, block_size):
            bytes_to_write = min(block_size, inode_table_bytes - i)
            self.write_data(offset + i, zero_block[:bytes_to_write])

    def _update_last_group_bitmap(self, last_group_idx, new_blocks_count):
        """Mark blocks beyond filesystem boundary as unavailable in last group's bitmap"""
        params = self._cached_params
        blocks_per_group = params['blocks_per_group']
        first_block = last_group_idx * blocks_per_group
        blocks_in_group = new_blocks_count - first_block

        gd = self.vol.group_descriptors[last_group_idx]
        bitmap_offset = gd.bg_block_bitmap * params['block_size']
        bitmap = bytearray(self.read_data(bitmap_offset, params['block_size']))

        for i in range(blocks_in_group, blocks_per_group):
            bitmap[i >> 3] |= (1 << (i & 7))

        self.write_data(bitmap_offset, bitmap)

    def _group_has_super_backup(self, group_idx):
        """Sparse_super: backups only in groups 0,1,3^n,5^n,7^n; otherwise all groups"""
        if group_idx == 0:
            return True
        
        if (self.vol.superblock.s_feature_ro_compat & EXT4_FEATURE_COMPAT_SPARSE_SUPER) == 0:
            return True
        
        if group_idx == 1:
            return True
        
        for base in (3, 5, 7):
            power = base
            while power <= group_idx:
                if power == group_idx:
                    return True
                power *= base
        
        return False
    
    def _update_group_descriptor_checksum(self, gd, group_idx):
        """Compute CRC32C over UUID + group_idx + descriptor bytes"""
        if not (self._has_gdt_csum() or self._has_metadata_csum()):
            gd.bg_checksum = 0
            return
        
        gd.bg_checksum = 0
        
        uuid = bytes(self.vol.superblock.s_uuid)
        group_bytes = struct.pack("<I", group_idx)
        gd_bytes = bytes(gd)
        
        checksum = crc32c(uuid)
        checksum = crc32c(group_bytes, checksum)
        checksum = crc32c(gd_bytes, checksum)
        gd.bg_checksum = checksum & 0xFFFF

    def _write_group_descriptors(self):
        """Write all group descriptors to primary location and all backup locations"""
        params = self._cached_params
        blocks_per_group = params['blocks_per_group']
        block_size = params['block_size']
        desc_size = params['desc_size']
        
        for backup_group_idx in range(len(self.vol.group_descriptors)):
            if not self._group_has_super_backup(backup_group_idx):
                continue
            
            if backup_group_idx == 0:
                gdt_start_block = (0x400 // block_size) + 1
            else:
                gdt_start_block = backup_group_idx * blocks_per_group + 1
            
            gdt_offset = gdt_start_block * block_size
            
            for group_idx, gd in enumerate(self.vol.group_descriptors):
                self.write_data(gdt_offset + group_idx * desc_size, bytes(gd))

    def physical_resize(self, new_size_bytes):
        """Truncate or extend the underlying file to new size; reopen volume"""
        if not os.path.isfile(self.file_path):
            print('Cannot resize block device; use Linux resize2fs')
            return
        
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
        self._cache_common_params()

    def resize(self, new_size):
        """Main resize operation: validate, grow file if needed, update metadata, shrink if needed"""
        new_size_bytes = self.parse_size(new_size) if isinstance(new_size, str) else new_size
        new_blocks_count, groups_count = self.calculate_new_fs_parameters(new_size_bytes)
        
        current_size_bytes = self.vol.get_block_count * self._cached_params['block_size']
        used_blocks = self.vol.get_block_count - self.vol.get_free_blocks_count

        min_required_blocks = used_blocks + 100
        if new_blocks_count < min_required_blocks:
            raise ResizeError(f"Minimum {min_required_blocks} blocks required for current data")

        self.check_resize_constraints(new_blocks_count)

        print(f"Size:   {_human_size(current_size_bytes)} -> {_human_size(new_size_bytes)}")
        print(f"Blocks: {self.vol.get_block_count} -> {new_blocks_count}")
        print(f"Used:   {used_blocks}")
        print(f"Free:   {self.vol.get_free_blocks_count} -> {new_blocks_count - used_blocks}")

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
            logger.error(f"Resize failed: {e}")
            raise


def _human_size(size_bytes):
    """Convert bytes to human-readable size"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} EB"


def is_ext4_filesystem(file_path):
    """Check if file contains valid ext4 magic number at superblock offset"""
    try:
        with open(file_path, 'rb') as f:
            f.seek(0x438)
            magic = int.from_bytes(f.read(2), byteorder='little')
            return magic == 0xEF53
    except Exception:
        return False


def main(file_path, new_size):
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return 1

    if not is_ext4_filesystem(file_path):
        logger.error(f"Not a valid ext4 filesystem: {file_path}")
        return 1
    
    try:
        with Ext4Resizer(file_path) as resizer:
            if not new_size:
                used_blocks = resizer.vol.get_block_count - resizer.vol.get_free_blocks_count
                buffer_blocks = max(int(used_blocks * 0.01), int(1024 * 1024 / resizer._cached_params['block_size']))
                new_size_bytes = (used_blocks + buffer_blocks) * resizer._cached_params['block_size']
                print(f"Auto-size: adding {buffer_blocks} block buffer (1% or 1MB minimum)")
                resizer.resize(new_size_bytes)
            else:
                resizer.resize(new_size)
            return 0

    except (Exception, ResizeError):
        logger.exception('Resize operation failed')
        return 1


if __name__ == '__main__':
    import sys
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else None)
