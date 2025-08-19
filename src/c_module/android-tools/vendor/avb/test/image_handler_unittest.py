#!/usr/bin/env python3

# Copyright 2016, The Android Open Source Project
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use, copy,
# modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


"""Unit-test for ImageHandler."""


import imp
import os
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
avbtool = imp.load_source('avbtool', './avbtool.py')

# The file test_file.bin and test_file.bin.sparse are generated using
# the following python code:
#
#  with open('test_file.bin', 'w+b') as f:
#    f.write('Barfoo43'*128*12)
#  os.system('img2simg test_file.bin test_file.bin.sparse')
#  image = avbtool.ImageHandler('test_file.bin.sparse')
#  image.append_dont_care(12*1024)
#  image.append_fill('\x01\x02\x03\x04', 12*1024)
#  image.append_raw('Foobar42'*128*12)
#  image.append_dont_care(12*1024)
#  del image
#  os.system('rm -f test_file.bin')
#  os.system('simg2img test_file.bin.sparse test_file.bin')
#
# and manually verified to be correct. The content of the raw and
# sparse files are as follows (the line with "Fill with 0x04030201" is
# a simg_dump.py bug):
#
# $ hexdump -C test_file.bin
# 00000000  42 61 72 66 6f 6f 34 33  42 61 72 66 6f 6f 34 33  |Barfoo43Barfoo43|
# *
# 00003000  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
# *
# 00006000  01 02 03 04 01 02 03 04  01 02 03 04 01 02 03 04  |................|
# *
# 00009000  46 6f 6f 62 61 72 34 32  46 6f 6f 62 61 72 34 32  |Foobar42Foobar42|
# *
# 0000c000  00 00 00 00 00 00 00 00  00 00 00 00 00 00 00 00  |................|
# *
# 0000f000
#
# $ system/core/libsparse/simg_dump.py -v test_file.bin.sparse
# test_file.bin.sparse: Total of 15 4096-byte output blocks in 5 input chunks.
#             input_bytes      output_blocks
# chunk    offset     number  offset  number
#    1         40      12288       0       3 Raw data
#    2      12340          0       3       3 Don't care
#    3      12352          4       6       3 Fill with 0x04030201
#    4      12368      12288       9       3 Raw data
#    5      24668          0      12       3 Don't care
#           24668                 15         End
#


