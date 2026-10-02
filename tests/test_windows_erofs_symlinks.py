import os
import shutil
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from src.core.posix import check_erofs_symlinks, repair_erofs_symlinks, symlink


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
            self.assertFalse(marker.exists())
            self.assertEqual(list(Path(temporary).iterdir()), [])

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

    def test_repairs_marker_without_changing_content_or_time(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / '配置'
            data = b'!<symlink>' + '/system/etc'.encode('utf-16') + b'\x00\x00'
            marker.write_bytes(data)
            before = marker.stat()

            self.assertEqual(repair_erofs_symlinks(temporary), 1)
            check_erofs_symlinks(temporary)
            self.assertEqual(marker.read_bytes(), data)
            self.assertEqual(marker.stat().st_mtime_ns, before.st_mtime_ns)
            self.assertTrue(marker.stat().st_file_attributes & 0x4)
            self.assertEqual(list(Path(temporary).iterdir()), [marker])

    def test_repairs_attribute_lost_by_copyfile(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            symlink('/system/etc', str(source))
            partition = root / 'partition'
            partition.mkdir()
            marker = partition / 'etc'
            shutil.copyfile(source, marker)
            self.assertFalse(marker.stat().st_file_attributes & 0x4)

            self.assertEqual(repair_erofs_symlinks(partition), 1)
            self.assertEqual(marker.read_bytes(), source.read_bytes())
            self.assertTrue(marker.stat().st_file_attributes & 0x4)
            self.assertTrue(source.stat().st_file_attributes & 0x4)

    def test_repair_detaches_hard_link_and_keeps_original_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            data = b'!<symlink>' + '/system/etc'.encode('utf-16') + b'\x00\x00'
            source.write_bytes(data)
            partition = root / 'partition'
            partition.mkdir()
            marker = partition / 'etc'
            os.link(source, marker)

            self.assertEqual(repair_erofs_symlinks(partition), 1)
            self.assertFalse(os.path.samefile(source, marker))
            self.assertEqual(source.read_bytes(), data)
            self.assertEqual(marker.read_bytes(), data)
            self.assertFalse(source.stat().st_file_attributes & 0x4)
            self.assertTrue(marker.stat().st_file_attributes & 0x4)

    def test_already_valid_marker_is_untouched(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / 'etc'
            symlink('/system/etc', str(marker))
            before = marker.stat()
            self.assertEqual(repair_erofs_symlinks(temporary), 0)
            self.assertEqual(marker.stat().st_ino, before.st_ino)

    def test_malformed_marker_is_rejected_without_repair(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / 'etc'
            marker.write_bytes(b'!<symlink>broken')
            with self.assertRaisesRegex(ValueError, 'Malformed Cygwin symlink marker'):
                repair_erofs_symlinks(temporary)
            self.assertFalse(marker.stat().st_file_attributes & 0x4)

    def test_repair_attribute_failure_keeps_shared_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            source.write_bytes(b'!<symlink>' + '/system/etc'.encode('utf-16') + b'\x00\x00')
            partition = root / 'partition'
            partition.mkdir()
            marker = partition / 'etc'
            os.link(source, marker)
            from src.core import posix
            with patch.object(posix, '_set_windows_attributes', side_effect=OSError('attribute failure')):
                with self.assertRaisesRegex(OSError, 'attribute failure'):
                    repair_erofs_symlinks(partition)
            self.assertTrue(os.path.samefile(source, marker))
            self.assertFalse(source.stat().st_file_attributes & 0x4)
            self.assertEqual(list(partition.iterdir()), [marker])

    def test_get_attributes_failure_is_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / 'etc'
            marker.write_bytes(b'!<symlink>' + '/system/etc'.encode('utf-16') + b'\x00\x00')
            api = SimpleNamespace(kernel32=SimpleNamespace(GetFileAttributesW=lambda *_: -1))
            with patch('src.core.posix.windll', api):
                with self.assertRaises(OSError):
                    repair_erofs_symlinks(temporary)
            self.assertFalse(marker.stat().st_file_attributes & 0x4)


if __name__ == '__main__':
    unittest.main()
