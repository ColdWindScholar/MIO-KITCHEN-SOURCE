#!/usr/bin/env python3

"""
    Kitoboot - By Kamenta

    Kitoboot is the boot image processing tool for the beta version of Kito-android.
    In the stable version of Kito-android, all functions have been implemented using Rust,
    so this boot image processing tool is no longer maintained or optimized by us.
    Therefore, it may have some potential issues! However,
    it seems to work normally when running the Unpack/Repack functions in a regular environment.
    Kitoboot is implemented by referring to magiskboot and mkbootimg,
    so you can consider Kitoboot as a Python-written magiskboot.
"""

__version__ = "beta-1.15.2"
__author__ = "Kamenta"

import struct
import hashlib
import gzip
import bz2
import lzma
import os
import io
from enum import Enum
from typing import Optional, List, BinaryIO, Tuple
from dataclasses import dataclass
from pathlib import Path

try:
    import lz4.frame
    import lz4.block
    HAS_LZ4 = True
except ImportError:
    HAS_LZ4 = False

try:
    import lzo
    HAS_LZO = True
except ImportError:
    HAS_LZO = False


# ============================================================================
# CONSTANTS
# ============================================================================

# File names
HEADER_FILE = "header"
KERNEL_FILE = "kernel"
RAMDISK_FILE = "ramdisk.cpio"
VND_RAMDISK_DIR = "vendor_ramdisk"
SECOND_FILE = "second"
EXTRA_FILE = "extra"
KER_DTB_FILE = "kernel_dtb"
RECV_DTBO_FILE = "recovery_dtbo"
DTB_FILE = "dtb"
BOOTCONFIG_FILE = "bootconfig"
NEW_BOOT = "new-boot.img"

# Magic numbers
BOOT_MAGIC = b"ANDROID!"
VENDOR_BOOT_MAGIC = b"VNDRBOOT"
CHROMEOS_MAGIC = b"CHROMEOS"
GZIP1_MAGIC = b"\x1f\x8b"
GZIP2_MAGIC = b"\x1f\x9e"
LZOP_MAGIC = b"\x89LZO"
XZ_MAGIC = b"\xfd7zXZ"
BZIP_MAGIC = b"BZh"
LZ4_LEG_MAGIC = b"\x02\x21\x4c\x18"
LZ41_MAGIC = b"\x03\x21\x4c\x18"
LZ42_MAGIC = b"\x04\x22\x4d\x18"
MTK_MAGIC = b"\x88\x16\x88\x58"
DTB_MAGIC = b"\xd0\x0d\xfe\xed"
LG_BUMP_MAGIC = b"\x41\xa9\xe4\x67\x74\x4d\x1d\x1b\xa4\x29\xf2\xec\xea\x65\x52\x79"
DHTB_MAGIC = b"\x44\x48\x54\x42\x01\x00\x00\x00"
SEANDROID_MAGIC = b"SEANDROIDENFORCE"
TEGRABLOB_MAGIC = b"-SIGNED-BY-SIGNBLOB-"
NOOKHD_RL_MAGIC = b"Red Loader"
NOOKHD_GL_MAGIC = b"Green Loader"
NOOKHD_GR_MAGIC = b"Green Recovery"
NOOKHD_EB_MAGIC = b"eMMC boot.img+secondloader"
NOOKHD_ER_MAGIC = b"eMMC recovery.img+secondloader"
NOOKHD_PRE_HEADER_SZ = 1048576
ACCLAIM_MAGIC = b"BauwksBoot"
ACCLAIM_PRE_HEADER_SZ = 262144
AMONET_MICROLOADER_MAGIC = b"microloader"
AMONET_MICROLOADER_SZ = 1024
AVB_FOOTER_MAGIC = b"AVBf"
AVB_MAGIC = b"AVB0"
ZIMAGE_MAGIC = b"\x18\x28\x6f\x01"

# Size constants
BOOT_MAGIC_SIZE = 8
BOOT_NAME_SIZE = 16
BOOT_ID_SIZE = 32
BOOT_ARGS_SIZE = 512
BOOT_EXTRA_ARGS_SIZE = 1024
VENDOR_BOOT_ARGS_SIZE = 2048
VENDOR_RAMDISK_NAME_SIZE = 32
VENDOR_RAMDISK_TABLE_ENTRY_BOARD_ID_SIZE = 16

# Vendor ramdisk types
VENDOR_RAMDISK_TYPE_NONE = 0
VENDOR_RAMDISK_TYPE_PLATFORM = 1
VENDOR_RAMDISK_TYPE_RECOVERY = 2
VENDOR_RAMDISK_TYPE_DLKM = 3

SHA_DIGEST_SIZE = 20
SHA256_DIGEST_SIZE = 32

# Return codes
RETURN_OK = 0
RETURN_ERROR = 1
RETURN_CHROMEOS = 2
RETURN_VENDOR = 3

# LZ4 constants
LZ4_BLOCK_SIZE = 0x800000
LZ4_MAGIC = 0x184c2102


# ============================================================================
# FORMAT DETECTION
# ============================================================================

class FileFormat(Enum):
    """Supported file formats"""
    UNKNOWN = 0
    CHROMEOS = 1
    AOSP = 2
    AOSP_VENDOR = 3
    GZIP = 4
    LZOP = 5
    XZ = 6
    LZMA = 7
    BZIP2 = 8
    LZ4 = 9
    LZ4_LEGACY = 10
    LZ4_LG = 11
    MTK = 12
    DTB = 13
    DHTB = 14
    BLOB = 15
    ZIMAGE = 16
    ZOPFLI = 17

    def __str__(self):
        return self.name.lower()

    @property
    def ext(self) -> str:
        """Get file extension for format"""
        ext_map = {
            FileFormat.GZIP: "gz",
            FileFormat.ZOPFLI: "gz",
            FileFormat.LZOP: "lzo",
            FileFormat.XZ: "xz",
            FileFormat.LZMA: "lzma",
            FileFormat.BZIP2: "bz2",
            FileFormat.LZ4: "lz4",
            FileFormat.LZ4_LEGACY: "lz4",
            FileFormat.LZ4_LG: "lz4",
        }
        return ext_map.get(self, "")

    def is_compressed(self) -> bool:
        """Check if format is a compression format"""
        return self in {
            FileFormat.GZIP, FileFormat.ZOPFLI, FileFormat.LZOP,
            FileFormat.XZ, FileFormat.LZMA, FileFormat.BZIP2,
            FileFormat.LZ4, FileFormat.LZ4_LEGACY, FileFormat.LZ4_LG,
        }


