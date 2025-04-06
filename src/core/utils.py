# pylint: disable=line-too-long, missing-class-docstring, missing-function-docstring
# Copyright (C) 2022-2025 The MIO-KITCHEN-SOURCE Project
#
# Licensed under the GNU AFFERO GENERAL PUBLIC LICENSE, Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.gnu.org/licenses/agpl-3.0.en.html#license-text
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import hashlib
import json
import os
import os.path
import platform
import struct
import sys
import tempfile
import traceback
from difflib import SequenceMatcher
from enum import IntEnum
from os import getcwd
from os.path import exists
from random import randint, choice
from threading import Thread
from lzma import LZMADecompressor
import tarfile
from . import blockimgdiff
from . import sparse_img
from . import update_metadata_pb2 as um
from .lpunpack import SparseImage

DataImage = blockimgdiff.DataImage

# -----
# ====================================================
#          FUNCTION: sdat2img img2sdat
#       AUTHORS: xpirt - luxi78 - howellzhu - ColdWindScholar
#          DATE: 2018-10-27 10:33:21 CEST | 2018-05-25 12:19:12 CEST
# ====================================================
# -----
# ----VALUES

# Prevent system errors
try:
    sys.set_int_max_str_digits(0)
except AttributeError:
    ...
if os.name == 'nt':
    prog_path = getcwd()
else:
    prog_path = os.path.normpath(os.path.abspath(os.path.dirname(sys.argv[0])))
    if platform.system() == 'Darwin':
        path_frags = prog_path.split(os.path.sep)
        if path_frags[-3:] == ['tool.app', 'Contents', 'MacOS']:
            path_frags = path_frags[:-3]
            prog_path = os.path.sep.join(path_frags)
project_name = None
# [header, desc, offset (if exist)]
formats = ([b'PK', "zip"], [b'OPPOENCRYPT!', "ozip"], [b'7z', "7z"], [b'\x53\xef', 'ext', 1080],
           [b'\x3a\xff\x26\xed', "sparse"], [b'\xe2\xe1\xf5\xe0', "erofs", 1024], [b"CrAU", "payload"],
           [b"AVB0", "vbmeta"], [b'\xd7\xb7\xab\x1e', "dtbo"], [b'\x10\x20\xF5\xF2', 'f2fs', 1024],
           [b'\xd0\x0d\xfe\xed', "dtb"], [b"MZ", "exe"], [b".ELF", 'elf'],
           [b'\x7fELF', 'elf'],
           [b"ANDROID!", "boot"], [b"VNDRBOOT", "vendor_boot"],
           [b'AVBf', "avb_foot"], [b'BZh', "bzip2"],
           [b'CHROMEOS', 'chrome'], [b'\x1f\x8b', "gzip"],
           [b'\x1f\x9e', "gzip"], [b'\x02\x21\x4c\x18', "lz4_legacy"],
           [b'\x03\x21\x4c\x18', 'lz4'], [b'\x04\x22\x4d\x18', 'lz4'],
           [b'\x1f\x8b\x08\x00\x00\x00\x00\x00\x02\x03', "zopfli"], [b'\xfd7zXZ', 'lzma'],
           [b'\x5d\x00', 'lzma'],
           [b']\x00\x00\x00\x04\xff\xff\xff\xff\xff\xff\xff\xff', 'lzma'], [b'\x02!L\x18', 'lz4_lg'],
           [b'\x89PNG', 'png'], [b"LOGO!!!!", 'logo', 4000], [b'\x28\xb5\x2f\xfd', 'zstd'],
           [b'(\x05\x00\x00$8"%', 'kdz'], [b"\x32\x96\x18\x74", 'dz'], [b'\xcf\xfa\xed\xfe', 'macos_bin'],
           [b'\xfa\xff\xfa\xff','pac',2116],
           [b"-rom1fs-", 'romfs'], [b'###\x00|\x00\x00\x00LOGO_TABLE\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00P', 'guoke_logo']
           )


# ----DEFS
if os.name == 'nt':
    from ctypes import windll
    kernel32 = windll.kernel32


    def terminate_process(pid):
        h_process = kernel32.OpenProcess(0x0001, False, pid)
        if h_process:
            kernel32.TerminateProcess(h_process, 0)
            kernel32.CloseHandle(h_process)
        else:
            print(f"Failed to open process with PID {pid}")
