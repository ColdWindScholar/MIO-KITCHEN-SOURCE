import sys

from .const import SQUASHFS_INVALID_BLK, SQUASHFS_INVALID_XATTR


def has_xattrs(file):
    # unsquashfs_xattr.c
    return (
        file.xattr != SQUASHFS_INVALID_XATTR
        and file.image.sblk.xattr_id_table_start != SQUASHFS_INVALID_BLK
    )


def write_xattr(pathname, file):
    # unsquashfs_xattr.c
    if sys.version_info < (3, 3) or sys.platform != "linux" or not has_xattrs(file):
        return