def check_format(buf: bytes) -> FileFormat:
    """Detect file format from buffer"""
    if len(buf) < 4:
        return FileFormat.UNKNOWN

    if buf.startswith(CHROMEOS_MAGIC):
        return FileFormat.CHROMEOS
    elif buf.startswith(BOOT_MAGIC):
        return FileFormat.AOSP
    elif buf.startswith(VENDOR_BOOT_MAGIC):
        return FileFormat.AOSP_VENDOR
    elif buf.startswith(GZIP1_MAGIC) or buf.startswith(GZIP2_MAGIC):
        return FileFormat.GZIP
    elif buf.startswith(LZOP_MAGIC):
        return FileFormat.LZOP
    elif buf.startswith(XZ_MAGIC):
        return FileFormat.XZ
    elif len(buf) >= 13 and buf[:3] == b"\x5d\x00\x00" and buf[12] in (0xff, 0x00):
        return FileFormat.LZMA
    elif buf.startswith(BZIP_MAGIC):
        return FileFormat.BZIP2
    elif buf.startswith(LZ41_MAGIC) or buf.startswith(LZ42_MAGIC):
        return FileFormat.LZ4
    elif buf.startswith(LZ4_LEG_MAGIC):
        return FileFormat.LZ4_LEGACY
    elif buf.startswith(MTK_MAGIC):
        return FileFormat.MTK
    elif buf.startswith(DTB_MAGIC):
        return FileFormat.DTB
    elif buf.startswith(DHTB_MAGIC):
        return FileFormat.DHTB
    elif buf.startswith(TEGRABLOB_MAGIC):
        return FileFormat.BLOB
    elif len(buf) >= 0x28 and buf[0x24:0x28] == ZIMAGE_MAGIC:
        return FileFormat.ZIMAGE

    return FileFormat.UNKNOWN


def check_format_lg(buf: bytes) -> FileFormat:
    """Check format with LG LZ4 detection"""
    fmt = check_format(buf)
    if fmt == FileFormat.LZ4_LEGACY:
        off = 4
        while off + 4 <= len(buf):
            if off + 4 > len(buf):
                break
            block_sz = int.from_bytes(buf[off:off + 4], 'little')
            off += 4
            if off + block_sz > len(buf):
                return FileFormat.LZ4_LG
            off += block_sz
    return fmt


def format_name(fmt: FileFormat) -> str:
    """Get human-readable format name"""
    name_map = {
        FileFormat.GZIP: "gzip", FileFormat.ZOPFLI: "zopfli", FileFormat.LZOP: "lzop",
        FileFormat.XZ: "xz", FileFormat.LZMA: "lzma", FileFormat.BZIP2: "bzip2",
        FileFormat.LZ4: "lz4", FileFormat.LZ4_LEGACY: "lz4_legacy", FileFormat.LZ4_LG: "lz4_lg",
        FileFormat.MTK: "mtk", FileFormat.DTB: "dtb", FileFormat.CHROMEOS: "chromeos",
        FileFormat.AOSP: "aosp", FileFormat.AOSP_VENDOR: "aosp_vendor",
        FileFormat.DHTB: "dhtb", FileFormat.BLOB: "blob", FileFormat.ZIMAGE: "zimage",
    }
    return name_map.get(fmt, "unknown")


# ============================================================================
# COMPRESSION
# ============================================================================

class LZ4BlockDecoder:
    """LZ4 block format decoder"""
    
    def __init__(self, stream: BinaryIO):
        self.stream = stream
        self.buffer = b""
        
    def read(self, size: int = -1) -> bytes:
        if not HAS_LZ4:
            raise RuntimeError("lz4 library not available")
        
        result = b""
        while size < 0 or len(result) < size:
            if not self.buffer:
                block_data = self.stream.read(4)
                if len(block_data) < 4:
                    break
                    
                block_size = struct.unpack('<I', block_data)[0]
                
                if block_size == LZ4_MAGIC:
                    block_data = self.stream.read(4)
                    if len(block_data) < 4:
                        break
                    block_size = struct.unpack('<I', block_data)[0]
                
                if block_size > 0x02000000:
                    break
                    
                compressed = self.stream.read(block_size)
                if len(compressed) < block_size:
                    break
                
                try:
                    self.buffer = lz4.block.decompress(compressed, uncompressed_size=LZ4_BLOCK_SIZE)
                except Exception:
                    break
            
            if size < 0:
                result += self.buffer
                self.buffer = b""
            else:
                chunk_size = min(size - len(result), len(self.buffer))
                result += self.buffer[:chunk_size]
                self.buffer = self.buffer[chunk_size:]
                
        return result


class LZ4BlockEncoder:
    """LZ4 block format encoder"""
    
    def __init__(self, stream: BinaryIO, is_lg: bool = False):
        self.stream = stream
        self.is_lg = is_lg
        self.buffer = b""
        self.total_size = 0
        self.header_written = False
        
    def write(self, data: bytes) -> int:
        if not HAS_LZ4:
            raise RuntimeError("lz4 library not available")
            
        if not self.header_written:
            self.stream.write(struct.pack('<I', LZ4_MAGIC))
            self.header_written = True
        
        self.buffer += data
        self.total_size += len(data)
        
        while len(self.buffer) >= LZ4_BLOCK_SIZE:
            block = self.buffer[:LZ4_BLOCK_SIZE]
            self.buffer = self.buffer[LZ4_BLOCK_SIZE:]
            compressed = lz4.block.compress(block, mode='high_compression', compression=12)
            self.stream.write(struct.pack('<I', len(compressed)))
            self.stream.write(compressed)
            
        return len(data)
    
    def flush(self):
        if not HAS_LZ4:
            return
            
        if self.buffer:
            compressed = lz4.block.compress(self.buffer, mode='high_compression', compression=12)
            self.stream.write(struct.pack('<I', len(compressed)))
            self.stream.write(compressed)
            self.buffer = b""
        
        if self.is_lg:
            self.stream.write(struct.pack('<I', self.total_size))
        
        self.stream.flush()


def get_decoder(fmt: FileFormat, stream: BinaryIO) -> BinaryIO:
    """Get decompressor for format"""
    if fmt == FileFormat.GZIP or fmt == FileFormat.ZOPFLI:
        return gzip.GzipFile(fileobj=stream, mode='rb')
    elif fmt == FileFormat.BZIP2:
        return bz2.BZ2File(stream, 'rb')
    elif fmt == FileFormat.XZ or fmt == FileFormat.LZMA:
        return lzma.LZMAFile(stream, 'rb')
    elif fmt == FileFormat.LZ4:
        if not HAS_LZ4:
            raise RuntimeError("lz4 library not installed: pip install lz4")
        return lz4.frame.LZ4FrameFile(stream, 'rb')
    elif fmt == FileFormat.LZ4_LEGACY or fmt == FileFormat.LZ4_LG:
        return LZ4BlockDecoder(stream)
    elif fmt == FileFormat.LZOP:
        raise RuntimeError("lzop not supported, install python-lzo")
    else:
        raise ValueError(f"Unsupported compression format: {fmt}")


