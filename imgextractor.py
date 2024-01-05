import os
import re
from string import printable
import struct

import ext4

if os.name == 'nt':
    from ctypes.wintypes import LPCSTR, DWORD
    from stat import FILE_ATTRIBUTE_SYSTEM
    from ctypes import windll
from timeit import default_timer as dti
from utils import simg2img


class Extractor:
    def __init__(self):
        self.BASE_DIR_ = None
        self.CONFING_DIR = None
        self.DIR = None
        self.FileName = ""
        self.OUTPUT_IMAGE_FILE = ""
        self.EXTRACT_DIR = ""
        self.BLOCK_SIZE = 4096
        self.context = []
        self.fs_config = []

    @staticmethod
    def __out_name(file_path, out=1):
        name = file_path if out == 1 else os.path.basename(file_path).rsplit('.', 1)[0]
        name = name.split('-')[0].split(' ')[0].split('+')[0].split('{')[0].split('(')[0]
        return name

    @staticmethod
    def __append(msg, log):
        if not os.path.isfile(log) and not os.path.exists(log):
            with open(log, 'tw', encoding='utf-8'):
                ...
        with open(log, 'a', newline='\n') as file:
            print(msg, file=file)

    @staticmethod
    def __get_perm(arg):
        if len(arg) < 9 or len(arg) > 10:
            return
        if len(arg) > 8:
            arg = arg[1:]
        oor, ow, ox, gr, gw, gx, wr, ww, wx = list(arg)
        o, g, w, s = 0, 0, 0, 0
        if oor == 'r':
            o += 4
        if ow == 'w':
            o += 2
        if ox == 'x':
            o += 1
        if ox == 'S':
            s += 4
        if ox == 's':
            s += 4
            o += 1
        if gr == 'r':
            g += 4
        if gw == 'w':
            g += 2
        if gx == 'x':
            g += 1
        if gx == 'S':
            s += 2
        if gx == 's':
            s += 2
            g += 1
        if wr == 'r':
            w += 4
        if ww == 'w':
            w += 2
        if wx == 'x':
            w += 1
        if wx == 'T':
            s += 1
        if wx == 't':
            s += 1
            w += 1
        return f'{s}{o}{g}{w}'

    def __ext4extractor(self):

        def scan_dir(root_inode, root_path=""):
            for entry_name, entry_inode_idx, entry_type in root_inode.open_dir():
                if entry_name in ['.', '..'] or entry_name.endswith(' (2)'):
                    continue
                entry_inode = root_inode.volume.get_inode(entry_inode_idx, entry_type)
                entry_inode_path = root_path + '/' + entry_name
                mode = self.__get_perm(entry_inode.mode_str)
                uid = entry_inode.inode.i_uid
                gid = entry_inode.inode.i_gid
                cap = ''
                link_target = ''
                tmp_path = self.DIR + entry_inode_path
                spaces_file = self.BASE_DIR_ + 'config' + os.sep + self.FileName + '_space.txt'
                for f, e in entry_inode.xattrs():
                    if f == 'security.selinux':
                        t_p_mkc = tmp_path
                        for fuk_ in '\\^$.|?*+(){}[]':
                            t_p_mkc = t_p_mkc.replace(fuk_, '\\' + fuk_)
                        self.context.append(f"/{t_p_mkc} {e.decode('utf8')[:-1]}")
                    elif f == 'security.capability':
                        r = struct.unpack('<5I', e)
                        if r[1] > 65535:
                            cap = hex(int(f'{r[3]:04x}{r[1]:04x}', 16))
                        else:
                            cap = hex(int(f'{r[3]:04x}{r[2]:04x}{r[1]:04x}', 16))
                        cap = f" capabilities={cap}"
                if entry_inode.is_symlink:
                    try:
                        link_target = entry_inode.open_read().read().decode("utf8")
                    except Exception and BaseException:
                        link_target_block = int.from_bytes(entry_inode.open_read().read(), "little")
                        link_target = root_inode.volume.read(link_target_block * root_inode.volume.block_size,
                                                             entry_inode.inode.i_size).decode("utf8")
                if tmp_path.find(' ', 1, len(tmp_path)) > 0:
                    self.__append(tmp_path, spaces_file)
                    self.fs_config.append(
                        f"{tmp_path.replace(' ', '_')} {uid} {gid} {mode}{cap} {link_target}")
                else:
                    self.fs_config.append(
                        f'{tmp_path} {uid} {gid} {mode}{cap} {link_target}')
                if entry_inode.is_dir:
                    dir_target = self.EXTRACT_DIR + entry_inode_path.replace(' ', '_').replace('"', '')
                    if dir_target.endswith('.') and os.name == 'nt':
                        dir_target = dir_target[:-1]
                    if not os.path.isdir(dir_target):
                        os.makedirs(dir_target)
                    if os.name == 'posix' and os.geteuid() == 0:
                        os.chmod(dir_target, int(mode, 8))
                        os.chown(dir_target, uid, gid)
                    scan_dir(entry_inode, entry_inode_path)
                elif entry_inode.is_file:
                    file_target = self.EXTRACT_DIR + entry_inode_path.replace(' ', '_').replace('"', '')
                    if os.name == 'nt':
                        file_target = file_target.replace('\\', '/')
                    try:
                        with open(file_target, 'wb') as out:
                            out.write(entry_inode.open_read().read())
                    except Exception and BaseException as e:
                        print(f'[E] Cannot Write {file_target}, Because of {e}')
                    if os.name == 'posix' and os.geteuid() == 0:
                        os.chmod(file_target, int(mode, 8))
                        os.chown(file_target, uid, gid)
                elif entry_inode.is_symlink:
                    target = self.EXTRACT_DIR + entry_inode_path.replace(' ', '_')
                    try:
                        if os.path.islink(target) or os.path.isfile(target):
                            try:
                                os.remove(target)
                            finally:
                                ...
                        if os.name == 'posix':
                            os.symlink(link_target, target)
                        if os.name == 'nt':
                            with open(target.replace('/', os.sep), 'wb') as out:
                                out.write(b'!<symlink>' + link_target.encode('utf-16') + b'\x00\x00')
                                try:
                                    windll.kernel32.SetFileAttributesA(LPCSTR(target.encode()),
                                                                       DWORD(FILE_ATTRIBUTE_SYSTEM))
                                except Exception as e:
                                    print(e.__str__())
                    except BaseException and Exception:
                        try:
                            if link_target and all(c_ in printable for c_ in link_target):
                                if os.name == 'posix':
                                    os.symlink(link_target, target)
                                if os.name == 'nt':
                                    with open(target.replace('/', os.sep), 'wb') as out:
                                        out.write(b'!<symlink>' + link_target.encode('utf-16') + b'\x00\x00')
                                    try:
                                        windll.kernel32.SetFileAttributesA(LPCSTR(target.encode()),
                                                                           DWORD(FILE_ATTRIBUTE_SYSTEM))
                                    except Exception as e:
                                        print(e.__str__())
                        finally:
                            ...

        if not os.path.isdir(self.CONFING_DIR):
            os.makedirs(self.CONFING_DIR)
        self.__append(os.path.getsize(self.OUTPUT_IMAGE_FILE), self.CONFING_DIR + os.sep + self.FileName + '_size.txt')
        with open(self.OUTPUT_IMAGE_FILE, 'rb') as file:
            dir_r = self.__out_name(os.path.basename(self.OUTPUT_IMAGE_FILE).rsplit('.', 1)[0])
            self.DIR = dir_r
            scan_dir(ext4.Volume(file).root)
            self.fs_config.insert(0, '/ 0 2000 0755' if dir_r == 'vendor' else '/ 0 0 0755')
            self.fs_config.insert(1, f'{dir_r} 0 2000 0755' if dir_r == 'vendor' else '/lost+found 0 0 0700')
            self.fs_config.insert(2 if dir_r == 'system' else 1, f'{dir_r} 0 0 0755')
            self.__append('\n'.join(self.fs_config), self.CONFING_DIR + os.sep + self.FileName + '_fs_config')
            p1 = p2 = 0
            if self.context:
                self.context.sort()
                for c in self.context:
                    if re.search('/system/system/build..prop ', c) and p1 == 0:
                        self.context.insert(3, '/lost+\\found' + ' u:object_r:rootfs:s0')
                        self.context.insert(4, '/' + dir_r + '/' + dir_r + '(/.*)? ' + c.split()[1])
                        p1 = 1
                    if re.search('lost..found', c) and p2 == 0:
                        self.context.insert(0, '/ ' + c.split()[1])
                        self.context.insert(1, '/' + dir_r + '(/.*)? ' + c.split()[1])
                        self.context.insert(2, f'/{dir_r} {c.split()[1]}')
                        self.context.insert(3, '/' + dir_r + '/lost+\\found ' + c.split()[1])
                        p2 = 1
                    if p1 == p2 == 1:
                        break
                self.__append('\n'.join(self.context), self.CONFING_DIR + os.sep + self.FileName + "_file_contexts")

    @staticmethod
    def fix_moto(input_file):
        if not os.path.exists(input_file):
            return
        output_file = input_file + "_"
        if os.path.exists(output_file):
            try:
                os.remove(output_file)
            finally:
                ...
        with open(input_file, 'rb') as f:
            data = f.read(500000)
        if not re.search(b'\x4d\x4f\x54\x4f', data):
            return
        offset = 0
        for i in re.finditer(b'\x53\xEF', data):
            if data[i.start() - 1080] == 0:
                offset = i.start() - 1080
                break
        if offset > 0:
            with open(output_file, 'wb') as o, open(input_file, 'rb') as f:
                data = f.read(15360)
                if data:
                    o.write(data)
        try:
            os.remove(input_file)
            os.rename(output_file, input_file)
        finally:
            ...

    def main(self, target: str, output_dir: str, work: str, target_type: str = 'img'):
        self.BASE_DIR_ = output_dir + os.sep
        self.EXTRACT_DIR = os.path.realpath(os.path.dirname(output_dir)) + os.sep + self.__out_name(
            os.path.basename(output_dir))
        self.OUTPUT_IMAGE_FILE = (os.path.realpath(os.path.dirname(target)) + os.sep) + os.path.basename(target)
        self.FileName = self.__out_name(os.path.basename(target), out=0)
        self.CONFING_DIR = work + os.sep + 'config'
        if target_type == 's_img':
            simg2img(target)
            target_type = 'img'
        if target_type == 'img':
            with open(os.path.abspath(self.OUTPUT_IMAGE_FILE), 'rb') as f:
                data = f.read(500000)
            if re.search(b'\x4d\x4f\x54\x4f', data):
                print(".....MOTO structure! Fixing.....")
                self.fix_moto(os.path.abspath(self.OUTPUT_IMAGE_FILE))
            print("Extracting %s --> %s" % (os.path.basename(target), os.path.basename(self.EXTRACT_DIR)))
            start = dti()
            self.__ext4extractor()
            print("Done! [%s]" % (dti() - start))
