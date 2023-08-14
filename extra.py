import os
import os.path as op
import re
import subprocess
from os import walk, symlink, readlink, name as osname
from platform import machine
from typing import Optional

if osname == 'nt':
    from ctypes import wintypes, windll


def clink(link: str, target: str):
    with open(link, 'wb') as f:
        f.write(b'!<symlink>')
        f.write(target.encode('utf-16'))
    if osname == 'nt':
        from ctypes.wintypes import LPCSTR
        from ctypes.wintypes import DWORD
        from stat import FILE_ATTRIBUTE_SYSTEM
        from ctypes import windll
        attrib = windll.kernel32.SetFileAttributesA
        attrib(LPCSTR(link.encode()), DWORD(FILE_ATTRIBUTE_SYSTEM))


class updaterutil:
    def __init__(self, fd):
        # self.path = Path(path)
        self.fd = fd
        if not self.fd:
            raise IOError("fd is not valid!")
        self.content = self.__parse_commands

    @property
    def __parse_commands(self):  # This part code from @libchara-dev
        self.fd.seek(0, 0)  # set seek from start
        commands = re.findall(r'(\w+)\((.*?)\)', self.fd.read().replace('\n', ''))
        parsed_commands = [
            [command, *(arg[0] or arg[1] or arg[2] for arg in re.findall(r'"([^"]+)"|(\b\d+\b)|(\b\S+\b)', args))]
            for command, args in commands]
        return parsed_commands


# This Function copy from affggh mtk-porttool(https://gitee.com/affggh/mtk-garbage-porttool)
def script2fs_context(input_f, outdir, project):
    def __readlink(dest: str):
        if os.name == 'nt':
            with open(dest, 'rb') as f:
                if f.read(10) == b'!<symlink>':
                    return f.read().decode('utf-16').rstrip('\0')
                else:
                    return None
        else:
            try:
                readlink(dest)
            except:
                return None

    def __symlink(src_l: str, dest: str):
        def set_attrib(path: str) -> wintypes.BOOL:
            return windll.kernel32.SetFileAttributesA(path.encode('gb2312'), wintypes.DWORD(0x4))

        print(f"创建软链接 [{src_l}] -> [{dest}]")
        if not os.path.exists(os.path.dirname(dest)):
            os.makedirs(os.path.dirname(dest))
        if osname == 'nt':
            with open(dest, 'wb') as f:
                f.write(
                    b"!<symlink>" + src_l.encode('utf-16') + b'\0\0')
            set_attrib(dest)
        else:
            symlink(src_l, dest)

    fs_label = []
    fc_label = []
    fs_label.append(
        ["/", '0', '0', '0755'])
    fs_label.append(
        ["/lost\\+found", '0', '0', '0700'])
    fc_label.append(
        ['/', 'u:object_r:system_file:s0'])
    fc_label.append(
        ['/system(/.*)?', 'u:object_r:system_file:s0'])
    print("分析刷机脚本...")
    with open(input_f, 'r', encoding='utf-8') as updater:
        contents = updaterutil(updater).content
    last_fpath = ''
    for content in contents:
        command, *args = content

        if command == 'symlink':
            src, *targets = args
            for target in targets:
                if osname == 'nt':
                    __symlink(src, str(os.path.join(project, target.lstrip('/'))))
                else:
                    os.symlink(src, str(os.path.join(project, target.lstrip('/'))))
        elif command in ['set_metadata', 'set_metadata_recursive']:
            dirmode = False if command == 'set_metadata' else True
            fpath, *fargs = args
            fpath = fpath.replace("+", "\\+").replace("[", "\\[").replace('//', '/')
            if fpath == last_fpath:
                continue  # skip same path
            # initial
            uid, gid, mode, extra = '0', '0', '644', ''
            selable = 'u:object_r:system_file:s0'  # common system selable
            for index, farg in enumerate(fargs):
                if farg == 'uid':
                    uid = fargs[index + 1]
                elif farg == 'gid':
                    gid = fargs[index + 1]
                elif farg in ['mode', 'fmode', 'dmode']:
                    if dirmode and farg == 'dmode':
                        mode = fargs[index + 1]
                    else:
                        mode = fargs[index + 1]
                elif farg == 'capabilities':
                    # continue
                    if fargs[index + 1] == '0x0':
                        extra = ''
                    else:
                        extra = 'capabilities=' + fargs[index + 1]
                elif farg == 'selabel':
                    selable = fargs[index + 1]
            fs_label.append(
                [fpath.lstrip('/'), uid, gid, mode, extra])
            fc_label.append(
                [fpath, selable])
            last_fpath = fpath

    # Patch fs_config
    print("添加缺失的文件和权限")
    fs_files = [i[0] for i in fs_label]
    for root, dirs, files in walk(project + os.sep + "system"):
        if project + os.sep + "install" in root.replace('\\', '/'): continue  # skip lineage spec
        for dir in dirs:
            unix_path = op.join(
                op.join("/system", op.relpath(op.join(root, dir), project + os.sep + "system")).replace("\\", "/")
            ).replace("[", "\\[")
            if not unix_path in fs_files:
                fs_label.append([unix_path.lstrip('/'), '0', '0', '0755'])
        for file in files:
            unix_path = op.join(
                op.join("/system", op.relpath(op.join(root, file), project + os.sep + "system")).replace("\\", "/")
            ).replace("[", "\\[")
            if not unix_path in fs_files:
                link = __readlink(op.join(root, file))
                if link:
                    fs_label.append(
                        [unix_path.lstrip('/'), '0', '2000', '0755', link])
                else:
                    if "bin/" in unix_path:
                        mode = '0755'
                    else:
                        mode = '0644'
                    fs_label.append(
                        [unix_path.lstrip('/'), '0', '2000', mode])

    # generate config
    print("生成fs_config 和 file_contexts")
    fs_label.sort()
    fc_label.sort()
    with open(os.path.join(outdir, "system_fs_config"), 'w', newline='\n') as fs_config, open(
            os.path.join(outdir, "system_file_contexts"), 'w', newline='\n') as file_contexts:
        for fs in fs_label:
            fs_config.write(" ".join(fs) + '\n')
        for fc in fc_label:
            file_contexts.write(" ".join(fc) + '\n')