def get_encoder(fmt: FileFormat, stream: BinaryIO) -> BinaryIO:
    """Get compressor for format"""
    if fmt == FileFormat.GZIP or fmt == FileFormat.ZOPFLI:
        return gzip.GzipFile(fileobj=stream, mode='wb', compresslevel=9)
    elif fmt == FileFormat.BZIP2:
        return bz2.BZ2File(stream, 'wb', compresslevel=9)
    elif fmt == FileFormat.XZ:
        return lzma.LZMAFile(stream, 'wb', format=lzma.FORMAT_XZ, preset=9)
    elif fmt == FileFormat.LZMA:
        return lzma.LZMAFile(stream, 'wb', format=lzma.FORMAT_ALONE, preset=9)
    elif fmt == FileFormat.LZ4:
        if not HAS_LZ4:
            raise RuntimeError("lz4 library not installed: pip install lz4")
        return lz4.frame.LZ4FrameFile(stream, 'wb', compression_level=9)
    elif fmt == FileFormat.LZ4_LEGACY:
        return LZ4BlockEncoder(stream, is_lg=False)
    elif fmt == FileFormat.LZ4_LG:
        return LZ4BlockEncoder(stream, is_lg=True)
    elif fmt == FileFormat.LZOP:
        raise RuntimeError("lzop not supported")
    else:
        raise ValueError(f"Unsupported compression format: {fmt}")


def decompress_bytes(fmt: FileFormat, data: bytes) -> bytes:
    """Decompress data"""
    stream = io.BytesIO(data)
    decoder = get_decoder(fmt, stream)
    return decoder.read()


def compress_bytes(fmt: FileFormat, data: bytes) -> bytes:
    """Compress data"""
    stream = io.BytesIO()
    encoder = get_encoder(fmt, stream)
    encoder.write(data)
    if hasattr(encoder, 'flush'):
        encoder.flush()
    if hasattr(encoder, 'close'):
        encoder.close()
    return stream.getvalue()


def decompress_file(input_path: str, output_path: str, fmt: Optional[FileFormat] = None):
    """Decompress file"""
    with open(input_path, 'rb') as f:
        header = f.read(4096)
        f.seek(0)
        
        if fmt is None:
            fmt = check_format(header)
        
        if not fmt.is_compressed():
            raise ValueError(f"Not a compressed file: {fmt}")
        
        decoder = get_decoder(fmt, f)
        with open(output_path, 'wb') as out:
            while True:
                chunk = decoder.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)


def compress_file(input_path: str, output_path: str, fmt: FileFormat):
    """Compress file"""
    if not fmt.is_compressed():
        raise ValueError(f"Not a compression format: {fmt}")
    
    with open(input_path, 'rb') as f:
        data = f.read()
    
    with open(output_path, 'wb') as out:
        encoder = get_encoder(fmt, out)
        encoder.write(data)
        if hasattr(encoder, 'flush'):
            encoder.flush()
        if hasattr(encoder, 'close'):
            encoder.close()


# ============================================================================
# BOOT IMAGE STRUCTURES
# ============================================================================

