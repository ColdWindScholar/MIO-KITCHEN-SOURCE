import os

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
if os.name == 'nt':
    from ctypes.wintypes import LPCWSTR, DWORD
    from stat import FILE_ATTRIBUTE_SYSTEM
    from ctypes import WinError, windll


def symlink(link_target, target):
    if not os.path.exists(os.path.dirname(target)):
        os.makedirs(os.path.dirname(target), exist_ok=True)
    if os.name == 'posix':
        os.symlink(link_target, target)
    elif os.name == 'nt':
        with open(target.replace('/', os.sep), 'wb') as out:
            out.write(b'!<symlink>' + link_target.encode('utf-16') + b'\x00\x00')
        if not windll.kernel32.SetFileAttributesW(LPCWSTR(target), DWORD(FILE_ATTRIBUTE_SYSTEM)):
            raise WinError()


def check_erofs_symlinks(root):
    """Reject Cygwin link markers that mkfs.erofs would pack as regular files."""
    if os.name != 'nt':
        return
    if not os.path.isdir(root):
        raise FileNotFoundError(root)

    def fail_on_walk_error(error):
        raise error

    for folder, _, filenames in os.walk(root, onerror=fail_on_walk_error):
        for name in filenames:
            path = os.path.join(folder, name)
            if os.path.islink(path):
                continue
            with open(path, 'rb') as stream:
                if stream.read(10) != b'!<symlink>':
                    continue
            if not os.stat(path, follow_symlinks=False).st_file_attributes & FILE_ATTRIBUTE_SYSTEM:
                raise ValueError(f'Cygwin symlink marker is missing the Windows System attribute: {path}')


def readlink(path):
    if os.name == 'nt':
        if not os.path.isdir(path):
            with open(path, 'rb') as f:
                if f.read(10) == b'!<symlink>':
                    return f.read().decode("utf-16")[:-1]
                else:
                    return ''
        return ''
    else:
        return os.readlink(path)