class proputil:
    def __init__(self, propfile: str):
        if os.path.exists(os.path.abspath(propfile)):
            self.propfd = open(propfile, 'r+')
        else:
            raise FileExistsError(f"File {propfile} does not exist!")
        self.prop = self.__loadprop

    @property
    def __loadprop(self) -> list:
        return self.propfd.readlines()

    def getprop(self, key: str) -> Optional[str]:
        """
        recive key and return value or None
        """
        for i in self.prop:
            if i[:1] == "#":
                continue
            if key in i:
                return i.rstrip().split('=')[1]
        return None

    def setprop(self, key, value) -> None:
        flag: bool = False  # maybe there is not only one item
        for index, current in enumerate(self.prop):
            if key in current:
                self.prop[index] = current.split('=')[0] + '=' + value + '\n'
                flag = True
        if not flag:
            self.prop.append(
                key + '=' + value + '\n'
            )

    def save(self):
        self.propfd.seek(0, 0)
        self.propfd.truncate()
        self.propfd.writelines(self.prop)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):  # with proputil('build.prop') as p:
        self.save()
        self.propfd.close()


def returnoutput(cmd, elocal, kz=1):
    if kz == 1:
        comd = "".join([elocal, os.sep, "bin", os.sep, os.name, '_', machine(), os.sep, cmd])
    else:
        comd = cmd
    if os.name == 'posix':
        comd = comd.split()
    else:
        comd = cmd
    try:
        ret = subprocess.check_output(comd, shell=False, stderr=subprocess.STDOUT)
        return ret.decode()
    except subprocess.CalledProcessError as e:
        return e