def align_to(value: int, alignment: int) -> int:
    """Align value to alignment boundary"""
    return ((value + alignment - 1) // alignment) * alignment


@dataclass
class BootImageHeader:
    """Base boot image header"""
    magic: bytes
    kernel_size: int
    kernel_addr: int
    ramdisk_size: int
    ramdisk_addr: int
    second_size: int
    second_addr: int
    tags_addr: int
    page_size: int
    header_version: int
    os_version: int
    name: bytes
    cmdline: bytes
    id: bytes
    extra_cmdline: bytes
    
    recovery_dtbo_size: int = 0
    recovery_dtbo_offset: int = 0
    header_size: int = 0
    dtb_size: int = 0
    dtb_addr: int = 0
    reserved: List[int] = None
    signature_size: int = 0
    extra_size: int = 0
    
    @staticmethod
    def from_bytes(data: bytes) -> 'BootImageHeader':
        """Parse boot image header from bytes"""
        magic = data[0:8]
        
        if magic != BOOT_MAGIC:
            raise ValueError("Invalid boot magic")
        
        (kernel_size, kernel_addr, ramdisk_size, ramdisk_addr,
         second_size, second_addr, tags_addr, page_size, header_version) = \
            struct.unpack('<9I', data[8:44])
        
        if page_size >= 0x02000000:
            return BootImageHeader._parse_pxa(data)
        
        if header_version == 3 or header_version == 4:
            return BootImageHeader._parse_v3_v4(data, header_version)
        
        os_version = struct.unpack('<I', data[44:48])[0]
        name = data[48:64]
        cmdline = data[64:576]
        id_bytes = data[576:608]
        extra_cmdline = data[608:1632]
        
        hdr = BootImageHeader(
            magic=magic, kernel_size=kernel_size, kernel_addr=kernel_addr,
            ramdisk_size=ramdisk_size, ramdisk_addr=ramdisk_addr,
            second_size=second_size, second_addr=second_addr,
            tags_addr=tags_addr, page_size=page_size,
            header_version=0 if header_version > 100000 else header_version,
            os_version=os_version, name=name, cmdline=cmdline,
            id=id_bytes, extra_cmdline=extra_cmdline,
        )
        
        if header_version > 100000:
            hdr.extra_size = header_version
            hdr.header_version = 0
        
        if hdr.header_version >= 1 and len(data) >= 1648:
            hdr.recovery_dtbo_size, = struct.unpack('<I', data[1632:1636])
            hdr.recovery_dtbo_offset, = struct.unpack('<Q', data[1636:1644])
            hdr.header_size, = struct.unpack('<I', data[1644:1648])
        
        if hdr.header_version >= 2 and len(data) >= 1660:
            hdr.dtb_size, = struct.unpack('<I', data[1648:1652])
            hdr.dtb_addr, = struct.unpack('<Q', data[1652:1660])
        
        return hdr
    
    @staticmethod
    def _parse_v3_v4(data: bytes, version: int) -> 'BootImageHeader':
        """Parse v3/v4 boot header"""
        magic = data[0:8]
        kernel_size, ramdisk_size, os_version, header_size = struct.unpack('<4I', data[8:24])
        reserved = list(struct.unpack('<4I', data[24:40]))
        header_version, = struct.unpack('<I', data[40:44])
        cmdline = data[44:1580]
        
        hdr = BootImageHeader(
            magic=magic, kernel_size=kernel_size, kernel_addr=0,
            ramdisk_size=ramdisk_size, ramdisk_addr=0, second_size=0,
            second_addr=0, tags_addr=0, page_size=4096, header_version=header_version,
            os_version=os_version, name=b"", cmdline=cmdline[:BOOT_ARGS_SIZE],
            id=b"", extra_cmdline=cmdline[BOOT_ARGS_SIZE:],
            header_size=header_size, reserved=reserved,
        )
        
        if version == 4 and len(data) >= 1584:
            hdr.signature_size, = struct.unpack('<I', data[1580:1584])
        
        return hdr
    
    @staticmethod
    def _parse_pxa(data: bytes) -> 'BootImageHeader':
        """Parse Samsung PXA boot header"""
        (kernel_size, kernel_addr, ramdisk_size, ramdisk_addr,
         second_size, second_addr, extra_size, unknown, tags_addr, page_size) = \
            struct.unpack('<10I', data[8:48])
        
        name = data[48:72]
        cmdline = data[72:584]
        id_bytes = data[584:616]
        extra_cmdline = data[616:1640]
        
        return BootImageHeader(
            magic=BOOT_MAGIC, kernel_size=kernel_size, kernel_addr=kernel_addr,
            ramdisk_size=ramdisk_size, ramdisk_addr=ramdisk_addr,
            second_size=second_size, second_addr=second_addr,
            tags_addr=tags_addr, page_size=page_size, header_version=0,
            os_version=0, name=name, cmdline=cmdline, id=id_bytes,
            extra_cmdline=extra_cmdline, extra_size=extra_size,
        )
    
    def to_bytes(self) -> bytes:
        """Convert header to bytes"""
        if self.header_version >= 3:
            return self._to_bytes_v3_v4()
        
        if self.header_version >= 2:
            size = 1660
        elif self.header_version >= 1:
            size = 1648
        else:
            size = 1632
        
        data = bytearray(size)
        
        struct.pack_into('<8s9I', data, 0,
                         self.magic, self.kernel_size, self.kernel_addr,
                         self.ramdisk_size, self.ramdisk_addr,
                         self.second_size, self.second_addr,
                         self.tags_addr, self.page_size,
                         self.extra_size if self.header_version == 0 and self.extra_size else self.header_version)
        
        struct.pack_into('<I', data, 44, self.os_version)
        data[48:64] = self.name[:16].ljust(16, b'\x00')
        data[64:576] = self.cmdline[:BOOT_ARGS_SIZE].ljust(BOOT_ARGS_SIZE, b'\x00')
        data[576:608] = self.id[:BOOT_ID_SIZE].ljust(BOOT_ID_SIZE, b'\x00')
        data[608:1632] = self.extra_cmdline[:BOOT_EXTRA_ARGS_SIZE].ljust(BOOT_EXTRA_ARGS_SIZE, b'\x00')
        
        if self.header_version >= 1:
            struct.pack_into('<IQI', data, 1632,
                             self.recovery_dtbo_size,
                             self.recovery_dtbo_offset,
                             self.header_size if self.header_size else size)
        
        if self.header_version >= 2:
            struct.pack_into('<IQ', data, 1648, self.dtb_size, self.dtb_addr)
        
        return bytes(data)
    
    def _to_bytes_v3_v4(self) -> bytes:
        """Convert v3/v4 header to bytes"""
        size = 1584 if self.header_version == 4 else 1580
        data = bytearray(size)
        
        struct.pack_into('<8s4I', data, 0, self.magic, self.kernel_size, self.ramdisk_size,
                         self.os_version, self.header_size if self.header_size else size)
        
        if self.reserved:
            struct.pack_into('<4I', data, 24, *self.reserved[:4])
        
        struct.pack_into('<I', data, 40, self.header_version)
        
        cmdline = self.cmdline[:BOOT_ARGS_SIZE] + self.extra_cmdline[:BOOT_EXTRA_ARGS_SIZE]
        data[44:1580] = cmdline[:1536].ljust(1536, b'\x00')
        
        if self.header_version == 4:
            struct.pack_into('<I', data, 1580, self.signature_size)
        
        return bytes(data)
    
    def print_info(self):
        """Print header information"""
        print(f"{'HEADER_VER':<15} [{self.header_version}]")
        if self.header_version < 3:
            print(f"{'KERNEL_SZ':<15} [{self.kernel_size}]")
        print(f"{'RAMDISK_SZ':<15} [{self.ramdisk_size}]")
        if self.header_version < 3:
            print(f"{'SECOND_SZ':<15} [{self.second_size}]")
        if self.header_version == 0 and self.extra_size:
            print(f"{'EXTRA_SZ':<15} [{self.extra_size}]")
        if self.header_version in (1, 2):
            print(f"{'RECOV_DTBO_SZ':<15} [{self.recovery_dtbo_size}]")
        if self.header_version == 2:
            print(f"{'DTB_SZ':<15} [{self.dtb_size}]")
        
        if self.os_version:
            version = self.os_version >> 11
            patch_level = self.os_version & 0x7ff
            a = (version >> 14) & 0x7f
            b = (version >> 7) & 0x7f
            c = version & 0x7f
            y = (patch_level >> 4) + 2000
            m = patch_level & 0xf
            print(f"{'OS_VERSION':<15} [{a}.{b}.{c}]")
            print(f"{'OS_PATCH_LEVEL':<15} [{y}-{m:02d}]")
        
        print(f"{'PAGESIZE':<15} [{self.page_size}]")
        if self.name.strip(b'\x00'):
            print(f"{'NAME':<15} [{self.name.decode('ascii', errors='ignore').rstrip(chr(0))}]")
        
        cmdline_full = (self.cmdline + self.extra_cmdline).rstrip(b'\x00')
        print(f"{'CMDLINE':<15} [{cmdline_full.decode('ascii', errors='ignore')}]")


@dataclass
class VendorBootHeader:
    """Vendor boot image header (v3+)"""
    magic: bytes
    header_version: int
    page_size: int
    kernel_addr: int
    ramdisk_addr: int
    ramdisk_size: int
    cmdline: bytes
    tags_addr: int
    name: bytes
    header_size: int
    dtb_size: int
    dtb_addr: int
    vendor_ramdisk_table_size: int = 0
    vendor_ramdisk_table_entry_num: int = 0
    vendor_ramdisk_table_entry_size: int = 0
    bootconfig_size: int = 0
    
    @staticmethod
    def from_bytes(data: bytes) -> 'VendorBootHeader':
        """Parse vendor boot header"""
        magic = data[0:8]
        if magic != VENDOR_BOOT_MAGIC:
            raise ValueError("Invalid vendor boot magic")
        
        (header_version, page_size, kernel_addr, ramdisk_addr, ramdisk_size) = \
            struct.unpack('<5I', data[8:28])
        
        cmdline = data[28:2076]
        tags_addr, = struct.unpack('<I', data[2076:2080])
        name = data[2080:2096]
        header_size, dtb_size = struct.unpack('<2I', data[2096:2104])
        dtb_addr, = struct.unpack('<Q', data[2104:2112])
        
        hdr = VendorBootHeader(
            magic=magic, header_version=header_version, page_size=page_size,
            kernel_addr=kernel_addr, ramdisk_addr=ramdisk_addr,
            ramdisk_size=ramdisk_size, cmdline=cmdline, tags_addr=tags_addr,
            name=name, header_size=header_size, dtb_size=dtb_size, dtb_addr=dtb_addr,
        )
        
        if header_version >= 4 and len(data) >= 2128:
            (hdr.vendor_ramdisk_table_size,
             hdr.vendor_ramdisk_table_entry_num,
             hdr.vendor_ramdisk_table_entry_size,
             hdr.bootconfig_size) = struct.unpack('<4I', data[2112:2128])
        
        return hdr


class BootImage:
    """Boot image container"""
    
    def __init__(self, path: str):
        self.path = path
        self.header: Optional[BootImageHeader] = None
        self.vendor_header: Optional[VendorBootHeader] = None
        
        self.kernel: bytes = b""
        self.ramdisk: bytes = b""
        self.second: bytes = b""
        self.extra: bytes = b""
        self.recovery_dtbo: bytes = b""
        self.dtb: bytes = b""
        self.kernel_dtb: bytes = b""
        self.signature: bytes = b""
        self.bootconfig: bytes = b""
        
        self.kernel_fmt = FileFormat.UNKNOWN
        self.ramdisk_fmt = FileFormat.UNKNOWN
        self.extra_fmt = FileFormat.UNKNOWN
        
        self.flags = {
            'mtk_kernel': False, 'mtk_ramdisk': False, 'chromeos': False,
            'dhtb': False, 'seandroid': False, 'lg_bump': False,
            'sha256': False, 'blob': False, 'nookhd': False,
            'acclaim': False, 'amonet': False, 'avb1_signed': False,
            'avb': False, 'zimage': False,
        }
        
        self.mtk_kernel_hdr: Optional[bytes] = None
        self.mtk_ramdisk_hdr: Optional[bytes] = None
        self.zimage_hdr: Optional[bytes] = None
        self.zimage_tail: bytes = b""
        
        self._parse()
    
    def _parse(self):
        """Parse boot image"""
        with open(self.path, 'rb') as f:
            data = f.read()
        
        print(f"Parsing boot image: [{self.path}]")
        
        offset = 0
        while offset < len(data):
            fmt = check_format_lg(data[offset:offset + 512])
            
            if fmt == FileFormat.CHROMEOS:
                self.flags['chromeos'] = True
                offset += 65536
                continue
            elif fmt == FileFormat.DHTB:
                self.flags['dhtb'] = True
                self.flags['seandroid'] = True
                print("DHTB_HDR")
                offset += 512
                continue
            elif fmt == FileFormat.BLOB:
                self.flags['blob'] = True
                print("TEGRA_BLOB")
                offset += 88
                continue
            elif fmt in (FileFormat.AOSP, FileFormat.AOSP_VENDOR):
                self._parse_aosp(data[offset:], fmt == FileFormat.AOSP_VENDOR)
                return
            
            offset += 1
        
        raise ValueError("No valid boot image found")
    
    def _parse_aosp(self, data: bytes, is_vendor: bool):
        """Parse AOSP boot image"""
        if is_vendor:
            print("VENDOR_BOOT_HDR")
            self.vendor_header = VendorBootHeader.from_bytes(data)
            self._parse_vendor_components(data)
        else:
            self.header = BootImageHeader.from_bytes(data)
            
            if self.header.id:
                for i in range(SHA_DIGEST_SIZE + 4, SHA256_DIGEST_SIZE):
                    if self.header.id[i] != 0:
                        self.flags['sha256'] = True
                        break
            
            self.header.print_info()
            self._parse_components(data)
    
    def _parse_components(self, data: bytes):
        """Parse boot image components"""
        hdr = self.header
        page_size = hdr.page_size
        
        hdr_size = hdr.header_size if hdr.header_size > 0 else len(hdr.to_bytes())
        off = align_to(hdr_size, 4096 if hdr.header_version >= 3 else page_size)
        
        # Kernel
        if hdr.kernel_size > 0:
            kernel_end = off + hdr.kernel_size
            kernel_data = data[off:kernel_end]
            
            if len(kernel_data) >= 512 and kernel_data[:4] == MTK_MAGIC:
                print("MTK_KERNEL_HDR")
                self.flags['mtk_kernel'] = True
                self.mtk_kernel_hdr = kernel_data[:512]
                mtk_size = struct.unpack('<I', kernel_data[4:8])[0]
                mtk_name = kernel_data[8:40].rstrip(b'\x00')
                print(f"{'SIZE':<15} [{mtk_size}]")
                if mtk_name:
                    print(f"{'NAME':<15} [{mtk_name.decode('ascii', errors='ignore')}]")
                kernel_data = kernel_data[512:]
                hdr.kernel_size -= 512
            
            dtb_off = self._find_dtb_offset(kernel_data)
            if dtb_off > 0:
                self.kernel_dtb = kernel_data[dtb_off:]
                kernel_data = kernel_data[:dtb_off]
                hdr.kernel_size = dtb_off
                print(f"{'KERNEL_DTB_SZ':<15} [{len(self.kernel_dtb)}]")
            
            self.kernel_fmt = check_format_lg(kernel_data)
            print(f"{'KERNEL_FMT':<15} [{format_name(self.kernel_fmt)}]")
            self.kernel = kernel_data
            off = align_to(kernel_end, page_size)
        
        # Ramdisk
        if hdr.ramdisk_size > 0:
            ramdisk_end = off + hdr.ramdisk_size
            ramdisk_data = data[off:ramdisk_end]
            
            if len(ramdisk_data) >= 512 and ramdisk_data[:4] == MTK_MAGIC:
                print("MTK_RAMDISK_HDR")
                self.flags['mtk_ramdisk'] = True
                self.mtk_ramdisk_hdr = ramdisk_data[:512]
                mtk_size = struct.unpack('<I', ramdisk_data[4:8])[0]
                mtk_name = ramdisk_data[8:40].rstrip(b'\x00')
                print(f"{'SIZE':<15} [{mtk_size}]")
                if mtk_name:
                    print(f"{'NAME':<15} [{mtk_name.decode('ascii', errors='ignore')}]")
                ramdisk_data = ramdisk_data[512:]
                hdr.ramdisk_size -= 512
            
            self.ramdisk_fmt = check_format_lg(ramdisk_data)
            print(f"{'RAMDISK_FMT':<15} [{format_name(self.ramdisk_fmt)}]")
            self.ramdisk = ramdisk_data
            off = align_to(ramdisk_end, page_size)
        
        # Second
        if hdr.second_size > 0:
            second_end = off + hdr.second_size
            self.second = data[off:second_end]
            off = align_to(second_end, page_size)
        
        # Extra
        if hdr.extra_size > 0:
            extra_end = off + hdr.extra_size
            extra_data = data[off:extra_end]
            self.extra_fmt = check_format_lg(extra_data)
            print(f"{'EXTRA_FMT':<15} [{format_name(self.extra_fmt)}]")
            self.extra = extra_data
            off = align_to(extra_end, page_size)
        
        # Recovery DTBO
        if hdr.recovery_dtbo_size > 0:
            hdr.recovery_dtbo_offset = off
            dtbo_end = off + hdr.recovery_dtbo_size
            self.recovery_dtbo = data[off:dtbo_end]
            off = align_to(dtbo_end, page_size)
        
        # DTB
        if hdr.dtb_size > 0:
            dtb_end = off + hdr.dtb_size
            self.dtb = data[off:dtb_end]
            off = align_to(dtb_end, page_size)
        
        # Signature (v4)
        if hdr.signature_size > 0:
            sig_end = off + hdr.signature_size
            self.signature = data[off:sig_end]
    
    def _parse_vendor_components(self, data: bytes):
        """Parse vendor boot image components"""
        hdr = self.vendor_header
        page_size = hdr.page_size
        
        off = align_to(hdr.header_size, page_size)
        
        if hdr.ramdisk_size > 0:
            ramdisk_end = off + hdr.ramdisk_size
            self.ramdisk = data[off:ramdisk_end]
            off = align_to(ramdisk_end, page_size)
        
        if hdr.dtb_size > 0:
            dtb_end = off + hdr.dtb_size
            self.dtb = data[off:dtb_end]
            off = align_to(dtb_end, page_size)
        
        if hdr.bootconfig_size > 0:
            bc_end = off + hdr.bootconfig_size
            self.bootconfig = data[off:bc_end]
    
    def _find_dtb_offset(self, data: bytes) -> int:
        """Find DTB offset in kernel"""
        offset = 0
        while offset < len(data) - 4:
            offset = data.find(DTB_MAGIC, offset)
            if offset == -1:
                return -1
            
            if offset + 40 > len(data):
                offset += 1
                continue
            
            totalsize = struct.unpack('>I', data[offset + 4:offset + 8])[0]
            if totalsize > len(data) - offset:
                offset += 1
                continue
            
            off_dt_struct = struct.unpack('>I', data[offset + 8:offset + 12])[0]
            if off_dt_struct > len(data) - offset:
                offset += 1
                continue
            
            if offset + off_dt_struct + 4 <= len(data):
                tag = struct.unpack('>I', data[offset + off_dt_struct:offset + off_dt_struct + 4])[0]
                if tag == 0x00000001:
                    return offset
            
            offset += 1
        
        return -1


# ============================================================================
# UNPACK
# ============================================================================

def dump_file(data: bytes, filename: str, output_dir: str = "."):
    """Dump data to file"""
    if not data:
        return
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'wb') as f:
        f.write(data)


