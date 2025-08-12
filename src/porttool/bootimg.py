#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Modified : jpacg <jpacg@vip.163.com>

import os
import sys
import struct
import hashlib
from stat import *
import shutil
from gzip import GzipFile

__all__ = ['repack_bootimg', 'unpack_bootimg']


def sha_file(sha, file):
    if file is None:
        return
    file.seek(0, 0)
    while True:
        data = file.read(65536)
        if not data:
            break
        sha.update(data)


def write_bootimg(output, kernel, ramdisk, second,
                  name, cmdline, base, ramdisk_addr, second_addr,
                  tags_addr, page_size, padding_size, dt_image):
    """ make C8600-compatible bootimg.
        output: file object
        kernel, ramdisk, second: file object or string
        name, cmdline: string
        base, page_size, padding_size: integer size

        official document:
        https://android.googlesource.com/platform/system/core/+/master/mkbootimg/bootimg.h

        Note: padding_size is not equal to page_size in HuaWei C8600
    """

    if name is None:
        name = ''

    if cmdline is None:
        cmdline = 'mem=211M console=null androidboot.hardware=qcom'

    assert len(name) <= 16, 'Error: board name too large'
    assert len(cmdline) <= 512, 'Error: kernel commandline too large'

    if not isinstance(base, int):
        base = 0x10000000  # 0x00200000?
        print('base is %s, using default base instead.\n' % type(base))

    if not isinstance(ramdisk_addr, int):
        ramdisk_addr = base + 0x01000000
        print('ramdisk_addr is %s, using default ramdisk_addr instead.\n' % type(ramdisk_addr))

    if not isinstance(second_addr, int):
        second_addr = base + 0x00F00000
        print('second_addr is %s, using default second_addr instead.\n' % type(second_addr))

    if not isinstance(tags_addr, int):
        tags_addr = base + 0x00000100
        print('tags_addr is %s, using default tags_addr instead.\n' % type(tags_addr))

    if not isinstance(page_size, int):
        page_size = 0x800
        print('page_size is %s, using default page_size instead.\n' % type(page_size))

    if not isinstance(padding_size, int):
        padding_size = 0x800  # 0x1000?
        print('padding_size is %s, using default padding_size instead.\n' % type(padding_size))

    if not hasattr(output, 'write'):
        output = sys.stdout

    padding = lambda x: struct.pack('%ds' % ((~x + 1) & (padding_size - 1)), b'')

    def getsize(x):
        if x is None:
            return 0
        assert hasattr(x, 'seek')
        assert hasattr(x, 'tell')
        x.seek(0, 2)
        return x.tell()

    def writecontent(output, x):
        if x is None:
            return None

        assert hasattr(x, 'read')

        x.seek(0, 0)
        output.write(x.read())
        output.write(padding(x.tell()))

        if hasattr(x, 'close'):
            x.close()

    sha = hashlib.sha1()
    sha_file(sha, kernel)
    sha.update(struct.pack('<I', getsize(kernel)))
    sha_file(sha, ramdisk)
    sha.update(struct.pack('<I', getsize(ramdisk)))
    sha_file(sha, second)
    sha.update(struct.pack('<I', getsize(second)))
    if dt_image is not None:
        sha_file(sha, dt_image)
        sha.update(struct.pack('<I', getsize(dt_image)))
    id = sha.digest()

    kernel_addr = base + 0x00008000
    output.write(struct.pack('<8s10I16s512s32s', b'ANDROID!',
                             getsize(kernel), kernel_addr,
                             getsize(ramdisk), ramdisk_addr,
                             getsize(second), second_addr,
                             tags_addr, page_size, getsize(dt_image), 0,
                             name.encode(), cmdline.encode(), id))

    output.write(padding(608))
    writecontent(output, kernel)
    writecontent(output, ramdisk)
    writecontent(output, second)
    writecontent(output, dt_image)
    if hasattr('output', 'close'):
        output.close()


