# -*- coding: utf-8 -*-

"""
This module is released with the LGPL license.
Copyright 2011-2012

Matteo Mattei <matteo.mattei@gmail.com>
Nicola Ponzeveroni <nicola.ponzeveroni@gilbarco.com>

It is intended to be used to access files inside a Squashfs 4.0 little endian
image file.

Based on squashfs-tools by Phillip Lougher <phillip@squashfs.org.uk>

https://github.com/matteomattei/PySquashfsImage
https://github.com/plougher/squashfs-tools

"""
__all__ = ["SquashFsImage"]
__version__ = "0.9.0"

import io
import stat
import struct
import sys
from ctypes import sizeof
try:
    from functools import lru_cache
except ImportError:
    def lru_cache(maxsize=128, typed=False):
        return lambda user_function: user_function

from .compressor import compressors
from .const import (
    SQUASHFS_INVALID_BLK,
    SQUASHFS_INVALID_FRAG,
    SQUASHFS_METADATA_SIZE,
    Type,
)
from .file import Directory, filetype
from .macro import (
    SQUASHFS_CHECK_DATA,
    SQUASHFS_COMPRESSED,
    SQUASHFS_COMPRESSED_BLOCK,
    SQUASHFS_COMPRESSED_SIZE,
    SQUASHFS_COMPRESSED_SIZE_BLOCK,
    SQUASHFS_FRAGMENT_BYTES,
    SQUASHFS_FRAGMENT_INDEXES,
    SQUASHFS_ID_BLOCK_BYTES,
    SQUASHFS_ID_BLOCKS,
    SQUASHFS_ID_BYTES,
    SQUASHFS_INODE_BLK,
    SQUASHFS_INODE_OFFSET,
    SQUASHFS_XATTR_BLOCK_BYTES,
    SQUASHFS_XATTR_BLOCKS,
    SQUASHFS_XATTR_BYTES,
)
from .structure import DirEntry, DirHeader, FragmentEntry, Superblock, XattrId, XattrTable
from .structure.inode import InodeHeader, inomap
from .util import check_super


SQUASHFS_LOOKUP_TYPE = [
    0,
    stat.S_IFDIR,
    stat.S_IFREG,
    stat.S_IFLNK,
    stat.S_IFBLK,
    stat.S_IFCHR,
    stat.S_IFIFO,
    stat.S_IFSOCK,
    stat.S_IFDIR,
    stat.S_IFREG,
    stat.S_IFLNK,
    stat.S_IFBLK,
    stat.S_IFCHR,
    stat.S_IFIFO,
    stat.S_IFSOCK
]


