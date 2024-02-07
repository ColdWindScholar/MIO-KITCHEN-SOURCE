import os
import re
from os import symlink, name as osname
from typing import Optional

import contextpatch
import fspatch

if osname == 'nt':
    from ctypes import wintypes, windll


def clink(link: str, target: str):
    with open(link, 'wb') as f:
        f.write(
            b"!<symlink>" + target.encode('utf-16') + b'\0\0')
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
    def __symlink(src_l: str, dest: str):
        print(f"创建软链接 [{src_l}] -> [{dest}]")
        if not os.path.exists(os.path.dirname(dest)):
            os.makedirs(os.path.dirname(dest))
        if osname == 'nt':
            with open(dest, 'wb') as f:
                f.write(
                    b"!<symlink>" + src_l.encode('utf-16') + b'\0\0')
            windll.kernel32.SetFileAttributesA(dest.encode('gb2312'), wintypes.DWORD(0x4))
        else:
            symlink(src_l, dest)

    fs_label = [["/", '0', '0', '0755'], ["/lost\\+found", '0', '0', '0700']]
    fc_label = [['/', 'u:object_r:system_file:s0'], ['/system(/.*)?', 'u:object_r:system_file:s0']]
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
    fspatch.main(os.path.join(project, 'system'), os.path.join(outdir, "system_fs_config"))
    contextpatch.main(os.path.join(project, 'system'), os.path.join(outdir, "system_file_contexts"))