def unpack(image_path: str, skip_decomp: bool = False, dump_header: bool = False, output_dir: str = ".") -> int:
    """
    Unpack boot image to individual components
    
    Args:
        image_path: Path to boot image
        skip_decomp: Skip decompression
        dump_header: Dump header file
        output_dir: Output directory (default: current directory)
    
    Returns:
        Return code (RETURN_OK, RETURN_CHROMEOS, RETURN_VENDOR, RETURN_ERROR)
    """
    if output_dir != ".":
        os.makedirs(output_dir, exist_ok=True)
    
    try:
        boot = BootImage(image_path)
    except Exception as e:
        print(f"Error: {e}")
        return RETURN_ERROR
        
    if dump_header and boot.header:
        dump_header_file(boot, output_dir)
    
    # Dump kernel
    if boot.kernel:
        if not skip_decomp and boot.kernel_fmt.is_compressed():
            try:
                decompressed = decompress_bytes(boot.kernel_fmt, boot.kernel)
                dump_file(decompressed, KERNEL_FILE, output_dir)
            except Exception as e:
                print(f"Failed to decompress kernel: {e}")
                dump_file(boot.kernel, KERNEL_FILE, output_dir)
        else:
            dump_file(boot.kernel, KERNEL_FILE, output_dir)
    
    if boot.kernel_dtb:
        dump_file(boot.kernel_dtb, KER_DTB_FILE, output_dir)
    
    # Dump ramdisk
    if boot.ramdisk:
        if not skip_decomp and boot.ramdisk_fmt.is_compressed():
            try:
                decompressed = decompress_bytes(boot.ramdisk_fmt, boot.ramdisk)
                dump_file(decompressed, RAMDISK_FILE, output_dir)
            except Exception as e:
                print(f"Failed to decompress ramdisk: {e}")
                dump_file(boot.ramdisk, RAMDISK_FILE, output_dir)
        else:
            dump_file(boot.ramdisk, RAMDISK_FILE, output_dir)
    
    if boot.second:
        dump_file(boot.second, SECOND_FILE, output_dir)
    
    # Dump extra
    if boot.extra:
        if not skip_decomp and boot.extra_fmt.is_compressed():
            try:
                decompressed = decompress_bytes(boot.extra_fmt, boot.extra)
                dump_file(decompressed, EXTRA_FILE, output_dir)
            except Exception as e:
                print(f"Failed to decompress extra: {e}")
                dump_file(boot.extra, EXTRA_FILE, output_dir)
        else:
            dump_file(boot.extra, EXTRA_FILE, output_dir)
    
    if boot.recovery_dtbo:
        dump_file(boot.recovery_dtbo, RECV_DTBO_FILE, output_dir)
    
    if boot.dtb:
        dump_file(boot.dtb, DTB_FILE, output_dir)
    
    if boot.bootconfig:
        dump_file(boot.bootconfig, BOOTCONFIG_FILE, output_dir)
    
    if boot.flags.get('chromeos'):
        return RETURN_CHROMEOS
    elif boot.vendor_header is not None:
        return RETURN_VENDOR
    
    return RETURN_OK