class SquashFsImage(object):

    def __init__(self, fd, offset=0, closefd=True):
        self._fd = fd
        self._offset = offset
        self._closefd = closefd
        self._sblk = None
        self._root = None
        self._comp = None
        self._inode_table_hash = {}
        self._directory_table_hash = {}
        self._fragment_table = []
        self._id_table = {}
        self._hash_table = {}
        self._xattrs = b""
        self._initialize()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._closefd:
            self.close()

    def __iter__(self):
        return self._root.riter()

    @property
    def root(self):
        return self._root

    @property
    def sblk(self):
        return self._sblk

    @property
    def size(self):
        """Filesystem size in bytes."""
        return self._sblk.bytes_used

    @classmethod
    def from_bytes(cls, bytes_, offset=0):
        return cls(io.BytesIO(bytes_), offset)

    @classmethod
    def from_file(cls, path, offset=0):
        return cls(open(path, "rb"), offset)

    def close(self):
        self._fd.close()
        self._fd = None

    def _read_super(self):
        self._sblk = Superblock.from_fd(self._fd)
        if not check_super(self._sblk):
            raise IOError("The file supplied is not a squashfs 4.0 image")
        self._comp = self._get_compressor(self._sblk.compression)

    def _get_compressor(self, compression_id):
        if compression_id not in compressors:
            raise ValueError("Unknown compression method %r" % compression_id)
        return compressors[compression_id]()

    def _initialize(self):
        self._fd.seek(self._offset)
        self._read_super()
        self._read_uids_guids()
        self._read_fragment_table()
        self._read_xattrs_from_disk()
        root_block = SQUASHFS_INODE_BLK(self._sblk.root_inode)
        root_offs = SQUASHFS_INODE_OFFSET(self._sblk.root_inode)
        self._root = self._dir_scan(root_block, root_offs)

    @lru_cache(maxsize=256)
    def _read_data_block(self, start, size):
        c_byte = SQUASHFS_COMPRESSED_SIZE_BLOCK(size)
        self._fd.seek(self._offset + start)
        data = self._fd.read(c_byte)
        if SQUASHFS_COMPRESSED_BLOCK(size):
            return self._comp.uncompress(data, c_byte, self._sblk.block_size)
        else:
            return data

    def iter_file(self, inode):
        # unsquashfs.c -> write_file
        start = inode.start
        file_end = inode.data // self._sblk.block_size
        if inode.blocks:
            block_list = self._read_block_list(inode.block_start, inode.block_offset, inode.blocks)
            for i, block in enumerate(block_list):
                if block == SQUASHFS_INVALID_FRAG:
                    continue
                if block:  # non sparse file
                    yield self._read_data_block(start, block)
                    start += SQUASHFS_COMPRESSED_SIZE_BLOCK(block)
                else:
                    if i == file_end:
                        yield b'\x00' * (inode.data & (self._sblk.block_size - 1))
                    else:
                        yield b'\x00' * self._sblk.block_size
        if inode.frag_bytes:
            start, size = self._read_fragment(inode.fragment)
            buffer = self._read_data_block(start, size)
            yield buffer[inode.offset : inode.offset + inode.frag_bytes]

    def read_file(self, inode):
        return b''.join(self.iter_file(inode))

    def _read_block_list(self, start, offset, blocks):
        # unsquash-4.c
        size = 4  # sizeof(unsigned int)
        idata, _, _ = self._read_inode_data(start, offset, blocks * size)
        ret = []
        ofs = 0
        for _ in range(blocks):  # use struct.iter_unpack when Py3 only
            ret.append(self._make_buf_integer(idata, ofs, size))
            ofs += size
        return ret

    def _read_block(self, start, expected=SQUASHFS_METADATA_SIZE):
        """Read a block starting at offset `start` relative to the start of the image.

        Return the uncompressed block and the start of the next compressed one.
        """
        # unsquashfs.c
        self._fd.seek(self._offset + start)
        c_byte = self._read_short()
        offset = 3 if SQUASHFS_CHECK_DATA(self._sblk.flags) else 2
        self._fd.seek(self._offset + start + offset)
        size = SQUASHFS_COMPRESSED_SIZE(c_byte)
        block = self._fd.read(size)
        if SQUASHFS_COMPRESSED(c_byte):
            block = self._comp.uncompress(block, size, expected)
        return block, start + offset + size

    def _read_fragment_table(self):
        # unsquash-4.c
        bytes_ = SQUASHFS_FRAGMENT_BYTES(self._sblk.fragments)
        indexes = SQUASHFS_FRAGMENT_INDEXES(self._sblk.fragments)
        if self._sblk.fragments == 0:
            return
        self._fd.seek(self._offset + self._sblk.fragment_table_start)
        fragment_table_index = [self._read_long() for _ in range(indexes)]
        table = b''
        for i, index in enumerate(fragment_table_index):
            if (i + 1) != indexes:
                expected = SQUASHFS_METADATA_SIZE
            else:
                expected = bytes_ & (SQUASHFS_METADATA_SIZE - 1)
            table += self._read_block(index, expected)[0]
        ofs = 0
        while ofs < len(table):
            entry = FragmentEntry.from_bytes(table, ofs)
            ofs += sizeof(FragmentEntry)
            self._fragment_table.append(entry)

    def _read_fragment(self, fragment):
        # unsquash-4.c
        entry = self._fragment_table[fragment]
        return (entry.start_block, entry.size)

    def _read_inode(self, start_block, offset):
        # unsquash-4.c
        start = self._sblk.inode_table_start + start_block
        idata, start, offset = self._read_inode_data(start, offset, sizeof(InodeHeader))
        header = InodeHeader.from_bytes(idata)
        cls = inomap[header.inode_type]
        idata, start, offset = self._read_inode_data(start, offset, sizeof(cls))
        ino = cls.from_bytes(idata)
        ino._header = header
        ino._uid = self._id_table[header.uid]
        ino._gid = self._id_table[header.guid]
        ino._mode = SQUASHFS_LOOKUP_TYPE[header.inode_type] | header.mode
        try:
            inode_type = Type(header.inode_type)
        except ValueError:
            raise RuntimeError("Unknown inode type %d in read_inode!\n" % header.inode_type)
        if inode_type in (Type.FILE, Type.LREG):
            ino._block_start = start
            ino._block_offset = offset
            if ino.fragment == SQUASHFS_INVALID_FRAG:
                ino._frag_bytes = 0
                ino._blocks = (ino.data + self._sblk.block_size - 1) >> self._sblk.block_log
            else:
                ino._frag_bytes = ino.file_size % self._sblk.block_size
                ino._blocks = ino.data >> self._sblk.block_log
        elif inode_type in (Type.SYMLINK, Type.LSYMLINK):
            idata, start, offset = self._read_inode_data(start, offset, ino.symlink_size)
            ino._symlink = idata
            if inode_type == Type.LSYMLINK:
                idata, start, offset = self._read_inode_data(start, offset, 4)
                ino._xattr = self._make_buf_integer(idata, 0, len(idata))
        return ino

    def _opendir(self, block_start, offset):
        # unsquash-4.c -> squashfs_opendir
        inode = self._read_inode(block_start, offset)
        directory = Directory(self, inode)
        directory.entries = []
        if inode.data == 3:
            return directory
        start = self._sblk.directory_table_start + inode.start
        offset = inode.offset
        size = inode.data - 3
        bytes_ = 0
        while bytes_ < size:
            ddata, start, offset = self._read_directory_data(start, offset, sizeof(DirHeader))
            dirh = DirHeader.from_bytes(ddata)
            bytes_ += sizeof(DirHeader)
            for _ in range(dirh.count + 1):
                ddata, start, offset = self._read_directory_data(start, offset, sizeof(DirEntry))
                dire = DirEntry.from_bytes(ddata)
                namelen = dire.size + 1
                ddata, start, offset = self._read_directory_data(start, offset, namelen)
                dire._name = ddata
                bytes_ += sizeof(DirEntry) + namelen
                directory.entries.append({
                    "name": dire._name,
                    "start_block": dirh.start_block,
                    "offset": dire.offset,
                    "type": dire.type
                })
        return directory

    def _read_uids_guids(self):
        size = 4
        bytes_ = SQUASHFS_ID_BYTES(self._sblk.no_ids)
        indexes = SQUASHFS_ID_BLOCKS(self._sblk.no_ids)
        id_index_table = []
        self._fd.seek(self._offset + self._sblk.id_table_start)
        for _ in range(indexes):
            id_index_table.append(self._make_integer(SQUASHFS_ID_BLOCK_BYTES(1)))
        for i, idx in enumerate(id_index_table):
            if (i + 1) != indexes:
                expected = SQUASHFS_METADATA_SIZE
            else:
                expected = bytes_ & (SQUASHFS_METADATA_SIZE - 1)
            block = self._read_block(idx, expected)[0]
            offset = 0
            index = i * (SQUASHFS_METADATA_SIZE // 4)
            while offset < len(block):
                self._id_table[index] = self._make_buf_integer(block, offset, size)
                offset += size
                index += 1

    def _read_xattrs_from_disk(self):
        # read_xattrs.c
        if self._sblk.xattr_id_table_start == SQUASHFS_INVALID_BLK:
            return SQUASHFS_INVALID_BLK
        self._fd.seek(self._offset + self._sblk.xattr_id_table_start)
        id_table = XattrTable.from_fd(self._fd)
        ids = id_table.xattr_ids
        xattr_table_start = id_table.xattr_table_start
        indexes = SQUASHFS_XATTR_BLOCKS(ids)
        index = []
        for _ in range(indexes):
            index.append(self._make_integer(SQUASHFS_XATTR_BLOCK_BYTES(1)))
        bytes_ = SQUASHFS_XATTR_BYTES(ids)
        xattr_ids = {}
        for i, idx in enumerate(index):
            if (i + 1) != indexes:
                expected = SQUASHFS_METADATA_SIZE
            else:
                expected = bytes_ & (SQUASHFS_METADATA_SIZE - 1)
            block = self._read_block(idx, expected)[0]
            cur_idx = (i * SQUASHFS_METADATA_SIZE) / 16
            ofs = 0
            while ofs < len(block):
                xattr_ids[cur_idx] = XattrId.from_bytes(block, ofs)
                cur_idx += 1
                ofs += sizeof(XattrId)
        start = xattr_table_start
        i = 0
        while start < index[0]:
            self._hash_table[start] = i * SQUASHFS_METADATA_SIZE
            block, start = self._read_block(start)
            for i in range(len(block), SQUASHFS_METADATA_SIZE):
                block += b'\x00'
            self._xattrs += block
            i += 1
        return ids

    def _dir_scan(self, start_block, offset):
        directory = self._opendir(start_block, offset)
        for entry in directory.entries:  # No need for squashfs_readdir()
            start_block = entry["start_block"]
            offset = entry["offset"]
            if entry["type"] == Type.DIR:
                subdir = self._dir_scan(start_block, offset)
                subdir._parent = directory
                subdir._name = entry["name"]
                directory.children[subdir.name] = subdir
            else:
                inode = self._read_inode(start_block, offset)
                cls = filetype[entry["type"]]
                file = cls(self, inode, entry["name"], directory)
                directory.children[file.name] = file
        del directory.entries
        return directory

    def _make_integer(self, length):
        """Assemble multibyte integer."""
        return self._make_buf_integer(self._fd.read(length), 0, length)

    def _make_buf_integer(self, buf, start, length):
        """Assemble multibyte integer."""
        if sys.version_info < (3, 2):
            ret = 0
            pwr = 1
            for i in range(start, start + length):
                ret += (ord(buf[i]) & 0xFF) * pwr
                pwr *= 0x100
            return ret
        else:
            return int.from_bytes(buf[start : start + length], byteorder='little')

    def _read_integer(self, fmt):
        return struct.unpack(fmt, self._fd.read(struct.calcsize(fmt)))[0]

    def _read_short(self):
        return self._read_integer("<H")

    def _read_long(self):
        return self._read_integer("<Q")

    def _get_metadata(self, hash_table, start):
        try:
            return hash_table[start]
        except KeyError:
            hash_table[start] = dict(zip(("buffer", "next_index"), self._read_block(start)))
            return hash_table[start]

    def _read_metadata(self, hash_table, block, offset, length):
        data = b''
        while True:
            entry = self._get_metadata(hash_table, block)
            copy = len(entry["buffer"]) - offset
            if copy < length:
                data += entry["buffer"][offset:]
                length -= copy
                block = entry["next_index"]
                offset = 0
            elif copy == length:
                data += entry["buffer"][offset : offset + length]
                return data, entry["next_index"], 0
            else:
                data += entry["buffer"][offset : offset + length]
                return data, block, offset + length

    def _read_inode_data(self, block, offset, length):
        return self._read_metadata(self._inode_table_hash, block, offset, length)

    def _read_directory_data(self, block, offset, length):
        return self._read_metadata(self._directory_table_hash, block, offset, length)

    def find(self, filename):
        return self._root.find(filename)

    def select(self, path):
        return self._root.select(path)
