# pylint: disable=line-too-long, missing-class-docstring, missing-function-docstring
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
import os.path
from ctypes import sizeof, c_char, LittleEndianStructure, byref, memmove, string_at
from enum import Enum

from _ctypes import addressof
from toml import dump, load
from .posix import symlink, readlink

CPIO_TRAILER_NAME = "TRAILER!!!"
CPIO_FULL_PERMISSION = 0o7777


class CpioMagicFormat(Enum):
    New = b'070701'
    Crc = b'070702'
    # I'm Not Intend To Support Old Format.
    Old = b'070707'


class CpioModes(Enum):
    # File Types
    C_IRUSR = 0o000400
    C_IWUSR = 0o000200
    C_IXUSR = 0o000100
    C_IRGRP = 0o000040
    C_IWGRP = 0o000020
    C_IXGRP = 0o000010
    C_IROTH = 0o000004
    C_IWOTH = 0o000002
    C_IXOTH = 0o000001

    C_ISUID = 0o004000
    C_ISGID = 0o002000
    C_ISVTX = 0o001000

    C_ISBLK = 0o060000
    C_ISCHR = 0o020000
    C_ISDIR = 0o040000
    C_ISFIFO = 0o010000
    C_ISSOCK = 0o0140000
    C_ISLNK = 0o0120000
    C_ISCTG = 0o0110000
    C_ISREG = 0o0100000
    # All Types
    MaskAllTypes = C_ISBLK | C_ISCHR | C_ISDIR | C_ISFIFO | C_ISSOCK | C_ISLNK | C_ISCTG | C_ISREG


class BasicStruct(LittleEndianStructure):
    @property
    def _size(self):
        return sizeof(type(self))

    def __len__(self):
        return self._size

    def unpack(self, data: bytes):
        if len(data) < self._size:
            raise Exception("Input data size less than struct size.")
        if not isinstance(data, (bytes, bytearray)):
            raise Exception("Input data must be byte data or bytearray.")

        return memmove(byref(self), data, self._size)

    def pack(self):
        return string_at(addressof(self), sizeof(self))


class CpioHeader(BasicStruct):
    _packed_ = 1
    _fields_ = [
        ("c_magic", c_char * 6),
        ("c_ino", c_char * 8),
        ("c_mode", c_char * 8),
        ("c_uid", c_char * 8),
        ("c_gid", c_char * 8),
        ("c_nlink", c_char * 8),
        ("c_mtime", c_char * 8),
        ("c_filesize", c_char * 8),
        ("c_dev_maj", c_char * 8),
        ("c_dev_min", c_char * 8),
        ("c_rdev_maj", c_char * 8),
        ("c_rdev_min", c_char * 8),
        ("c_namesize", c_char * 8),
        ("c_chksum", c_char * 8),
    ]


# unsigned short = 2
def parser_c_mode(data: str) -> tuple[CpioModes, int]:
    # Parse C_Mode from str to int
    c_mode = int(data, 16)
    # Get File Type
    file_type = c_mode & CpioModes.MaskAllTypes.value
    # Get File Mode
    file_mode = c_mode & CPIO_FULL_PERMISSION
    return CpioModes(file_type), file_mode


def pack_c_mode(file_type: int, file_mode: int | str) -> str:
    if isinstance(file_mode, str):
        file_mode = int(file_mode, 8)
    return f"{file_mode | file_type:08x}"


def calc_crc(data):
    crc = sum(data)
    if crc >= 0xffffffff:
        crc = crc & 0xffffffff
    return crc


def extract(filename, outputdir, output_info, check_crc: bool = False):
    info = {}
    if not os.path.exists(outputdir):
        os.makedirs(outputdir, exist_ok=True)
    if not os.path.exists(filename):
        print("No Such File!")
        return 1
    with open(filename, 'rb') as f:
        while True:
            header = CpioHeader()
            header_size = len(header)
            header.unpack(f.read(header_size))
            namesize = int(header.c_namesize, 16)
            name_bytes_with_null = f.read(namesize)

            try:
                name = name_bytes_with_null[:-1].decode('utf-8')
            except UnicodeDecodeError:
                problematic_bytes = name_bytes_with_null[:-1]
                hex_representation = problematic_bytes.hex(' ')

                print("\n--- DECODING ERROR ---")
                print("Failed to decode a filename as UTF-8.")
                print(f"Problematic bytes in HEX format: {hex_representation}")
                print("Use an online converter to determine the correct encoding.")
                print("----------------------\n")

                raise

            if not name in info.keys():
                info[name] = {}
            # If In The End
            for i in ['c_ino', 'c_uid', 'c_gid', 'c_nlink', 'c_mtime', 'c_dev_maj', 'c_dev_min',
                      'c_rdev_maj', 'c_rdev_min']:
                # To Recover it, hex(data) to 8 bytes
                info[name][i] = int(getattr(header, i), 16)
            if name == CPIO_TRAILER_NAME:
                info[name]['c_mode'] = int(header.c_mode, 16)
                break
            file_type, file_mode = parser_c_mode(header.c_mode)
            info[name]['file_type'] = file_type.value
            # Repack just int(file_mode, 8)
            info[name]['file_mode'] = oct(file_mode)
            if (namesize + header_size) % 4:
                f.read(4 - ((namesize + header_size) % 4))
            file_size = int(header.c_filesize, 16)
            output_file = os.path.join(outputdir, name)
            if not os.path.exists(os.path.dirname(output_file)):
                os.makedirs(os.path.dirname(output_file))
            file_content = f.read(file_size)
            if (header.c_magic == CpioMagicFormat.Crc.value) and check_crc:
                print(f"CRC State:{calc_crc(file_content) == int(header.c_chksum.decode('utf-8'), 16)}")
            if file_type == CpioModes.C_ISREG:
                with open(output_file, 'wb') as o:
                    o.write(file_content)
            elif file_type == CpioModes.C_ISDIR:
                os.makedirs(output_file, exist_ok=True)
            elif file_type == CpioModes.C_ISLNK:
                symlink(file_content.decode('utf-8'), output_file)
            else:
                print(f"Unsupported Type:{file_type}")
            print(f"Extracted:{name}")
            if file_size % 4:
                f.read(4 - (file_size % 4))
        with open(output_info, 'w', encoding='utf-8', newline='\n') as con:
            dump(info, con)


