from __future__ import print_function

import os
import sys
from contextlib import contextmanager
from errno import EEXIST, ENOENT, EPERM
from stat import S_IFBLK, S_IFCHR, S_IFIFO, S_IFSOCK, S_IWUSR

from .file import FIFO, BlockDevice, CharacterDevice, RegularFile, Socket, Symlink
from .macro import LOOKUP_INDEX, LOOKUP_OFFSET
from .xattr import has_xattrs, write_xattr

try:
    from os import geteuid
except ImportError:
    _root = False
else:
    _root = geteuid() == 0

try:
    from os import supports_follow_symlinks
except ImportError:
    supports_follow_symlinks = set()

try:
    from os import chown
except ImportError:
    def chown(path, uid, gid):
        pass

try:
    from os import lchown
except ImportError:
    def lchown(path, uid, gid):
        pass

try:
    from os import makedev
except ImportError:
    def makedev(major, minor):
        pass

try:
    from os import mknod
except ImportError:
    def mknod(path, mode=0o600, device=0):
        pass


def set_attributes(pathname, file, set_mode):
    # unsquashfs.c
    os.utime(pathname, (file.time, file.time))
    mode = file.mode
    if _root:
        chown(pathname, file.uid, file.gid)
    else:
        mode &= ~0o6000
    write_xattr(pathname, file)
    if set_mode or (mode & 0o7000):
        try:
            os.chmod(pathname, mode)
        except (IOError, OSError) as e:
            if _root or e.errno != EPERM or not (mode & 0o1000):
                raise
            else:
                os.chmod(pathname, mode & ~0o1000)


def _write_file(file, pathname):
    mode = file.mode
    if not _root and not (mode & S_IWUSR) and has_xattrs(file):
        mode |= S_IWUSR
    flags = os.O_CREAT | os.O_WRONLY
    if sys.platform == "win32":
        flags |= os.O_BINARY
    fd = os.open(pathname, flags, mode & 0o777)  # Use os.open() because umask
    try:
        for block in file.iter_bytes():
            os.write(fd, block)
    finally:
        os.close(fd)


@contextmanager
def appropriate_umask():
    if not _root:
        yield
        return
    old = os.umask(0)
    try:
        yield
    finally:
        os.umask(old)


def unlink(path):
    try:
        os.unlink(path)
    except Exception:
        pass


def write_file(file, pathname, force=False):
    # unsquashfs.c -> write_file
    try:
        os.lstat(pathname)
    except (IOError, OSError) as e:  # Should be FileNotFoundError (Python 2 compatibility)
        if e.errno != ENOENT:
            raise
    else:
        if force:
            os.unlink(pathname)  # Don't ignore errors here.
        elif sys.version_info >= (3, 3):
            raise FileExistsError("file already exists")
        else:
            raise OSError("file already exists")
    with appropriate_umask():
        _write_file(file, pathname)
    set_ = not _root and not (file.mode & S_IWUSR) and has_xattrs(file)
    set_attributes(pathname, file, force or set_)


def _lookup(lookup_table, number):
    # unsquash-34.c
    index = LOOKUP_INDEX(number - 1)
    offset = LOOKUP_OFFSET(number - 1)
    if lookup_table.get(index) is None:
        return None
    return lookup_table[index].get(offset)


def _insert_lookup(lookup_table, number, pathname):
    # unsquash-34.c
    index = LOOKUP_INDEX(number - 1)
    offset = LOOKUP_OFFSET(number - 1)
    if lookup_table.get(index) is None:
        lookup_table[index] = {}
    lookup_table[index][offset] = pathname


def _print(*args, **kwargs):
    if not kwargs.pop("quiet", False):
        print(*args, **kwargs)


def extract_file(file, dest=None, force=False, lookup_table=None, quiet=True):
    # unsquashfs.c -> create_inode
    dest = dest if dest else os.path.basename(file.path)
    _print("extract {} to {}".format(file.path, dest), quiet=quiet)
    lookup_table = lookup_table if lookup_table is not None else {}
    link_path = _lookup(lookup_table, file.inode.inode_number)
    if link_path is not None:
        if force:
            unlink(dest)
        if sys.version_info >= (3, 3) and os.link in supports_follow_symlinks:
            os.link(link_path, dest, follow_symlinks=False)
        return
    if isinstance(file, RegularFile):
        write_file(file, dest, force)
    elif isinstance(file, Symlink):
        if force:
            unlink(dest)
        try:
            os.symlink(file.readlink(), dest)
        except (OSError, AttributeError) as e:
            # Windows + Python < 3.2 -> AttributeError
            # Windows + unprivileged user + Developer Mode disabled -> OSError
            if isinstance(e, OSError) and not (hasattr(e, "winerror") and e.winerror == 1314):
                raise
            elif isinstance(e, AttributeError) and os.path.isfile(dest):
                raise OSError("file already exists")
            with open(dest, "wb") as f:
                f.write(file.inode._symlink)
            os.utime(dest, (file.time, file.time))
        if sys.version_info >= (3, 3) and os.utime in supports_follow_symlinks:
            os.utime(dest, (file.time, file.time), follow_symlinks=False)
        if _root:
            lchown(dest, file.uid, file.gid)
        write_xattr(dest, file)
    elif isinstance(file, (BlockDevice, CharacterDevice)):
        if _root:
            chrdev = isinstance(file, CharacterDevice)
            if force:
                unlink(dest)
            mknod(dest, S_IFCHR if chrdev else S_IFBLK, makedev(file.major, file.minor))
            set_attributes(dest, file, True)
        else:
            _print("WARNING: could not create block or character device because you are not root", quiet=quiet)
    elif isinstance(file, FIFO):
        if force:
            unlink(dest)
        mknod(dest, S_IFIFO, 0)
        set_attributes(dest, file, True)
    elif isinstance(file, Socket):
        mknod(dest, S_IFSOCK, 0)
        set_attributes(dest, file, True)
    else:
        raise Exception("unknown file type")
    _insert_lookup(lookup_table, file.inode.inode_number, dest)


def extract_dir(directory, dest="squashfs-root", force=False, lookup_table=None, quiet=True):
    _print("extract {} to {}".format(directory.path, dest), quiet=quiet)
    lookup_table = lookup_table if lookup_table is not None else {}
    try:
        os.mkdir(dest, 0o700)
    except (IOError, OSError) as e:  # Should be FileExistsError (Python 2 compatibility)
        if force and e.errno == EEXIST:
            os.chmod(dest, 0o700)
        else:
            raise
    for file in directory:
        path = os.path.join(dest, os.path.relpath(file.path, directory.path))
        if file.is_dir:
            extract_dir(file, path, force, lookup_table, quiet)
        else:
            extract_file(file, path, force, lookup_table, quiet)
    set_attributes(dest, directory, True)
