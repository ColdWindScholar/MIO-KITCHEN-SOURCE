#!/usr/bin/env python3
#
# Copyright (C) 2013 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import os
import sys
import struct
import shlex
import subprocess
import tempfile

VERSION = 0
MAGIC_NUMBER = 0xb001b001
MAGIC_DISABLE = 0x46464f56 # "VOFF"
BLOCK_SIZE = 4096
METADATA_SIZE = BLOCK_SIZE * 8

def run(cmd):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
    output, _ = p.communicate()
    print(output)
    if p.returncode:
        exit(-1)

def get_verity_metadata_size(data_size):
    return METADATA_SIZE

def build_metadata_block(verity_table, signature, verity_disable=False):
    table_len = len(verity_table)
    magic = MAGIC_DISABLE if verity_disable else MAGIC_NUMBER
    block = struct.pack("II256sI", magic, VERSION, signature, table_len)
    block += verity_table
    block = block.ljust(METADATA_SIZE, b'\x00')
    return block

def sign_verity_table(table, signer_path, key_path, signer_args=None):
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.table') as table_file:
        with tempfile.NamedTemporaryFile(mode='rb', suffix='.sig') as signature_file:
            table_file.write(table)
            table_file.flush()
            if signer_args is None:
              cmd = [signer_path, table_file.name, key_path, signature_file.name]
            else:
              args_list = shlex.split(signer_args)
              cmd = [signer_path] + args_list + [table_file.name, key_path, signature_file.name]
            print(cmd)
            run(cmd)
            return signature_file.read()

def build_verity_table(block_device, data_blocks, root_hash, salt):
    table = "1 %s %s %s %s %s %s sha256 %s %s"
    table %= (  block_device,
                block_device,
                BLOCK_SIZE,
                BLOCK_SIZE,
                data_blocks,
                data_blocks,
                root_hash,
                salt)
    return table.encode()

def build_verity_metadata(data_blocks, metadata_image, root_hash, salt,
        block_device, signer_path, signing_key, signer_args=None,
        verity_disable=False):
    # build the verity table
    verity_table = build_verity_table(block_device, data_blocks, root_hash, salt)
    # build the verity table signature
    signature = sign_verity_table(verity_table, signer_path, signing_key, signer_args)
    # build the metadata block
    metadata_block = build_metadata_block(verity_table, signature, verity_disable)
    # write it to the outfile
    with open(metadata_image, "wb") as f:
        f.write(metadata_block)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    parser_size = subparsers.add_parser('size')
    parser_size.add_argument('partition_size', type=int, action='store', help='partition size')
    parser_size.set_defaults(dest='size')

    parser_build = subparsers.add_parser('build')
    parser_build.add_argument('blocks', type=int, help='data image blocks')
    parser_build.add_argument('metadata_image', action='store', help='metadata image')
    parser_build.add_argument('root_hash', action='store', help='root hash')
    parser_build.add_argument('salt', action='store', help='salt')
    parser_build.add_argument('block_device', action='store', help='block device')
    parser_build.add_argument('signer_path', action='store', help='verity signer path')
    parser_build.add_argument('signing_key', action='store', help='verity signing key')
    parser_build.add_argument('--signer_args', action='store', help='verity signer args')
    parser_build.add_argument('--verity_disable', action='store_true',
                              default=False, help='disable verity')
    parser_build.set_defaults(dest='build')

    args = parser.parse_args()

    if args.dest == 'size':
        print(get_verity_metadata_size(args.partition_size))
    else:
        build_verity_metadata(args.blocks // 4096, args.metadata_image,
                              args.root_hash, args.salt, args.block_device,
                              args.signer_path, args.signing_key,
                              args.signer_args, args.verity_disable)