else:
    def terminate_process(pid):
        os.kill(pid, 9)

class GuoKeLogo:
    def __init__(self):
        self.offset = 8192
        self.header_size = 128

    def unpack(self, file:str, output_dir:str):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        with open(file, 'rb') as f:
            with open(os.path.join(output_dir, 'header'), 'wb') as header:
                header.write(f.read(self.header_size))
            with open(os.path.join(output_dir,'image.jpg'),'wb') as image:
                f.seek(self.offset)
                image.write(f.read())
        print("Unpack Done!")

    def pack(self, output_dir, file):
        if os.path.exists(file):
            os.remove(file)
        if not os.path.exists(os.path.join(output_dir, 'header')) or not os.path.exists(os.path.join(output_dir, 'image.jpg')):
            print('Cannot Pack The logo!:sth losing.')
        with open(file,'wb') as f:
            with open(os.path.join(output_dir, 'header'), 'rb') as header:
                f.write(header.read())
            with open(os.path.join(output_dir, 'image.jpg'), 'rb') as image:
                f.write((self.offset - self.header_size)*b'\x00')
                f.write(image.read())
        print('Pack Done!')


class Unxz:
    def __init__(self, file_path: str, remove_src: bool = True, buff_size: int = 8192):
        self.remove_src = remove_src
        self.buff_size = buff_size
        self.file_path = file_path

        if not self.file_path.endswith('.xz'):
            print('To use Unxz, File name must end with .xz, Stop.')
            return

        self.out_file = file_path.rsplit('.xz', 1)[0]
        if exists(self.out_file):
            print(f'Output file {self.out_file!r} already exist! Not overwriting.')
            return

        try:
            self.do_unxz()
        except:
            traceback.print_exc()
            try:
                os.remove(self.out_file)
            except:
                ...
        else:
            if self.remove_src:
                try:
                    os.remove(self.file_path)
                except:
                    ...


    def do_unxz(self):
        dec = LZMADecompressor()
        with open(self.file_path, 'rb') as in_fd, open(self.out_file, 'wb') as out_fd:
            while raw := in_fd.read(self.buff_size):
                while True:
                    raw = dec.decompress(raw, max_length=self.buff_size)
                    out_fd.write(raw)
                    if dec.needs_input or dec.eof:
                        break
                    raw = b''


class Sdat2img:
    def __init__(self, transfer_list_file, new_data_file, output_image_file):
        print('sdat2img binary - version: 1.3\n')
        self.transfer_list_file = transfer_list_file
        self.new_data_file = new_data_file
        self.output_image_file = output_image_file
        self.list_file = self.parse_transfer_list_file()
        block_size = 4096
        version = next(self.list_file)
        self.version = version
        next(self.list_file)
        versions = {
            1: "Lollipop 5.0",
            2: "Lollipop 5.1",
            3: "Marshmallow 6.x",
            4: "Nougat 7.x / Oreo 8.x / Pie 9.x",
        }
        print("Android {} detected!\n".format(versions.get(version, f'Unknown version {version}!\n')))
        # Don't clobber existing files to avoid accidental data loss
        try:
            output_img = open(self.output_image_file, 'wb')
        except IOError as e:
            if e.errno == 17:
                print(f'Error: the output file "{e.filename}" already exists')
                print('Remove it, rename it, or choose a different file name.')
                return
            else:
                print(e)
                return

        new_data_file = open(self.new_data_file, 'rb')
        max_file_size = 0

        for cmd, block_list in self.list_file:
            max_file_size = max(pair[1] for pair in block_list) * block_size
            for begin, block_all in block_list:
                block_count = block_all - begin
                print(f'Copying {block_count} blocks into position {begin}...')

                # Position output file
                output_img.seek(begin * block_size)

                # Copy one block at a time
                while block_count > 0:
                    output_img.write(new_data_file.read(block_size))
                    block_count -= 1

        # Make file larger if necessary
        if output_img.tell() < max_file_size:
            output_img.truncate(max_file_size)

        output_img.close()
        new_data_file.close()
        print(f'Done! Output image: {os.path.realpath(output_img.name)}')

    @staticmethod
    def rangeset(src):
        src_set = src.split(',')
        num_set = [int(item) for item in src_set]
        if len(num_set) != num_set[0] + 1:
            print(f'Error on parsing following data to rangeset:\n{src}')
            return

        return tuple([(num_set[i], num_set[i + 1]) for i in range(1, len(num_set), 2)])

    def parse_transfer_list_file(self):
        with open(self.transfer_list_file, 'r', encoding='utf-8') as trans_list:
            # First line in transfer list is the version number
            # Second line in transfer list is the total number of blocks we expect to write
            if (version := int(trans_list.readline())) >= 2 and (new_blocks := int(trans_list.readline())):
                # Third line is how many stash entries are needed simultaneously
                trans_list.readline()
                # Fourth line is the maximum number of blocks that will be stashed simultaneously
                trans_list.readline()
            # Subsequent lines are all individual transfer commands
            yield version
            yield new_blocks
            for line in trans_list:
                line = line.split(' ')
                cmd = line[0]
                if cmd == 'new':
                    # if cmd in ['erase', 'new', 'zero']:
                    yield [cmd, self.rangeset(line[1])]
                else:
                    if cmd in ['erase', 'new', 'zero']:
                        print(f'Skipping command {cmd}...')
                        continue
                    # Skip lines starting with numbers, they are not commands anyway
                    if not cmd[0].isdigit():
                        print(f'Command "{cmd}" is not valid.')
                        return

