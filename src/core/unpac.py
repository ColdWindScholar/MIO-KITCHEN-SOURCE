#!/usr/bin/env python3

# source from https://github.com/ilyakurdyukov/spreadtrum_flash/blob/main/unpac/unpac.c
# rewritten to python by affggh
import ctypes
from io import SEEK_SET
from os import makedirs
from os.path import exists
from os.path import join as path_join
from enum import Enum

class common_struct(ctypes.LittleEndianStructure):
    @property
    def _size(self):
        return ctypes.sizeof(type(self))

    def __len__(self):
        return self._size

    def unpack(self, data: bytes):
        if len(data) < self._size:
            raise Exception("Input data size less than struct size.")
        if not isinstance(data, (bytes, bytearray)):
            raise Exception("Input data must be byte data or bytearray.")

        return ctypes.memmove(ctypes.byref(self), data, self._size)

    def pack(self) -> bytes:
        return bytes(self)


class sprd_head(common_struct):
    _fields_ = [
        ("pac_version", ctypes.c_uint16 * 24),
        ("pac_size", ctypes.c_uint32),
        ("fw_name", ctypes.c_uint16 * 256),
        ("fw_version", ctypes.c_uint16 * 256),
        ("file_count", ctypes.c_uint32),
        ("dir_offset", ctypes.c_uint32),
        ("unknow1", ctypes.c_uint32 * 5),
        ("fw_alias", ctypes.c_uint16 * 100),
        ("unknow2", ctypes.c_uint32 * 3),
        ("unknow", ctypes.c_uint32 * 200),
        ("pac_magic", ctypes.c_uint32),
        ("head_crc", ctypes.c_uint16),
        ("data_crc", ctypes.c_uint16),
    ]


class sprd_file(common_struct):
    _fields_ = [
        ("struct_size", ctypes.c_uint32),
        ("id", ctypes.c_uint16 * 256),
        ("name", ctypes.c_uint16 * 256),
        ("unknow1", ctypes.c_uint16 * 256),
        ("size", ctypes.c_uint32),
        ("type", ctypes.c_uint32),
        ("flash_use", ctypes.c_uint32),
        ("pac_offset", ctypes.c_uint32),
        ("omit_flag", ctypes.c_uint32),
        ("addr_num", ctypes.c_uint32),
        ("addr", ctypes.c_uint32 * 5),
        ("unknow2", ctypes.c_uint32 * 249),
    ]


def convert_u16_to_string(data):
    byte_data: bytes = bytes(data)
    return byte_data.decode("utf-16")

class file_types(Enum):
    operation = 0
    file = 1
    xml = 2
    fdl = 0x101
class MODE(Enum):
    NONE = 0
    LIST = 1
    EXTRACT = 2
    CHECK = 3



def crc16(crc: int, src: bytes):
    for byte in src:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0xA001 if (crc & 1) else 0)
    return crc

def check_path(path):
    INVALID_STR = ["/", "\\", ":"]
    for s in INVALID_STR:
        if s in path:
            return False
    return True

def unpac(image_path: str, out_dir:str, mode: MODE = MODE.LIST):
    if not exists(out_dir):
        makedirs(out_dir, exist_ok=True)
    chunk = 0x1000
    head = sprd_head()
    # file = sprd_file()

    with open(image_path, "rb") as fi:
        head.unpack(fi.read(len(head)))

        if head.pac_magic != 0xFFFAFFFA:  # ~0x50005u
            raise Exception("Bad pac_magic!")

        if mode == MODE.LIST:
            print("pac_version: %s" % convert_u16_to_string(head.pac_version))
            print("pac_size: %u" % head.pac_size)

            print("fw_name: %s" % convert_u16_to_string(head.fw_version))
            print("fw_version: %s" % convert_u16_to_string(head.fw_version))
            print("fw_alias: %s" % convert_u16_to_string(head.fw_alias))

        if mode == MODE.LIST or mode == MODE.CHECK:
            head_crc = crc16(0, head.pack()[: len(head) - 4])
            print("head_crc: 0x%04x" % head.head_crc)
            if head.head_crc != head_crc:
                print("(expected 0x%04x)" % head_crc)

        if head.dir_offset != len(head):
            raise Exception("unexpected directory offset")

        if (head.file_count >> 10) != 0:
            raise Exception("too many files")

        if mode == MODE.LIST or mode == MODE.EXTRACT:
            for i in range(head.file_count):
                file = sprd_file()
                file.unpack(fi.read(len(file)))

                if file.struct_size != len(file):
                    raise Exception("unexpected struct size")
            
                if mode == MODE.EXTRACT:
                    if (file.name[0] == 0) or (file.pac_offset == 0) or (file.size == 0): continue

                if mode == MODE.LIST:
                    print(f"type = {file_types(file.type).name}", end='')
                    if file.size > 0:
                        print(", size = 0x%x" %file.size, end='')
                    if file.pac_offset > 0:
                        print(", offset = 0x%x" %file.pac_offset, end='')
                    
                    if file.addr_num <= 5:
                        for j in range(file.addr_num):
                            if file.addr[j] == 0: continue
                            if j <= 0: print(", addr = 0x%x" % file.addr[j], end='')
                            else: print(", addr%u = 0x%x" %(j, file.addr[j]), end='')
                    
                    if file.id[0] != 0:
                        print(", id = \"%s\"" %convert_u16_to_string(file.id), end='')
                    
                    if file.name[0] != 0:
                        print(", name = \"%s\"" %convert_u16_to_string(file.name), end='')
                    
                    print()
                else:
                    file_name = convert_u16_to_string(file.name).strip("\0")
                    print(file_name)

                    fi.seek(file.pac_offset, SEEK_SET)
                    if not check_path(file_name):
                        print("!!! unsafe filename detected!")
                        continue

                    with open(path_join(out_dir, file_name), 'wb') as fo:
                        l = file.size
                        for n in range(0, l, chunk):
                            buf  = fi.read(chunk if l - n > chunk else l - n)
                            fo.write(buf)
                    
                    fi.seek(len(head) + (i + 1) * len(file), SEEK_SET)

        elif mode == MODE.CHECK:
            l = head.pac_size
            data_crc = 0
            n = head._size

            if l < n:
                raise Exception("unexpected pac size")
            for n in range(0, l, chunk):
                buf = fi.read(chunk if l - n > chunk else l - n)
                data_crc = crc16(data_crc, buf)

            print("data_crc: 0x%04x" %head.data_crc)
            if head.data_crc != data_crc:
                print("(ecpected 0x%04x)" %data_crc)
            
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(prog="unpac", usage="<list|extract|check> -d out pac_file")
    parser.add_argument("command")
    parser.add_argument("-d,--dir", metavar="outdir", dest="outdir")
    parser.add_argument("pac_file")

    args = parser.parse_args()

    command = args.command
    outdir = "out"
    if args.outdir:
        outdir = args.outdir
    
    pac_file = args.pac_file

    mode = MODE.NONE

    if command == "list":
        mode = MODE.LIST
    elif command == "check":
        mode = MODE.CHECK
    elif command == "extract":
        mode = MODE.EXTRACT
    else:
        raise Exception("Unsupported command")
    
    if not exists(outdir):
        makedirs(outdir)

    unpac(pac_file, outdir, mode)
