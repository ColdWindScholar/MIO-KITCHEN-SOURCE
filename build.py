#!/usr/bin/env python3
# pylint: disable=line-too-long
# Copyright (C) 2022-2025 The MIO-KITCHEN-SOURCE Project
#
# Licensed under the GNU AFFERO GENERAL PUBLIC LICENSE, Version 3.0 (the "License");
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
import os
import platform
import shutil
import subprocess
import sys
import zipfile
from platform import system

from pip._internal.cli.main import main as _main


class Builder:
    def __init__(self):
        ostype = system()
        try:
            from tkinter import END
        except:
            raise FileNotFoundError("Tkinter IS not exist!\nThe Build may not Work!")
        if ostype == 'Linux':
            name = 'MIO-KITCHEN-linux.zip'
        elif ostype == 'Darwin':
            if platform.machine() == 'x86_64':
                name = 'MIO-KITCHEN-macos-intel.zip'
            else:
                name = 'MIO-KITCHEN-macos.zip'
        else:
            name = 'MIO-KITCHEN-win.zip'
        self.name = name
        self.local = os.getcwd()
        self.ostype = ostype
        self.dndplat = None

    def build(self):
        print('Building...')
        self.install_package()
        self.unit_test()
        self.pyinstaller_build()
        self.config_folder()
        self.pack_zip(f'{self.local}/dist', self.name)

    def run_command(self,  command:list[str],strip:bool=False):
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            return result.stdout.strip() if strip else result.stdout
        except subprocess.CalledProcessError:
            return None

    def generate_release_body(self):
        print('Generating Release Body...')
        # load config
        with open('bin/setting.ini', 'r', encoding='utf-8') as f:
            ver = [line for line in f.readlines() if 'version' in line]
            ver = ver[0].strip().split(' = ')[1]
        with open('body.md', 'w', encoding='utf-8', newline='\n') as f:
            f.write(f"Build times: {os.getenv('GITHUB_RUN_NUMBER')}\n")
            f.write(f"Actor: {os.getenv('GITHUB_TRIGGERING_ACTOR')}\n")
            f.write(f"Repository: {os.getenv('GITHUB_REPOSITORY')}\n")
            f.write(f'Version: {ver}\n')
            f.write(f'```\n')
            f.write(f'Changelog:\n')
            head = self.run_command(['git', 'rev-parse', 'HEAD'], strip=True)
            f.write(self.run_command(['git', "log", "-1", "--pretty=%B", head]))
            f.write(f'```\n')

    def move_artifacts(self):
        with open('bin/setting.ini', 'r', encoding='utf-8') as f:
            ver = [line for line in f.readlines() if 'version' in line]
            ver = ver[0].strip().split(' = ')[1]
        for i in ['MIO-KITCHEN-win', 'MIO-KITCHEN-linux', 'MIO-KITCHEN-macos', 'MIO-KITCHEN-macos-intel']:
            name_list = i.rsplit('-')
            name_list.insert(2, ver)
            name = '-'.join(name_list)
            os.rename(f'{i}/{i}.zip', f'{name}.zip')

    def unit_test(self):
        from src.tool_tester import test_main, Test

        if Test:
            test_main(exit=False)

    def install_package(self):
        with open('requirements.txt', 'r', encoding='utf-8') as l:
            for i in l.read().split("\n"):
                print(f"Installing {i}")
                _main(['install', i])

    def pyinstaller_build(self):
        import PyInstaller.__main__
        dndplat = self.dndplat
        if self.ostype == 'Darwin':
            if platform.machine() == 'x86_64':
                dndplat = 'osx-x64'
            elif platform.machine() == 'arm64':
                dndplat = 'osx-arm64'
            PyInstaller.__main__.run([
                'tool.py',
                '-Fw',
                '--exclude-module',
                'numpy',
                '-i',
                'icon.ico',
                '--collect-data',
                'sv_ttk',
                '--collect-data',
                'chlorophyll',
                '--hidden-import',
                'tkinter',
                '--hidden-import',
                'PIL',
                '--hidden-import',
                'PIL._tkinter_finder'
            ])
        elif os.name == 'posix':
            if self.ostype == 'Linux':
                if platform.machine() == 'x86_64':
                    dndplat = 'linux-x64'
                elif platform.machine() == 'aarch64':
                    dndplat = 'linux-arm64'
                elif platform.machine() == 'loongarch64':
                    dndplat = 'linux-loongarch64'
            PyInstaller.__main__.run([
                'tool.py',
                '-Fw',
                '--exclude-module',
                'numpy',
                '-i',
                'icon.ico',
                '--collect-data',
                'sv_ttk',
                '--collect-data',
                'chlorophyll',
                '--hidden-import',
                'tkinter',
                '--hidden-import',
                'PIL',
                '--hidden-import',
                'PIL._tkinter_finder',
                '--splash',
                'splash_loongarch.png' if platform.machine() == 'loongarch64' else 'splash.png'
            ])
        elif os.name == 'nt':
            mach_ = platform.machine()
            platform.machine = lambda: 'x86' if platform.architecture()[0] == '32bit' and mach_ == 'AMD64' else mach_
            if platform.machine() == 'x86':
                dndplat = 'win-x86'
            elif platform.machine() == 'AMD64':
                dndplat = 'win-x64'
            elif platform.machine() == 'ARM64':
                dndplat = 'win-arm64'
            PyInstaller.__main__.run([
                'tool.py',
                '-Fw',
                '--exclude-module',
                'numpy',
                '-i',
                'icon.ico',
                '--collect-data',
                'sv_ttk',
                '--collect-data',
                'chlorophyll',
                '--splash',
                'splash.png'
            ])
        self.dndplat = dndplat

    def config_folder(self):
        if not os.path.exists('dist/bin'):
            os.makedirs('dist/bin', exist_ok=True)
        while_list = ['images', 'languages', 'licenses', 'module', 'temp', 'extra_flash', 'setting.ini', self.ostype,
                      'kemiaojiang.png', 'License_kemiaojiang.txt', "tkdnd", 'help_document.json', "exec.sh"]
        for i in os.listdir(self.local + "/bin"):
            if i in while_list:
                if os.path.isdir(f"{self.local}/bin/{i}"):
                    shutil.copytree(f"{self.local}/bin/{i}", f"{self.local}/dist/bin/{i}", dirs_exist_ok=True)
                else:
                    shutil.copy(f"{self.local}/bin/{i}", f"{self.local}/dist/bin/{i}")
        if not os.path.exists('dist/LICENSE'):
            shutil.copy(f'{self.local}/LICENSE', f"{self.local}/dist/LICENSE")
        if self.dndplat:
            for i in os.listdir(f"{self.local}/dist/bin/tkdnd"):
                if i[:3] == self.dndplat[:3] and i.endswith("x64") and self.dndplat.endswith('x86'):
                    continue
                if i == self.dndplat:
                    continue
                if os.path.isdir(f"{self.local}/dist/bin/tkdnd/{i}"):
                    shutil.rmtree(f'{self.local}/dist/bin/tkdnd/{i}', ignore_errors=True)
        else:
            raise FileNotFoundError("Cannot Build!!!TkinterDnd2 Missing!!!!!!!!!!")
        if os.name == 'posix':
            if platform.machine() == 'x86_64' and os.path.exists(f'{self.local}/dist/bin/Linux/aarch64'):
                try:
                    shutil.rmtree(f'{self.local}/dist/bin/Linux/aarch64')
                except Exception as e:
                    print(e)
            for root, dirs, files in os.walk(f'{self.local}/dist', topdown=True):
                for i in files:
                    print(f"Chmod {os.path.join(root, i)}")
                    os.chmod(os.path.join(root, i), 0o7777, follow_symlinks=False)

    def pack_zip(self, source, name):
        # 获取文件夹的绝对路径和文件夹名称
        abs_folder_path = os.path.abspath(source)
        # 创建一个同名的zip文件
        zip_file_path = os.path.join(self.local, name)
        with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as archive:
            # 遍历文件夹中的所有文件和子文件夹
            for root, _, files in os.walk(abs_folder_path):
                for file in files:
                    if file == name:
                        continue
                    file_path = os.path.join(root, file)
                    if ".git" in file_path:
                        continue
                    print(f"Adding: {file_path}")
                    # 将文件添加到zip文件中
                    archive.write(file_path, os.path.relpath(file_path, abs_folder_path))
        print("Pack Zip Done!")


if __name__ == '__main__':
    if len(sys.argv) == 1:
        builder = Builder()
        builder.build()
    else:
        # Generate Release Body
        if sys.argv[1] == 'grb':
            builder = Builder()
            builder.generate_release_body()
        elif sys.argv[1] == 'ma':
            builder = Builder()
            builder.move_artifacts()
        else:
            print('Usage:')
            print('To Build Binary and Pack')
            print('\tpython build.py')
            print('To Move artifacts to local folder')
            print('\tpython build.py ma')
            print('To Generate Release Body')
            print('\tpython build.py grb')

