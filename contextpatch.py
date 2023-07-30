#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os


def scan_context(file) -> dict:  # 读取context文件返回一个字典
    context = {}
    with open(file, "r") as file_:
        for i in file_.readlines():
            filepath, *other = i.strip().split()
            context[filepath] = other
            if len(i.split()) > 2:
                print(f"Warn:{i[0]} has too much data.")
    return context


def scan_dir(folder) -> list:  # 读取解包的目录，返回一个字典
    part_name = os.path.dirname(folder)
    allfiles = ['/', '/lost\\+found', f'/{part_name}/lost\\+found', f'/{part_name}/']
    for root, dirs, files in os.walk(folder, topdown=True):
        for dir_ in dirs:
            if os.name == 'nt':
                allfiles.append(os.path.join(root, dir_).replace(folder, os.path.basename(folder)).replace('\\', '/'))
            elif os.name == 'posix':
                allfiles.append(os.path.join(root, dir_).replace(folder, os.path.basename(folder)))
        for file in files:
            if os.name == 'nt':
                allfiles.append(os.path.join(root, file).replace(folder, os.path.basename(folder)).replace('\\', '/'))
            elif os.name == 'posix':
                allfiles.append(os.path.join(root, file).replace(folder, os.path.basename(folder)))
    return sorted(set(allfiles), key=allfiles.index)


def context_patch(fs_file, filename, dir_path) -> dict:  # 接收两个字典对比
    new_fs = {}
    permission = fs_file[0].split()[1]
    for i in filename:
        if fs_file.get(i):
            new_fs[i] = fs_file[i]
        else:
            if os.name == 'nt':
                filepath = os.path.abspath(dir_path + os.sep + ".." + os.sep + i.replace('/', '\\'))
            elif os.name == 'posix':
                filepath = os.path.abspath(dir_path + os.sep + ".." + os.sep + i)
            else:
                filepath = os.path.abspath(dir_path + os.sep + ".." + os.sep + i)
            if filepath:
                for e in fs_file:
                    if os.path.dirname(filepath) in e:
                        permission = e.split()[1]
                        break
            print(f'Add [{i}:{permission}]')
            new_fs[i] = permission
    return new_fs


def main(dir_path, fs_config) -> None:
    origin = scan_context(os.path.abspath(fs_config))
    allfiles = scan_dir(os.path.abspath(dir_path))
    new_fs = context_patch(origin, allfiles, dir_path)
    with open(fs_config, "w", encoding='utf-8', newline='\n') as f:
        f.writelines([i + " " + " ".join(new_fs[i]) + "\n" for i in sorted(new_fs.keys())])
    print("Load origin %d" % (len(origin.keys())) + " entries")
    print("Detect total %d" % (len(allfiles)) + " entries")
    print('Add %d' % (len(new_fs.keys()) - len(origin.keys())) + " entries")
