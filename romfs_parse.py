#!/usr/bin/env python3
# pylint: disable=line-too-long, missing-class-docstring, missing-function-docstring
# Thanks: The File Refer From https://github.com/ddddhm1234/ROMFS_PARSER , Used By MIO-KITCHEN Open Source Project
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
import os
from typing import Literal

Romfs_types = {
    0: "hlink",
    1: "dir",
    2: "file",
    3: "symlink",
    4: "block",
    5: "char_device",
    6: "socket",
    7: "fifo",
    8: "exec"
}

class RomfsNode:
    def __init__(self, node_type: Literal["dir", "file", "hlink", "block", "unknown"]):
        self.type = node_type
        self.children = []
        self.data = b""
        self.entry_start = -1
        self.name = ""
        self.checksum = ''
        self.info = ''

class RomfsParse:
    def __init__(self, path) -> None:
        self.file = path
        # Information Of FileSystem
        self.volume_name = ''
        self.size = ''
        self.nodes = ''

        self.root_node : RomfsNode = RomfsNode('unknown')
        self.all_nodes = []
        self.init()
    @staticmethod
    def read_volume_name(fp):
        i = 16
        name = b""
        origin_seek = fp.tell()
        fp.seek(i)
        data_i = fp.read(1)
        while int.from_bytes(data_i) != 0:
            name += data_i
            data_i = fp.read(1)
            i += 1
        fp.seek(origin_seek)
        if i % 16 == 0:
            return i, name.decode("utf-8")
        else:
            return (i // 16 + 1) * 16, name.decode("utf-8")

    @staticmethod
    def read_filename(fp, entry_start):
        origin_seek = fp.tell()
        start = entry_start + 16
        filename_start = start
        name = b""
        while True:
            fp.seek(filename_start)
            data = fp.read(16)
            name += data
            if name.find(b"\x00") > -1:
                break
            filename_start += 16

        name = name[:name.find(b"\x00")]
        filename_end = start + len(name) + 1
        fp.seek(origin_seek)
        if filename_end % 16 == 0:
            return filename_end, name.decode("utf-8")
        else:
            return (filename_end // 16 + 1) * 16, name.decode("utf-8")

    def view_one_level(self, fp, entry_start):
        origin_seek = fp.tell()
        nodes = []
        while entry_start != 0:
            fp.seek(entry_start)
            next_entry = int.from_bytes(fp.read(4), byteorder="big")
            info = int.from_bytes(fp.read(4), byteorder="big")
            size = int.from_bytes(fp.read(4), byteorder="big")
            checksum = int.from_bytes(fp.read(4), byteorder="big")
            data_begin, filename = self.read_filename(fp, entry_start)
            node = RomfsNode(Romfs_types.get(next_entry & 0b111, 'unknown'))
            node.entry_start = entry_start
            fp.seek(data_begin)
            node.data = fp.read(size)
            node.name = filename
            node.checksum = checksum
            node.info = info
            nodes.append(node)
            next_entry >>= 4
            next_entry <<= 4
            entry_start = next_entry
        fp.seek(origin_seek)
        return nodes

    def init(self):
        with open(self.file, 'rb') as f:
            if f.read(8) != b"-rom1fs-":
                raise TypeError("not a romfs bin")
            system_size = int.from_bytes(f.read(4), byteorder="big")
            self.size = system_size
            entry_start, volume_name = self.read_volume_name(f)
            root_node = RomfsNode("dir")
            root_node.name = volume_name
            self.volume_name = volume_name
            root_node.entry_start = entry_start
            path_nodes = [root_node]  # 获取根节点作为目录节点集中的第一个元素
            all_nodes = [root_node]
            while len(path_nodes) > 0:
                node = path_nodes.pop()  # 从目录节点集中弹出一个元素
                node_entry = node.entry_start
                f.seek(node_entry +  4)
                data = f.read(4)
                next_entry = int.from_bytes(data, byteorder="big")
                once_nodes = self.view_one_level(f, next_entry)  # 遍历这个目录节点的所属文件
                all_nodes += once_nodes
                node.children = once_nodes
                for _ in once_nodes:
                    if _.type == "dir" and _.name != ".":
                        # 如果目录下还有子目录，添加到目录节点集
                        path_nodes.append(_)
            self.nodes = len(all_nodes)
            # 返回根节点与所有节点集
            self.root_node = root_node
            self.all_nodes = all_nodes

    def __extract(self, root_node, prefix="."):
        path = os.path.join(prefix, root_node.name)
        if root_node.name in ['.', '..']:
            return
        if root_node.type == "file":
            with open(path, "wb") as f:
                f.write(root_node.data)
                f.flush()
        elif root_node.type == "dir" and root_node.name != ".":
            os.makedirs(path, exist_ok=True)
        else:
            print(root_node.type, root_node.name, root_node.data)

        for c in root_node.children:
            self.__extract(c, path)

    def extract(self, prefix='.'):
        self.__extract(self.root_node, prefix)

    def __print_struct(self, root_node, depth=0):
        if (root_node.type == "dir" and root_node.name != ".") or (root_node.type == "file"):
            print(depth * "\t" + root_node.name)
        for c in root_node.children:
            self.__print_struct(c, depth + 1)

    def print(self):
        self.__print_struct(self.root_node)

    def __repr__(self):
        return f"(Romfs, volume_name = {self.volume_name}, size = {self.size}, nodes_number = {self.nodes})"


fs = RomfsParse(r"app.bin")
fs.extract()
print(fs)

