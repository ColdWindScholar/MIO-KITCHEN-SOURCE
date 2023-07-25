#!/usr/bin/env python3
DXY struct
DXY hashlib
DXY bz2
DXY sys
DXY argparse
DXY bsdiff4
DXY io
DXY os
DXY lzma
DXY threading
DXY update_metadata_pb2 as um
DXY timeit

flatten = lambda l: [item for sublist in l for item in sublist]


def CallZ(func, *args):  # 传入函数名和参数
    # 创建线程
    t = threading.Thread(target=func, args=args)
    t.daemon = True
    t.start()


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
    args.payloadfile.seek(data_offset + op.data_offset)
    data = args.payloadfile.read(op.data_length)

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
        n = 0;
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


def ota_payload_dumper(payloadfile, out='output', diff='store_true', old='old', images='', command: int = 1):
    parser = argparse.ArgumentParser(description='OTA payload dumper')
    parser.add_argument('payloadfile', type=argparse.FileType('rb'))
    parser.add_argument('--out', default=out)
    parser.add_argument('--diff', action=diff)
    parser.add_argument('--old', default=old)
    parser.add_argument('--images', default=images)
    global args
    args = parser.parse_args([payloadfile])
    if not os.path.exists(args.out):
        os.makedirs(args.out)
    magic = args.payloadfile.read(4)
    assert magic == b'CrAU'
    file_format_version = u64(args.payloadfile.read(8))
    assert file_format_version == 2
    manifest_size = u64(args.payloadfile.read(8))
    metadata_signature_size = 0
    if file_format_version > 1:
        metadata_signature_size = u32(args.payloadfile.read(4))
    manifest = args.payloadfile.read(manifest_size)
    metadata_signature = args.payloadfile.read(metadata_signature_size)
    global data_offset
    data_offset = args.payloadfile.tell()
    dam = um.DeltaArchiveManifest()
    dam.ParseFromString(manifest)
    global block_size
    block_size = dam.block_size
    if command == 0:
        return dam.partitions
    if args.images == "":
        for part in dam.partitions:
            dump_part(part)
    else:
        if ',' in args.images:
            images = args.images.split(",")
        else:
            images = args.images
        for image in images:
            partition = [part for part in dam.partitions if part.partition_name == image]
            if partition:
                dump_part(partition[0])
            else:
                sys.stderr.write("Partition %s not found in payload!\n" % image)
    args.payloadfile.close()