def parse_bootimg(bootimg):
    """ parse C8600-compatible bootimg.
        write kernel to kernel[.gz]
        write ramdisk to ramdisk[.gz]
        write second to second[.gz]

        official document:
        https://android.googlesource.com/platform/system/core/+/master/mkbootimg/bootimg.h

        Note: padding_size is not equal to page_size in HuaWei C8600
    """

    bootinfo = open('bootinfo.txt', 'w')
    # check_mtk_head(bootimg, bootinfo)

    (magic,
     kernel_size, kernel_addr,
     ramdisk_size, ramdisk_addr,
     second_size, second_addr,
     tags_addr, page_size, dt_size, zero,
     name, cmdline, id4x8
     ) = struct.unpack('<8s10I16s512s32s', bootimg.read(608))
    bootimg.seek(page_size - 608, 1)

    base = kernel_addr - 0x00008000
    assert magic.decode('latin') == 'ANDROID!', 'invald bootimg'
    if not base == ramdisk_addr - 0x01000000:
        print('found nonstandard ramdisk_addr\n')
    if not base == second_addr - 0x00f00000:
        print('found nonstandard second_addr\n')
    if not base == tags_addr - 0x00000100:
        print('found nonstandard tags_addr\n')
    if dt_size:
        print('found device_tree_image\n')
    cmdline = cmdline[:cmdline.find(b'\x00')]

    print('base: 0x%x\n' % base)
    print('ramdisk_addr: 0x%x\n' % ramdisk_addr)
    print('second_addr: 0x%x\n' % second_addr)
    print('tags_addr: 0x%x\n' % tags_addr)
    print('page_size: %d\n' % page_size)
    print('name: "%s"\n' % name.decode('latin').strip('\x00'))
    print('cmdline: "%s"\n' % cmdline.decode('latin').strip('\x00'))

    bootinfo.write('base:0x%x\n' % base)
    bootinfo.write('ramdisk_addr:0x%x\n' % ramdisk_addr)
    bootinfo.write('second_addr:0x%x\n' % second_addr)
    bootinfo.write('tags_addr:0x%x\n' % tags_addr)
    bootinfo.write('page_size:0x%x\n' % page_size)
    bootinfo.write('name:%s\n' % name.decode('latin').strip('\x00'))
    bootinfo.write('cmdline:%s\n' % cmdline.decode('latin').strip('\x00'))

    while True:
        if bootimg.read(page_size) == struct.pack('%ds' % page_size, b''):
            continue
        bootimg.seek(-page_size, 1)
        size = bootimg.tell()
        break

    padding = lambda x: (~x + 1) & (size - 1)
    print('padding_size=%d\n' % size)

    bootinfo.write('padding_size:0x%x\n' % size)
    bootinfo.close()

    gzname = lambda x: x == struct.pack('3B', 0x1f, 0x8b, 0x08) and '.gz' or ''

    kernel = bootimg.read(kernel_size)
    output = open('kernel%s' % gzname(kernel[:3]), 'wb')
    output.write(kernel)
    output.close()
    bootimg.seek(padding(kernel_size), 1)

    ramdisk = bootimg.read(ramdisk_size)
    output = open('ramdisk%s' % gzname(ramdisk[:3]), 'wb')
    output.write(ramdisk)
    output.close()
    bootimg.seek(padding(ramdisk_size), 1)

    if second_size:
        second = bootimg.read(second_size)
        output = open('second%s' % gzname(second[:3]), 'wb')
        output.write(second)
        output.close()
        bootimg.seek(padding(ramdisk_size), 1)

    if dt_size:
        dt_image = bootimg.read(dt_size)
        output = open('dt_image%s' % gzname(dt_image[:3]), 'wb')
        output.write(dt_image)
        output.close()
    #        bootimg.seek(padding(second_size), 1)

    bootimg.close()


def parse_cpio(cpio, directory, cpiolist):
    """ parse cpio, write content under directory.
        cpio: file object
        directory: string
        cpiolist: file object

        official document: (cpio newc structure)
        http://git.kernel.org/?p=linux/kernel/git/torvalds/linux-2.6.git;a=blob;f=usr/gen_init_cpio.c
    """

    padding = lambda x: (~x + 1) & 3

    def read_cpio_header(cpio):
        assert cpio.read(6).decode('latin') == '070701', 'invalid cpio'
        cpio.read(8)  # ignore inode number
        mode = int(cpio.read(8), 16)
        cpio.read(8)  # uid
        cpio.read(8)  # gid
        cpio.read(8)  # nlink
        cpio.read(8)  # timestamp
        filesize = int(cpio.read(8), 16)
        cpio.read(8)  # major
        cpio.read(8)  # minor
        cpio.read(8)  # rmajor
        cpio.read(8)  # rminor
        namesize = int(cpio.read(8), 16)
        cpio.read(8)
        name = cpio.read(namesize - 1).decode('utf8')
        cpio.read(1)
        cpio.read(padding(namesize + 110))
        return name, mode, filesize

    os.makedirs(directory)

    while True:
        name, mode, filesize = read_cpio_header(cpio)
        if name == 'TRAILER!!!':
            break

        if name[:1] == '/':
            name = name[1:]

        name = os.path.normpath(name)
        path = '%s/%s' % (directory, name)
        name = name.replace(os.sep, '/')  # for windows

        srwx = oct(S_IMODE(mode))
        if S_ISLNK(mode):
            location = cpio.read(filesize)
            location = location.decode()
            cpio.read(padding(filesize))
            cpiolist.write('slink\t%s\t%s\t%s\n' % (name, location, srwx))
        elif S_ISDIR(mode):
            try:
                os.makedirs(path)
            except os.error:
                pass
            cpiolist.write('dir\t%s\t%s\n' % (name, srwx))
        elif S_ISREG(mode):
            tmp = open(path, 'wb')
            tmp.write(cpio.read(filesize))
            cpio.read(padding(filesize))
            tmp.close()
            cpiolist.write('file\t%s\t%s\t%s\n' % (name, path, srwx))
        else:
            cpio.read(filesize)
            cpio.read(padding(filesize))

    cpio.close()
    cpiolist.close()


