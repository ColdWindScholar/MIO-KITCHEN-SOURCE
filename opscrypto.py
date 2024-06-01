#!/usr/bin/env python3

# Oneplus Decrypter (c) V 1.4 B.Kerler 2019-2022
# Licensed under MIT License


import shutil

import os
from struct import pack, unpack
import xml.etree.ElementTree as et
import hashlib
from pathlib import Path
from queue import Queue

import mmap


def mmap_io(filename, mode, length=0):
    if mode == "rb":
        with open(filename, mode="rb") as file_obj:
            return mmap.mmap(file_obj.fileno(), length=0, access=mmap.ACCESS_READ)
    elif mode == "wb":
        if os.path.exists(filename):
            length = os.stat(filename).st_size
        else:
            with open(filename, "wb") as wf:
                wf.write(length * b'\0')
        with open(filename, mode="r+b") as file_obj:
            return mmap.mmap(file_obj.fileno(), length=length, access=mmap.ACCESS_WRITE)
        # mmap_obj.flush() on finish


key = unpack("<4I", b'\xd1\xb5\xe3\x9e^\xea\x04\x9dg\x1d\xd5\xab\xd2\xaf\xcb\xaf')

# guacamoles_31_O.09_190820
mbox5 = [0x60, 0x8a, 0x3f, 0x2d, 0x68, 0x6b, 0xd4, 0x23, 0x51, 0x0c,
         0xd0, 0x95, 0xbb, 0x40, 0xe9, 0x76, 0x00, 0x00, 0x00, 0x00,
         0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
         0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
         0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
         0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
         0x0a, 0x00]
# instantnoodlev_15_O.07_201103
mbox6 = [0xAA, 0x69, 0x82, 0x9E, 0x5D, 0xDE, 0xB1, 0x3D, 0x30, 0xBB,
         0x81, 0xA3, 0x46, 0x65, 0xa3, 0xe1, 0x00, 0x00, 0x00, 0x00,
         0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
         0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
         0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
         0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
         0x0a, 0x00]
# guacamolet_21_O.08_190502
mbox4 = [0xC4, 0x5D, 0x05, 0x71, 0x99, 0xDD, 0xBB, 0xEE, 0x29, 0xA1,
         0x6D, 0xC7, 0xAD, 0xBF, 0xA4, 0x3F, 0x00, 0x00, 0x00, 0x00,
         0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
         0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
         0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
         0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
         0x0a, 0x00]