def get_all_file_paths(directory):
    for root, _, files in os.walk(directory):
        for filename in files:
            yield os.path.join(root, filename)
def zero_start(file: str, c: int, buff_size: int = 8192) -> bool:
    with open(file, 'rb') as f:
        zeros_ = bytearray(buff_size)
        while c:
            buf = f.read(min(c, buff_size))
            n = len(buf)
            if n != len(zeros_):
                # short read?
                zeros_ = bytearray(n)
            if buf != zeros_:
                return False
            c -= n
    return True
is_empty_img = lambda file: zero_start(file, os.path.getsize(file))
def gettype(file) -> str:
    """
    Return File Type:str
    :param file: file path
    :return:
    """
    if not os.path.isfile(file):
        return 'fnf'
    if not os.path.exists(file):
        return "fne"

    def is_super(fil) -> any:
        with open(fil, 'rb') as file_:
            try:
                file_.seek(4096, 0)
                return file_.read(4) == b'\x67\x44\x6c\x61'
            except EOFError:
                return False

    try:
        if is_super(file):
            return 'super'
    except IndexError:
        ...
    for header, desc, *offset in formats:
        with open(file, 'rb') as f:
            f.seek(offset[0] if offset else 0)
            if f.read(len(header)) == header:
                return desc

    if not zero_start(file, 512) and tarfile.is_tarfile(file):
        return 'tar'
    try:
        if LogoDumper(file, str(None)).check_img(file):
            return 'logo'
    except AssertionError:
        ...
    except struct.error:
        ...
    return "unknown"


def dynamic_list_reader(path):
    """
    read dynamic_list and return a dict
    :param path:
    :return:
    """
    data = {}
    with open(path, 'r', encoding='utf-8') as l_f:
        for p in l_f.readlines():
            if p[:1] == '#':
                continue
            tmp = p.strip().split()
            if tmp[0] == 'remove_all_groups':
                data.clear()
            elif tmp[0] == 'add_group':
                data[tmp[1]] = {}
                data[tmp[1]]['size'] = tmp[2]
                data[tmp[1]]['parts'] = []
            elif tmp[0] == 'add':
                data[tmp[2]]['parts'].append(tmp[1])
    return data



