import io
from functools import partial

from .const import SQUASHFS_MAGIC, Compression
from .structure import Superblock


try:
    MAGIC_BYTES = SQUASHFS_MAGIC.to_bytes(4, "little")
except AttributeError:
    MAGIC_BYTES = b'hsqs'  # Python 2


def check_super(sblk):
    if sblk.s_magic != SQUASHFS_MAGIC or sblk.s_major != 4 or sblk.s_minor != 0:
        return False
    if not min(Compression) <= sblk.compression <= max(Compression):
        return False
    return True


def _find_superblocks(stream, size=1024**2):
    stream.seek(0)
    indexes = set()
    result = []
    prev_block = b''
    for count, next_block in enumerate(iter(partial(stream.read, size), b'')):
        # We don't want to "cut" in the middle of a magic.
        block = prev_block + next_block
        index = block.find(MAGIC_BYTES)
        if index != -1:
            indexes.add(index + (count * size) - len(prev_block))
        prev_block = next_block[-(len(MAGIC_BYTES) - 1) :]
    for index in sorted(indexes):
        stream.seek(index)
        sblk = Superblock.from_fd(stream)
        if check_super(sblk):
            result.append(dict(sblk, offset=index))
    return result


def find_superblocks(file_or_bytes, size=1024**2):
    """Return a list of dictionaries representing the
    superblocks found in the file with their offset.
    """
    if hasattr(file_or_bytes, "read"):
        return _find_superblocks(file_or_bytes, size)
    try:
        with open(file_or_bytes, "rb") as f:
            return _find_superblocks(f, size)
    except (IOError, OSError, TypeError, UnicodeDecodeError):
        # TypeError and IOError: Python 2 only
        # UnicodeDecodeError: Python 3 only, when argument is file as bytes
        pass
    try:
        return _find_superblocks(io.BytesIO(file_or_bytes), size)
    except TypeError:
        pass
    raise Exception("file not found or wrong type")  # TODO: Python 3 from None