sbox = b'\xc6cc\xa5\xc6cc\xa5\xf8||\x84\xf8||\x84\xeeww\x99\xeeww\x99\xf6{{\x8d\xf6{{\x8d\xff\xf2\xf2\r\xff\xf2\xf2\r\xd6kk\xbd\xd6kk\xbd\xdeoo\xb1\xdeoo\xb1\x91\xc5\xc5T\x91\xc5\xc5T`00P`00P\x02\x01\x01\x03\x02\x01\x01\x03\xcegg\xa9\xcegg\xa9V++}V++}\xe7\xfe\xfe\x19\xe7\xfe\xfe\x19\xb5\xd7\xd7b\xb5\xd7\xd7bM\xab\xab\xe6M\xab\xab\xe6\xecvv\x9a\xecvv\x9a\x8f\xca\xcaE\x8f\xca\xcaE\x1f\x82\x82\x9d\x1f\x82\x82\x9d\x89\xc9\xc9@\x89\xc9\xc9@\xfa}}\x87\xfa}}\x87\xef\xfa\xfa\x15\xef\xfa\xfa\x15\xb2YY\xeb\xb2YY\xeb\x8eGG\xc9\x8eGG\xc9\xfb\xf0\xf0\x0b\xfb\xf0\xf0\x0bA\xad\xad\xecA\xad\xad\xec\xb3\xd4\xd4g\xb3\xd4\xd4g_\xa2\xa2\xfd_\xa2\xa2\xfdE\xaf\xaf\xeaE\xaf\xaf\xea#\x9c\x9c\xbf#\x9c\x9c\xbfS\xa4\xa4\xf7S\xa4\xa4\xf7\xe4rr\x96\xe4rr\x96\x9b\xc0\xc0[\x9b\xc0\xc0[u\xb7\xb7\xc2u\xb7\xb7\xc2\xe1\xfd\xfd\x1c\xe1\xfd\xfd\x1c=\x93\x93\xae=\x93\x93\xaeL&&jL&&jl66Zl66Z~??A~??A\xf5\xf7\xf7\x02\xf5\xf7\xf7\x02\x83\xcc\xccO\x83\xcc\xccOh44\\h44\\Q\xa5\xa5\xf4Q\xa5\xa5\xf4\xd1\xe5\xe54\xd1\xe5\xe54\xf9\xf1\xf1\x08\xf9\xf1\xf1\x08\xe2qq\x93\xe2qq\x93\xab\xd8\xd8s\xab\xd8\xd8sb11Sb11S*\x15\x15?*\x15\x15?\x08\x04\x04\x0c\x08\x04\x04\x0c\x95\xc7\xc7R\x95\xc7\xc7RF##eF##e\x9d\xc3\xc3^\x9d\xc3\xc3^0\x18\x18(0\x18\x18(7\x96\x96\xa17\x96\x96\xa1\n\x05\x05\x0f\n\x05\x05\x0f/\x9a\x9a\xb5/\x9a\x9a\xb5\x0e\x07\x07\t\x0e\x07\x07\t$\x12\x126$\x12\x126\x1b\x80\x80\x9b\x1b\x80\x80\x9b\xdf\xe2\xe2=\xdf\xe2\xe2=\xcd\xeb\xeb&\xcd\xeb\xeb&N\'\'iN\'\'i\x7f\xb2\xb2\xcd\x7f\xb2\xb2\xcd\xeauu\x9f\xeauu\x9f\x12\t\t\x1b\x12\t\t\x1b\x1d\x83\x83\x9e\x1d\x83\x83\x9eX,,tX,,t4\x1a\x1a.4\x1a\x1a.6\x1b\x1b-6\x1b\x1b-\xdcnn\xb2\xdcnn\xb2\xb4ZZ\xee\xb4ZZ\xee[\xa0\xa0\xfb[\xa0\xa0\xfb\xa4RR\xf6\xa4RR\xf6v;;Mv;;M\xb7\xd6\xd6a\xb7\xd6\xd6a}\xb3\xb3\xce}\xb3\xb3\xceR)){R)){\xdd\xe3\xe3>\xdd\xe3\xe3>^//q^//q\x13\x84\x84\x97\x13\x84\x84\x97\xa6SS\xf5\xa6SS\xf5\xb9\xd1\xd1h\xb9\xd1\xd1h\x00\x00\x00\x00\x00\x00\x00\x00\xc1\xed\xed,\xc1\xed\xed,@  `@  `\xe3\xfc\xfc\x1f\xe3\xfc\xfc\x1fy\xb1\xb1\xc8y\xb1\xb1\xc8\xb6[[\xed\xb6[[\xed\xd4jj\xbe\xd4jj\xbe\x8d\xcb\xcbF\x8d\xcb\xcbFg\xbe\xbe\xd9g\xbe\xbe\xd9r99Kr99K\x94JJ\xde\x94JJ\xde\x98LL\xd4\x98LL\xd4\xb0XX\xe8\xb0XX\xe8\x85\xcf\xcfJ\x85\xcf\xcfJ\xbb\xd0\xd0k\xbb\xd0\xd0k\xc5\xef\xef*\xc5\xef\xef*O\xaa\xaa\xe5O\xaa\xaa\xe5\xed\xfb\xfb\x16\xed\xfb\xfb\x16\x86CC\xc5\x86CC\xc5\x9aMM\xd7\x9aMM\xd7f33Uf33U\x11\x85\x85\x94\x11\x85\x85\x94\x8aEE\xcf\x8aEE\xcf\xe9\xf9\xf9\x10\xe9\xf9\xf9\x10\x04\x02\x02\x06\x04\x02\x02\x06\xfe\x7f\x7f\x81\xfe\x7f\x7f\x81\xa0PP\xf0\xa0PP\xf0x<<Dx<<D%\x9f\x9f\xba%\x9f\x9f\xba\x8a?\x92\x92\xad?\x92\x92\xad!\x9d\x9d\xbc!\x9d\x9d\xbcp88Hp88H\xf1\xf5\xf5\x04\xf1\xf5\xf5\x04c\xbc\xbc\xdfc\xbc\xbc\xdfw\xb6\xb6\xc1w\xb6\xb6\xc1\xaf\xda\xdau\xaf\xda\xdauB!!cB!!c \x10\x100 \x10\x100\xe5\xff\xff\x1a\xe5\xff\xff\x1a\xfd\xf3\xf3\x0e\xfd\xf3\xf3\x0e\xbf\xd2\xd2m\xbf\xd2\xd2m\x81\xcd\xcdL\x81\xcd\xcdL\x18\x0c\x0c\x14\x18\x0c\x0c\x14&\x13\x135&\x13\x135\xc3\xec\xec/\xc3\xec\xec/\xbe__\xe1\xbe__\xe15\x97\x97\xa25\x97\x97\xa2\x88DD\xcc\x88DD\xcc.\x17\x179.\x17\x179\x93\xc4\xc4W\x93\xc4\xc4WU\xa7\xa7\xf2U\xa7\xa7\xf2\xfc~~\x82\xfc~~\x82z==Gz==G\xc8dd\xac\xc8dd\xac\xba]]\xe7\xba]]\xe72\x19\x19+2\x19\x19+\xe6ss\x95\xe6ss\x95\xc0``\xa0\xc0``\xa0\x19\x81\x81\x98\x19\x81\x81\x98\x9eOO\xd1\x9eOO\xd1\xa3\xdc\xdc\x7f\xa3\xdc\xdc\x7fD""fD""fT**~T**~;\x90\x90\xab;\x90\x90\xab\x0b\x88\x88\x83\x0b\x88\x88\x83\x8cFF\xca\x8cFF\xca\xc7\xee\xee)\xc7\xee\xee)k\xb8\xb8\xd3k\xb8\xb8\xd3(\x14\x14<(\x14\x14<\xa7\xde\xdey\xa7\xde\xdey\xbc^^\xe2\xbc^^\xe2\x16\x0b\x0b\x1d\x16\x0b\x0b\x1d\xad\xdb\xdbv\xad\xdb\xdbv\xdb\xe0\xe0;\xdb\xe0\xe0;d22Vd22Vt::Nt::N\x14\n\n\x1e\x14\n\n\x1e\x92II\xdb\x92II\xdb\x0c\x06\x06\n\x0c\x06\x06\nH$$lH$$l\xb8\\\\\xe4\xb8\\\\\xe4\x9f\xc2\xc2]\x9f\xc2\xc2]\xbd\xd3\xd3n\xbd\xd3\xd3nC\xac\xac\xefC\xac\xac\xef\xc4bb\xa6\xc4bb\xa69\x91\x91\xa89\x91\x91\xa81\x95\x95\xa41\x95\x95\xa4\xd3\xe4\xe47\xd3\xe4\xe47\xf2yy\x8b\xf2yy\x8b\xd5\xe7\xe72\xd5\xe7\xe72\x8b\xc8\xc8C\x8b\xc8\xc8Cn77Yn77Y\xdamm\xb7\xdamm\xb7\x01\x8d\x8d\x8c\x01\x8d\x8d\x8c\xb1\xd5\xd5d\xb1\xd5\xd5d\x9cNN\xd2\x9cNN\xd2I\xa9\xa9\xe0I\xa9\xa9\xe0\xd8ll\xb4\xd8ll\xb4\xacVV\xfa\xacVV\xfa\xf3\xf4\xf4\x07\xf3\xf4\xf4\x07\xcf\xea\xea%\xcf\xea\xea%\xcaee\xaf\xcaee\xaf\xf4zz\x8e\xf4zz\x8eG\xae\xae\xe9G\xae\xae\xe9\x10\x08\x08\x18\x10\x08\x08\x18o\xba\xba\xd5o\xba\xba\xd5\xf0xx\x88\xf0xx\x88J%%oJ%%o\\..r\\..r8\x1c\x1c$8\x1c\x1c$W\xa6\xa6\xf1W\xa6\xa6\xf1s\xb4\xb4\xc7s\xb4\xb4\xc7\x97\xc6\xc6Q\x97\xc6\xc6Q\xcb\xe8\xe8#\xcb\xe8\xe8#\xa1\xdd\xdd|\xa1\xdd\xdd|\xe8tt\x9c\xe8tt\x9c>\x1f\x1f!>\x1f\x1f!\x96KK\xdd\x96KK\xdda\xbd\xbd\xdca\xbd\xbd\xdc\r\x8b\x8b\x86\r\x8b\x8b\x86\x0f\x8a\x8a\x85\x0f\x8a\x8a\x85\xe0pp\x90\xe0pp\x90|>>B|>>Bq\xb5\xb5\xc4q\xb5\xb5\xc4\xccff\xaa\xccff\xaa\x90HH\xd8\x90HH\xd8\x06\x03\x03\x05\x06\x03\x03\x05\xf7\xf6\xf6\x01\xf7\xf6\xf6\x01\x1c\x0e\x0e\x12\x1c\x0e\x0e\x12\xc2aa\xa3\xc2aa\xa3j55_j55_\xaeWW\xf9\xaeWW\xf9i\xb9\xb9\xd0i\xb9\xb9\xd0\x17\x86\x86\x91\x17\x86\x86\x91\x99\xc1\xc1X\x99\xc1\xc1X:\x1d\x1d\':\x1d\x1d\'\'\x9e\x9e\xb9\'\x9e\x9e\xb9\xd9\xe1\xe18\xd9\xe1\xe18\xeb\xf8\xf8\x13\xeb\xf8\xf8\x13+\x98\x98\xb3+\x98\x98\xb3"\x11\x113"\x11\x113\xd2ii\xbb\xd2ii\xbb\xa9\xd9\xd9p\xa9\xd9\xd9p\x07\x8e\x8e\x89\x07\x8e\x8e\x893\x94\x94\xa73\x94\x94\xa7-\x9b\x9b\xb6-\x9b\x9b\xb6<\x1e\x1e"<\x1e\x1e"\x15\x87\x87\x92\x15\x87\x87\x92\xc9\xe9\xe9 \xc9\xe9\xe9 \x87\xce\xceI\x87\xce\xceI\xaaUU\xff\xaaUU\xffP((xP((x\xa5\xdf\xdfz\xa5\xdf\xdfz\x03\x8c\x8c\x8f\x03\x8c\x8c\x8fY\xa1\xa1\xf8Y\xa1\xa1\xf8\t\x89\x89\x80\t\x89\x89\x80\x1a\r\r\x17\x1a\r\r\x17e\xbf\xbf\xdae\xbf\xbf\xda\xd7\xe6\xe61\xd7\xe6\xe61\x84BB\xc6\x84BB\xc6\xd0hh\xb8\xd0hh\xb8\x82AA\xc3\x82AA\xc3)\x99\x99\xb0)\x99\x99\xb0Z--wZ--w\x1e\x0f\x0f\x11\x1e\x0f\x0f\x11{\xb0\xb0\xcb{\xb0\xb0\xcb\xa8TT\xfc\xa8TT\xfcm\xbb\xbb\xd6m\xbb\xbb\xd6,\x16\x16:,\x16\x16:'


