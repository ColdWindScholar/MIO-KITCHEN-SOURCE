#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
from re import escape, search
from typing import Any, Generator, Union, Optional
from .utils import JsonEdit

def scan_context(file) -> dict:  # 读取context文件返回一个字典
    context = {}
    with open(file, "r", encoding='utf-8') as file_:
        for i in file_.readlines():
            if not i.strip():
                print('[W] data is empty!')
                continue
            filepath, rule, *other = i.strip().split()
            filepath = filepath.replace(r'\@', '@')
            context[filepath] = rule
            if len(other) > 0:
                print(f"[Warn] {i[0]} has too much data.Skip.")
                del context[filepath]
    return context


def scan_dir(folder) -> Generator[Union[str, Any], Optional[Any], None]:  # 读取解包的目录，返回一个字典
    part_name = os.path.basename(folder)
    allfiles = ['/', '/lost+found', f'/{part_name}/lost+found', f'/{part_name}', f'/{part_name}/', f'/{part_name}(/.*)?']
    for root, dirs, files in os.walk(folder, topdown=True):
        for dir_ in dirs:
            yield os.path.join(root, dir_).replace(folder, '/' + part_name).replace('\\', '/')
        for file in files:
            yield os.path.join(root, file).replace(folder, '/' + part_name).replace('\\', '/')
        yield from allfiles

str_to_selinux = lambda string: escape(string).replace('\\-', '-')


def context_patch(fs_file, dir_path, fix_permission:dict) -> tuple:  # 接收两个字典对比
    new_fs = {}
    # 定义已修补过的 避免重复修补
    r_new_fs = {}
    add_new = 0
    print(f"ContextPatcher: the Original File Has {len(fs_file.keys()):d} entries")
    # 定义默认SeLinux标签
    permission_d = 'u:object_r:system_file:s0'
    for i in scan_dir(os.path.abspath(dir_path)):
        # 把不可打印字符替换为*
        if not i.isprintable():
            i = ''.join([c if c.isprintable() or not c.strip(' ') else '*' for c in i])

        i = str_to_selinux(i)
        if fs_file.get(i):
            # 如果存在直接使用默认的
            new_fs[i] = fs_file[i]
        else:
            permission = None
            if r_new_fs.get(i):
                continue
            # 确认i不为空
            if i:
                # 搜索已定义的权限
                for f in fix_permission.keys():
                    if search(f, i):
                        permission = fix_permission.get(f)
                #upper
                if not permission:
                    permission = permission_d
            if " " in permission:
                permission = permission.replace(' ', '*')
            print(f"ADD [{i} {permission}]")
            add_new += 1
            r_new_fs[i] = permission
            new_fs[i] = permission
    return new_fs, add_new


def main(dir_path, fs_config, fix_permission_file) -> None:
    if fix_permission_file is not None:
        fix_permission:dict = JsonEdit(fix_permission_file).read()
    else:
        fix_permission = {}
    new_fs, add_new = context_patch(scan_context(os.path.abspath(fs_config)), dir_path, fix_permission)
    with open(fs_config, "w+", encoding='utf-8', newline='\n') as f:
        f.writelines([f"{i} {new_fs[i]}\n" for i in sorted(new_fs.keys())])
    print(f'ContextPatcher: Add {add_new:d} entries')