def dump_header_file(boot: BootImage, output_dir: str = "."):
    """Dump header information to file"""
    hdr = boot.header
    if not hdr:
        return
    
    filepath = os.path.join(output_dir, HEADER_FILE)
    with open(filepath, 'w') as f:
        if hdr.name.strip(b'\x00'):
            name = hdr.name.decode('ascii', errors='ignore').rstrip('\x00')
            f.write(f"name={name}\n")
        
        cmdline = (hdr.cmdline + hdr.extra_cmdline).rstrip(b'\x00')
        cmdline_str = cmdline.decode('ascii', errors='ignore')
        f.write(f"cmdline={cmdline_str}\n")
        
        if hdr.os_version:
            version = hdr.os_version >> 11
            patch_level = hdr.os_version & 0x7ff
            a = (version >> 14) & 0x7f
            b = (version >> 7) & 0x7f
            c = version & 0x7f
            y = (patch_level >> 4) + 2000
            m = patch_level & 0xf
            f.write(f"os_version={a}.{b}.{c}\n")
            f.write(f"os_patch_level={y}-{m:02d}\n")


# ============================================================================
# REPACK
# ============================================================================

def read_file(filename: str, input_dir: str = ".") -> Optional[bytes]:
    """Read file if it exists"""
    filepath = os.path.join(input_dir, filename)
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'rb') as f:
        return f.read()