def generate_dynamic_list(group_name:str, size:int, super_type:int, part_list:list, work):
    data = ['# Remove all existing dynamic partitions and groups before applying full OTA', 'remove_all_groups']
    with open(f"{work}/dynamic_partitions_op_list", 'w', encoding='utf-8', newline='\n') as d_list:
        if super_type == 1:
            data.append(f'# Add group {group_name} with maximum size {size}')
            data.append(f'add_group {group_name} {size}')
        elif super_type in [2, 3]:
            data.append(f'# Add group {group_name}_a with maximum size {size}')
            data.append(f'add_group {group_name}_a {size}')
            data.append(f'# Add group {group_name}_b with maximum size {size}')
            data.append(f'add_group {group_name}_b {size}')
        for part in part_list:
            if super_type == 1:
                data.append(f'# Add partition {part} to group {group_name}')
                data.append(f'add {part} {group_name}')
            elif super_type in [2, 3]:
                data.append(f'# Add partition {part}_a to group {group_name}_a')
                data.append(f'add {part}_a {group_name}_a')
                data.append(f'# Add partition {part}_b to group {group_name}_b')
                data.append(f'add {part}_b {group_name}_b')
        for part in part_list:
            if super_type == 1:
                data.append(f'# Grow partition {part} from 0 to {os.path.getsize(f"{work}/{part}.img")}')
                data.append(f'resize {part} {os.path.getsize(f"{work}/{part}.img")}')
            elif super_type in [2, 3]:
                data.append(f'# Grow partition {part}_a from 0 to {os.path.getsize(f"{work}/{part}.img")}')
                data.append(f'resize {part}_a {os.path.getsize(f"{work}/{part}.img")}')
        d_list.writelines([f"{key}\n" for key in data])
        data.clear()


def v_code(num=6) -> str:
    """
    Get Random Str in Number and words
    :param num: number of Random Str
    :return:
    """
    ret = ""
    for i in range(num):
        num = randint(0, i)
        # num = chr(random.randint(48,57))#ASCII表示数字
        letter = chr(randint(97, 122))  # 取小写字母
        letter_ = chr(randint(65, 90))  # 取大写字母
        s = str(choice([num, letter, letter_]))
        ret += s
    return ret


def qc(file_) -> None:
    """
    remove Same Line of File
    :param file_:
    :return:
    """
    if not exists(file_):
        return
    with open(file_, 'r+', encoding='utf-8', newline='\n') as f:
        data = f.readlines()
        data = sorted(set(data), key=data.index)
        f.seek(0)
        f.truncate()
        f.writelines(data)
    del data

def create_thread(func, *args, join=False, deamon:bool=True):
    """
    Multithreaded running tasks
    :param deamon:
    :param func: Function
    :param args:Args for the task
    :param join:if wait the task
    :return:
    """
    t = Thread(target=func, args=args, daemon=deamon)
    t.start()
    if join:
        t.join()


def simg2img(path):
    """
    convert Sparse image to Raw Image
    :param path:
    :return:
    """
    with open(path, 'rb') as fd:
        if SparseImage(fd).check():
            print('Sparse image detected.')
            print('Converting to raw image...')
            unsparse_file = SparseImage(fd).unsparse()
            print('Result:[ok]')
        else:
            print(f"{path} not Sparse.Skip!")
    try:
        if os.path.exists(unsparse_file):
            os.remove(path)
            os.rename(unsparse_file, path)
    except Exception as e:
        print(e)


def img2sdat(input_image, out_dir='.', version=None, prefix='system'):
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    versions = {
        1: "Android Lollipop 5.0",
        2: "Android Lollipop 5.1",
        3: "Android Marshmallow 6.0",
        4: "Android Nougat 7.0/7.1/8.0/8.1"}
    if version not in versions.keys():
        version = 4
    print(f"Img2sdat(1.7):{versions[version]}")
    blockimgdiff.BlockImageDiff(sparse_img.SparseImage(input_image, tempfile.mkstemp()[1], '0'), None, version).Compute(
        f'{out_dir}/{prefix}')


def findfile(file, dir_) -> str:
    for root, _, files in os.walk(dir_, topdown=True):
        if file in files:
            if os.name == 'nt':
                return f'{root}/{file}'.replace("\\", '/')
            else:
                return f'{root}/{file}'
    return ''


def findfolder(dir__, folder_name):
    """
    Find Folder
    :param dir__: dir that need Search
    :param folder_name: folder name need found
    :return:
    """
    for root, dirnames, _ in os.walk(dir__):
        for dirname in dirnames:
            if dirname == folder_name:
                return os.path.join(root, dirname).replace("\\", '/')
    return None


def move_center(master):
    """
    Replace Toplevel or Tk to Center
    :param master: Window
    :return:
    """
    master.geometry(
        f'+{int(master.winfo_screenwidth() / 2 - master.winfo_width() / 2)}+{int(master.winfo_screenheight() / 2 - master.winfo_height() / 2)}')
    master.update()