# 根据system/core/cpio/mkbootfs.c对代码进行修正
def write_cpio(cpiolist, output):
    """ generate cpio from cpiolist.
        cpiolist: file object
        output: file object
    """

    padding = lambda x, y: struct.pack('%ds' % ((~x + 1) & (y - 1)), b'')

    def write_cpio_header(output, ino, name, mode=0, nlink=1, filesize=0):
        name = name.encode()
        namesize = len(name) + 1
        latin = lambda x: x.encode('latin')
        output.write(latin('070701'))
        output.write(latin('%08x' % ino))  # Android自300000递增 # ino normally only for hardlink

        output.write(latin('%08x' % mode))
        output.write(latin('%08x%08x' % (0, 0)))  # uid, gid set to 0
        output.write(latin('%08x' % 1))  # 在Android中恒为1而非nlink
        output.write(latin('%08x' % 0))  # timestamp set to 0
        output.write(latin('%08x' % filesize))
        output.write(latin('%08x%08x' % (0, 0)))  # 在Android中为(0, 0) 而非 (3, 1)
        output.write(latin('%08x%08x' % (0, 0)))  # dont support rmajor, rminor
        output.write(latin('%08x' % namesize))
        output.write(latin('%08x' % 0))  # chksum always be 0
        output.write(name)
        output.write(struct.pack('1s', b''))
        output.write(padding(namesize + 110, 4))

    def cpio_mkfile(output, ino, name, path, mode, *kw):
        mode = int(mode, 8) | S_IFREG
        if os.path.lexists(path):
            filesize = os.path.getsize(path)
            write_cpio_header(output, ino, name, mode, 1, filesize)
            tmp = open(path, 'rb')
            output.write(tmp.read())
            tmp.close()
            output.write(padding(filesize, 4))
        else:
            print('not found file %s, skip it\n' % path)

    def cpio_mkdir(output, ino, name, mode='755', *kw):
        # if name == 'tmp':
        #    mode = '1777'
        mode = int(mode, 8) | S_IFDIR
        write_cpio_header(output, ino, name, mode, 2, 0)

    def cpio_mkslink(output, ino, name, path, mode='777', *kw):
        mode = int(mode, 8) | S_IFLNK
        filesize = len(path)
        write_cpio_header(output, ino, name, mode, 1, filesize)
        output.write(path.encode())
        output.write(padding(filesize, 4))

    def cpio_tailer(output, ino):
        name = 'TRAILER!!!'
        write_cpio_header(output, ino, name, 0o644)  # 8进制权限644, 的确应该为0? 为调用fix_stat引起的bug.

        # normally, padding is ignored by decompresser
        if hasattr(output, 'tell'):
            output.write(padding(output.tell(), 512))

    files = []
    functions_ = {'dir': cpio_mkdir,
                  'file': cpio_mkfile,
                  'slink': cpio_mkslink,
                  'nod': lambda *x: print("No Supported Yet"),
                  'pipe': lambda *x: print("No Supported Yet"),
                  'sock': lambda *x: print("No Supported Yet")}
    next_inode = 300000
    while True:
        line = cpiolist.readline()
        if not line:
            break
        lines = line.split('\t')
        if len(lines) < 1 or lines[0] == '#':
            continue
        function = functions_.get(lines[0])
        if not function:
            continue
        lines.pop(0)
        lines[0] = lines[0].replace(os.sep, '/')  # if any
        if lines[0] in files:
            print('ignore duplicate %s\n' % lines[0])
            continue
        files.append(lines[0])
        function(output, next_inode, *lines)
        next_inode += 1

    # for extra in ['/tmp', '/mnt']:
    #    if extra not in files:
    #        print('add extra %s\n' % extra)
    #        cpio_mkdir(output, extra)

    cpio_tailer(output, next_inode)
    cpiolist.close()
    output.close()


