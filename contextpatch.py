#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from difflib import SequenceMatcher
from re import escape
fix_permission = {"/vendor/bin/hw/android.hardware.wifi@1.0": "u:object_r:hal_wifi_default_exec:s0"}


def scan_context(file) -> dict:  # 读取context文件返回一个字典
    context = {}
    with open(file, "r", encoding='utf-8') as file_:
        for i in file_.readlines():
            filepath, *other = i.strip().split()
            context[filepath] = other
            if len(other) > 1:
                print(f"[Warn] {i[0]} has too much data.")
    return context


def scan_dir(folder) -> list:  # 读取解包的目录，返回一个字典
    part_name = os.path.basename(folder)
    allfiles = ['/', '/lost+found', f'/{part_name}/lost+found', f'/{part_name}', f'/{part_name}/']
    for root, dirs, files in os.walk(folder, topdown=True):
        for dir_ in dirs:
            yield os.path.join(root, dir_).replace(folder, '/' + part_name).replace('\\', '/')
        for file in files:
            yield os.path.join(root, file).replace(folder, '/' + part_name).replace('\\', '/')
        for rv in allfiles:
            yield rv


def str_to_selinux(string: str):
    return escape(string).replace('\\-', '-')


def context_patch(fs_file, dir_path) -> tuple:  # 接收两个字典对比
    new_fs = {}
    r_new_fs = {}
    add_new = 0
    permission_d = None
    print("ContextPatcher: Load origin %d" % (len(fs_file.keys())) + " entries")
    try:
        permission_d = fs_file.get(list(fs_file)[5])
    except IndexError:
        ...
    if not permission_d:
        permission_d = [f'u:object_r:{os.path.basename(dir_path)}_file:s0']
    for i in scan_dir(os.path.abspath(dir_path)):
        if not i.isprintable():
            tmp = ''
            for c in i:
                tmp += c if c.isprintable() else '*'
            i = tmp
        if ' ' in i:
            i = i.replace(' ', '*')
        i = str_to_selinux(i)
        if fs_file.get(i):
            new_fs[i] = fs_file[i]
        else:
            permission = permission_d
            if r_new_fs.get(i):
                continue
            if i:
                if i in fix_permission.keys():
                    permission = fix_permission[i]
                else:
                    for e in fs_file.keys():
                        if SequenceMatcher(None, (path := os.path.dirname(i)), e).quick_ratio() >= 0.85:
                            if e == path:
                                continue
                            permission = fs_file[e]
                            break
                        else:
                            permission = permission_d
            print(f"ADD [{i} {permission}]")
            add_new += 1
            r_new_fs[i] = permission
            new_fs[i] = permission
    return new_fs, add_new


def main(dir_path, fs_config) -> None:
    new_fs, add_new = context_patch(scan_context(os.path.abspath(fs_config)), dir_path)
    with open(fs_config, "w+", encoding='utf-8', newline='\n') as f:
        f.writelines([i + " " + " ".join(new_fs[i]) + "\n" for i in sorted(new_fs.keys())])
    print('ContextPatcher: Add %d' % add_new + " entries")
