import posixpath
import sys
from collections import OrderedDict

from .const import Type


class File(object):  # Python 2
    """Abstract base class for files."""

    def __init__(self, image, inode, name, parent):
        self._image = image
        self._inode = inode
        self._name = name
        self._parent = parent

    def __str__(self):
        return self.name

    def __repr__(self):
        if sys.version_info >= (3, 3):
            return "{}({!r})".format(self.__class__.__qualname__, self.name)
        else:
            return "{}({!r})".format(self.__class__.__name__, self.name)

    def __lt__(self, other):
        if not isinstance(other, File):
            return NotImplemented
        return self._name < other._name

    def __le__(self, other):
        if not isinstance(other, File):
            return NotImplemented
        return self._name <= other._name

    @property
    def image(self):
        return self._image

    @property
    def inode(self):
        return self._inode

    @property
    def name(self):
        return self._name.decode()

    @property
    def parent(self):
        return self._parent

    @property
    def path(self):
        """Return the file's absolute path."""
        if self._parent is None:
            return '/'
        else:
            return posixpath.join(self._parent.path, self.name)

    @property
    def mode(self):
        return self._inode.mode

    @property
    def uid(self):
        return self._inode.uid

    @property
    def gid(self):
        return self._inode.gid

    @property
    def time(self):
        return self._inode.time

    @property
    def size(self):
        """Return the data attribute of this file's inode.
        - regular file: uncompressed file size in bytes
        - directory: uncompressed listing size in bytes
        - symlink: uncompressed target path size in bytes
        - device file: device number, major and minor
        - FIFO and socket should be 0
        """
        return self._inode.data

    @property
    def xattr(self):
        return self._inode.xattr

    @property
    def filemode(self):
        return self._inode.filemode

    @property
    def is_dir(self):
        return False

    @property
    def is_file(self):
        return False

    @property
    def is_symlink(self):
        return False

    @property
    def is_block_device(self):
        return False

    @property
    def is_char_device(self):
        return False

    @property
    def is_fifo(self):
        return False

    @property
    def is_socket(self):
        return False

    def _lselect(self, lpath, ofs):
        # print lpath,self.name,ofs
        if ofs >= len(lpath):
            return self
        return None


class Directory(File):

    def __init__(self, image, inode, name=b'', parent=None, children=None):
        super(Directory, self).__init__(image, inode, name, parent)  # Python 2
        # OrderedDict for Python 3.6 and lower compatibility.
        self._children = children if children is not None else OrderedDict()

    def __len__(self):
        return len(self._children)

    def __iter__(self):
        return self.iterdir()

    def __getitem__(self, key):
        return self._children[key]

    def __contains__(self, item):
        if isinstance(item, str):
            return item in self._children
        elif isinstance(item, File):
            return item in self._children.values()
        return False

    def __reversed__(self):
        for filename in reversed(self._children):
            yield self._children[filename]

    @property
    def is_dir(self):
        return True

    @property
    def children(self):
        return self._children

    def iterdir(self):
        for file in self._children.values():
            yield file

    def riter(self):
        """Iterate over this directory recursively."""
        yield self
        for file in self._children.values():
            if file.is_dir:
                for f in file.riter():
                    yield f
            else:
                yield file

    def find(self, filename):
        """Find the first file with this name in the subtree."""
        for file in self.riter():
            if file.name == filename:
                return file
        return None

    def select(self, path):
        if path == "/":
            path = ''
        lpath = path.split('/')
        start = self
        ofs = 0
        if not lpath[0]:
            ofs = 1
            while start.parent:
                start = start.parent
        if ofs >= len(lpath):
            return start
        for child_name, child in start.children.items():
            if child_name == lpath[ofs]:
                return child._lselect(lpath, ofs + 1)
        return None

    def _lselect(self, lpath, ofs):
        # print lpath,self.name,ofs
        if ofs >= len(lpath):
            return self
        for child_name, child in self._children.items():
            if child_name == lpath[ofs]:
                return child._lselect(lpath, ofs + 1)
        return None


class RegularFile(File):

    @property
    def is_file(self):
        return True

    def iter_bytes(self):
        return self._image.iter_file(self._inode)

    def read_bytes(self):
        return self._image.read_file(self._inode)

    def read_text(self, encoding="utf8", errors="strict"):
        return self.read_bytes().decode(encoding, errors)


class Symlink(File):

    @property
    def is_symlink(self):
        return True

    def readlink(self):
        return self._inode.symlink


class FIFO(File):

    @property
    def is_fifo(self):
        return True


class Socket(File):

    @property
    def is_socket(self):
        return True


class _Device(File):

    @property
    def major(self):
        return (self._inode.data & 0xFFF00) >> 8

    @property
    def minor(self):
        return (self._inode.data & 0xFF) | ((self._inode.data >> 12) & 0xFFF00)


class CharacterDevice(_Device):

    @property
    def is_char_device(self):
        return True


class BlockDevice(_Device):

    @property
    def is_block_device(self):
        return True


filetype = {
    Type.FILE: RegularFile,
    Type.DIR: Directory,
    Type.SYMLINK: Symlink,
    Type.FIFO: FIFO,
    Type.SOCKET: Socket,
    Type.BLKDEV: BlockDevice,
    Type.CHRDEV: CharacterDevice
}
