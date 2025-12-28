from ctypes import LittleEndianStructure, c_int16, c_uint16, c_uint32, c_uint64, sizeof

from ..const import Type


class _Base(LittleEndianStructure):

    def __iter__(self):
        # This allows calling dict() on instances of this class.
        for name, _ in self._fields_:
            name = name.lstrip('_')
            yield name, getattr(self, name)

    @classmethod
    def from_bytes(cls, bytes_, offset=0):
        return cls.from_buffer_copy(bytes_, offset)
    
    @classmethod
    def from_fd(cls, fd):
        return cls.from_bytes(fd.read(sizeof(cls)))


class Superblock(_Base):
    _fields_ = [
        ("_s_magic", c_uint32),
        ("_inodes", c_uint32),
        ("_mkfs_time", c_uint32),
        ("_block_size", c_uint32),
        ("_fragments", c_uint32),
        ("_compression", c_uint16),
        ("_block_log", c_uint16),
        ("_flags", c_uint16),
        ("_no_ids", c_uint16),
        ("_s_major", c_uint16),
        ("_s_minor", c_uint16),
        ("_root_inode", c_uint64),
        ("_bytes_used", c_uint64),
        ("_id_table_start", c_uint64),
        ("_xattr_id_table_start", c_uint64),
        ("_inode_table_start", c_uint64),
        ("_directory_table_start", c_uint64),
        ("_fragment_table_start", c_uint64),
        ("_lookup_table_start", c_uint64)
    ]

    @property
    def s_magic(self):
        return self._s_magic
    
    @property
    def inodes(self):
        return self._inodes
    
    @property
    def mkfs_time(self):
        return self._mkfs_time
    
    @property
    def block_size(self):
        return self._block_size
    
    @property
    def fragments(self):
        return self._fragments
    
    @property
    def compression(self):
        return self._compression
    
    @property
    def block_log(self):
        return self._block_log
    
    @property
    def flags(self):
        return self._flags
    
    @property
    def no_ids(self):
        return self._no_ids
    
    @property
    def s_major(self):
        return self._s_major
    
    @property
    def s_minor(self):
        return self._s_minor
    
    @property
    def root_inode(self):
        return self._root_inode
    
    @property
    def bytes_used(self):
        return self._bytes_used
    
    @property
    def id_table_start(self):
        return self._id_table_start
    
    @property
    def xattr_id_table_start(self):
        return self._xattr_id_table_start
    
    @property
    def inode_table_start(self):
        return self._inode_table_start
    
    @property
    def directory_table_start(self):
        return self._directory_table_start
    
    @property
    def fragment_table_start(self):
        return self._fragment_table_start
    
    @property
    def lookup_table_start(self):
        return self._lookup_table_start


class DirEntry(_Base):
    _fields_ = [
        ("_offset", c_uint16),
        ("_inode_number", c_int16),
        ("_type", c_uint16),
        ("_size", c_uint16),
    ]
    _name = None

    @property
    def offset(self):
        return self._offset

    @property
    def inode_number(self):
        return self._inode_number

    @property
    def type(self):
        return Type(self._type)

    @property
    def size(self):
        return self._size

    @property
    def name(self):
        return self._name.decode()


class DirHeader(_Base):
    _fields_ = [
        ("_count", c_uint32),
        ("_start_block", c_uint32),
        ("_inode_number", c_uint32),
    ]

    @property
    def count(self):
        return self._count

    @property
    def start_block(self):
        return self._start_block

    @property
    def inode_number(self):
        return self._inode_number


class FragmentEntry(_Base):
    _fields_ = [
        ("_start_block", c_uint64),
        ("_size", c_uint32),
        ("_unused", c_uint32)
    ]
    
    @property
    def start_block(self):
        return self._start_block
    
    @property
    def size(self):
        return self._size
    
    @property
    def unused(self):
        return self._unused


class XattrId(_Base):
    _fields_ = [
        ("_xattr", c_uint64),
        ("_count", c_uint32),
        ("_size", c_uint32)
    ]
    
    @property
    def xattr(self):
        return self._xattr
    
    @property
    def count(self):
        return self._count
    
    @property
    def size(self):
        return self._size


class XattrTable(_Base):
    _fields_ = [
        ("_xattr_table_start", c_uint64),
        ("_xattr_ids", c_uint32),
        ("_unused", c_uint32)
    ]

    @property
    def xattr_table_start(self):
        return self._xattr_table_start
    
    @property
    def xattr_ids(self):
        return self._xattr_ids
    
    @property
    def unused(self):
        return self._unused
