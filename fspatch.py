#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os


def scanfs(file) -> dict:
    filesystem_config = {}
    with open(file, "r") as file_:
        for i in file_.readlines():
            filepath, *other = i.strip().split()
            filesystem_config[filepath] = other
            if len(other) > 4:
                print(f"Warn:{i[0]} has too much data.")
    return filesystem_config


def scan_dir(folder) -> bool and list:
    allfiles = ['/']
    if os.name == 'nt':
        allfiles.append(os.path.basename(folder).replace('\\', ''))
    elif os.name == 'posix':
        allfiles.append(os.path.basename(folder).replace('/', ''))
    else:
        return False
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
    return allfiles


def islink(file) -> str and bool:
    if os.name == 'nt':
        if not os.path.isdir(file):
            with open(file, 'rb') as f:
                if f.read(12) == b'!<symlink>\xff\xfe':
                    return f.read().decode("utf-8").replace('\x00', '')
                else:
                    return False
    elif os.name == 'posix':
        if os.path.islink(file):
            return os.readlink(file)
        else:
            return False


def fs_patch(fs_file, filename, dir_path) -> dict:  # 接收两个字典对比
    new_fs = {}
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
            if os.path.isdir(filepath):
                uid = '0'
                if "system/bin" in i or "system/xbin" in i or "vendor/bin" in i:
                    gid = '2000'
                else:
                    gid = '0'
                mode = '0755'  # dir path always 755
                config = [uid, gid, mode]
            elif islink(filepath):
                uid = '0'
                if ("system/bin" in i) or ("system/xbin" in i) or ("vendor/bin" in i):
                    gid = '2000'
                else:
                    gid = '0'
                if ("/bin" in i) or ("/xbin" in i):
                    mode = '0755'
                elif ".sh" in i:
                    mode = "0750"
                else:
                    mode = "0644"
                link = islink(filepath)
                config = [uid, gid, mode, link]
            elif ("/bin" in i) or ("/xbin" in i):
                uid = '0'
                mode = '0755'
                if ("system/bin" in i) or ("system/xbin" in i) or ("vendor/bin" in i):
                    gid = '2000'
                else:
                    gid = '0'
                    mode = '0755'
                if ".sh" in i:
                    mode = "0750"
                else:
                    for s in ["/bin/su", "/xbin/su", "disable_selinux.sh", "daemon", "ext/.su", "install-recovery",
                              'installed_su_daemon']:
                        if s in i:
                            mode = "0755"
                config = [uid, gid, mode]
            else:
                uid = '0'
                gid = '0'
                mode = '0644'
                config = [uid, gid, mode]
            print(f'Add [{i}:{config}]')
            new_fs[i] = config
    return new_fs


def main(dir_path, fs_config) -> None:
    origin_fs = scanfs(os.path.abspath(fs_config))
    allfiles = scan_dir(os.path.abspath(dir_path))
    new_fs = fs_patch(origin_fs, allfiles, dir_path)
    with open(fs_config, "w", encoding='utf-8', newline='\n') as f:
        f.writelines([i + " " + " ".join(new_fs[i]) + "\n" for i in sorted(new_fs.keys())])
    print("Load origin %d" % (len(origin_fs.keys())) + " entries")
    print("Detect total %d" % (len(allfiles)) + " entries")
    print('Add %d' % (len(new_fs.keys()) - len(origin_fs.keys())) + " entries")
