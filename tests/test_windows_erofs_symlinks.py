import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from src.core.posix import check_erofs_symlinks, symlink


@unittest.skipUnless(os.name == 'nt', 'Cygwin marker behavior is Windows-specific')
class WindowsErofsSymlinkTests(unittest.TestCase):
    def test_rejects_marker_without_system_attribute(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'ordinary').write_bytes(b'ordinary file')
            marker = root / 'etc'
            marker.write_bytes(b'!<symlink>' + '/system/etc'.encode('utf-16') + b'\x00\x00')

            with self.assertRaisesRegex(ValueError, 'missing the Windows System attribute'):
                check_erofs_symlinks(root)

    def test_created_unicode_marker_is_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'ordinary').write_bytes(b'ordinary file')
            marker = root / '配置'
            symlink('/system/etc', str(marker))

            check_erofs_symlinks(root)
            self.assertTrue(marker.stat().st_file_attributes & 0x4)

    def test_missing_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(FileNotFoundError):
                check_erofs_symlinks(Path(temporary) / 'missing')

    def test_attribute_failure_is_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / 'etc'
            api = SimpleNamespace(kernel32=SimpleNamespace(SetFileAttributesW=lambda *_: 0))
            with patch('src.core.posix.windll', api):
                with self.assertRaises(OSError):
                    symlink('/system/etc', str(marker))

    def test_rejection_does_not_modify_shared_marker(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'original'
            source.write_bytes(b'!<symlink>' + '/system/etc'.encode('utf-16') + b'\x00\x00')
            folder = root / 'partition'
            folder.mkdir()
            marker = folder / 'etc'
            os.link(source, marker)
            before = source.read_bytes()

            with self.assertRaises(ValueError):
                check_erofs_symlinks(folder)
            self.assertEqual(source.read_bytes(), before)
            self.assertTrue(os.path.samefile(source, marker))
            self.assertFalse(source.stat().st_file_attributes & 0x4)


if __name__ == '__main__':
    unittest.main()