class CPIOGZIP(GzipFile):
    # dont write filename
    def _write_gzip_header(self, compresslevel: int = 9):
        self.fileobj.write(struct.pack('4B', 0x1f, 0x8b, 0x08, 0x00))
        self.fileobj.write(struct.pack('4s', b''))
        self.fileobj.write(struct.pack('2B', 0x00, 0x03))

    # don't check crc and length
    def _read_eof(self):
        pass


__all__ += ['parse_bootimg',
            'write_bootimg',
            'parse_cpio',
            'write_cpio',
            'cpio_list',
            ]

base = None
ramdisk_addr = None
second_addr = None
tags_addr = None
name = None
cmdline = None
page_size = None
padding_size = None


def parse_bootinfo(bootinfo):
    # ''' parse bootinfo for repack bootimg.
    #    bootinfo: file object
    # '''
    global base, ramdisk_addr, second_addr, tags_addr, name, cmdline, page_size, padding_size

    def set_base(addr):
        global base
        if base is None:
            base = int(addr, 16)

    def set_ramdisk_addr(addr):
        global ramdisk_addr
        if ramdisk_addr is None:
            ramdisk_addr = int(addr, 16)

    def set_second_addr(addr):
        global second_addr
        if second_addr is None:
            second_addr = int(addr, 16)

    def set_tags_addr(addr):
        global tags_addr
        if tags_addr is None:
            tags_addr = int(addr, 16)

    def set_page_size(size):
        global page_size
        if page_size is None:
            page_size = int(size, 16)

    def set_padding_size(size):
        global padding_size
        if padding_size is None:
            padding_size = int(size, 16)

    def set_name(old_name):
        global name
        if name is None:
            name = old_name.strip()

    def set_cmdline(old_cmdline):
        global cmdline
        if cmdline is None:
            cmdline = old_cmdline.strip()

    functions = {'base': set_base,
                 'ramdisk_addr': set_ramdisk_addr,
                 'second_addr': set_second_addr,
                 'tags_addr': set_tags_addr,
                 'page_size': set_page_size,
                 'padding_size': set_padding_size,
                 'name': set_name,
                 'cmdline': set_cmdline}

    while True:
        line = bootinfo.readline().lstrip()
        if not line:
            break
        lines = line.split(':', 1)
        if len(lines) < 1 or lines[0][0] == '#':
            continue
        function = functions.get(lines[0])
        if not function:
            continue
        lines.pop(0)
        function(*lines)


# above is the module of bootimg
# below is only for usage...

