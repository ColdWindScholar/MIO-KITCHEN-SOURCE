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
from ctypes import LittleEndianStructure, sizeof, memmove, string_at, addressof, byref, c_uint, c_ulonglong, c_char, \
    c_ushort, c_uint64


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


amlogic_magic = 0x27b51956


class AmlHeader(BasicStruct):
    _pack_ = 1
    _fields_ = [
        ("crc32", c_uint),
        ("version", c_uint),
        # ---VersionHeader---
        ("magic", c_uint),
        ("imageSz", c_ulonglong),
        ("itemAlginSize", c_uint),
        ("itemNum", c_uint),
        ("reserve", c_char * 44),
    ]


class ItemInfo(BasicStruct):
    _pack_ = 1
    _fields_ = [
        ("itemId", c_uint),
        ("fileType", c_uint),
        ("curoffsetInItem", c_uint64),
        ("offsetInImage", c_uint64),
        ("itemMainType", c_char * 256),
        ("itemSubType", c_char * 256),
        ("verify", c_uint),
        ("isBackUpItem", c_ushort),
        ("backUpItemId", c_ushort),
        ("reserve", c_char * 32),
    ]


def generate_cfg(partitions_list: list, partitions_verify: list, output_file:str):
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    partitions_normal = [i for i in partitions_list if i[1] not in partitions_verify]
    with open(output_file, "w", encoding='utf-8', newline='\n') as f:
        f.write('[LIST_NORMAL]\n')
        for i in partitions_normal:
            main_type, sub_type = i
            f.write(f'file="{sub_type}.{main_type}"		main_type="{main_type}"		sub_type="{sub_type}"\n')
        f.write('[LIST_VERIFY]\n')
        for i in partitions_list:
            if i[1] not in partitions_verify:
                continue
            main_type, sub_type = i
            f.write(f'file="{sub_type}.{main_type}"		main_type="{main_type}"		sub_type="{sub_type}"\n')
    print(f"Generated config file to {output_file} successfully.")


def main(filepath: str, output_path: str):
    partitions = []
    partitions_verify = []
    with open(filepath, "rb") as f:
        header = AmlHeader()
        d = f.read(len(header))
        header.unpack(d)
        if header.magic != amlogic_magic:
            raise Exception("magic is not amlogic magic.")
        if header.version != 2:
            print(f"Only Amlogic v2 supported.\nIf u wanna support v{header.version}, Please sent this file to developers.")
            return
        i = 0
        while i < header.itemNum:
            h2 = ItemInfo()
            h2.unpack(f.read(len(h2)))
            i += 1
            main_type = h2.itemMainType.decode()
            sub_type = h2.itemSubType.decode()
            if main_type == 'VERIFY':
                partitions_verify.append(sub_type)
                continue
            print(f"[{i}/{header.itemNum}] Extracting {sub_type}.{main_type}...")
            with open(output_path + f"/{sub_type}.{main_type}", "wb") as output_file:
                origin_position = f.tell()
                f.seek(h2.curoffsetInItem)
                output_file.write(f.read(h2.offsetInImage))
                f.seek(origin_position)
                partitions.append([main_type, sub_type])

    generate_cfg(partitions, partitions_verify, output_path + "/config/image.cfg")
