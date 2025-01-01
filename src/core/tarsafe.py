"""
tarsafe module is a more secure drop-in replacement for tarfile module.

We expose everything tarfile does, but some methods are overridden to add
safety features.
"""

import os
import tarfile
from pathlib import Path
from tarfile import *  # noqa: F401, F403


__all__ = tarfile.__all__ + [
    "TarSafe",
    "TarSafeException",
]


class TarSafe(tarfile.TarFile):
    """
    A safe subclass of the TarFile class for interacting with tar files.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.directory = os.getcwd()

    @classmethod
    def open(cls, name=None, mode="r", fileobj=None, bufsize=tarfile.RECORDSIZE, **kwargs):
        return super().open(name, mode, fileobj, bufsize, **kwargs)

    def extract(self, member, path="", set_attrs=True, *, numeric_owner=False):
        """
        Override the parent extract method and add safety checks.
        """
        self._safetar_check()
        super().extract(member, path, set_attrs=set_attrs, numeric_owner=numeric_owner)

    def extractall(self, path=".", members=None, *, numeric_owner=False):
        """
        Override the parent extractall method and add safety checks.
        """
        self._safetar_check()
        super().extractall(path, members, numeric_owner=numeric_owner)

    def _safetar_check(self):
        """
        Runs all necessary checks for the safety of a tarfile.
        """
        try:
            for tarinfo in self.__iter__():
                if self._is_traversal_attempt(tarinfo=tarinfo):
                    raise TarSafeException(f"Attempted directory traversal for member: {tarinfo.name}")
                if self._is_unsafe_symlink(tarinfo=tarinfo):
                    raise TarSafeException(f"Attempted directory traversal via symlink for member: {tarinfo.linkname}")
                if self._is_unsafe_link(tarinfo=tarinfo):
                    raise TarSafeException(f"Attempted directory traversal via link for member: {tarinfo.linkname}")
                if self._is_device(tarinfo=tarinfo):
                    raise TarSafeException(f"tarfile returns true for isblk() or ischr()")
        except Exception:
            raise

    def _is_traversal_attempt(self, tarinfo):
        # Adding this additional simple qualifier that the path seems suspect in order to avoid expensive
        # path normalization when testing deeply nested archives
        if tarinfo.name.startswith(os.sep) or ".." in tarinfo.name:
            if not os.path.abspath(os.path.join(self.directory, tarinfo.name)).startswith(self.directory):
                return True
        return False

    def _is_unsafe_symlink(self, tarinfo):
        if tarinfo.issym():
            symlink_file = Path(os.path.normpath(os.path.join(self.directory, tarinfo.linkname)))
            if not os.path.abspath(os.path.join(self.directory, symlink_file)).startswith(self.directory):
                return True
        return False

    def _is_unsafe_link(self, tarinfo):
        if tarinfo.islnk():
            link_file = Path(os.path.normpath(os.path.join(self.directory, tarinfo.linkname)))
            if not os.path.abspath(os.path.join(self.directory, link_file)).startswith(self.directory):
                return True
        return False

    def _is_device(self, tarinfo):
        return tarinfo.ischr() or tarinfo.isblk()


class TarSafeException(Exception):
    pass


class TarFile(TarSafe):
    """Override of tarfile.TarFile to maintain compatibility."""


open = TarSafe.open
