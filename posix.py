import os
# Copyright (C) 2024 The MIO-KITCHEN-SOURCE Project
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
if os.name == 'nt':
    from ctypes.wintypes import LPCSTR, DWORD
    from stat import FILE_ATTRIBUTE_SYSTEM
    from ctypes import windll


def symlink(link_target, target):
    if os.name == 'posix':
        os.symlink(link_target, target)
    elif os.name == 'nt':
        with open(target.replace('/', os.sep), 'wb') as out:
            out.write(b'!<symlink>' + link_target.encode('utf-16') + b'\x00\x00')
            try:
                windll.kernel32.SetFileAttributesA(LPCSTR(target.encode()),
                                                   DWORD(FILE_ATTRIBUTE_SYSTEM))
            except Exception as e:
                print(str(e))


def readlink(path):
    if os.name == 'nt':
        if not os.path.isdir(path):
            with open(path, 'rb') as f:
                if f.read(10) == b'!<symlink>':
                    return f.read().decode("utf-16")[:-1]
                else:
                    return ''
    else:
        if os.path.islink(path):
            return os.readlink(path)
        else:
            return ''
    return ''
