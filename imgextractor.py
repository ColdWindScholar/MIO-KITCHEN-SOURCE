import os
import re
import string
import struct

import ext4

if os.name == 'nt':
    from ctypes.wintypes import LPCSTR
    from ctypes.wintypes import DWORD
    from stat import FILE_ATTRIBUTE_SYSTEM
    from ctypes import windll
from timeit import default_timer as dti
from collections import deque
from utils import simg2img

EXT4_HEADER_MAGIC = 0xED26FF3A
EXT4_SPARSE_HEADER_LEN = 28
EXT4_CHUNK_HEADER_SIZE = 12


class ext4_file_header(object):
    def __init__(self, buf):
        (self.magic,
         self.major,
         self.minor,
         self.file_header_size,
         self.chunk_header_size,
         self.block_size,
         self.total_blocks,
         self.total_chunks,
         self.crc32) = struct.unpack('<I4H4I', buf)


class ext4_chunk_header(object):
    def __init__(self, buf):
        (self.type,
         self.reserved,
         self.chunk_size,
         self.total_size) = struct.unpack('<2H2I', buf)


class Extractor(object):
    def __init__(self):
        self.CONFING_DIR = None
        self.MYFileName = None
        self.OUTPUT_MYIMAGE_FILE = None
        self.BASE_DIR_ = None
        self.DIR = None
        self.FileName = ""
        self.BASE_DIR = ""
        self.OUTPUT_IMAGE_FILE = ""
        self.EXTRACT_DIR = ""
        self.BLOCK_SIZE = 4096
        self.TYPE_IMG = 'system'
        self.context = deque()
        self.fs_config = deque()

    @staticmethod
    def __file_name(file_path):
        name = os.path.basename(file_path).rsplit('.', 1)[0]
        name = name.split('-')[0]
        name = name.split(' ')[0]
        name = name.split('+')[0]
        name = name.split('{')[0]
        name = name.split('(')[0]
        return name

    @staticmethod
    def __out_name(file_path):
        name = file_path
        name = name.split('-')[0]
        name = name.split(' ')[0]
        name = name.split('+')[0]
        name = name.split('{')[0]
        name = name.split('(')[0]
        return name

    @staticmethod
    def __append(msg, log):
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
        fs_config_file = self.FileName + '_fs_config'
        fuk_symbols = '\\^$.|?*+(){}[]'
        contexts = self.CONFING_DIR + os.sep + self.FileName + "_file_contexts"  # 08.05.18

        def scan_dir(root_inode, root_path=""):
            for entry_name, entry_inode_idx, entry_type in root_inode.open_dir():
                if entry_name in ['.', '..'] or entry_name.endswith(' (2)'):
                    continue
                entry_inode = root_inode.volume.get_inode(entry_inode_idx, entry_type)
                entry_inode_path = root_path + '/' + entry_name
                mode = self.__get_perm(entry_inode.mode_str)
                uid = entry_inode.inode.i_uid
                gid = entry_inode.inode.i_gid
                con = ''
                cap = ''
                tmp_path = self.DIR + entry_inode_path
                spaces_file = self.BASE_DIR_ + 'config' + os.sep + self.FileName + '_space.txt'
                for i in list(entry_inode.xattrs()):
                    if i[0] == 'security.selinux':
                        con = i[1].decode('utf8')[:-1]
                    elif i[0] == 'security.capability':
                        raw_cap = struct.unpack("<5I", i[1])
                        if raw_cap[1] > 65535:
                            cap = f"{hex(int('%04x%04x' % (raw_cap[3], raw_cap[1]), 16))}"
                        else:
                            cap = f"{hex(int('%04x%04x%04x' % (raw_cap[3], raw_cap[2], raw_cap[1]), 16))}"
                        cap = f' capabilities={cap}'
                if entry_inode.is_symlink:
                    link_target = entry_inode.open_read().read().decode("utf8")
                else:
                    link_target = ''
                if tmp_path.find(' ', 1, len(tmp_path)) > 0:
                    if not os.path.isfile(spaces_file):
                        with open(spaces_file, 'tw', encoding='utf-8'):
                            self.__append(tmp_path, spaces_file)
                    else:
                        self.__append(tmp_path, spaces_file)
                    tmp_path = tmp_path.replace(' ', '_')
                    self.fs_config.append(
                        f'{tmp_path} {uid} {gid} {mode + cap if cap else mode} {link_target}')
                else:
                    self.fs_config.append(
                        f'{self.DIR + entry_inode_path} {uid} {gid} {mode + cap if cap else mode} {link_target}')
                if not cap:
                    if con:
                        for fuk_ in fuk_symbols:
                            tmp_path = tmp_path.replace(fuk_, '\\' + fuk_)
                        self.context.append('/%s %s' % (tmp_path, con))
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
                        print(f'ERROR:Cannot Write {file_target}, Because of {e}')
                    if os.name == 'posix':
                        if os.geteuid() == 0:
                            os.chmod(file_target, int(mode, 8))
                            os.chown(file_target, uid, gid)
                elif entry_inode.is_symlink:
                    try:
                        link_target = entry_inode.open_read().read().decode("utf8")
                        target = self.EXTRACT_DIR + entry_inode_path.replace(' ', '_')
                        if os.path.islink(target) or os.path.isfile(target):
                            try:
                                os.remove(target)
                            finally:
                                ...
                        if os.name == 'posix':
                            os.symlink(link_target, target)
                        if os.name == 'nt':
                            with open(target.replace('/', os.sep), 'wb') as out:
                                tmp = b'!<symlink>\xff\xfe'
                                for index in list(link_target):
                                    tmp = tmp + struct.pack('>sx', index.encode('utf-8'))
                                out.write(tmp + struct.pack('xx'))
                                if os.name == 'nt':
                                    try:
                                        windll.kernel32.SetFileAttributesA(LPCSTR(target.encode()),
                                                                           DWORD(FILE_ATTRIBUTE_SYSTEM))
                                    except Exception as e:
                                        print(e.__str__())
                    except BaseException and Exception:
                        try:
                            link_target_block = int.from_bytes(entry_inode.open_read().read(), "little")
                            link_target = root_inode.volume.read(link_target_block * root_inode.volume.block_size,
                                                                 entry_inode.inode.i_size).decode("utf8")
                            target = self.EXTRACT_DIR + entry_inode_path.replace(' ', '_')
                            if link_target and all(c_ in string.printable for c_ in link_target):
                                if os.name == 'posix':
                                    os.symlink(link_target, target)
                                if os.name == 'nt':
                                    with open(target.replace('/', os.sep), 'wb') as out:
                                        tmp = b'!<symlink>\xff\xfe'
                                        for index in list(link_target):
                                            tmp = tmp + struct.pack('>sx', index.encode('utf-8'))
                                        out.write(tmp + struct.pack('xx'))
                            else:
                                ...
                        finally:
                            ...

        dir_my = self.CONFING_DIR + os.sep
        if not os.path.isdir(dir_my):
            os.makedirs(dir_my)
        with open(dir_my + self.FileName + '_size.txt', 'tw', encoding='utf-8'):
            self.__append(os.path.getsize(self.OUTPUT_IMAGE_FILE), dir_my + self.FileName + '_size.txt')
        with open(self.OUTPUT_IMAGE_FILE, 'rb') as file:
            root = ext4.Volume(file).root
            dir_r = self.__out_name(os.path.basename(self.OUTPUT_IMAGE_FILE).rsplit('.', 1)[0])  # 11.05.18
            self.DIR = dir_r
            scan_dir(root)
            if dir_r == 'vendor':
                self.fs_config.insert(0, '/ 0 2000 0755')
                self.fs_config.insert(1, dir_r + ' 0 2000 0755')
            elif dir_r == 'system':
                self.fs_config.insert(0, '/ 0 0 0755')
                self.fs_config.insert(1, '/lost+found 0 0 0700')
                self.fs_config.insert(2, dir_r + ' 0 0 0755')
            else:
                self.fs_config.insert(0, '/ 0 0 0755')
                self.fs_config.insert(1, dir_r + ' 0 0 0755')

            self.__append('\n'.join(self.fs_config), self.CONFING_DIR + os.sep + fs_config_file)
            if self.context:  # 11.05.18
                for c in self.context:
                    if re.search('lost..found', c):
                        self.context.insert(0, '/' + ' ' + c.split(" ")[1])
                        self.context.insert(1, '/' + dir_r + '(/.*)? ' + c.split(" ")[1])
                        self.context.insert(2, '/' + dir_r + ' ' + c.split(" ")[1])
                        self.context.insert(3, '/' + dir_r + '/lost+\\found' + ' ' + c.split(" ")[1])
                        break

                for c in self.context:
                    if re.search('/system/system/build..prop ', c):
                        self.context.insert(3, '/lost+\\found' + ' u:object_r:rootfs:s0')
                        self.context.insert(4, '/' + dir_r + '/' + dir_r + '(/.*)? ' + c.split(" ")[1])
                        break
                self.__append('\n'.join(sorted(self.context)), contexts)  # 11.05.18

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

    def main(self, target, output_dir, work):
        self.BASE_DIR = (os.path.realpath(os.path.dirname(target)) + os.sep)
        self.BASE_DIR_ = output_dir + os.sep
        self.EXTRACT_DIR = os.path.realpath(os.path.dirname(output_dir)) + os.sep + self.__out_name(
            os.path.basename(output_dir))  # output_dir
        self.OUTPUT_IMAGE_FILE = self.BASE_DIR + os.path.basename(target)
        self.OUTPUT_MYIMAGE_FILE = os.path.basename(target)
        self.MYFileName = os.path.basename(self.OUTPUT_IMAGE_FILE).replace(".img", "")
        self.FileName = self.__file_name(os.path.basename(target))
        target_type = 'img'
        self.CONFING_DIR = work + os.sep + 'config'
        if target_type == 's_img':
            print(".....Convert %s to %s" % (
                os.path.basename(target), os.path.basename(target).replace(".img", ".raw.img")))
            simg2img(target)
            target_type = 'img'
        if target_type == 'img':
            with open(os.path.abspath(self.OUTPUT_IMAGE_FILE), 'rb') as f:
                data = f.read(500000)
            if re.search(b'\x4d\x4f\x54\x4f', data):
                print(".....Finding MOTO structure! Fixing.....")
                self.fix_moto(os.path.abspath(self.OUTPUT_IMAGE_FILE))
            print("Extracting %s --> %s" % (os.path.basename(target), os.path.basename(self.EXTRACT_DIR)))
            start = dti()
            self.__ext4extractor()
            print("Done! [%s]" % (dti() - start))
