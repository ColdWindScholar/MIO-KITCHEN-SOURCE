#!/usr/bin/env python
import bz2
import lzma
import struct
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count

import zstandard

from update_metadata_reader import Type, Metadata

flatten = lambda l: [item for sublist in l for item in sublist]


def u32(x):
    return struct.unpack(">I", x)[0]


def u64(x):
    return struct.unpack(">Q", x)[0]


class Dumper:
    def __init__(
            self, payloadfile, out, diff=None, old=None, images="", workers=cpu_count(), buffsize=8192
    ):
        self.payloadpath = payloadfile
        payloadfile = self.open_payloadfile()
        self.payloadfile = payloadfile
        self.tls = threading.local()
        self.out = out
        self.diff = diff
        self.old = old
        self.images = images
        self.workers = workers
        self.buffsize = buffsize
        self.validate_magic()

    def open_payloadfile(self):
        return open(self.payloadpath, 'rb')

    def run(self) -> bool:
        if self.images == "":
            partitions = self.dam2.partitions
        else:
            partitions = []
            for image in self.images:
                found = False
                for dam_part in self.dam2.partitions:
                    if dam_part.get('1') == image:
                        partitions.append(dam_part)
                        found = True
                        break
                if not found:
                    print(f"Partition {image} not found in image")

        if len(partitions) == 0:
            print("Not operating on any partitions")
            return False

        partitions_with_ops = []
        for partition in partitions:
            operations = []
            if isinstance(partition.get('8'), dict):
                operations_ = [partition.get('8')]
            else:
                operations_ = partition.get('8')
            for operation in operations_:
                self.payloadfile.seek(self.data_offset + int(operation.get("2", 0)))
                operations.append({"data_offset": self.payloadfile.tell(), "operation": operation,
                                   "data_length": int(operation.get("3"))})
            partitions_with_ops.append({"name": partition.get('1'), "operations": operations})

        self.payloadfile.close()
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {executor.submit(self.dump_part, part): part for part in partitions_with_ops}
            for future in as_completed(futures):
                partition_name = futures[future]['name']
                future.result()
                print(f"{partition_name} Done!")
        return True

    def validate_magic(self):
        magic = self.payloadfile.read(4)
        assert magic == b"CrAU"
        file_format_version = u64(self.payloadfile.read(8))
        assert file_format_version == 2
        manifest_size = u64(self.payloadfile.read(8))
        metadata_signature_size = 0
        if file_format_version > 1:
            metadata_signature_size = u32(self.payloadfile.read(4))
        manifest = self.payloadfile.read(manifest_size)
        self.metadata_signature = self.payloadfile.read(metadata_signature_size)
        self.data_offset = self.payloadfile.tell()
        self.dam2 = Metadata(manifest)
        self.block_size = self.dam2.block_size

    def data_for_op(self, operation, out_file, old_file):
        payloadfile = self.tls.payloadfile
        payloadfile.seek(operation["data_offset"])
        buffsize = self.buffsize
        processed_len = 0
        data_length = operation["data_length"]
        op = operation["operation"]

        # assert hashlib.sha256(data).digest() == op.data_sha256_hash, 'operation data hash mismatch'
        op_type = int(op.get('1'))
        if op_type == Type.REPLACE_ZSTD:
            if payloadfile.read(4) != b'(\xb5/\xfd':
                op_type = Type.REPLACE
            payloadfile.seek(payloadfile.tell() - 4)
        if op_type == Type.REPLACE_ZSTD:
            dec = zstandard.ZstdDecompressor().decompressobj()
            while processed_len < data_length:
                data = payloadfile.read(buffsize)
                processed_len += len(data)
                data = dec.decompress(data)
                out_file.write(data)
                out_file.write(dec.flush())
        elif op_type == Type.REPLACE_XZ:
            dec = lzma.LZMADecompressor()
            if isinstance(op.get('6'), dict):
                dst_extents = [op.get('6')]
            else:
                dst_extents = op.get('6')
            out_file.seek(int(dst_extents[0].get('1')) * self.block_size)
            while processed_len < data_length:
                data = payloadfile.read(buffsize)
                processed_len += len(data)
                while True:
                    data = dec.decompress(data, max_length=buffsize)
                    out_file.write(data)
                    if dec.needs_input or dec.eof:
                        break
                    data = b''
        elif op_type == Type.REPLACE_BZ:
            dec = bz2.BZ2Decompressor()
            if isinstance(op.get('6'), dict):
                dst_extents = [op.get('6')]
            else:
                dst_extents = op.get('6')
            out_file.seek(int(dst_extents[0].get('1')) * self.block_size)
            while processed_len < data_length:
                data = payloadfile.read(buffsize)
                processed_len += len(data)
                while True:
                    data = dec.decompress(data, max_length=buffsize)
                    out_file.write(data)
                    if dec.needs_input or dec.eof:
                        break
                    data = b''
        elif op_type == Type.REPLACE:
            if isinstance(op.get('6'), dict):
                dst_extents = [op.get('6')]
            else:
                dst_extents = op.get('6')
            out_file.seek(int(dst_extents[0].get('1')) * self.block_size)
            while processed_len < data_length:
                data = payloadfile.read(buffsize)
                processed_len += len(data)
                out_file.write(data)

        elif op_type == Type.SOURCE_COPY:
            if not self.diff:
                print("SOURCE_COPY supported only for differential OTA")
                sys.exit(-2)
            if isinstance(op.get('6'), dict):
                dst_extents = [op.get('6')]
            else:
                dst_extents = op.get('6')
            out_file.seek(int(dst_extents[0].get('1')) * self.block_size)
            if isinstance(op.get('4'), dict):
                src_extents = [op.get('4')]
            else:
                src_extents = op.get('4')
            for ext in src_extents:
                old_file.seek(int(ext.get('1')) * self.block_size)
                data_length = int(ext.get('2')) * self.block_size
                while processed_len < data_length:
                    data = old_file.read(buffsize)
                    processed_len += len(data)
                    out_file.write(data)
                processed_len = 0
        elif op_type == Type.ZERO:
            if isinstance(op.get('6'), dict):
                dst_extents = [op.get('6')]
            else:
                dst_extents = op.get('6')
            for ext in dst_extents:
                out_file.seek(int(ext.get('1')) * self.block_size)
                data_length = int(ext.get('2')) * self.block_size
                while processed_len < data_length:
                    data = bytes(min(data_length - processed_len, buffsize))
                    out_file.write(data)
                    processed_len += len(data)
                processed_len = 0
        else:
            print(f"Unsupported type = {op_type:d}")
            sys.exit(-1)
        del data

    def dump_part(self, part):
        name = part["name"]
        out_file = open(f"{self.out}/{name}.img", "wb")
        old_file = open(f"{self.old}/{name}.img", "rb") if self.diff else None
        with self.open_payloadfile() as payloadfile:
            self.tls.payloadfile = payloadfile
            for op in part["operations"]:
                self.data_for_op(op, out_file, old_file)
        out_file.close()