# ----CLASSES
class LangUtils:
    def __init__(self):
        self.second = {}

    def __getattr__(self, item):
        try:
            return self.__getattribute__(item)
        except (AttributeError, ):
            return self.second.get(item, 'None')


lang = LangUtils()

u64 = lambda x:struct.unpack('>Q', x)[0]

def payload_reader(payloadfile):
    """
    Read Payload.bin Return dam
    :param payloadfile: File Path
    :return:
    """
    if payloadfile.read(4) != b'CrAU':
        print("Magic Check Fail\n")
        payloadfile.close()
        return um
    file_format_version = u64(payloadfile.read(8))
    assert file_format_version == 2
    manifest_size = u64(payloadfile.read(8))
    metadata_signature_size = struct.unpack('>I', payloadfile.read(4))[0] if file_format_version > 1 else 0
    manifest = payloadfile.read(manifest_size)
    payloadfile.read(metadata_signature_size)
    dam = um.DeltaArchiveManifest()
    dam.ParseFromString(manifest)
    return dam


class Vbpatch:
    def __init__(self, file_):
        self.file = file_
        self.disavb = lambda: self.patchvb(b'\x02')

    def checkmagic(self) -> bool:
        """
        Check The Magic if vbmeta
        :return:
        """
        if os.access(self.file, os.F_OK):
            with open(self.file, "rb") as f:
                return b'AVB0' == f.read(4)
        else:
            print("File does not exist!")
        return False

    def patchvb(self, flag):
        if not self.checkmagic():
            return False
        if os.access(self.file, os.F_OK):
            with open(self.file, 'rb+') as f:
                f.seek(123, 0)
                f.write(flag)
            print("Done!")
        else:
            print("File not Found")
            return False
        return True


class Dumpcfg:
    blksz = 4096
    headoff = 16384
    magic = b"LOGO!!!!"
    imgnum = 0
    imgblkoffs = []
    imgblkszs = []


class Bmphead:
    def __init__(self, buf: bytes = None):  # Read bytes buf and use this struct to parse
        assert buf is not None, f"buf Should be bytes, not {type(buf)}"
        # print(buf)
        (
            self.magic,
            self.fsize,
            self.reserved,
            self.hsize,
            self.dib,
            self.width,
            self.height,
        ) = struct.unpack("<H6I", buf)


class XiaomiBlkstruct:
    def __init__(self, buf: bytes):
        self.img_offset, self.blksz = struct.unpack("2I", buf)


class LogoDumper:
    def __init__(self, img: str, out: str, dir__: str = "pic"):
        self.magic = None
        self.out = out
        self.img = img
        self.dir = dir__
        self.struct_str = "<8s"
        self.cfg = Dumpcfg()
        self.check_img(img)

    def check_img(self, img: str):
        """
        Check The Img If Unpack Able
        :param img:
        :return:
        """
        assert os.access(img, os.F_OK), f"{img} does not exist!"
        with open(img, 'rb') as f:
            f.seek(self.cfg.headoff, 0)
            self.magic = struct.unpack(
                self.struct_str, f.read(struct.calcsize(self.struct_str))
            )[0]
            while True:
                m = XiaomiBlkstruct(f.read(8))
                if m.img_offset != 0:
                    self.cfg.imgblkszs.append(m.blksz << 0xc)
                    self.cfg.imgblkoffs.append(m.img_offset << 0xc)
                    self.cfg.imgnum += 1
                else:
                    break
        assert self.magic == b"LOGO!!!!", "File does not match xiaomi logo magic!"
        return True

    def unpack(self):
        """
        Unpack Logo Img, Output To self.out
        :return:
        """
        with open(self.img, 'rb') as f:
            print("Unpack:\n"
                  "BMP\tSize\tWidth\tHeight")
            for i in range(self.cfg.imgnum):
                f.seek(self.cfg.imgblkoffs[i], 0)
                bmp_h = Bmphead(f.read(26))
                f.seek(self.cfg.imgblkoffs[i], 0)
                print(f"{i:d}\t{bmp_h.fsize:d}\t{bmp_h.width:d}\t{bmp_h.height:d}")
                with open(os.path.join(self.out, f"{i}.bmp"), 'wb') as o:
                    o.write(f.read(bmp_h.fsize))
            print("\tDone!")

    def repack(self) -> None:
        """
        Repack Logo Img
        :return:
        """
        with open(self.out, 'wb') as o:
            off = 0x5
            for i in range(self.cfg.imgnum):
                print(f"Write BMP [{i:d}.bmp] at offset 0x{off << 0xc:X}")
                with open(os.path.join(self.dir, f"{i}.bmp"), 'rb') as b:
                    bmp_head = Bmphead(b.read(26))
                    b.seek(0, 0)
                    self.cfg.imgblkszs[i] = (bmp_head.fsize >> 0xc) + 1
                    self.cfg.imgblkoffs[i] = off
                    o.seek(off << 0xc)
                    o.write(b.read(bmp_head.fsize))
                    off += self.cfg.imgblkszs[i]
            o.seek(self.cfg.headoff)
            o.write(self.magic)
            for i in range(self.cfg.imgnum):
                o.write(struct.pack("<I", self.cfg.imgblkoffs[i]))
                o.write(struct.pack("<I", self.cfg.imgblkszs[i]))
            print("\tDone!")

