import os
import re
import struct

import ext4

if os.name == 'nt':
    from ctypes.wintypes import LPCSTR, DWORD
    from stat import FILE_ATTRIBUTE_SYSTEM
    from ctypes import windll
from timeit import default_timer as dti
from utils import simg2img

try:
    from pycase import ensure_dir_case_sensitive
except ImportError:
    ensure_dir_case_sensitive = lambda *x: ...


class Extractor:
    def __init__(self):
        self.CONFIG_DIR = None
        self.FileName = ""
        self.OUTPUT_IMAGE_FILE = ""
        self.EXTRACT_DIR = ""
        self.context = []
        self.fs_config = []
        self.space = []

    @staticmethod
    def __out_name(file_path, out=1):
        name = file_path if out == 1 else os.path.basename(file_path).rsplit('.', 1)[0]
        return name.split('-')[0].split(' ')[0].split('+')[0].split('{')[0].split('(')[0]

    @staticmethod
    def __write(msg, log):
        if not os.path.isfile(log) and not os.path.exists(log):
            open(log, 'tw', encoding='utf-8').close()
        with open(log, 'w', newline='\n') as file:
            print(msg, file=file)

    @staticmethod
    def __get_perm(arg):
        if len(arg) < 9 or len(arg) > 10:
            return
        if len(arg) > 8:
            arg = arg[1:]
        o = s = w = g = 0
        perms = {
            'r': 4,
            'w': 2,
            'x': 1
        }
        for n, sym in enumerate(arg):
            if n == 0 and perms.get(sym):
                o = perms.get(sym)
            elif n == 1 and perms.get(sym):
                o += perms.get(sym)
            elif n == 2:
                if sym == 'S':
                    s = 4
                elif perms.get(sym):
                    o += perms.get(sym)
                elif sym == 's':
                    s += 4
                    o += 1
            elif n == 3 and perms.get(sym):
                g = perms.get(sym)
            elif n == 4 and perms.get(sym):
                g += perms.get(sym)
            if n == 5:
                if perms.get(sym):
                    g += perms.get(sym)
                elif sym == 'S':
                    s += 2
                elif sym == 's':
                    s += 2
                    g += 1
            elif n == 6 and perms.get(sym):
                w = perms.get(sym)
            elif n == 7 and perms.get(sym):
                w += perms.get(sym)
            elif n == 8:
                if perms.get(sym):
                    w += perms.get(sym)
                elif sym == 'T':
                    s += 1
                elif sym == 't':
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
                if entry_inode_path[-1:] == '/' and not entry_inode.is_dir:
                    continue

                mode = self.__get_perm(entry_inode.mode_str)
                uid = entry_inode.inode.i_uid
                gid = entry_inode.inode.i_gid
                cap = ''
                link_target = ''
                tmp_path = self.FileName + entry_inode_path
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
                    self.space.append(tmp_path)
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
                        if os.name == 'nt' and windll.shell32.IsUserAnAdmin():
                            try:
                                ensure_dir_case_sensitive(dir_target)
                            except (Exception, BaseException):
                                ...
                    if os.name == 'posix' and os.geteuid() == 0:
                        os.chmod(dir_target, int(mode, 8))
                        os.chown(dir_target, uid, gid)
                    scan_dir(entry_inode, entry_inode_path)
                elif entry_inode.is_file:
                    file_target = self.EXTRACT_DIR + entry_inode_path.replace(' ', '_').replace('"', '')
                    try:
                        with open(file_target, 'wb') as out:
                            out.write(entry_inode.open_read().read())
                    except Exception and BaseException as e:
                        print(f'[E] Cannot Write to {file_target}, Reason: {e}')
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
                        elif os.name == 'nt':
                            with open(target.replace('/', os.sep), 'wb') as out:
                                out.write(b'!<symlink>' + link_target.encode('utf-16') + b'\x00\x00')
                                try:
                                    windll.kernel32.SetFileAttributesA(LPCSTR(target.encode()),
                                                                       DWORD(FILE_ATTRIBUTE_SYSTEM))
                                except Exception as e:
                                    print(e.__str__())
                    except BaseException and Exception:
                        try:
                            if link_target and link_target.isprintable():
                                if os.name == 'posix':
                                    os.symlink(link_target, target)
                                elif os.name == 'nt':
                                    with open(target.replace('/', os.sep), 'wb') as out:
                                        out.write(b'!<symlink>' + link_target.encode('utf-16') + b'\x00\x00')
                                    try:
                                        windll.kernel32.SetFileAttributesA(LPCSTR(target.encode()),
                                                                           DWORD(FILE_ATTRIBUTE_SYSTEM))
                                    except Exception as e:
                                        print(e.__str__())
                        finally:
                            ...

        if not os.path.isdir(self.CONFIG_DIR):
            os.makedirs(self.CONFIG_DIR)
        self.__write(os.path.getsize(self.OUTPUT_IMAGE_FILE), self.CONFIG_DIR + os.sep + self.FileName + '_size.txt')
        with open(self.OUTPUT_IMAGE_FILE, 'rb') as file:
            dir_r = self.FileName
            scan_dir(ext4.Volume(file).root)
            self.fs_config.insert(0, '/ 0 2000 0755' if dir_r == 'vendor' else '/ 0 0 0755')
            self.fs_config.insert(1, f'{dir_r} 0 2000 0755' if dir_r == 'vendor' else '/lost+found 0 0 0700')
            self.fs_config.insert(2 if dir_r == 'system' else 1, f'{dir_r} 0 0 0755')
            self.__write('\n'.join(self.fs_config), self.CONFIG_DIR + os.sep + self.FileName + '_fs_config')
            self.__write('\n'.join(self.space), os.path.join(self.CONFIG_DIR, self.FileName + '_space.txt'))
            p1 = p2 = 0
            if self.context:
                self.context.sort()
                for c in self.context:
                    if re.search('/system/system/build..prop ', c) and p1 == 0:
                        self.context.insert(3, '/lost+\\found u:object_r:rootfs:s0')
                        self.context.insert(4, f'/{dir_r}/{dir_r}/(/.*)? ' + c.split()[1])
                        p1 = 1
                    if re.search('lost..found', c) and p2 == 0:
                        self.context.insert(0, '/ ' + c.split()[1])
                        self.context.insert(1, f'/{dir_r}(/.*)? ' + c.split()[1])
                        self.context.insert(2, f'/{dir_r} {c.split()[1]}')
                        self.context.insert(3, f'/{dir_r}/lost+\\found ' + c.split()[1])
                        p2 = 1
                    if p1 == p2 == 1:
                        break
                self.__write('\n'.join(self.context), self.CONFIG_DIR + os.sep + self.FileName + "_file_contexts")

    @staticmethod
    def fix_moto(input_file):
        if not os.path.exists(input_file):
            return
        output_file = input_file + "_"
        if os.path.exists(output_file):
            try:
                os.remove(output_file)
            finally:
                pass
        with open(input_file, 'rb') as f:
            data = f.read(500000)
        if not re.search(b'\x4d\x4f\x54\x4f', data):
            return
        result = []
        for i in re.finditer(b'\x53\xEF', data):
            result.append(i.start() - 1080)
        offset = 0
        for i in result:
            if data[i] == 0:
                offset = i
                break
        if offset > 0:
            with open(output_file, 'wb') as o, open(input_file, 'rb') as f:
                f.seek(offset)
                data = f.read(15360)
                if data:
                    o.write(data)
        if os.path.exists(output_file):
            try:
                os.remove(input_file)
                os.rename(output_file, input_file)
            finally:
                pass

    def fix_size(self):
        orig_size = os.path.getsize(self.OUTPUT_IMAGE_FILE)
        with open(self.OUTPUT_IMAGE_FILE, 'rb+') as file:
            t = ext4.Volume(file)
            real_size = t.get_block_count * t.block_size
            if orig_size < real_size:
                print(
                    f"......Your image is smaller than expected! Expanding the file.......\n"
                    f"Expected:{real_size}\nGot:{orig_size}")
                file.truncate(real_size)

    def main(self, target: str, output_dir: str, work: str, target_type: str = 'img'):
        self.EXTRACT_DIR = os.path.realpath(os.path.dirname(output_dir)) + os.sep + self.__out_name(
            os.path.basename(output_dir))
        self.OUTPUT_IMAGE_FILE = (os.path.realpath(os.path.dirname(target)) + os.sep) + os.path.basename(target)
        self.FileName = self.__out_name(os.path.basename(target), out=0)
        self.CONFIG_DIR = work + os.sep + 'config'
        with open(self.OUTPUT_IMAGE_FILE, 'rb+') as file:
            mount = ext4.Volume(file).get_mount_point
            if mount[:1] == '/':
                mount = mount[1:]
            if '/' in mount:
                mount = mount.split('/')
                mount = mount[len(mount) - 1]
            if [True for i in [".", "@", "#"] if i in mount]:
                mount = ""
            if self.__out_name(os.path.basename(output_dir)) != mount and mount and self.FileName != 'mi_ext':
                print(
                    f"[N]:Filename appears to be wrong , We will Extract {self.OUTPUT_IMAGE_FILE} to {mount}")
                self.EXTRACT_DIR = os.path.realpath(os.path.dirname(output_dir)) + os.sep + mount
                self.FileName = mount
        if target_type == 's_img':
            simg2img(target)
            target_type = 'img'
        if target_type == 'img':
            with open(os.path.abspath(self.OUTPUT_IMAGE_FILE), 'rb') as f:
                data = f.read(500000)
            if re.search(b'\x4d\x4f\x54\x4f', data):
                print(".....MOTO structure! Fixing.....")
                self.fix_moto(os.path.abspath(self.OUTPUT_IMAGE_FILE))
            self.fix_size()
            print("Extracting %s --> %s" % (os.path.basename(target), os.path.basename(self.EXTRACT_DIR)))
            start = dti()
            self.__ext4extractor()
            print("Done! [%s]" % (dti() - start))
