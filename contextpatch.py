#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from difflib import SequenceMatcher
from re import escape

fix_permission = {
    "system/app/*/.apk": "u:object_r:system_file:s0",
    "data-app/.apk": "u:object_r:system_file:s0",
    "android.hardware.wifi": "u:object_r:hal_wifi_default_exec:s0",
    "bin/idmap": "u:object_r:idmap_exec:s0",
    "bin/fsck": "u:object_r:fsck_exec:s0",
    "bin/e2fsck": "u:object_r:fsck_exec:s0",
    "bin/logcat": "u:object_r:logcat_exec:s0",
    "system/bin": "u:object_r:system_file:s0",
    "/system/bin/init": "u:object_r:init_exec:s0",
    r"/lost\+found": "u:object_r:rootfs:s0"
}


def scan_context(file) -> dict:  # 读取context文件返回一个字典
    context = {}
    with open(file, "r", encoding='utf-8') as file_:
        for i in file_.readlines():
            filepath, *other = i.strip().split()
            filepath = filepath.replace(r'\@', '@')
            context[filepath] = other
            if len(other) > 1:
                print(f"[Warn] {i[0]} has too much data.Skip.")
                del context[filepath]
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
    # 定义已修补过的 避免重复修补
    r_new_fs = {}
    add_new = 0
    print("ContextPatcher: the Original File Has %d" % (len(fs_file.keys())) + " entries")
    # 定义默认SeLinux标签
    permission_d = [f'u:object_r:{os.path.basename(dir_path).replace("_a", "")}_file:s0']
    for i in scan_dir(os.path.abspath(dir_path)):
        # 把不可打印字符替换为*
        if not i.isprintable():
            tmp = ''
            for c in i:
                tmp += c if c.isprintable() else '*'
            i = tmp
        if ' ' in i:
            i = i.replace(' ', '*')
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
                    if f in i:
                        permission = [fix_permission[f]]
                if not permission:
                    for e in fs_file.keys():
                        if SequenceMatcher(None, (path := os.path.dirname(i)), e).quick_ratio() >= 0.75:
                            if e == path:
                                continue
                            permission = fs_file[e]
                            break
                        else:
                            permission = permission_d
            if " " in permission:
                permission = permission.replace(' ', '')
            print(f"ADD [{i} {permission}], May be Inaccurate")
            add_new += 1
            r_new_fs[i] = permission
            new_fs[i] = permission
    return new_fs, add_new


def main(dir_path, fs_config) -> None:
    new_fs, add_new = context_patch(scan_context(os.path.abspath(fs_config)), dir_path)
    with open(fs_config, "w+", encoding='utf-8', newline='\n') as f:
        f.writelines([i + " " + " ".join(new_fs[i]) + "\n" for i in sorted(new_fs.keys())])
    print('ContextPatcher: Add %d' % add_new + " entries")