class ImageHandler(unittest.TestCase):

  TEST_FILE_SPARSE_PATH = 'test/data/test_file.bin.sparse'
  TEST_FILE_PATH = 'test/data/test_file.bin'
  TEST_FILE_SIZE = 61440
  TEST_FILE_BLOCK_SIZE = 4096

  def _file_contents_equal(self, path1, path2, size):
    f1 = open(path1, 'r')
    f2 = open(path2, 'r')
    if f1.read(size) != f2.read(size):
      return False
    return True

  def _file_size(self, f):
    old_pos = f.tell()
    f.seek(0, os.SEEK_END)
    size = f.tell()
    f.seek(old_pos)
    return size

  def _clone_sparse_file(self):
    f = tempfile.NamedTemporaryFile(mode='wb')
    f.write(open(self.TEST_FILE_SPARSE_PATH, 'rb').read())
    f.flush()
    return f

  def _unsparsify(self, path):
    f = tempfile.NamedTemporaryFile()
    os.system('simg2img {} {}'.format(path, f.name))
    return f

  def testRead(self):
    """Checks that reading from a sparse file works as intended."""
    ih = avbtool.ImageHandler(self.TEST_FILE_SPARSE_PATH)

    # Check that we start at offset 0.
    self.assertEqual(ih.tell(), 0)

    # Check that reading advances the cursor.
    self.assertEqual(ih.read(14), bytearray(b'Barfoo43Barfoo'))
    self.assertEqual(ih.tell(), 14)
    self.assertEqual(ih.read(2), bytearray(b'43'))
    self.assertEqual(ih.tell(), 16)

    # Check reading in the middle of a fill chunk gets the right data.
    ih.seek(0x6000 + 1)
    self.assertEqual(ih.read(4), bytearray(b'\x02\x03\x04\x01'))

    # Check we can cross the chunk boundary correctly.
    ih.seek(0x3000 - 10)
    self.assertEqual(ih.read(12), bytearray(b'43Barfoo43\x00\x00'))
    ih.seek(0x9000 - 3)
    self.assertEqual(ih.read(5), bytearray(b'\x02\x03\x04Fo'))

    # Check reading at end of file is a partial read.
    ih.seek(0xf000 - 2)
    self.assertEqual(ih.read(16), bytearray(b'\x00\x00'))

  def testTruncate(self):
    """Checks that we can truncate a sparse file correctly."""
    # Check truncation at all possible boundaries (including start and end).
    for size in range(0, self.TEST_FILE_SIZE + self.TEST_FILE_BLOCK_SIZE,
                      self.TEST_FILE_BLOCK_SIZE):
      sparse_file = self._clone_sparse_file()
      ih = avbtool.ImageHandler(sparse_file.name)
      ih.truncate(size)
      unsparse_file = self._unsparsify(sparse_file.name)
      self.assertEqual(self._file_size(unsparse_file), size)
      self.assertTrue(self._file_contents_equal(unsparse_file.name,
                                                self.TEST_FILE_PATH,
                                                size))

    # Check truncation to grow the file.
    grow_size = 8192
    sparse_file = self._clone_sparse_file()
    ih = avbtool.ImageHandler(sparse_file.name)
    ih.truncate(self.TEST_FILE_SIZE + grow_size)
    unsparse_file = self._unsparsify(sparse_file.name)
    self.assertEqual(self._file_size(unsparse_file),
                     self.TEST_FILE_SIZE + grow_size)
    self.assertTrue(self._file_contents_equal(unsparse_file.name,
                                              self.TEST_FILE_PATH,
                                              self.TEST_FILE_SIZE))
    unsparse_file.seek(self.TEST_FILE_SIZE)
    self.assertEqual(unsparse_file.read(), b'\0'*grow_size)

  def testAppendRaw(self):
    """Checks that we can append raw data correctly."""
    sparse_file = self._clone_sparse_file()
    ih = avbtool.ImageHandler(sparse_file.name)
    data = b'SomeData'*4096
    ih.append_raw(data)
    unsparse_file = self._unsparsify(sparse_file.name)
    self.assertTrue(self._file_contents_equal(unsparse_file.name,
                                              self.TEST_FILE_PATH,
                                              self.TEST_FILE_SIZE))
    unsparse_file.seek(self.TEST_FILE_SIZE)
    self.assertEqual(unsparse_file.read(), data)

  def testAppendFill(self):
    """Checks that we can append fill data correctly."""
    sparse_file = self._clone_sparse_file()
    ih = avbtool.ImageHandler(sparse_file.name)
    data = b'ABCD'*4096
    ih.append_fill(b'ABCD', len(data))
    unsparse_file = self._unsparsify(sparse_file.name)
    self.assertTrue(self._file_contents_equal(unsparse_file.name,
                                              self.TEST_FILE_PATH,
                                              self.TEST_FILE_SIZE))
    unsparse_file.seek(self.TEST_FILE_SIZE)
    self.assertEqual(unsparse_file.read(), data)

  def testDontCare(self):
    """Checks that we can append DONT_CARE data correctly."""
    sparse_file = self._clone_sparse_file()
    ih = avbtool.ImageHandler(sparse_file.name)
    data = b'\0'*40960
    ih.append_dont_care(len(data))
    unsparse_file = self._unsparsify(sparse_file.name)
    self.assertTrue(self._file_contents_equal(unsparse_file.name,
                                              self.TEST_FILE_PATH,
                                              self.TEST_FILE_SIZE))
    unsparse_file.seek(self.TEST_FILE_SIZE)
    self.assertEqual(unsparse_file.read(), data)


if __name__ == '__main__':
  unittest.main()
