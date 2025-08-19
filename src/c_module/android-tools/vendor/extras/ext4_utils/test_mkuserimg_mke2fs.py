#!/usr/bin/env python
#
# Copyright (C) 2018 The Android Open Source Project
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

import unittest

import mkuserimg_mke2fs

class MkuserimgMke2fsTest(unittest.TestCase):
  def setUp(self):
    self.optional_arguments = {
        "-j": "10", "-T": "1230768000.0", "-C": "fs_config",
        "-D": "product_out", "-B": "block_list_file",
        "-d": "base_alloc_file_in", "-A": "base_alloc_file_out",
        "-L": "label", "-i": "20", "-M": "30", "-e": "8192",
        "-o": "16384", "-U": "mke2fs_uuid", "-S": "mke2fs_hash_seed",
    }

  def test_parse_arguments_smoke(self):
    args_list = ["source_directory", "output_file", "ext4", "data", "8192"]
    for key, value in self.optional_arguments.items():
      args_list += [key, value]
    args_list.append("-c")

    args = mkuserimg_mke2fs.ParseArguments(args_list)

    self.assertEqual("source_directory", args.src_dir)
    self.assertEqual("output_file", args.output_file)
    self.assertEqual("ext4", args.ext_variant)
    self.assertEqual("data", args.mount_point)
    self.assertEqual("8192", args.fs_size)

    self.assertFalse(args.android_sparse)
    self.assertEqual("10", args.journal_size)
    self.assertEqual("1230768000.0", args.timestamp)
    self.assertEqual("fs_config", args.fs_config)
    self.assertEqual("product_out", args.product_out)
    self.assertEqual("block_list_file", args.block_list_file)
    self.assertEqual("base_alloc_file_in", args.base_alloc_file_in)
    self.assertEqual("base_alloc_file_out", args.base_alloc_file_out)
    self.assertEqual("label", args.label)
    self.assertEqual("20", args.inodes)
    self.assertEqual("30", args.reserved_percent)
    self.assertEqual("8192", args.flash_erase_block_size)
    self.assertEqual("16384", args.flash_logical_block_size)
    self.assertEqual("mke2fs_uuid", args.mke2fs_uuid)
    self.assertEqual("mke2fs_hash_seed", args.mke2fs_hash_seed)
    self.assertTrue(args.share_dup_blocks)

  def test_parse_arguments_with_filecontext(self):
    args_list = ["-s", "source_directory", "output_file", "ext4", "data",
                 "8192"]
    for key, value in self.optional_arguments.items():
      args_list += [key, value]
    args_list += ["-c", "file_contexts.bin"]

    args = mkuserimg_mke2fs.ParseArguments(args_list)

    self.assertEqual("file_contexts.bin", args.file_contexts)

    self.assertEqual("source_directory", args.src_dir)
    self.assertEqual("output_file", args.output_file)
    self.assertEqual("ext4", args.ext_variant)
    self.assertEqual("data", args.mount_point)
    self.assertEqual("8192", args.fs_size)

    self.assertTrue(args.android_sparse)
    self.assertEqual("10", args.journal_size)
    self.assertEqual("1230768000.0", args.timestamp)
    self.assertEqual("fs_config", args.fs_config)
    self.assertEqual("product_out", args.product_out)
    self.assertEqual("block_list_file", args.block_list_file)
    self.assertEqual("base_alloc_file_in", args.base_alloc_file_in)
    self.assertEqual("base_alloc_file_out", args.base_alloc_file_out)
    self.assertEqual("label", args.label)
    self.assertEqual("20", args.inodes)
    self.assertEqual("30", args.reserved_percent)
    self.assertEqual("8192", args.flash_erase_block_size)
    self.assertEqual("16384", args.flash_logical_block_size)
    self.assertEqual("mke2fs_uuid", args.mke2fs_uuid)
    self.assertEqual("mke2fs_hash_seed", args.mke2fs_hash_seed)
    self.assertTrue(args.share_dup_blocks)

  def test_parse_arguments_not_enough_arguments(self):
    args_list = ["-s", "source_directory", "output_file", "ext4", "data",]
    for key, value in self.optional_arguments.items():
      args_list += [key, value]

    with self.assertRaises(SystemExit):
      mkuserimg_mke2fs.ParseArguments(args_list)

  def test_construct_e2fs_opts_smoke(self):
    args_list = ["-s", "source_directory", "output_file", "ext4", "data",
                 "8192"]
    for key, value in self.optional_arguments.items():
      args_list += [key, value]
    args_list += ["-c", "file_contexts.bin"]

    args = mkuserimg_mke2fs.ParseArguments(args_list)

    mke2fs_cmd, e2fsdroid_cmd = mkuserimg_mke2fs.ConstructE2fsCommands(
        args)

    expected_mke2fs_extended_opts = (
        "android_sparse,stripe_width=2,stride=4,hash_seed={}".format(
            args.mke2fs_hash_seed))
    expected_mke2fs_cmd = [
        "mke2fs", "-J", "size=10", "-L", args.label, "-N", args.inodes, "-m",
        args.reserved_percent, "-U", args.mke2fs_uuid, "-E",
        expected_mke2fs_extended_opts, "-t", args.ext_variant, "-b", "4096",
        args.output_file, str(int(args.fs_size) / 4096)]

    expected_e2fsdroid_cmd = [
        "e2fsdroid", "-T", args.timestamp, "-C", args.fs_config, "-p",
        args.product_out, "-B", args.block_list_file, "-d",
        args.base_alloc_file_in, "-D", args.base_alloc_file_out, "-s", "-S",
        args.file_contexts, "-f", args.src_dir, "-a", args.mount_point,
        args.output_file]

    self.assertEqual(' '.join(mke2fs_cmd), ' '.join(expected_mke2fs_cmd))

    self.assertEqual(' '.join(e2fsdroid_cmd),
                     ' '.join(expected_e2fsdroid_cmd))
