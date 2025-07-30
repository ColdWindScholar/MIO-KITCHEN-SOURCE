#!/usr/bin/env python
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
import bz2
import lzma
import struct
import sys
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count

import zstandard

from . import update_metadata_pb2 as um

flatten = lambda l: [item for sublist in l for item in sublist]
u32 = lambda x:struct.unpack(">I", x)[0]
u64 = lambda x:struct.unpack(">Q", x)[0]

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
        if zipfile.is_zipfile(self.payloadpath):
            zf = zipfile.ZipFile(self.payloadpath)
            if "payload.bin" in zf.namelist():
                return zf.open("payload.bin")
            else:
                raise ValueError("payload.bin not found in zip file")
        else:
            return open(self.payloadpath, 'rb')

    def run(self, slow=False) -> bool:
        if self.images == "":
            partitions = self.dam.partitions
        else:
            partitions = []
            for image in self.images:
                found = False
                for dam_part in self.dam.partitions:
                    if dam_part.partition_name == image:
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
            for operation in partition.operations:
                self.payloadfile.seek(self.data_offset + operation.data_offset)
                operations.append(
                    {
                        "data_offset": self.payloadfile.tell(),
                        "operation": operation,
                        "data_length": operation.data_length,
                    }
                )
            partitions_with_ops.append(
                {
                    "partition": partition,
                    "operations": operations,
                }
            )

        self.payloadfile.close()
        if slow:
            self.extract_slow(partitions_with_ops)
        else:
            self.multiprocess_partitions(partitions_with_ops)
        return True

    def extract_slow(self, partitions):
        for part in partitions:
            self.dump_part(part)

    def multiprocess_partitions(self, partitions):
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {executor.submit(self.dump_part, part): part for part in partitions}
            for future in as_completed(futures):
                partition_name = futures[future]['partition'].partition_name
                future.result()
                print(f"{partition_name} Done!")

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
        self.dam = um.DeltaArchiveManifest()
        self.dam.ParseFromString(manifest)
        self.block_size = self.dam.block_size

    def data_for_op(self, operation, out_file, old_file):
        payloadfile = self.tls.payloadfile
        payloadfile.seek(operation["data_offset"])
        buffsize = self.buffsize
        processed_len = 0
        data_length = operation["data_length"]
        op = operation["operation"]

        ZSTD_TYPE = getattr(um.InstallOperation, 'ZSTD', -1)
        REPLACE_ZSTD_TYPE = getattr(um.InstallOperation, 'REPLACE_ZSTD', -2)
        op_type = op.type

        if op_type in (ZSTD_TYPE, REPLACE_ZSTD_TYPE):
            if data_length >= 4:
                magic_bytes = payloadfile.read(4)
                if magic_bytes != b'(\xb5/\xfd':
                    op_type = um.InstallOperation.REPLACE
                payloadfile.seek(payloadfile.tell() - 4)
            else:
                op_type = um.InstallOperation.REPLACE

        if op_type in (ZSTD_TYPE, REPLACE_ZSTD_TYPE):
            dec = zstandard.ZstdDecompressor().decompressobj()
            out_file.seek(op.dst_extents[0].start_block * self.block_size)
            while processed_len < data_length:
                chunk_to_read = min(buffsize, data_length - processed_len)
                data = payloadfile.read(chunk_to_read)
                if not data: break
                processed_len += len(data)
                decompressed_data = dec.decompress(data)
                out_file.write(decompressed_data)
            remaining_data = dec.flush()
            if remaining_data:
                out_file.write(remaining_data)

        elif op_type == um.InstallOperation.REPLACE_XZ:
            dec = lzma.LZMADecompressor()
            out_file.seek(op.dst_extents[0].start_block * self.block_size)
            while processed_len < data_length:
                chunk_to_read = min(buffsize, data_length - processed_len)
                data = payloadfile.read(chunk_to_read)
                if not data: break
                processed_len += len(data)
                while True:
                    try:
                        out_file.write(dec.decompress(data, max_length=buffsize))
                        if dec.needs_input:
                            break
                        if dec.eof:
                            break
                        data = b''
                    except lzma.LZMAError:
                        print("LZMA Error: Corrupted data or invalid format.")
                        break
        
        elif op_type == um.InstallOperation.REPLACE_BZ:
            dec = bz2.BZ2Decompressor()
            out_file.seek(op.dst_extents[0].start_block * self.block_size)
            while processed_len < data_length:
                chunk_to_read = min(buffsize, data_length - processed_len)
                data = payloadfile.read(chunk_to_read)
                if not data: break
                processed_len += len(data)
                try:
                    out_file.write(dec.decompress(data))
                except EOFError:
                    break
        
        elif op_type == um.InstallOperation.REPLACE:
            out_file.seek(op.dst_extents[0].start_block * self.block_size)
            while processed_len < data_length:
                chunk_to_read = min(buffsize, data_length - processed_len)
                data = payloadfile.read(chunk_to_read)
                if not data: break
                processed_len += len(data)
                out_file.write(data)

        elif op_type == um.InstallOperation.SOURCE_COPY:
            if not self.diff:
                print("SOURCE_COPY supported only for differential OTA")
                sys.exit(-2)
            for i, ext in enumerate(op.dst_extents):
                 out_file.seek(ext.start_block * self.block_size)
                 src_ext = op.src_extents[i]
                 old_file.seek(src_ext.start_block * self.block_size)
                 copy_data_length = src_ext.num_blocks * self.block_size
                 copied_len = 0
                 while copied_len < copy_data_length:
                     chunk_to_read = min(buffsize, copy_data_length - copied_len)
                     data = old_file.read(chunk_to_read)
                     if not data: break
                     copied_len += len(data)
                     out_file.write(data)

        elif op_type == um.InstallOperation.ZERO:
            zero_chunk = bytes(buffsize)
            for ext in op.dst_extents:
                out_file.seek(ext.start_block * self.block_size)
                zero_data_length = ext.num_blocks * self.block_size
                zeroed_len = 0
                while zeroed_len < zero_data_length:
                    chunk_to_write = min(buffsize, zero_data_length - zeroed_len)
                    out_file.write(zero_chunk[:chunk_to_write])
                    zeroed_len += chunk_to_write
                    
        else:
            print(f"Unsupported type = {op.type:d}")
            sys.exit(-1)

    def dump_part(self, part):
        name = part["partition"].partition_name
        out_file = open(f"{self.out}/{name}.img", "wb")

        if self.diff:
            old_file = open(f"{self.old}/{name}.img", "rb")
        else:
            old_file = None

        with self.open_payloadfile() as payloadfile:
            self.tls.payloadfile = payloadfile
            for op in part["operations"]:
                self.data_for_op(op, out_file, old_file)
        out_file.close()