class QCSparse:
    def __init__(self, filename):
        self.rf = mmap_io(filename, "rb")
        self.data = Queue()
        self.offset = 0
        self.tmpdata = bytearray()

        self.major_version = None
        self.minor_version = None
        self.file_hdr_sz = None
        self.chunk_hdr_sz = None
        self.blk_sz = None
        self.total_blks = None
        self.total_chunks = None
        self.image_checksum = None

        self.error = print

    def readheader(self, offset):
        self.rf.seek(offset)
        header = unpack("<I4H4I", self.rf.read(0x1C))
        magic = header[0]
        self.major_version = header[1]
        self.minor_version = header[2]
        self.file_hdr_sz = header[3]
        self.chunk_hdr_sz = header[4]
        self.blk_sz = header[5]
        self.total_blks = header[6]
        self.total_chunks = header[7]
        self.image_checksum = header[8]
        if magic != 0xED26FF3A:
            return False
        if self.file_hdr_sz != 28:
            self.error("The file header size was expected to be 28, but is %u." % self.file_hdr_sz)
            return False
        if self.chunk_hdr_sz != 12:
            print("The chunk header size was expected to be 12, but is %u." % self.chunk_hdr_sz)
            return False
        print("Sparse Format detected. Using unpacked image.")
        return True

    def get_chunk_size(self):
        if self.total_blks < self.offset:
            self.error(
                "The header said we should have %u output blocks, but we saw %u" % (self.total_blks, self.offset))
            return -1
        header = unpack("<2H2I", self.rf.read(self.chunk_hdr_sz))
        chunk_type = header[0]
        chunk_sz = header[2]
        total_sz = header[3]
        data_sz = total_sz - 12
        if chunk_type == 0xCAC1:
            if data_sz != (chunk_sz * self.blk_sz):
                self.error(
                    "Raw chunk input size (%u) does not match output size (%u)" % (data_sz, chunk_sz * self.blk_sz))
                return -1
            else:
                self.rf.seek(self.rf.tell() + chunk_sz * self.blk_sz)
                return chunk_sz * self.blk_sz
        elif chunk_type == 0xCAC2:
            if data_sz != 4:
                self.error("Fill chunk should have 4 bytes of fill, but this has %u" % data_sz)
                return -1
            else:
                return chunk_sz * self.blk_sz // 4
        elif chunk_type == 0xCAC3:
            return chunk_sz * self.blk_sz
        elif chunk_type == 0xCAC4:
            if data_sz != 4:
                self.error("CRC32 chunk should have 4 bytes of CRC, but this has %u" % data_sz)
                return -1
            else:
                self.rf.seek(self.rf.tell() + 4)
                return 0
        else:
            print("Unknown chunk type 0x%04X" % chunk_type)
            return -1

    def unsparse(self):
        if self.total_blks < self.offset:
            self.error(
                "The header said we should have %u output blocks, but we saw %u" % (self.total_blks, self.offset))
            return -1
        header = unpack("<2H2I", self.rf.read(self.chunk_hdr_sz))
        chunk_type = header[0]
        chunk_sz = header[2]
        total_sz = header[3]
        data_sz = total_sz - 12
        if chunk_type == 0xCAC1:
            if data_sz != (chunk_sz * self.blk_sz):
                self.error(
                    "Raw chunk input size (%u) does not match output size (%u)" % (data_sz, chunk_sz * self.blk_sz))
                return -1
            else:
                # self.debug("Raw data")
                data = self.rf.read(chunk_sz * self.blk_sz)
                self.offset += chunk_sz
                return data
        elif chunk_type == 0xCAC2:
            if data_sz != 4:
                self.error("Fill chunk should have 4 bytes of fill, but this has %u" % data_sz)
                return -1
            else:
                fill_bin = self.rf.read(4)
                # self.debug(format("Fill with 0x%08X" % fill))
                data = fill_bin * (chunk_sz * self.blk_sz // 4)
                self.offset += chunk_sz
                return data
        elif chunk_type == 0xCAC3:
            data = b'\x00' * chunk_sz * self.blk_sz
            self.offset += chunk_sz
            return data
        elif chunk_type == 0xCAC4:
            if data_sz != 4:
                self.error("CRC32 chunk should have 4 bytes of CRC, but this has %u" % data_sz)
                return -1
            else:
                # self.debug(format("Unverified CRC32 0x%08X" % crc))
                return b""
        else:
            # self.debug("Unknown chunk type 0x%04X" % chunk_type)
            return -1

    def getsize(self):
        self.rf.seek(0x1C)
        length = 0
        chunk = 0
        while chunk < self.total_chunks:
            tlen = self.get_chunk_size()
            if tlen == -1:
                break
            length += tlen
            chunk += 1
        self.rf.seek(0x1C)
        return length

    def read(self, length=None):
        if length is None:
            return self.unsparse()
        if length <= len(self.tmpdata):
            tdata = self.tmpdata[:length]
            self.tmpdata = self.tmpdata[length:]
            return tdata
        while len(self.tmpdata) < length:
            self.tmpdata.extend(self.unsparse())
            if length <= len(self.tmpdata):
                tdata = self.tmpdata[:length]
                self.tmpdata = self.tmpdata[length:]
                return tdata


def gsbox(offset):
    return int.from_bytes(sbox[offset:offset + 4], 'little')


def key_update(iv1, asbox):
    d = iv1[0] ^ asbox[0]  # 9EE3B5B1
    a = iv1[1] ^ asbox[1]
    b = iv1[2] ^ asbox[2]  # ABD51D58
    c = iv1[3] ^ asbox[3]  # AFCBAFFF
    e = gsbox(((b >> 0x10) & 0xff) * 8 + 2) ^ gsbox(((a >> 8) & 0xff) * 8 + 3) ^ gsbox((c >> 0x18) * 8 + 1) ^ \
        gsbox((d & 0xff) * 8) ^ asbox[4]  # 35C2A10B

    h = gsbox(((c >> 0x10) & 0xff) * 8 + 2) ^ gsbox(((b >> 8) & 0xff) * 8 + 3) ^ gsbox((d >> 0x18) * 8 + 1) ^ \
        gsbox((a & 0xff) * 8) ^ asbox[5]  # 75CF3118
    i = gsbox(((d >> 0x10) & 0xff) * 8 + 2) ^ gsbox(((c >> 8) & 0xff) * 8 + 3) ^ gsbox((a >> 0x18) * 8 + 1) ^ \
        gsbox((b & 0xff) * 8) ^ asbox[6]  # 6AD3F5C4
    a = gsbox(((d >> 8) & 0xff) * 8 + 3) ^ gsbox(((a >> 0x10) & 0xff) * 8 + 2) ^ gsbox((b >> 0x18) * 8 + 1) ^ \
        gsbox((c & 0xff) * 8) ^ asbox[7]  # D99AC8FB

    g = 8

    for f in range(asbox[0x3c] - 2):
        d = e >> 0x18  # 35
        m = h >> 0x10  # cf
        s = h >> 0x18
        z = e >> 0x10
        l = i >> 0x18
        t = e >> 8
        e = gsbox(((i >> 0x10) & 0xff) * 8 + 2) ^ gsbox(((h >> 8) & 0xff) * 8 + 3) ^ \
            gsbox((a >> 0x18) * 8 + 1) ^ gsbox((e & 0xff) * 8) ^ asbox[g]  # B67F2106, 82508918
        h = gsbox(((a >> 0x10) & 0xff) * 8 + 2) ^ gsbox(((i >> 8) & 0xff) * 8 + 3) ^ \
            gsbox(d * 8 + 1) ^ gsbox((h & 0xff) * 8) ^ asbox[g + 1]  # 85813F52
        i = gsbox((z & 0xff) * 8 + 2) ^ gsbox(((a >> 8) & 0xff) * 8 + 3) ^ \
            gsbox(s * 8 + 1) ^ gsbox((i & 0xff) * 8) ^ asbox[g + 2]  # C8022573
        a = gsbox((t & 0xff) * 8 + 3) ^ gsbox((m & 0xff) * 8 + 2) ^ \
            gsbox(l * 8 + 1) ^ gsbox((a & 0xff) * 8) ^ asbox[g + 3]  # AD34EC55
        g = g + 4
    # a=6DB8AA0E
    # b=ABD51D58
    # c=AFCBAFFF
    # d=51
    # e=AC402324
    # h=B2D24440
    # i=CC2ADF24
    # t=510805
    return [(gsbox(((i >> 0x10) & 0xff) * 8) & 0xff0000) ^ (gsbox(((h >> 8) & 0xff) * 8 + 1) & 0xff00) ^
            (gsbox((a >> 0x18) * 8 + 3) & 0xff000000) ^ gsbox((e & 0xff) * 8 + 2) & 0xFF ^ asbox[g],
            (gsbox(((a >> 0x10) & 0xff) * 8) & 0xff0000) ^ (gsbox(((i >> 8) & 0xff) * 8 + 1) & 0xff00) ^
            (gsbox((e >> 0x18) * 8 + 3) & 0xff000000) ^ (gsbox((h & 0xff) * 8 + 2) & 0xFF) ^ asbox[g + 3],
            (gsbox(((e >> 0x10) & 0xff) * 8) & 0xff0000) ^ (gsbox(((a >> 8) & 0xff) * 8 + 1) & 0xff00) ^
            (gsbox((h >> 0x18) * 8 + 3) & 0xff000000) ^ (gsbox((i & 0xff) * 8 + 2) & 0xFF) ^ asbox[g + 2],
            (gsbox(((h >> 0x10) & 0xff) * 8) & 0xff0000) ^ (gsbox(((e >> 8) & 0xff) * 8 + 1) & 0xff00) ^
            (gsbox((i >> 0x18) * 8 + 3) & 0xff000000) ^ (gsbox((a & 0xff) * 8 + 2) & 0xFF) ^ asbox[g + 1]]


def key_custom(inp, rkey, outlength=0, encrypt=False):
    outp = bytearray()
    inp = bytearray(inp)
    pos = outlength
    outp_extend = outp.extend
    ptr = 0
    length = len(inp)
    if outlength != 0:
        while pos < len(rkey):
            if length == 0:
                break
            buffer = inp[pos]
            outp_extend(rkey[pos] ^ buffer)
            rkey[pos] = buffer
            length -= 1
            pos += 1

    if length > 0xF:
        for ptr in range(0, length, 0x10):
            rkey = key_update(rkey, mbox)
            if pos < 0x10:
                slen = ((0xf - pos) >> 2) + 1
                tmp = [rkey[i] ^ int.from_bytes(inp[pos + (i * 4) + ptr:pos + (i * 4) + ptr + 4], "little") for i in
                       range(0, slen)]
                outp.extend(b"".join(tmp[i].to_bytes(4, 'little') for i in range(0, slen)))
                if encrypt:
                    rkey = tmp
                else:
                    rkey = [int.from_bytes(inp[pos + (i * 4) + ptr:pos + (i * 4) + ptr + 4], "little") for i in
                            range(0, slen)]
            length = length - 0x10
    if length != 0:
        rkey = key_update(rkey, sbox)
        j = pos
        m = 0
        while length > 0:
            data = inp[j + ptr:j + ptr + 4]
            if len(data) < 4:
                data += b"\x00" * (4 - len(data))
            tmp = int.from_bytes(data, 'little')
            outp_extend((tmp ^ rkey[m]).to_bytes(4, 'little'))
            if encrypt:
                rkey[m] = tmp ^ rkey[m]
            else:
                rkey[m] = tmp
            length -= 4
            j += 4
            m += 1
    return outp


def extractxml(filename, key):
    with mmap_io(filename, 'rb') as rf:
        sfilename = os.path.join(filename[:-len(os.path.basename(filename))], "extract", "settings.xml")
        filesize = os.stat(filename).st_size
        rf.seek(filesize - 0x200)
        hdr = rf.read(0x200)
        xmllength = int.from_bytes(hdr[0x18:0x18 + 4], 'little')
        xmlpad = 0x200 - (xmllength % 0x200)
        rf.seek(filesize - 0x200 - (xmllength + xmlpad))
        inp = rf.read(xmllength + xmlpad)
        outp = key_custom(inp, key, 0)
        if b"xml " not in outp:
            return None
        with mmap_io(sfilename, 'wb', xmllength) as wf:
            wf.write(outp[:xmllength])
        return outp[:xmllength].decode('utf-8')


def decryptfile(rkey, filename, path, wfilename, start, length):
    sha256 = hashlib.sha256()
    print(f"Extracting {wfilename}")
    with mmap_io(filename, 'rb') as rf:
        rf.seek(start)
        data = rf.read(length)
        if length % 4:
            data += (4 - (length % 4)) * b'\x00'
        outp = key_custom(data, rkey, 0)
        sha256.update(outp[:length])
        with mmap_io(os.path.join(path, wfilename), 'wb', length) as wf:
            wf.write(outp[:length])
    if length % 0x1000 > 0:
        sha256.update(b"\x00" * (0x1000 - (length % 0x1000)))
    return sha256.hexdigest()


def encryptsubsub(rkey, data, wf):
    length = len(data)
    if length % 4:
        data += (4 - (length % 4)) * b'\x00'
    outp = key_custom(data, rkey, 0, True)
    wf.write(outp[:length])
    return length


def encryptsub(rkey, rf, wf):
    data = rf.read()
    return encryptsubsub(rkey, data, wf)


def encryptfile(key, filename, wfilename):
    print(f"Encrypting {filename}")
    with mmap_io(filename, 'rb') as rf:
        filesize = os.stat(filename).st_size
        with mmap_io(wfilename, 'wb', filesize) as wf:
            return encryptsub(key, rf, wf)


def calc_digest(filename):
    with mmap_io(filename, 'rb') as rf:
        data = rf.read()
        sha256 = hashlib.sha256()
        sha256.update(data)
        if len(data) % 0x1000 > 0:
            sha256.update(b"\x00" * (0x1000 - (len(data) % 0x1000)))
    return sha256.hexdigest()


def copysub(rf, wf, start, length):
    rf.seek(start)
    rlen = 0
    while length > 0:
        if length < 0x100000:
            size = length
        else:
            size = 0x100000
        data = rf.read(size)
        wf.write(data)
        rlen += len(data)
        length -= size
    return rlen


def copyfile(filename, path, wfilename, start, length):
    print(f"Extracting {wfilename}")
    with mmap_io(filename, 'rb') as rf:
        with mmap_io(os.path.join(path, wfilename), 'wb', length) as wf:
            return copysub(rf, wf, start, length)


def encryptitem(key, item, directory, pos, wf):
    try:
        filename = item.attrib["Path"]
    except:
        filename = item.attrib["filename"]
    if filename == "":
        return item, pos
    filename = os.path.join(directory, filename)
    start = pos // 0x200
    item.attrib["FileOffsetInSrc"] = str(start)
    size = os.stat(filename).st_size
    item.attrib["SizeInByteInSrc"] = str(size)
    sectors = size // 0x200
    if (size % 0x200) != 0:
        sectors += 1
    item.attrib["SizeInSectorInSrc"] = str(sectors)
    with mmap_io(filename, 'rb') as rf:
        rlen = encryptsub(key, rf, wf)
        pos += rlen
        if (rlen % 0x200) != 0:
            sublen = 0x200 - (rlen % 0x200)
            wf.write(b'\x00' * sublen)
            pos += sublen
    return item, pos


def copyitem(item, directory, pos, wf):
    try:
        filename = item.attrib["Path"]
    except:
        filename = item.attrib["filename"]
    if filename == "":
        return item, pos
    filename = os.path.join(directory, filename)
    start = pos // 0x200
    item.attrib["FileOffsetInSrc"] = str(start)

    size = os.stat(filename).st_size
    item.attrib["SizeInByteInSrc"] = str(size)
    sectors = size // 0x200
    if (size % 0x200) != 0:
        sectors += 1
    item.attrib["SizeInSectorInSrc"] = str(sectors)
    with mmap_io(filename, 'rb') as rf:
        rlen = copysub(rf, wf, 0, size)
        pos += rlen
        if (rlen % 0x200) != 0:
            sublen = 0x200 - (rlen % 0x200)
            wf.write(b'\x00' * sublen)
            pos += sublen
    return item, pos


def main(args):
    global mbox
    print("Oneplus CryptTools V1.4 (c) B. Kerler 2019-2021\n----------------------------\n")
    if args["decrypt"]:
        filename = args["<filename>"].replace("\\", "/")
        print(f"Extracting {filename}")
        if args['outdir']:
            path = args['outdir']
        elif "/" in filename:
            path = filename[:filename.rfind("/")]
        else:
            path = ""
        path = os.path.join(path, "extract")
        if os.path.exists(path):
            shutil.rmtree(path)
            os.mkdir(path)
        else:
            os.mkdir(path)
        mbox = mbox5
        xml = extractxml(filename, key)
        if xml is not None:
            print("MBox5")
        else:
            mbox = mbox6
            xml = extractxml(filename, key)
            if xml is not None:
                print("MBox6")
            else:
                mbox = mbox4
                xml = extractxml(filename, key)
                if xml is not None:
                    print("MBox4")
                else:
                    print("Unsupported key !")
                    exit(0)
        root = et.fromstring(xml)
        for child in root:
            if child.tag == "SAHARA":
                for item in child:
                    if item.tag == "File":
                        wfilename = item.attrib["Path"]
                        start = int(item.attrib["FileOffsetInSrc"]) * 0x200
                        slength = int(item.attrib["SizeInSectorInSrc"]) * 0x200
                        length = int(item.attrib["SizeInByteInSrc"])
                        decryptfile(key, filename, path, wfilename, start, length)
            elif child.tag == "UFS_PROVISION":
                for item in child:
                    if item.tag == "File":
                        wfilename = item.attrib["Path"]
                        start = int(item.attrib["FileOffsetInSrc"]) * 0x200
                        # length = int(item.attrib["SizeInSectorInSrc"]) * 0x200
                        length = int(item.attrib["SizeInByteInSrc"])
                        copyfile(filename, path, wfilename, start, length)
            elif "Program" in child.tag:
                # if not os.path.exists(os.path.join(path, child.tag)):
                #    os.mkdir(os.path.join(path, child.tag))
                # spath = os.path.join(path, child.tag)
                for item in child:
                    if "filename" in item.attrib:
                        sparse = item.attrib["sparse"] == "true"
                        wfilename = item.attrib["filename"]
                        if wfilename == "":
                            continue
                        start = int(item.attrib["FileOffsetInSrc"]) * 0x200
                        slength = int(item.attrib["SizeInSectorInSrc"]) * 0x200
                        length = int(item.attrib["SizeInByteInSrc"])
                        sha256 = item.attrib["Sha256"]
                        copyfile(filename, path, wfilename, start, length)
                        csha256 = calc_digest(os.path.join(path, wfilename))
                        if sha256 != csha256 and not sparse:
                            print("Sha256 fail.")
                    else:
                        for subitem in item:
                            if "filename" in subitem.attrib:
                                wfilename = subitem.attrib["filename"]
                                sparse = subitem.attrib["sparse"] == "true"
                                if wfilename == "":
                                    continue
                                start = int(subitem.attrib["FileOffsetInSrc"]) * 0x200
                                slength = int(subitem.attrib["SizeInSectorInSrc"]) * 0x200
                                length = int(subitem.attrib["SizeInByteInSrc"])
                                sha256 = subitem.attrib["Sha256"]
                                copyfile(filename, path, wfilename, start, length)
                                csha256 = calc_digest(os.path.join(path, wfilename))
                                if sha256 != csha256 and not sparse:
                                    print("Sha256 fail.")
            # else:
            #    print (child.tag, child.attrib)
        print("Done. Extracted files to " + path)
        exit(0)
    elif args["encrypt"]:
        if args["--mbox"] == "4":
            mbox = mbox4
        elif args["--mbox"] == "5":
            mbox = mbox5
        elif args["--mbox"] == "6":
            mbox = mbox6
        directory = args["<directory>"].replace("\\", "/")
        settings = os.path.join(directory, "settings.xml")
        # root = ET.fromstring(settings)
        tree = et.parse(settings)
        root = tree.getroot()
        outfilename = os.path.join(Path(directory).parent, args["--savename"])
        projid = None
        firmware = None
        if os.path.exists(outfilename):
            os.remove(outfilename)
        with open(outfilename, 'wb') as wf:
            pos = 0
            for child in root:
                if child.tag == "BasicInfo":
                    if "Project" in child.attrib:
                        projid = child.attrib["Project"]
                    if "Version" in child.attrib:
                        firmware = child.attrib["Version"]
                if child.tag == "SAHARA":
                    for item in child:
                        if item.tag == "File":
                            item, pos = encryptitem(key, item, directory, pos, wf)
                elif child.tag == "UFS_PROVISION":
                    for item in child:
                        if item.tag == "File":
                            item, pos = copyitem(item, directory, pos, wf)
                elif "Program" in child.tag:
                    for item in child:
                        if "filename" in item.attrib:
                            item, pos = copyitem(item, directory, pos, wf)
                        else:
                            for subitem in item:
                                subitem, pos = copyitem(subitem, directory, pos, wf)
            try:
                configpos = pos // 0x200
                with open(settings, 'rb') as rf:
                    data = rf.read()
                    rlength = len(data)
                    data += (0x10 - (rlength % 0x10)) * b"\x00"
                    rlen = encryptsubsub(key, data, wf)
                    if ((rlen + pos) % 0x200) != 0:
                        sublen = 0x200 - ((rlen + pos) % 0x200)
                        wf.write(b'\x00' * sublen)
                        pos += sublen
                if args["--projid"] is None:
                    if projid is None:
                        projid = "18801"
                else:
                    projid = args["--projid"]

                if args["--firmwarename"] is None:
                    if firmware is None:
                        firmware = "fajita_41_J.42_191214"
                else:
                    firmware = args["--firmwarename"]
                magic = 0x7CEF
                hdr = b""
                hdr += pack("<I", 2)
                hdr += pack("<I", 1)
                hdr += pack("<I", 0)
                hdr += pack("<I", 0)
                hdr += pack("<I", magic)
                hdr += pack("<I", configpos)
                hdr += pack("<I", rlength)
                hdr += bytes(projid, 'utf-8')
                hdr += b"\x00" * (0x10 - len(projid))
                hdr += bytes(firmware, 'utf-8')
                hdr += b"\x00" * (0x200 - len(hdr))
                wf.write(hdr)
                with open(outfilename, 'rb') as rt:
                    with open("md5sum_pack.md5", 'wb') as wt:
                        mt = hashlib.md5()
                        mt.update(rt.read())
                        wt.write(bytes(mt.hexdigest(), 'utf-8') + b" " + bytes(os.path.basename(outfilename), 'utf-8'))
                print("Done. Created " + outfilename)
            except Exception as e:
                print(e)
        exit(0)
    elif args["encryptfile"]:
        filename = args["<filename>"].replace("\\", "/")
        mbox = mbox5
        encryptfile(key, filename, filename + ".enc")
        print("Done.")
    elif args["decryptfile"]:
        filename = args["<filename>"].replace("\\", "/")
        mbox = mbox5
        fsize = os.stat(filename).st_size
        decryptfile(key, filename, "", filename + ".dec", 0, fsize)
        print("Done.")
