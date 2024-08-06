import os.path
import platform
import unittest
from utils import *
from config_parser import ConfigParser

if os.name == 'nt':
    prog_path = os.getcwd()
else:
    prog_path = os.path.normpath(os.path.abspath(os.path.dirname(sys.argv[0])))

tool_bin = os.path.join(prog_path, 'bin', platform.system(), platform.machine()) + os.sep
set_file = os.path.join(prog_path, "bin", "setting.ini")


class Test(unittest.TestCase):
    def setUp(self):
        print('\nStarting Test.')

    def test_import(self):
        pys = [i[:-3] for i in os.listdir(prog_path) if i.endswith('.py') and i != 'build.py']
        pys.remove(os.path.basename(__file__).split('.')[0])
        pys.append('tkinter')
        pys.remove('tool')
        sys.path.append(prog_path)
        for i in pys:
            print(f'Importing {i}')
            __import__(i)

    @unittest.skipIf(platform.system() == 'Darwin', "Macos Is Not Supported Complete!")
    def test_binaries(self):
        file_list = ['brotli', 'busybox', 'cpio', 'dtc', 'e2fsdroid', 'extract.erofs', 'extract.f2fs', 'img2simg',
                     'lpmake', 'magiskboot', 'make_ext4fs', 'mke2fs', 'mkfs.erofs', 'mkfs.f2fs', 'sload.f2fs', 'zstd']
        if platform.machine() != 'x86_64' or os.name == 'nt':
            file_list.remove('mkfs.f2fs')
            file_list.remove('extract.f2fs')
        if os.name == 'nt':
            file_list = [i + '.exe' for i in file_list]
            file_list.append('cygwin1.dll')
            file_list.append('mv.exe')
        for i in file_list:
            if not os.path.exists(os.path.join(tool_bin, i)):
                raise FileNotFoundError(f'{i} is missing!')

    def test_values_files(self):
        self.assertNotEqual(v_code(), v_code())
        self.assertIs(os.path.exists(set_file), True, 'Settings File Not Found!')
        self.assertIs(os.access(set_file, os.F_OK), True, 'Settings File IS Not Ok!')
        config = ConfigParser()
        config.read(set_file)
        self.assertIsNot(config.items('setting'), (None, None), 'The Setting Config Format Is Wrong!')
        self.assertIs(gettype(os.path.join(prog_path, 'bin', 'extra_flash.zip')), 'zip', 'The Extra Flash Tools Missing!')

    def tearDown(self):
        print('Test Done!')


if __name__ == '__main__':
    unittest.main()
else:
    test_main = unittest.main