def parse_header_file(hdr, input_dir: str = "."):
    """Parse and update header from header file"""
    filepath = os.path.join(input_dir, HEADER_FILE)
    if not os.path.exists(filepath):
        return
    
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or '=' not in line:
                continue
            
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            
            if key == 'name' and hasattr(hdr, 'name'):
                hdr.name = value.encode('ascii')[:BOOT_NAME_SIZE].ljust(BOOT_NAME_SIZE, b'\x00')
            elif key == 'cmdline':
                cmdline_bytes = value.encode('ascii')
                if len(cmdline_bytes) > BOOT_ARGS_SIZE:
                    hdr.cmdline = cmdline_bytes[:BOOT_ARGS_SIZE]
                    hdr.extra_cmdline = cmdline_bytes[BOOT_ARGS_SIZE:BOOT_ARGS_SIZE + BOOT_EXTRA_ARGS_SIZE]
                else:
                    hdr.cmdline = cmdline_bytes.ljust(BOOT_ARGS_SIZE, b'\x00')
                    hdr.extra_cmdline = b'\x00' * BOOT_EXTRA_ARGS_SIZE
            elif key == 'os_version':
                parts = value.split('.')
                if len(parts) == 3:
                    a, b, c = int(parts[0]), int(parts[1]), int(parts[2])
                    patch_level = hdr.os_version & 0x7ff
                    hdr.os_version = (((a << 14) | (b << 7) | c) << 11) | patch_level
            elif key == 'os_patch_level':
                parts = value.split('-')
                if len(parts) == 2:
                    y, m = int(parts[0]) - 2000, int(parts[1])
                    os_ver = hdr.os_version >> 11
                    hdr.os_version = (os_ver << 11) | (y << 4) | m


def calculate_checksum(kernel: bytes, ramdisk: bytes, second: bytes, extra: bytes,
                       recovery_dtbo: bytes, dtb: bytes, header_version: int, use_sha256: bool) -> bytes:
    """Calculate boot image checksum (SHA1 or SHA256)"""
    h = hashlib.sha256() if use_sha256 else hashlib.sha1()
    
    for data in [kernel, ramdisk, second]:
        h.update(data)
        h.update(struct.pack('<I', len(data)))
    
    if extra:
        h.update(extra)
        h.update(struct.pack('<I', len(extra)))
    
    if header_version in (1, 2) and recovery_dtbo:
        h.update(recovery_dtbo)
        h.update(struct.pack('<I', len(recovery_dtbo)))
    
    if header_version == 2 and dtb:
        h.update(dtb)
        h.update(struct.pack('<I', len(dtb)))
    
    return h.digest().ljust(SHA256_DIGEST_SIZE, b'\x00')


