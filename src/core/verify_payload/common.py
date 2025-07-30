# src/core/verify_payload/common.py

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
#

"""Utilities for update payload processing."""

from __future__ import absolute_import
from __future__ import print_function

import base64

from .. import update_metadata_pb2
from .error import PayloadError


#
# Constants.
#
SIG_ASN1_HEADER = (
    b'\x30\x31\x30\x0d\x06\x09\x60\x86'
    b'\x48\x01\x65\x03\x04\x02\x01\x05'
    b'\x00\x04\x20'
)

BRILLO_MAJOR_PAYLOAD_VERSION = 2

SOURCE_MINOR_PAYLOAD_VERSION = 2
OPSRCHASH_MINOR_PAYLOAD_VERSION = 3
BROTLI_BSDIFF_MINOR_PAYLOAD_VERSION = 4
PUFFDIFF_MINOR_PAYLOAD_VERSION = 5

# KERNEL = 'kernel'
# ROOTFS = 'root'
# # Tuple of (name in system, name in protobuf).
# CROS_PARTITIONS = ((KERNEL, KERNEL), (ROOTFS, 'rootfs'))


#
# Payload operation types.
#
class OpType(object):
  """Container for operation type constants."""
  _CLASS = update_metadata_pb2.InstallOperation
  REPLACE = _CLASS.REPLACE
  REPLACE_BZ = _CLASS.REPLACE_BZ
  SOURCE_COPY = _CLASS.SOURCE_COPY
  SOURCE_BSDIFF = _CLASS.SOURCE_BSDIFF
  ZERO = _CLASS.ZERO
  DISCARD = _CLASS.DISCARD
  REPLACE_XZ = _CLASS.REPLACE_XZ
  PUFFDIFF = _CLASS.PUFFDIFF
  BROTLI_BSDIFF = _CLASS.BROTLI_BSDIFF
  ZUCCHINI = _CLASS.ZUCCHINI
  ### --- ИСПРАВЛЕННЫЙ КОД --- ###
  # Defensively get the ZSTD operation type, checking for REPLACE_ZSTD first,
  # as this is more consistent with other parts of the codebase.
  # This prevents an AttributeError if ZSTD does not exist in the enum.
  ZSTD = getattr(_CLASS, "REPLACE_ZSTD", getattr(_CLASS, "ZSTD", -1))
  ALL = (REPLACE, REPLACE_BZ, SOURCE_COPY, SOURCE_BSDIFF, ZERO,
         DISCARD, REPLACE_XZ, PUFFDIFF, BROTLI_BSDIFF, ZUCCHINI, ZSTD)
  NAMES = {
      REPLACE: 'REPLACE',
      REPLACE_BZ: 'REPLACE_BZ',
      SOURCE_COPY: 'SOURCE_COPY',
      SOURCE_BSDIFF: 'SOURCE_BSDIFF',
      ZERO: 'ZERO',
      DISCARD: 'DISCARD',
      REPLACE_XZ: 'REPLACE_XZ',
      PUFFDIFF: 'PUFFDIFF',
      BROTLI_BSDIFF: 'BROTLI_BSDIFF',
      ZUCCHINI: 'ZUCCHINI',
      # Use the correct name for logging/reporting.
      ZSTD: 'REPLACE_ZSTD',
  }

  def __init__(self):
    pass


#
# Checked and hashed reading of data.
#
def IntPackingFmtStr(size, is_unsigned):
  """Returns an integer format string for use by the struct module.

  Args:
    size: the integer size in bytes (2, 4 or 8)
    is_unsigned: whether it is signed or not

  Returns:
    A format string for packing/unpacking integer values; assumes network byte
    order (big-endian).

  Raises:
    PayloadError if something is wrong with the arguments.
  """
  # Determine the base conversion format.
  if size == 2:
    fmt = 'h'
  elif size == 4:
    fmt = 'i'
  elif size == 8:
    fmt = 'q'
  else:
    raise PayloadError('unsupport numeric field size (%s)' % size)

  # Signed or unsigned?
  if is_unsigned:
    fmt = fmt.upper()

  # Make it network byte order (big-endian).
  fmt = '!' + fmt

  return fmt


def Read(file_obj, length, offset=None, hasher=None):
  """Reads binary data from a file.

  Args:
    file_obj: an open file object
    length: the length of the data to read
    offset: an offset to seek to prior to reading; this is an absolute offset
            from either the beginning (non-negative) or end (negative) of the
            file.  (optional)
    hasher: a hashing object to pass the read data through (optional)

  Returns:
    A string containing the read data.

  Raises:
    PayloadError if a read error occurred or not enough data was read.
  """
  if offset is not None:
    if offset >= 0:
      file_obj.seek(offset)
    else:
      file_obj.seek(offset, 2)

  try:
    data = file_obj.read(length)
  except IOError as e:
    raise PayloadError('error reading from file (%s): %s' % (file_obj.name, e))

  if len(data) != length:
    raise PayloadError(
        'reading from file (%s) too short (%d instead of %d bytes)' %
        (file_obj.name, len(data), length))

  if hasher:
    hasher.update(data)

  return data


#
# Formatting functions.
#
def FormatExtent(ex, block_size=0):
  end_block = ex.start_block + ex.num_blocks
  if block_size:
    return '%d->%d * %d' % (ex.start_block, end_block, block_size)
  return '%d->%d' % (ex.start_block, end_block)


def FormatSha256(digest):
  """Returns a canonical string representation of a SHA256 digest."""
  return base64.b64encode(digest).decode('utf-8')


#
# Useful iterators.
#
def _ObjNameIter(items, base_name, reverse=False, name_format_func=None):
  """A generic (item, name) tuple iterators.

  Args:
    items: the sequence of objects to iterate on
    base_name: the base name for all objects
    reverse: whether iteration should be in reverse order
    name_format_func: a function to apply to the name string

  Yields:
    An iterator whose i-th invocation returns (items[i], name), where name ==
    base_name + '[i]' (with a formatting function optionally applied to it).
  """
  idx, inc = (len(items), -1) if reverse else (1, 1)
  if reverse:
    items = reversed(items)
  for item in items:
    item_name = '%s[%d]' % (base_name, idx)
    if name_format_func:
      item_name = name_format_func(item, item_name)
    yield (item, item_name)
    idx += inc


def _OperationNameFormatter(op, op_name):
  return '%s(%s)' % (op_name, OpType.NAMES.get(op.type, '?'))


def OperationIter(operations, base_name, reverse=False):
  """An (item, name) iterator for update operations."""
  return _ObjNameIter(operations, base_name, reverse=reverse,
                      name_format_func=_OperationNameFormatter)


def ExtentIter(extents, base_name, reverse=False):
  """An (item, name) iterator for operation extents."""
  return _ObjNameIter(extents, base_name, reverse=reverse)


def SignatureIter(sigs, base_name, reverse=False):
  """An (item, name) iterator for signatures."""
  return _ObjNameIter(sigs, base_name, reverse=reverse)