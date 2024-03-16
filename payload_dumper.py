#!/usr/bin/env python3
from argparse import Namespace
from bz2 import BZ2Decompressor
from lzma import LZMADecompressor
from os import F_OK, access, makedirs, path
from struct import unpack
from timeit import default_timer

import update_metadata_pb2 as um

flatten = lambda l: [item for sublist in l for item in sublist]


def u64(x):
    return unpack('>Q', x)[0]


class ota_payload_dumper:
    def __init__(self, payloadfile_, out='output', old='old', images='', command: int = 1):
        self.payloadfile = payloadfile_
        self.args = Namespace(out=out, old=old, images=images, payload=self.payloadfile)
        if not path.exists(self.args.out):
            makedirs(self.args.out)
        magic = self.payloadfile.read(4)
        if magic != b'CrAU':
            print(f"Magic Check Fail{magic}\n")
            payloadfile_.close()
            return
        file_format_version = u64(self.payloadfile.read(8))
        assert file_format_version == 2
        manifest_size = u64(self.payloadfile.read(8))
        metadata_signature_size = 0
        if file_format_version > 1:
            metadata_signature_size = unpack('>I', self.payloadfile.read(4))[0]
        manifest = self.payloadfile.read(manifest_size)
        self.payloadfile.read(metadata_signature_size)
        self.data_offset = self.payloadfile.tell()
        self.dam = um.DeltaArchiveManifest()
        self.dam.ParseFromString(manifest)
        self.block_size = self.dam.block_size
        if command == 0:
            return
        for image in self.args.images:
            partition = [part for part in self.dam.partitions if part.partition_name == image]
            print(f'[EXTRACTING]: {image}')
            assert partition, "Partition %s not found in payload!\n" % image
            self.dump_part(partition[0])
        self.payloadfile.close()

    def dump_part(self, part):
        start = default_timer()
        if access(self.args.out + part.partition_name + ".img", F_OK):
            print(part.partition_name + "已存在\n")
        else:
            with open('%s/%s.img' % (self.args.out, part.partition_name), 'wb') as out_file:
                for op in part.operations:
                    if self.data_for_op(op, out_file) == 1:
                        print(f'Clean Extract [{part.partition_name}]\n')
                        return
            print("%s:[%s]\n" % (part.partition_name, default_timer() - start))

    def data_for_op(self, op, out_file):
        try:
            self.payloadfile.seek(self.data_offset + op.data_offset)
        except ValueError as e:
            print(e)
            return 1
        if op.type == op.REPLACE_XZ:
            out_file.seek(op.dst_extents[0].start_block * self.block_size)
            out_file.write(LZMADecompressor().decompress(self.payloadfile.read(op.data_length)))
        elif op.type == op.REPLACE_BZ:
            out_file.seek(op.dst_extents[0].start_block * self.block_size)
            out_file.write(BZ2Decompressor().decompress(self.payloadfile.read(op.data_length)))
        elif op.type == op.REPLACE:
            out_file.seek(op.dst_extents[0].start_block * self.block_size)
            out_file.write(self.payloadfile.read(op.data_length))
        elif op.type == op.ZERO:
            for ext in op.dst_extents:
                out_file.seek(ext.start_block * self.block_size)
                out_file.write(b'\x00' * ext.num_blocks * self.block_size)
        else:
            print("Unsupported type = %d\n" % op.type)
            exit(-2)
        return 0