def repack_bootimg(_base=None, _cmdline=None, _page_size=None, _padding_size=None, cpiolist=None):
    repack_ramdisk(cpiolist)

    global base, ramdisk_addr, second_addr, tags_addr, name, cmdline, page_size, padding_size
    if os.path.exists('ramdisk.cpio.gz'):
        ramdisk = 'ramdisk.cpio.gz'
    elif os.path.exists('ramdisk'):
        ramdisk = 'ramdisk'
    else:
        ramdisk = 'ramdisk.gz'

    if os.path.exists('second.gz'):
        second = 'second.gz'
    elif os.path.exists('second'):
        second = 'second'
    else:
        second = ''

    if os.path.exists('dt_image.gz'):
        dt_image = 'dt_image.gz'
    elif os.path.exists('dt_image'):
        dt_image = 'dt_image'
    else:
        dt_image = ''

    if os.path.exists('kernel.gz'):
        kernel = 'kernel.gz'
    else:
        kernel = 'kernel'

    if _base is not None:
        base = int(_base, 16)

    if _cmdline is not None:
        cmdline = _cmdline

    if _page_size is not None:
        page_size = int(str(_page_size), 16)

    if _padding_size is not None:
        padding_size = int(str(_padding_size), 16)

    if os.path.exists('bootinfo.txt'):
        bootinfo = open('bootinfo.txt', 'r')
        parse_bootinfo(bootinfo)
        bootinfo.close()

    print('arguments: [base] [cmdline] [page_size] [padding_size]\n')
    print('kernel: kernel\n')
    print('ramdisk: %s\n' % ramdisk)
    print('second: %s\n' % second)
    print('dt_image: %s\n' % dt_image)
    print('base: 0x%x\n' % base)
    print('ramdisk_addr: 0x%x\n' % ramdisk_addr)
    print('second_addr: 0x%x\n' % second_addr)
    print('tags_addr: 0x%x\n' % tags_addr)
    print('name: %s\n' % name)
    print('cmdline: %s\n' % cmdline)
    print('page_size: %d\n' % page_size)
    print('padding_size: %d\n' % padding_size)
    print('output: boot-new.img\n')

    tmp = open('boot.img.tmp', 'wb')
    options = {'base': base,
               'ramdisk_addr': ramdisk_addr,
               'second_addr': second_addr,
               'tags_addr': tags_addr,
               'name': name,
               'cmdline': cmdline,
               'output': tmp,
               'kernel': open(kernel, 'rb'),
               'ramdisk': open(ramdisk, 'rb'),
               'second': second and open(second, 'rb') or None,
               'page_size': page_size,
               'padding_size': padding_size,
               'dt_image': dt_image and open(dt_image, 'rb') or None,
               }

    write_bootimg(**options)
    tmp.close()
    if os.path.exists('bootinfo.txt'):
        bootinfo = open('bootinfo.txt', 'r')
        output = open('boot.img', 'wb')
        tmp = open('boot.img.tmp', 'rb')
        if try_add_head(tmp, output, bootinfo):
            bootinfo.close()
            while True:
                data = tmp.read(65536)
                if not data:
                    break
                output.write(data)
            tmp.close()
            os.remove('boot.img.tmp')
            output.close()
            return
        else:
            tmp.close()
            output.close()
            bootinfo.close()
    os.remove('bootinfo.txt')
    os.remove('boot.img')
    os.remove('cpiolist.txt')
    if os.path.exists('ramdisk.gz'):
        os.remove('ramdisk.gz')
    if os.path.exists('ramdisk.cpio.gz'):
        os.remove('ramdisk.cpio.gz')
    if os.path.exists('kernel.gz'):
        os.remove('kernel.gz')
    if os.path.exists('kernel'):
        os.remove('kernel')
    if os.path.exists('dt_image'):
        os.remove('dt_image')
    if os.path.exists('ramdisk'):
        os.remove('ramdisk')
    shutil.rmtree('initrd')
    os.rename('boot.img.tmp', 'boot-new.img')


def unpack_bootimg(bootimg=None, ramdisk=None, directory=None):
    # shutil.copy('boot.img', 'boot-old.img')
    if bootimg is None:
        bootimg = 'boot.img'
        if os.path.exists('recovery.img') and not os.path.exists('boot.img'):
            bootimg = 'recovery.img'
    print('arguments: [bootimg file]\n')
    print('bootimg file: %s\n' % bootimg)
    print('output: kernel[.gz] ramdisk[.gz] second[.gz]\n')
    parse_bootimg(open(bootimg, 'rb'))

    unpack_ramdisk(ramdisk, directory)


def check_mtk_head(imgfile, outinfofile):
    # 备份原地址
    offset = imgfile.tell()

    # check for magic
    data = imgfile.read(0x4)
    # assert len(data) == 0x4, 'bad imgfile'
    if len(data) != 0x4:
        return False
    (tag,) = struct.unpack('<I', data)

    if tag == 0x58881688:
        print('Found mtk magic, skip header.\n')
        data = imgfile.read(0x4)
        (size1,) = struct.unpack('<I', data)
        assert len(data) == 0x4, 'bad imgfile'
        imgfile.seek(0, 2)
        size2 = imgfile.tell() - 0x200
        assert size1 == size2, 'Incomplete or wrong file'
        imgfile.seek(0x8, 0)
        data = imgfile.read(0x20)
        assert len(data) == 0x20, 'bad imgfile'
        (name,) = struct.unpack('32s', data)
        print('Found header name %s\n' % name)
        outinfofile.write('mode:mtk\n')
        outinfofile.write('mtk_header_name:%s\n' % name.decode('latin').strip('\x00'))
        imgfile.seek(0x200, 0)
        return True
    else:
        # assert False, 'Unsupported mode.'
        imgfile.seek(offset, 0)
        return False


