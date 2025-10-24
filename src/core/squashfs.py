from ctypes import LittleEndianStructure, sizeof, memmove, byref, string_at, addressof, c_uint32, c_uint16, c_uint64, \
    c_uint, c_ushort

try:
    from enum import IntEnum
except ImportError:
    IntEnum = int
magic = b'sqsh'
magic_swap = b'hsqs'


class BasicStruct(LittleEndianStructure):
    @property
    def _size(self):
        return sizeof(type(self))

    def __len__(self):
        return self._size

    def unpack(self, data: bytes):
        if len(data) < self._size:
            raise Exception("Input data size less than struct size.")
        if not isinstance(data, (bytes, bytearray)):
            raise Exception("Input data must be byte data or bytearray.")

        return memmove(byref(self), data, self._size)

    def pack(self):
        return string_at(addressof(self), sizeof(self))


class SuperblockFlags(IntEnum):
    UNCOMPRESSED_INODES = 0x0001
    UNCOMPRESSED_DATA = 0x0002
    CHECK = 0x0004
    UNCOMPRESSED_FRAGMENTS = 0x0008
    NO_FRAGMENTS = 0x0010
    ALWAYS_FRAGMENTS = 0x0020
    DUPLICATES = 0x0040
    EXPORTABLE = 0x0080
    UNCOMPRESSED_XATTRS = 0x0100
    NO_XATTRS = 0x0200
    COMPRESSOR_OPTIONS = 0x0400
    UNCOMPRESSED_IDS = 0x0800


class Compressor(IntEnum):
    GZIP = 1
    LZMA = 2
    LZO = 3
    XZ = 4
    LZ4 = 5
    ZSTD = 6


class DirHeader(BasicStruct):
    _fields_ = [
        ("count", c_uint),
        ("start_block", c_uint),
        ("inode_number", c_uint),
    ]


class SuperBlock(BasicStruct):
    _fields_ = [
        ("magic", c_uint),
        ("inode_count", c_uint),
        ("mod_time", c_uint),
        ("block_size", c_uint),
        ("frag_count", c_uint),
        ("compressor", c_ushort),
        ("block_log", c_ushort),
        ("flags", c_ushort),
        ("id_count", c_ushort),
        ("version_major", c_ushort),
        ("version_minor", c_ushort),
        ("root_inode", c_uint64),
        ("bytes_used", c_uint64),
        ("id_table", c_uint64),
        ("xattr_table", c_uint64),
        ("inode_table", c_uint64),
        ("dir_table", c_uint64),
        ("frag_table", c_uint64),
        ("export_table", c_uint64),
    ]


class InodeHeader(BasicStruct):
    _fields_ = [
        ("inode_type", c_uint16),
        ("permissions", c_uint16),
        ("uid_idx", c_uint16),
        ("gid_idx", c_uint16),
        ("modified_time", c_uint32),
        ("inode_number", c_uint32),
    ]



