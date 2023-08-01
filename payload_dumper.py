#!/usr/bin/env python3
import struct
import hashlib
import bz2
import sys
import argparse
import bsdiff4
import io
import os
import lzma
import update_metadata_pb2 as um
import timeit

flatten = lambda l: [item for sublist in l for item in sublist]


def u32(x):
    return struct.unpack('>I', x)[0]


def u64(x):
    return struct.unpack('>Q', x)[0]


def verify_contiguous(exts):
    blocks = 0

    for ext in exts:
        if ext.start_block != blocks:
            return False

        blocks += ext.num_blocks

    return True


def data_for_op(op, out_file, old_file):
    payloadfile.seek(data_offset + op.data_offset)
    data = payloadfile.read(op.data_length)

    # assert hashlib.sha256(data).digest() == op.data_sha256_hash, 'operation data hash mismatch'

    if op.type == op.REPLACE_XZ:
        dec = lzma.LZMADecompressor()
        data = dec.decompress(data)
        out_file.seek(op.dst_extents[0].start_block * block_size)
        out_file.write(data)
    elif op.type == op.REPLACE_BZ:
        dec = bz2.BZ2Decompressor()
        data = dec.decompress(data)
        out_file.seek(op.dst_extents[0].start_block * block_size)
        out_file.write(data)
    elif op.type == op.REPLACE:
        out_file.seek(op.dst_extents[0].start_block * block_size)
        out_file.write(data)
    elif op.type == op.SOURCE_COPY:
        if not args.diff:
            print("SOURCE_COPY supported only for differential OTA")
            sys.exit(-2)
        out_file.seek(op.dst_extents[0].start_block * block_size)
        for ext in op.src_extents:
            old_file.seek(ext.start_block * block_size)
            data = old_file.read(ext.num_blocks * block_size)
            out_file.write(data)
    elif op.type == op.SOURCE_BSDIFF:
        if not args.diff:
            print("SOURCE_BSDIFF supported only for differential OTA")
            sys.exit(-3)
        out_file.seek(op.dst_extents[0].start_block * block_size)
        tmp_buff = io.BytesIO()
        for ext in op.src_extents:
            old_file.seek(ext.start_block * block_size)
            old_data = old_file.read(ext.num_blocks * block_size)
            tmp_buff.write(old_data)
        tmp_buff.seek(0)
        old_data = tmp_buff.read()
        tmp_buff.seek(0)
        tmp_buff.write(bsdiff4.patch(old_data, data))
        n = 0
        tmp_buff.seek(0)
        for ext in op.dst_extents:
            tmp_buff.seek(n * block_size)
            n += ext.num_blocks
            data = tmp_buff.read(ext.num_blocks * block_size)
            out_file.seek(ext.start_block * block_size)
            out_file.write(data)
    elif op.type == op.ZERO:
        for ext in op.dst_extents:
            out_file.seek(ext.start_block * block_size)
            out_file.write(b'\x00' * ext.num_blocks * block_size)
    else:
        print("Unsupported type = %d" % op.type)
        sys.exit(-1)

    return data


def dump_part(part):
    start = timeit.default_timer()
    if os.access(args.out + part.partition_name + ".img", os.F_OK):
        print(part.partition_name + "已存在")
    else:
        print("%s:[EXTRACTING]" % part.partition_name)
        out_file = open('%s/%s.img' % (args.out, part.partition_name), 'wb')
        h = hashlib.sha256()
        if args.diff:
            old_file = open('%s/%s.img' % (args.old, part.partition_name), 'rb')
        else:
            old_file = None
        for op in part.operations:
            data = data_for_op(op, out_file, old_file)
        print("%s:[%s]" % (part.partition_name, timeit.default_timer() - start))


def ota_payload_dumper(payloadfile_, out='output', diff='store_true', old='old', images='', command: int = 1):
    parser = argparse.ArgumentParser(description='OTA payload dumper')
    parser.add_argument('--out', default=out)
    parser.add_argument('--diff', action=diff)
    parser.add_argument('--old', default=old)
    parser.add_argument('--images', default=images)
    global args
    args = parser.parse_args()
    global payloadfile
    payloadfile = payloadfile_
    args.payload = payloadfile
    if not os.path.exists(args.out):
        os.makedirs(args.out)
    magic = payloadfile.read(4)
    assert magic == b'CrAU'
    file_format_version = u64(payloadfile.read(8))
    assert file_format_version == 2
    manifest_size = u64(payloadfile.read(8))
    metadata_signature_size = 0
    if file_format_version > 1:
        metadata_signature_size = u32(payloadfile.read(4))
    manifest = payloadfile.read(manifest_size)
    metadata_signature = payloadfile.read(metadata_signature_size)
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