def scan_dir(folder: str, return_trailer: bool = True):
    if os.name == 'nt':
        yield os.path.basename(folder).replace('\\', '')
    elif os.name == 'posix':
        yield os.path.basename(folder).replace('/', '')
    else:
        yield os.path.basename(folder)
    for root, dirs, files in os.walk(folder, topdown=True):
        for dir_ in dirs:
            yield os.path.join(root, dir_).replace(folder, '').replace('\\', '/')[1:]
        for file in files:
            yield os.path.join(root, file).replace(folder, '').replace('\\', '/')[1:]
    if return_trailer:
        yield CPIO_TRAILER_NAME


def repack(input_dir, config_file, output_file: str, magic_type: CpioMagicFormat = None):
    # Fixme:We not allow folder or file that using same inode.So may cause bugs.will fix.lol
    ino_sum = 0
    if not magic_type:
        magic_type = CpioMagicFormat.New.value
    with open(config_file, 'r', encoding='utf-8', newline='\n') as con:
        cpio_info = load(con)
    output_dirname = os.path.dirname(output_file)

    if not os.path.exists(output_dirname) and output_dirname:
        os.makedirs(output_dirname, exist_ok=True)

    with open(output_file, 'wb') as out:
        header = CpioHeader()
        for entry in scan_dir(input_dir):
            if entry in cpio_info.keys():
                value = cpio_info[entry]
            else:
                if not os.path.exists(os.path.join(input_dir, entry)):
                    continue
                if os.path.isdir(os.path.join(input_dir, entry)):
                    file_type = CpioModes.C_ISDIR.value
                    file_mode = '0o755'
                elif os.path.isfile(os.path.join(input_dir, entry)):
                    file_type = CpioModes.C_ISREG.value
                    file_mode = '0o644'
                elif readlink(os.path.join(input_dir, entry)):
                    file_type = CpioModes.C_ISLNK.value
                    file_mode = "0o777"
                value = {'file_type': file_type, 'file_mode': file_mode}
            ino_sum += 1
            ino_ran = max(value.get('c_ino', 0), ino_sum)
            if ino_ran == ino_sum:
                print(f"Warning: {entry}:{ino_ran} == {ino_sum}")
                ino_ran += 1
            is_file = False
            is_link = False
            print(f'adding: {entry}')
            header.c_magic = magic_type
            header.c_ino = f"{value.get('c_ino', ino_ran):08x}".encode('utf-8')
            if value.get('c_mode') is not None:
                header.c_mode = f"{value.get('c_mode'):08x}".encode('utf-8')
            else:
                header.c_mode = pack_c_mode(value.get('file_type'), value.get('file_mode')).encode('utf-8')
                is_mode = parser_c_mode(header.c_mode.decode('utf-8'))[0]
                is_file = is_mode == CpioModes.C_ISREG
                is_link = is_mode == CpioModes.C_ISLNK
            header.c_uid = f"{value.get('c_uid', 0):08x}".encode('utf-8')
            header.c_gid = f"{value.get('c_gid', 0):08x}".encode('utf-8')
            header.c_nlink = f"{value.get('c_nlink', 1):08x}".encode('utf-8')
            header.c_mtime = f"{value.get('c_mtime', 0):08x}".encode('utf-8')
            filesize = 0
            if is_file:
                filesize = os.path.getsize(os.path.join(input_dir, entry))
            if is_link:
                filesize = len(readlink(os.path.join(input_dir, entry)).encode('utf-8'))
            header.c_filesize = f"{filesize:08x}".encode(
                'utf-8')
            header.c_dev_maj = f"{value.get('c_dev_maj', 0):08x}".encode('utf-8')
            header.c_dev_min = f"{value.get('c_dev_min', 0):08x}".encode('utf-8')
            header.c_rdev_maj = f"{value.get('c_rdev_maj', 0):08x}".encode('utf-8')
            header.c_rdev_min = f"{value.get('c_rdev_min', 0):08x}".encode('utf-8')
            header.c_namesize = f"{len(entry.encode('utf-8')) + 1:08x}".encode('utf-8')
            header.c_chksum = f"{value.get('c_chksum', 0):08x}".encode('utf-8')
            out.write(header.pack())
            out.write(entry.encode('utf-8') + b'\x00')

            if (len(header) + len(entry.encode('utf-8')) + 1) % 4:
                out.write((4 - (len(header) + len(entry.encode('utf-8')) + 1) % 4) * b'\x00')
            if is_file:
                with open(os.path.join(input_dir, entry), 'rb') as f:
                    out.write(f.read())
                    if f.tell() % 4:
                        out.write(b'\x00' * (4 - f.tell() % 4))
            if is_link:
                content = readlink(os.path.join(input_dir, entry)).encode('utf-8')
                out.write(content)
                if len(content) % 4:
                    out.write(b'\x00' * (4 - len(content) % 4))
    print(f'{ino_sum} Inodes.')
