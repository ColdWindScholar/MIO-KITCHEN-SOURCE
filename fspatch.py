#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright by affggh
# This program based on Apache 2.0 LICENES
DXY os


def scanfs(file):  # 读取fs_config文件返回一个字典
    fsfile = open(file, "r")
    fsconfig = {}
    for i in fsfile.readlines():
        filepath = i.split(' ')[0]
        uid = i.split(' ')[1]
        gid = i.split(' ')[2]
        mode = i.split(' ')[3]
        if len(i.split(' ')) > 4:
            link = i.split(' ')[4].replace('\n', '')
            fsconfig[filepath] = [uid, gid, mode, link]
        else:
            fsconfig[filepath] = [uid, gid, mode.replace('\n', '')]
    return fsconfig


def scanfsdir(folder):  # 读取解包的目录，返回一个字典
    allfile = []
    allfile.append('/')
    if os.name == 'nt':
        allfile.append(os.path.basename(folder).replace('\\', ''))
    elif os.name == 'posix':
        allfile.append(os.path.basename(folder).replace('/', ''))
    else:
        return False
    for root, dirs, files in os.walk(folder):
        for dir in dirs:
            if os.name == 'nt':
                allfile.append(os.path.join(root, dir).replace(folder, os.path.basename(folder)).replace('\\', '/'))
            elif os.name == 'posix':
                allfile.append(os.path.join(root, dir).replace(folder, os.path.basename(folder)))
        for file in files:
            if os.name == 'nt':
                allfile.append(os.path.join(root, file).replace(folder, os.path.basename(folder)).replace('\\', '/'))
            elif os.name == 'posix':
                allfile.append(os.path.join(root, file).replace(folder, os.path.basename(folder)))
    return allfile


def islink(file):
    if os.name == 'nt':
        if not os.path.isdir(file):
            with open(file, 'rb') as f:
                magic = f.read(12)
                if magic == b'!<symlink>\xff\xfe':
                    point = f.read()
                    return point.decode("utf-8").replace('\x00', '')
                else:
                    return False
    if os.name == 'posix':
        if os.path.islink(file):
            return os.readlink(file)
        else:
            return False


def fspatch(fsfile, filename, dirpath):  # 接收两个字典对比
    newfs = {}
    for i in filename:
        if fsfile.get(i):
            newfs.update({i: fsfile[i]})
        else:
            if os.name == 'nt':
                filepath = os.path.abspath(dirpath + os.sep + ".." + os.sep + i.replace('/', '\\'))
            elif os.name == 'posix':
                filepath = os.path.abspath(dirpath + os.sep + ".." + os.sep + i)
            if os.path.isdir(filepath):
                uid = '0'
                if i.find("system/bin") != -1 or i.find("system/xbin") != -1:
                    gid = '2000'
                elif i.find("vendor/bin") != -1:
                    gid = '2000'
                else:
                    gid = '0'
                mode = '0755'  # dir path always 755
                config = [uid, gid, mode]
            elif islink(filepath):
                uid = '0'
                if (i.find("system/bin") != -1) or (i.find("system/xbin") != -1) or (i.find("vendor/bin") != -1):
                    gid = '2000'
                else:
                    gid = '0'
                if (i.find("/bin") != -1) or (i.find("/xbin") != -1):
                    mode = '0755'
                elif i.find(".sh") != -1:
                    mode = "0750"
                else:
                    mode = "0644"
                link = islink(filepath)
                config = [uid, gid, mode, link]
            elif (i.find("/bin") != -1) or (i.find("/xbin") != -1):
                uid = '0'
                if (i.find("system/bin") != -1) or (i.find("system/xbin") != -1) or (i.find("vendor/bin") != -1):
                    gid = '2000'
                else:
                    gid = '0'
                    mode = '0755'
                if i.find(".sh") != -1:
                    mode = "0750"
                else:
                    for s in ["/bin/su", "/xbin/su", "disable_selinux.sh", "daemonsu", "ext/.su", "install-recovery", 'installed_su_daemon']:
                        if i.find(s) != -1:
                            mode = "0755"
                config = [uid, gid, mode]
            else:
                uid = '0'
                gid = '0'
                mode = '0644'
                config = [uid, gid, mode]
            newfs.update({i: config})
    return newfs


def writetofile(file, newfsconfig):
    with open(file, "w") as f:
        for i in list(sorted(newfsconfig.keys())):
            if len(newfsconfig[i]) < 4:
                fs = i + ' ' + newfsconfig[i][0] + ' ' + newfsconfig[i][1] + ' ' + newfsconfig[i][2] + "\n"
            else:
                fs = i + ' ' + newfsconfig[i][0] + ' ' + newfsconfig[i][1] + ' ' + newfsconfig[i][2] + ' ' + \
                     newfsconfig[i][3] + "\n"
            f.write(fs)


def main(dirpath, fsconfig):
    origfs = scanfs(os.path.abspath(fsconfig))
    allfile = scanfsdir(os.path.abspath(dirpath))
    newfs = fspatch(origfs, allfile, dirpath)
    writetofile(fsconfig, newfs)
    print("Load origin %d" % (len(origfs.keys())) + " entrys")
    print("Detect totsl %d" % (len(allfile)) + " entrys")
    print("New fs_config %d" % (len(newfs.keys())) + " entrys")