def repack(src_img: str, out_img: str, skip_comp: bool = False, input_dir: str = "."):
    """
    Repack boot image from components
    
    Args:
        src_img: Original boot image (for header reference)
        out_img: Output boot image path
        skip_comp: Skip compression
        input_dir: Input directory containing components (default: current directory)
    """
    try:
        boot = BootImage(src_img)
    except Exception as e:
        print(f"Error loading source image: {e}")
        return

    hdr = boot.header
    if not hdr:
        print("Error: No boot header found")
        return
    
    parse_header_file(hdr, input_dir)
    
    hdr.kernel_size = 0
    hdr.ramdisk_size = 0
    hdr.second_size = 0
    hdr.dtb_size = 0
    if hasattr(hdr, 'bootconfig_size'):
        hdr.bootconfig_size = 0
    
    output = bytearray()
    
    with open(src_img, 'rb') as f:
        if boot.flags.get('dhtb'):
            output.extend(f.read(512))
        elif boot.flags.get('blob'):
            output.extend(f.read(88))
        elif boot.flags.get('nookhd'):
            output.extend(f.read(NOOKHD_PRE_HEADER_SZ))
        elif boot.flags.get('acclaim'):
            output.extend(f.read(ACCLAIM_PRE_HEADER_SZ))
    
    header_off = len(output)
    output.extend(b'\x00' * align_to(len(hdr.to_bytes()), hdr.page_size))
    
    # Build kernel block
    kernel_off = len(output)
    kernel_data = bytearray()
    
    if boot.flags.get('mtk_kernel') and boot.mtk_kernel_hdr:
        kernel_data.extend(boot.mtk_kernel_hdr)
    
    if boot.flags.get('zimage') and boot.zimage_hdr:
        kernel_data.extend(boot.zimage_hdr)
    
    kernel_file = read_file(KERNEL_FILE, input_dir) or boot.kernel
    if kernel_file:
        kernel_fmt = check_format(kernel_file)
        if not skip_comp and not kernel_fmt.is_compressed() and boot.kernel_fmt.is_compressed():
            compress_fmt = FileFormat.ZOPFLI if boot.flags.get('zimage') and boot.kernel_fmt == FileFormat.GZIP else boot.kernel_fmt
            try:
                kernel_file = compress_bytes(compress_fmt, kernel_file)
            except Exception as e:
                print(f"Kernel compression failed: {e}")
        kernel_data.extend(kernel_file)
    
    if boot.flags.get('zimage') and boot.zimage_tail:
        kernel_data.extend(boot.zimage_tail)
    
    kernel_dtb = read_file(KER_DTB_FILE, input_dir) or boot.kernel_dtb
    if kernel_dtb:
        kernel_data.extend(kernel_dtb)
    
    hdr.kernel_size = len(kernel_data) - (512 if boot.flags.get('mtk_kernel') else 0)
    output.extend(kernel_data)
    
    padding = align_to(len(output), hdr.page_size) - len(output)
    if padding > 0:
        output.extend(b'\x00' * padding)
    
    # Build ramdisk block
    ramdisk_off = len(output)
    ramdisk_data = bytearray()
    
    if boot.flags.get('mtk_ramdisk') and boot.mtk_ramdisk_hdr:
        ramdisk_data.extend(boot.mtk_ramdisk_hdr)
    
    ramdisk_file = read_file(RAMDISK_FILE, input_dir) or boot.ramdisk
    if ramdisk_file:
        ramdisk_fmt = check_format(ramdisk_file)
        if not skip_comp and not ramdisk_fmt.is_compressed() and boot.ramdisk_fmt.is_compressed():
            compress_fmt = FileFormat.LZ4_LEGACY if hdr.header_version == 4 and boot.ramdisk_fmt != FileFormat.LZ4_LEGACY else boot.ramdisk_fmt
            if compress_fmt != boot.ramdisk_fmt:
                print(f"RAMDISK_FMT: [{format_name(boot.ramdisk_fmt)}] -> [{format_name(compress_fmt)}]")
            try:
                ramdisk_file = compress_bytes(compress_fmt, ramdisk_file)
            except Exception as e:
                print(f"Ramdisk compression failed: {e}")
        ramdisk_data.extend(ramdisk_file)
    
    hdr.ramdisk_size = len(ramdisk_data) - (512 if boot.flags.get('mtk_ramdisk') else 0)
    output.extend(ramdisk_data)
    
    padding = align_to(len(output), hdr.page_size) - len(output)
    if padding > 0:
        output.extend(b'\x00' * padding)
    
    # Second
    second_off = len(output)
    second_file = read_file(SECOND_FILE, input_dir)
    if second_file:
        hdr.second_size = len(second_file)
        output.extend(second_file)
        padding = align_to(len(output), hdr.page_size) - len(output)
        if padding > 0:
            output.extend(b'\x00' * padding)
    
    # Extra block
    extra_off = len(output)
    extra_file = read_file(EXTRA_FILE, input_dir)
    if extra_file:
        extra_fmt = check_format(extra_file)
        if not skip_comp and not extra_fmt.is_compressed() and boot.extra_fmt.is_compressed():
            try:
                extra_file = compress_bytes(boot.extra_fmt, extra_file)
            except Exception as e:
                print(f"Extra compression failed: {e}")
        hdr.extra_size = len(extra_file)
        output.extend(extra_file)
        padding = align_to(len(output), hdr.page_size) - len(output)
        if padding > 0:
            output.extend(b'\x00' * padding)
    
    # Recovery DTBO
    dtbo_file = read_file(RECV_DTBO_FILE, input_dir)
    if dtbo_file:
        hdr.recovery_dtbo_offset = len(output)
        hdr.recovery_dtbo_size = len(dtbo_file)
        output.extend(dtbo_file)
        padding = align_to(len(output), hdr.page_size) - len(output)
        if padding > 0:
            output.extend(b'\x00' * padding)
    
    # DTB
    dtb_off = len(output)
    dtb_file = read_file(DTB_FILE, input_dir)
    if dtb_file:
        hdr.dtb_size = len(dtb_file)
        output.extend(dtb_file)
        padding = align_to(len(output), hdr.page_size) - len(output)
        if padding > 0:
            output.extend(b'\x00' * padding)
    
    # Signature (v4)
    if hdr.signature_size > 0 and boot.signature:
        output.extend(boot.signature)
        padding = align_to(len(output), hdr.page_size) - len(output)
        if padding > 0:
            output.extend(b'\x00' * padding)
    
    # Bootconfig
    bc_file = read_file(BOOTCONFIG_FILE, input_dir)
    if bc_file and hasattr(hdr, 'bootconfig_size'):
        hdr.bootconfig_size = len(bc_file)
        output.extend(bc_file)
        padding = align_to(len(output), hdr.page_size) - len(output)
        if padding > 0:
            output.extend(b'\x00' * padding)
    
    tail_off = len(output)
    
    if boot.flags.get('seandroid'):
        output.extend(SEANDROID_MAGIC)
        if boot.flags.get('dhtb'):
            output.extend(b'\xff\xff\xff\xff')
    elif boot.flags.get('lg_bump'):
        output.extend(LG_BUMP_MAGIC)
    
    # Calculate and update checksum
    mtk_k_off = 512 if boot.flags.get('mtk_kernel') else 0
    mtk_r_off = 512 if boot.flags.get('mtk_ramdisk') else 0
    
    checksum = calculate_checksum(
        output[kernel_off + mtk_k_off:kernel_off + mtk_k_off + hdr.kernel_size],
        output[ramdisk_off + mtk_r_off:ramdisk_off + mtk_r_off + hdr.ramdisk_size],
        output[second_off:second_off + hdr.second_size] if hdr.second_size else b'',
        output[extra_off:extra_off + hdr.extra_size] if hdr.extra_size else b'',
        output[int(hdr.recovery_dtbo_offset):int(hdr.recovery_dtbo_offset) + hdr.recovery_dtbo_size] if hdr.recovery_dtbo_size else b'',
        output[dtb_off:dtb_off + hdr.dtb_size] if hdr.dtb_size else b'',
        hdr.header_version,
        boot.flags.get('sha256', False)
    )
    hdr.id = checksum[:BOOT_ID_SIZE]
    
    # Update MTK headers
    if boot.flags.get('mtk_kernel'):
        struct.pack_into('<I', output, kernel_off + 4, hdr.kernel_size)
        hdr.kernel_size += 512
    
    if boot.flags.get('mtk_ramdisk'):
        struct.pack_into('<I', output, ramdisk_off + 4, hdr.ramdisk_size)
        hdr.ramdisk_size += 512
    
    # Write final header
    if hasattr(hdr, 'header_size'):
        hdr.header_size = len(hdr.to_bytes())
    
    hdr_bytes = hdr.to_bytes()
    output[header_off:header_off + len(hdr_bytes)] = hdr_bytes
    
    # Write output file
    with open(out_img, 'wb') as f:
        f.write(output)
    
    print(f"\nRepacked: {out_img} ({len(output)} bytes)")
    hdr.print_info()


# ============================================================================
# API
# ============================================================================

def kito_unpack_boot(input_file: str, output_dir: str) -> bool:
    """
    Unpack boot image to directory
    
    Args:
        input_file: Boot image path
        output_dir: Output directory
        
    Returns:
        True if success, False otherwise
    """
    try:
        os.makedirs(output_dir, exist_ok=True)
        result = unpack(input_file, skip_decomp=False, dump_header=True, output_dir=output_dir)
        return result == 0
    except Exception as e:
        print(f"Unpack failed: {e}")
        return False


def kito_repack_boot(input_dir: str, original_boot: str, output_file: str) -> bool:
    """
    Repack boot image from directory
    
    Args:
        input_dir: Directory containing unpacked components
        original_boot: Original boot image (for reference)
        output_file: Output boot image path
        
    Returns:
        True if success, False otherwise
    """
    try:
        repack(original_boot, output_file, skip_comp=False, input_dir=input_dir)
        return os.path.exists(output_file)
    except Exception as e:
        print(f"Repack failed: {e}")
        return False


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'FileFormat', 'check_format', 'format_name',
    'compress_bytes', 'decompress_bytes', 'compress_file', 'decompress_file',
    'BootImage', 'BootImageHeader', 'VendorBootHeader',
    'unpack', 'repack',
    'kito_unpack_boot', 'kito_repack_boot',
]

