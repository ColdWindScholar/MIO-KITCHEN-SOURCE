#!/usr/bin/env python
import bz2
import hashlib
import lzma
import struct
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count

import update_metadata_pb2 as um

flatten = lambda l: [item for sublist in l for item in sublist]


def u32(x):
    return struct.unpack(">I", x)[0]


def u64(x):
    return struct.unpack(">Q", x)[0]


class Dumper:
    def __init__(
            self, payloadfile, out, diff=None, old=None, images="", workers=cpu_count()
    ):
        self.payloadfile = payloadfile
        self.out = out
        self.diff = diff
        self.old = old
        self.images = images
        self.workers = workers
        self.validate_magic()

    def run(self, slow=False):
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
                    print("Partition %s not found in image" % image)

        if len(partitions) == 0:
            print("Not operating on any partitions")
            return 0

        partitions_with_ops = []
        for partition in partitions:
            operations = []
            for operation in partition.operations:
                self.payloadfile.seek(self.data_offset + operation.data_offset)
                operations.append(
                    {
                        "operation": operation,
                        "data": self.payloadfile.read(operation.data_length),
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

    def extract_slow(self, partitions):
        for part in partitions:
            self.dump_part(part)

    def multiprocess_partitions(self, partitions):
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {executor.submit(self.dump_part, part): part for part in partitions}
            for future in as_completed(futures):
                partition_name = futures[future]['partition'].partition_name
                try:
                    future.result()
                    print(f"{partition_name} Done!")
                except Exception as exc:
                    print(f"{partition_name} - processing generated an exception: {exc}")

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
        data = operation["data"]
        op = operation["operation"]

        # assert hashlib.sha256(data).digest() == op.data_sha256_hash, 'operation data hash mismatch'

        if op.type == op.REPLACE_XZ:
            dec = lzma.LZMADecompressor()
            data = dec.decompress(data)
            out_file.seek(op.dst_extents[0].start_block * self.block_size)
            out_file.write(data)
        elif op.type == op.REPLACE_BZ:
            dec = bz2.BZ2Decompressor()
            data = dec.decompress(data)
            out_file.seek(op.dst_extents[0].start_block * self.block_size)
            out_file.write(data)
        elif op.type == op.REPLACE:
            out_file.seek(op.dst_extents[0].start_block * self.block_size)
            out_file.write(data)
        elif op.type == op.SOURCE_COPY:
            if not self.diff:
                print("SOURCE_COPY supported only for differential OTA")
                sys.exit(-2)
            out_file.seek(op.dst_extents[0].start_block * self.block_size)
            for ext in op.src_extents:
                old_file.seek(ext.start_block * self.block_size)
                data = old_file.read(ext.num_blocks * self.block_size)
                out_file.write(data)
        elif op.type == op.ZERO:
            for ext in op.dst_extents:
                out_file.seek(ext.start_block * self.block_size)
                out_file.write(b"\x00" * ext.num_blocks * self.block_size)
        else:
            print("Unsupported type = %d" % op.type)
            sys.exit(-1)
        del data

    def dump_part(self, part):
        name = part["partition"].partition_name
        out_file = open("%s/%s.img" % (self.out, name), "wb")
        h = hashlib.sha256()

        if self.diff:
            old_file = open("%s/%s.img" % (self.old, name), "rb")
        else:
            old_file = None

        for op in part["operations"]:
            data = self.data_for_op(op, out_file, old_file)
