import stat
import sys
from ctypes import c_uint16, c_uint32, c_uint64

from ..const import SQUASHFS_INVALID_XATTR
from ..structure import _Base


class InodeHeader(_Base):
    _fields_ = [
        ("_inode_type", c_uint16),
        ("_mode", c_uint16),
        ("_uid", c_uint16),
        ("_guid", c_uint16),
        ("_mtime", c_uint32),
        ("_inode_number", c_uint32),
    ]

    @property
    def inode_type(self):
        return self._inode_type

    @property
    def mode(self):
        return self._mode

    @property
    def uid(self):
        """Index of the UID in the table."""
        return self._uid

    @property
    def guid(self):
        """Index of the GUID in the table."""
        return self._guid

    @property
    def mtime(self):
        return self._mtime

    @property
    def inode_number(self):
        return self._inode_number


class _BaseInode(_Base):

    _header = None
    _uid = None
    _gid = None
    _mode = None

    @property
    def header(self):
        return self._header

    @property
    def uid(self):
        return self._uid

    @property
    def gid(self):
        return self._gid

    @property
    def mode(self):
        return self._mode

    @property
    def type(self):
        return self._header.inode_type

    @property
    def time(self):
        return self._header.mtime

    @property
    def inode_number(self):
        return self._header.inode_number

    @property
    def data(self):
        return 0

    @property
    def xattr(self):
        return getattr(self, "_xattr", SQUASHFS_INVALID_XATTR)

    @property
    def filemode(self):
        if sys.version_info >= (3, 3):
            return stat.filemode(self._mode)
        ret = ['-'] * 10

        if self.is_socket:
            ret[0] = 's'
        if self.is_symlink:
            ret[0] = 'l'
        if self.is_block_device:
            ret[0] = 'b'
        if self.is_dir:
            ret[0] = 'd'
        if self.is_char_device:
            ret[0] = 'c'
        if self.is_fifo:
            ret[0] = 'p'

        if (self._mode & stat.S_IRUSR) == stat.S_IRUSR:
            ret[1] = 'r'
        if (self._mode & stat.S_IWUSR) == stat.S_IWUSR:
            ret[2] = 'w'
        if (self._mode & stat.S_IRGRP) == stat.S_IRGRP:
            ret[4] = 'r'
        if (self._mode & stat.S_IWGRP) == stat.S_IWGRP:
            ret[5] = 'w'
        if (self._mode & stat.S_IROTH) == stat.S_IROTH:
            ret[7] = 'r'
        if (self._mode & stat.S_IWOTH) == stat.S_IWOTH:
            ret[8] = 'w'

        if (self._mode & stat.S_IXUSR) == stat.S_IXUSR:
            ret[3] = 'x'
            if (self._mode & stat.S_ISUID) == stat.S_ISUID:
                ret[3] = 's'
        if (self._mode & stat.S_IXGRP) == stat.S_IXGRP:
            ret[6] = 'x'
            if (self._mode & stat.S_ISGID) == stat.S_ISGID:
                ret[6] = 's'
        if (self._mode & stat.S_IXOTH) == stat.S_IXOTH:
            ret[9] = 'x'

        return ''.join(ret)

    @property
    def is_dir(self):
        return stat.S_ISDIR(self._mode)

    @property
    def is_file(self):
        return stat.S_ISREG(self._mode)

    @property
    def is_symlink(self):
        return stat.S_ISLNK(self._mode)

    @property
    def is_block_device(self):
        return stat.S_ISBLK(self._mode)

    @property
    def is_char_device(self):
        return stat.S_ISCHR(self._mode)

    @property
    def is_fifo(self):
        return stat.S_ISFIFO(self._mode)

    @property
    def is_socket(self):
        return stat.S_ISSOCK(self._mode)


class _DirectoryInodeCommon:

    @property
    def start_block(self):
        return self._start_block

    @property
    def nlink(self):
        return self._nlink

    @property
    def file_size(self):
        return self._file_size

    @property
    def offset(self):
        return self._offset

    @property
    def parent_inode(self):
        return self._parent_inode

    # These fields are either shortcuts or filled in read_inode().

    @property
    def data(self):
        return self.file_size

    @property
    def start(self):
        return self.start_block


class DirectoryInode(_DirectoryInodeCommon, _BaseInode):
    _fields_ = [
        ("_start_block", c_uint32),
        ("_nlink", c_uint32),
        ("_file_size", c_uint16),
        ("_offset", c_uint16),
        ("_parent_inode", c_uint32),
    ]


