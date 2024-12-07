# Copyright (C) 2024 The MIO-KITCHEN-SOURCE Project
#
# Licensed under theGNU AFFERO GENERAL PUBLIC LICENSE, Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.gnu.org/licenses/agpl-3.0.en.html#license-text
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os.path
import unittest

from .config_parser import ConfigParser
from .utils import *

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
        try:
            pys.remove(os.path.basename(__file__).split('.')[0])
        except ValueError:
            ...
        pys.append('tkinter')
        pys.append('tkinterdnd2')
        pys.remove('tool')
        if os.name != 'nt':
            pys.remove('sv_ttk_fixes')
            pys.remove('pycase')
        sys.path.append(prog_path)
        for i in pys:
            print(f'Importing {i}')
            __import__(i)

    def test_binaries(self):
        file_list = ['brotli', 'busybox', 'cpio', 'dtc', 'e2fsdroid', 'extract.erofs', 'extract.f2fs', 'img2simg',
                     'lpmake', 'magiskboot', 'make_ext4fs', 'mke2fs', 'mkfs.erofs', 'mkfs.f2fs', 'sload.f2fs', 'zstd']
        if platform.machine() != 'x86_64' or platform.system() != 'Linux':
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
