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
from ctypes import LittleEndianStructure, sizeof, memmove, string_at, addressof, byref, c_char, \
    c_uint32, c_uint16


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


HeaderMagic = b"RSCE"
EntryMagic = b"ENTR"


class Header(BasicStruct):
    _fields_ = [
        ("magic", c_char * 4),
        ("RSCEver", c_uint16),
        ("RSCEfileTblVer", c_uint16),
        ("HdrBlkSize", c_char),
        ("FileTblBlkOffset", c_char),
        ("FileTblRecBlkSize", c_char),
        ("Unknown", c_char),
        ("FileCount", c_uint32),
        ("Reserved", c_char * 496)
    ]


class FileEntry(BasicStruct):
    _fields_ = [
        ("magic", c_char * 4),
        ("FileName", c_char * 256),
        ("FileBlkOffset", c_uint32),
        ("FileSize", c_uint32),
        ("Reserved", c_char * 244)
    ]


def unpack(filename, output_dir, config_file):
    os.makedirs(output_dir, exist_ok=True)
    header = Header()
    file_list: list[str] = []
    with open(filename, "rb") as f:
        data = f.read(len(header))
        header.unpack(data)
        if header.magic != HeaderMagic:
            raise TypeError("Header magic mismatch.", header.magic)
        i = 0
        while i < header.FileCount:
            entry = FileEntry()
            entry.unpack(f.read(len(entry)))
            if entry.magic != EntryMagic:
                raise TypeError("Entry magic mismatch.", entry.magic)
            print('Found File:', name := entry.FileName.decode())
            origin_seek = f.tell()
            offset = entry.FileBlkOffset
            size = entry.FileSize
            f.seek(offset * 512)
            file_list.append(name)
            with open(output_dir + "/" + name, 'wb') as output_file:
                output_file.write(f.read(size))
            f.seek(origin_seek)
            i += 1
    with open(config_file, "w", newline='\n', encoding='utf-8') as f:
        f.write("\n".join(file_list))


def repack(files_path, output_file, config_file):
    if os.path.exists(output_file):
        os.remove(output_file)
    if not os.path.exists(files_path):
        print("No such files_path.")
        return
    files_list = os.listdir(files_path)
    with open(config_file, 'r', newline='\n', encoding='utf-8') as f:
        files = [i.strip('\n') for i in f.readlines()]
    files_list_new = [i for i in files if os.path.exists(os.path.join(files_path, i))]
    [files_list_new.append(i) for i in files_list if i not in files]
    files_list = files_list_new
    header = Header()
    header.magic = HeaderMagic
    header.RSCEver = c_uint16(0)
    header.RSCEfileTblVer = c_uint16(0)
    header.HdrBlkSize = c_char(1)
    header.FileTblBlkOffset = c_char(1)
    header.FileTblRecBlkSize = c_char(1)
    header.Unknown = c_char(0)
    header.FileCount = len(files_list)
    total_offset = (header.FileCount + 1) * 512
    with open(output_file, "wb") as f:
        f.write(header.pack())
        for i in files_list:
            if total_offset % 512:
                raise ValueError("Total offset is not a multiple of 512.")
            file_path = os.path.join(files_path, i)
            file_entry = FileEntry()
            file_entry.magic = EntryMagic
            file_entry.FileName = i.encode()
            file_entry.FileBlkOffset = total_offset // 512
            file_entry.FileSize = os.path.getsize(file_path)
            print(f'Adding: {i}')
            f.write(file_entry.pack())
            with open(file_path, "rb") as input_file:
                origin_seek = f.tell()
                f.seek(total_offset)
                file_content = input_file.read()
                total_offset += f.write(file_content)
                if total_offset % 512:
                    total_offset += 512 - total_offset % 512
                f.seek(origin_seek)


if __name__ == "__main__":
    import sys

    print(f'Usage:\n{sys.argv[0]} [u|r] <input_file> <output_dir> <config_file>')
    if len(sys.argv) >= 5:
        cmd = sys.argv[1]
        if cmd == 'r':
            repack(sys.argv[2], sys.argv[3], sys.argv[4])
        elif cmd == 'u':
            unpack(sys.argv[2], sys.argv[3], sys.argv[4])