def try_add_head(imgfile, outfile, imginfofile, mode=None):
    imginfofile.seek(0, 0)
    if mode == 'auto':
        mode = None
    if mode is None:
        for line in imginfofile.readlines():
            lines = line.split(':')
            if len(lines) < 1 or lines[0][0] == '#':
                continue
            if lines[0].strip() == 'mode':
                mode = lines[1].strip()
                break

    if mode == 'mtk':
        print('mtk mode\n')
        magic = 0x58881688
        off1 = imgfile.tell()
        imgfile.seek(0, 2)
        size = imgfile.tell()
        name = ''
        off2 = imginfofile.tell()
        imginfofile.seek(0, 0)
        for line in imginfofile.readlines():
            lines = line.split(':')
            if len(lines) < 1 or lines[0][0] == '#':
                continue
            if lines[0].strip() == 'mtk_header_name':
                name = lines[1].strip()
                break
        data = struct.pack('<II32s472s', magic, size, name.encode(), b''.ljust(472, b'\xff'))
        outfile.write(data)

        imgfile.seek(off1, 0)
        imginfofile.seek(off2, 0)
        return True
    else:
        # assert False, 'Unsupported mode.'
        return False


def unpack_ramdisk(ramdisk=None, directory=None):
    if ramdisk is None:
        if os.path.exists('ramdisk.gz'):
            ramdisk = 'ramdisk.gz'
        elif os.path.exists('ramdisk'):
            ramdisk = 'ramdisk'
        elif os.path.exists('ramdisk.cpio.gz'):
            ramdisk = 'ramdisk.cpio.gz'
        else:
            ramdisk = 'ramdisk.gz'

    if directory is None:
        directory = 'initrd'

    print('arguments: [ramdisk file] [directory]\n')
    print('ramdisk file: %s\n' % ramdisk)
    print('directory: %s\n' % directory)
    print('output: cpiolist.txt\n')

    if os.path.lexists(directory):
        raise SystemExit('please remove %s' % directory)

    tmp = open(ramdisk, 'rb')
    cpiolist = open('cpiolist.txt', 'w', encoding='utf8')
    check_mtk_head(tmp, cpiolist)
    pos = tmp.tell()

    compress_level = 0
    magic = tmp.read(6)
    if magic[:3] == struct.pack('3B', 0x1f, 0x8b, 0x08):
        tmp.seek(pos, 0)
        compress_level = 6
        cpio = CPIOGZIP(None, 'rb', compress_level, tmp)
    elif magic.decode('latin') == '070701':
        tmp.seek(pos, 0)
        cpio = tmp
    else:
        tmp.close()
        raise IOError('invalid ramdisk')

    cpiolist.write('compress_level:%d\n' % compress_level)
    print('compress: %s\n' % (compress_level > 0))
    parse_cpio(cpio, directory, cpiolist)


def repack_ramdisk(cpiolist=None):
    if cpiolist is None:
        cpiolist = 'cpiolist.txt'

    print('arguments: [cpiolist file]\n')
    print('cpiolist file: %s\n' % cpiolist)
    print('output: ramdisk.cpio.gz\n')

    tmp = open('ramdisk.cpio.gz.tmp', 'wb')
    out = open('ramdisk.cpio.gz', 'wb')

    info = open(cpiolist, 'r', encoding='utf8')
    compress_level = 6

    off2 = info.tell()
    info.seek(0, 0)
    for line in info.readlines():
        lines = line.split(':')
        if len(lines) < 1 or lines[0][0] == '#':
            continue
        if lines[0].strip() == 'compress_level':
            compress_level = int(lines[1], 10)
            break
    info.seek(off2, 0)

    if compress_level <= 0:
        cpiogz = tmp
    else:
        if compress_level > 9:
            compress_level = 9
        cpiogz = CPIOGZIP(None, 'wb', compress_level, tmp)
    print('compress_level: %d\n' % compress_level)
    write_cpio(info, cpiogz)
    # cpiogz.close()
    tmp.close()
    # info.close()

    tmp = open('ramdisk.cpio.gz.tmp', 'rb')
    info = open(cpiolist, 'r')
    if try_add_head(tmp, out, info):
        while True:
            data = tmp.read(65536)
            if not data:
                break
            out.write(data)
        tmp.close()
        out.close()
        os.remove('ramdisk.cpio.gz.tmp')
    else:
        tmp.close()
        out.close()
        os.remove('ramdisk.cpio.gz')
        os.rename('ramdisk.cpio.gz.tmp', 'ramdisk.cpio.gz')
    info.close()