class ExtendedDirectoryInode(_DirectoryInodeCommon, _BaseInode):
    _fields_ = [
        ("_nlink", c_uint32),
        ("_file_size", c_uint32),
        ("_start_block", c_uint32),
        ("_parent_inode", c_uint32),
        ("_i_count", c_uint16),
        ("_offset", c_uint16),
        ("_xattr", c_uint32),
    ]
    _index = None  # Not used anywhere for now.

    @property
    def i_count(self):
        return self._i_count

    @property
    def index(self):
        return self._index


class _RegularFileInodeCommon:

    _block_list = None
    _frag_bytes = None
    _blocks = None
    _block_start = None
    _block_offset = None
    _sparse = 0

    @property
    def start_block(self):
        return self._start_block

    @property
    def fragment(self):
        return self._fragment

    @property
    def offset(self):
        return self._offset

    @property
    def file_size(self):
        return self._file_size

    @property
    def block_list(self):
        return self._block_list

    # These fields are either shortcuts or filled in read_inode().

    @property
    def data(self):
        return self.file_size

    @property
    def frag_bytes(self):
        return self._frag_bytes

    @property
    def blocks(self):
        return self._blocks

    @property
    def start(self):
        return self.start_block

    @property
    def block_start(self):
        return self._block_start

    @property
    def block_offset(self):
        return self._block_offset

    @property
    def sparse(self):
        return self._sparse


class RegularFileInode(_RegularFileInodeCommon, _BaseInode):
    _fields_ = [
        ("_start_block", c_uint32),
        ("_fragment", c_uint32),
        ("_offset", c_uint32),
        ("_file_size", c_uint32),
    ]


class ExtendedRegularFileInode(_RegularFileInodeCommon, _BaseInode):
    _fields_ = [
        ("_start_block", c_uint64),
        ("_file_size", c_uint64),
        ("_sparse", c_uint64),
        ("_nlink", c_uint32),
        ("_fragment", c_uint32),
        ("_offset", c_uint32),
        ("_xattr", c_uint32),
    ]

    @property
    def sparse(self):
        return self._sparse != 0

    @property
    def nlink(self):
        return self._nlink


class SymlinkInode(_BaseInode):
    _fields_ = [
        ("_nlink", c_uint32),
        ("_symlink_size", c_uint32),
    ]
    _symlink = None

    @property
    def nlink(self):
        return self._nlink

    @property
    def symlink_size(self):
        return self._symlink_size

    @property
    def symlink(self):
        return self._symlink.decode()

    # These fields are either shortcuts or filled in read_inode().

    @property
    def data(self):
        return self.symlink_size


class ExtendedSymlinkInode(SymlinkInode):
    pass


class _DeviceInode(_BaseInode):
    _fields_ = [
        ("_nlink", c_uint32),
        ("_rdev", c_uint32),
    ]

    @property
    def nlink(self):
        return self._nlink

    @property
    def rdev(self):
        return self._rdev

    # These fields are either shortcuts or filled in read_inode().

    @property
    def data(self):
        return self.rdev


class _ExtendedDeviceInode(_DeviceInode):
    _fields_ = [
        ("_xattr", c_uint32),
    ]


class BlockDeviceInode(_DeviceInode):
    pass


class ExtendedBlockDeviceInode(_ExtendedDeviceInode):
    pass


class CharacterDeviceInode(_DeviceInode):
    pass


class ExtendedCharacterDeviceInode(_ExtendedDeviceInode):
    pass


class _IPCInode(_BaseInode):
    _fields_ = [
        ("_nlink", c_uint32),
    ]

    @property
    def nlink(self):
        return self._nlink


class _ExtendedIPCInode(_IPCInode):
    _fields_ = [
        ("_xattr", c_uint32),
    ]


class FIFOInode(_IPCInode):
    pass


class ExtendedFIFOInode(_ExtendedIPCInode):
    pass


class SocketInode(_IPCInode):
    pass


class ExtendedSocketInode(_ExtendedIPCInode):
    pass


inomap = {
    1: DirectoryInode,
    2: RegularFileInode,
    3: SymlinkInode,
    4: BlockDeviceInode,
    5: CharacterDeviceInode,
    6: FIFOInode,
    7: SocketInode,
    8: ExtendedDirectoryInode,
    9: ExtendedRegularFileInode,
    10: ExtendedSymlinkInode,
    11: ExtendedBlockDeviceInode,
    12: ExtendedCharacterDeviceInode,
    13: ExtendedFIFOInode,
    14: ExtendedSocketInode,
}
