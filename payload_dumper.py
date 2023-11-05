#!/usr/bin/env python3
from argparse import Namespace
from bz2 import BZ2Decompressor
from lzma import LZMADecompressor
from os import F_OK, access, makedirs, path
from struct import unpack
from timeit import default_timer

import update_metadata_pb2 as um

flatten = lambda l: [item for sublist in l for item in sublist]


def u32(x):
    return unpack('>I', x)[0]


def u64(x):
    return unpack('>Q', x)[0]


def data_for_op(op, out_file):
    payloadfile.seek(data_offset + op.data_offset)
    data = payloadfile.read(op.data_length)
    if op.type == op.REPLACE_XZ:
        data = LZMADecompressor().decompress(data)
        out_file.seek(op.dst_extents[0].start_block * block_size)
        out_file.write(data)
    elif op.type == op.REPLACE_BZ:
        data = BZ2Decompressor().decompress(data)
        out_file.seek(op.dst_extents[0].start_block * block_size)
        out_file.write(data)
    elif op.type == op.REPLACE:
        out_file.seek(op.dst_extents[0].start_block * block_size)
        out_file.write(data)
    elif op.type == op.ZERO:
        for ext in op.dst_extents:
            out_file.seek(ext.start_block * block_size)
            out_file.write(b'\x00' * ext.num_blocks * block_size)
    else:
        print("Unsupported type = %d\n" % op.type)
        exit(-2)

    return data


def dump_part(part):
    start = default_timer()
    if access(args.out + part.partition_name + ".img", F_OK):
        print(part.partition_name + "已存在\n")
    else:
        print("%s:[EXTRACTING]\n" % part.partition_name)
        with open('%s/%s.img' % (args.out, part.partition_name), 'wb') as out_file:
            for op in part.operations:
                data_for_op(op, out_file)
        print("%s:[%s]\n" % (part.partition_name, default_timer() - start))


def ota_payload_dumper(payloadfile_, out='output', old='old', images='', command: int = 1):
    global args
    args = Namespace(out=out, old=old, images=images)
    global payloadfile
    payloadfile = payloadfile_
    args.payload = payloadfile
    if not path.exists(args.out):
        makedirs(args.out)
    magic = payloadfile.read(4)
    assert magic == b'CrAU'
    file_format_version = u64(payloadfile.read(8))
    assert file_format_version == 2
    manifest_size = u64(payloadfile.read(8))
    metadata_signature_size = 0
    if file_format_version > 1:
        metadata_signature_size = u32(payloadfile.read(4))
    manifest = payloadfile.read(manifest_size)
    payloadfile.read(metadata_signature_size)
    global data_offset
    data_offset = payloadfile.tell()
    dam = um.DeltaArchiveManifest()
    dam.ParseFromString(manifest)
    global block_size
    block_size = dam.block_size
    if command == 0:
        return dam.partitions
    for image in args.images:
        partition = [part for part in dam.partitions if part.partition_name == image]
        assert partition, "Partition %s not found in payload!\n" % image
        dump_part(partition[0])
    payloadfile_.close()