class States:
    update_window = False
    donate_window = False
    mpk_store = False
    open_pids = []
    run_source = gettype(sys.argv[0]) == "unknown"
    in_oobe = False
    development = False
    inited = False
    open_source_license = "GNU AFFERO GENERAL PUBLIC LICENSE V3"

def hashlib_calculate(file_path, method: str):
    if not hasattr(hashlib, method):
        print(f"Warn, The algorithm {method} not exist in hashlib!")
        return 1
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        print(f"Warn, The file {file_path} not exist!")
        return 1
    algorithm = getattr(hashlib, method)()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            algorithm.update(chunk)
    return algorithm.hexdigest()


calculate_sha256_file = lambda file_path: hashlib_calculate(file_path, 'sha256')
calculate_md5_file = lambda file_path: hashlib_calculate(file_path, 'md5')

class JsonEdit:
    def __init__(self, file_path):
        self.file = file_path

    def read(self):
        if not os.path.exists(self.file):
            return {}
        with open(self.file, 'r+', encoding='utf-8') as pf:
            try:
                return json.load(pf)
            except (AttributeError, ValueError, json.decoder.JSONDecodeError):
                return {}

    def write(self, data):
        with open(self.file, 'w+', encoding='utf-8') as pf:
            json.dump(data, pf, indent=4)

    def edit(self, name, value):
        data = self.read()
        data[name] = value
        self.write(data)

class MkcSugges:
    def __init__(self, help_file:str = 'None'):
        if not help_file:
            self.help_file = os.path.join(prog_path, 'bin', 'help_document.json')
        else:
            self.help_file = help_file
        with open(self.help_file, 'r', encoding='utf-8') as f:
            self.library = json.load(f)

    def get(self, language: str, prompt: str):
        similarity = 0
        text = f"No idea about:\n\t{prompt}\nPlease Report It To us."
        detail = 'Unknown'
        if prompt:
            for i in self.library.keys():
                if not language in self.library[i]:
                    language = 'English'
                if 'detail' in self.library[i]:
                    try:
                        detail = self.library[i]['detail'][language]
                    except (ValueError, KeyError):
                        detail = 'Unknown'
                similarity_ = SequenceMatcher(None, i, prompt).quick_ratio()
                if similarity_ >= 0.8:
                    text = self.library[i][language]
                    break
                else:
                    similarity = max(similarity_, similarity)
                    if similarity < 0.5:
                        break
                    else:
                        text = self.library[i][language]
                        break
            return text, detail
        else:
            return None, None

    def catch_error(self, string):
        catch_error = [i for i in string.split("\n") if 'error' in i or 'failed' in i]
        if not catch_error:
            return
        else:
            catch_error = catch_error[0]
        if not catch_error:
            return
        return catch_error

class DevNull:
    def __init__(self):
        self.data = ''

    def write(self, string):
        self.data += string

    def flush(self):
        ...

def hum_convert(value):
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = 1024.0
    for i in range(len(units)):
        if (value / size) < 1:
            return f"{value:.2f}{units[i]}"
        value = value / size

class ModuleErrorCodes(IntEnum):
    Normal = 0
    PlatformNotSupport = 1
    DependsMissing = 2
    IsBroken = 3

