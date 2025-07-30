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

"""Various formatting functions."""

from __future__ import division


def NumToPercent(num, total, min_precision=1, max_precision=5):
  """Returns the percentage (string) of |num| out of |total|.

  If the percentage includes a fraction, it will be computed down to the least
  precision that yields a non-zero and ranging between |min_precision| and
  |max_precision|. Values are always rounded down. All arithmetic operations
  are integer built-ins. Examples (using default precision):

    (1, 1) => 100%
    (3, 10) => 30%
    (3, 9) => 33.3%
    (3, 900) => 0.3%
    (3, 9000000) => 0.00003%
    (3, 900000000) => 0%
    (5, 2) => 250%

  Args:
    num: the value of the part
    total: the value of the whole
    min_precision: minimum precision for fractional percentage
    max_precision: maximum precision for fractional percentage
  Returns:
    Percentage string, or None if percent cannot be computed (i.e. total is
    zero).

  """
  if total == 0:
    return None

  percent = 0
  precision = min(min_precision, max_precision)
  factor = 10 ** precision
  while precision <= max_precision:
    percent = num * 100 * factor // total
    if percent:
      break
    factor *= 10
    precision += 1

  whole, frac = divmod(percent, factor)
  while frac and not frac % 10:
    frac /= 10
    precision -= 1

  return '%d%s%%' % (whole, '.%0*d' % (precision, frac) if frac else '')


def BytesToHumanReadable(size, precision=1, decimal=False):
  """Returns a human readable representation of a given |size|.

  The returned string includes unit notations in either binary (KiB, MiB, etc)
  or decimal (kB, MB, etc), based on the value of |decimal|. The chosen unit is
  the largest that yields a whole (or mixed) number. It may contain up to
  |precision| fractional digits. Values are always rounded down. Largest unit
  is an exabyte. All arithmetic operations are integer built-ins. Examples
  (using default precision and binary units):

    4096 => 4 KiB
    5000 => 4.8 KiB
    500000 => 488.2 KiB
    5000000 => 4.7 MiB

  Args:
    size: the size in bytes
    precision: the number of digits past the decimal point
    decimal: whether to compute/present decimal or binary units
  Returns:
    Readable size string, or None if no conversion is applicable (i.e. size is
    less than the smallest unit).

  """
  constants = (
      (('KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB'), 1024),
      (('kB', 'MB', 'GB', 'TB', 'PB', 'EB'), 1000)
  )
  suffixes, base = constants[decimal]
  exp, magnitude = 0, 1
  while exp < len(suffixes):
    next_magnitude = magnitude * base
    if size < next_magnitude:
      break
    exp += 1
    magnitude = next_magnitude

  if exp != 0:
    whole = size // magnitude
    frac = (size % magnitude) * (10 ** precision) // magnitude
    while frac and not frac % 10:
      frac /= 10
    return '%d%s %s' % (whole, '.%d' % frac if frac else '', suffixes[exp - 1])
