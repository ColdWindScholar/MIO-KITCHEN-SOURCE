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

"""Histogram generation tools."""

from __future__ import absolute_import
from __future__ import division

from collections import defaultdict

# --- ИСПРАВЛЕННЫЕ ИМПОРТЫ ---
from . import format_utils


class Histogram(object):
  """A histogram generating object.

  This object serves the sole purpose of formatting (key, val) pairs as an
  ASCII histogram, including bars and percentage markers, and taking care of
  label alignment, scaling, etc. In addition to the standard __init__
  interface, two static methods are provided for conveniently converting data
  in different formats into a histogram. Histogram generation is exported via
  its __str__ method, and looks as follows:

    Yes |################    | 5 (83.3%)
    No  |###                 | 1 (16.6%)

  TODO(garnold) we may want to add actual methods for adding data or tweaking
  the output layout and formatting. For now, though, this is fine.

  """

  def __init__(self, data, scale=20, formatter=None):
    """Initialize a histogram object.

    Args:
      data: list of (key, count) pairs constituting the histogram
      scale: number of characters used to indicate 100%
      formatter: function used for formatting raw histogram values

    """
    self.data = data
    self.scale = scale
    self.formatter = formatter or str
    self.max_key_len = max([len(str(key)) for key, count in self.data])
    self.total = sum([count for key, count in self.data])

  @staticmethod
  def FromCountDict(count_dict, scale=20, formatter=None, key_names=None):
    """Takes a dictionary of counts and returns a histogram object.

    This simply converts a mapping from names to counts into a list of (key,
    count) pairs, optionally translating keys into name strings, then
    generating and returning a histogram for them. This is a useful convenience
    call for clients that update a dictionary of counters as they (say) scan a
    data stream.

    Args:
      count_dict: dictionary mapping keys to occurrence counts
      scale: number of characters used to indicate 100%
      formatter: function used for formatting raw histogram values
      key_names: dictionary mapping keys to name strings
    Returns:
      A histogram object based on the given data.

    """
    namer = None
    if key_names:
      namer = lambda key: key_names[key]
    else:
      namer = lambda key: key

    hist = [(namer(key), count) for key, count in count_dict.items()]
    return Histogram(hist, scale, formatter)

  @staticmethod
  def FromKeyList(key_list, scale=20, formatter=None, key_names=None):
    """Takes a list of (possibly recurring) keys and returns a histogram object.

    This converts the list into a dictionary of counters, then uses
    FromCountDict() to generate the actual histogram. For example:

      ['a', 'a', 'b', 'a', 'b'] --> {'a': 3, 'b': 2} --> ...

    Args:
      key_list: list of (possibly recurring) keys
      scale: number of characters used to indicate 100%
      formatter: function used for formatting raw histogram values
      key_names: dictionary mapping keys to name strings
    Returns:
      A histogram object based on the given data.

    """
    count_dict = defaultdict(int)  # Unset items default to zero
    for key in key_list:
      count_dict[key] += 1
    return Histogram.FromCountDict(count_dict, scale, formatter, key_names)

  def __str__(self):
    hist_lines = []
    hist_bar = '|'
    for key, count in self.data:
      if self.total:
        bar_len = count * self.scale // self.total
        hist_bar = '|%s|' % ('#' * bar_len).ljust(self.scale)

      line = '%s %s %s' % (
          str(key).ljust(self.max_key_len),
          hist_bar,
          self.formatter(count))
      percent_str = format_utils.NumToPercent(count, self.total)
      if percent_str:
        line += ' (%s)' % percent_str
      hist_lines.append(line)

    return '\n'.join(hist_lines)

  def GetKeys(self):
    """Returns the keys of the histogram."""
    return [key for key, _ in self.data]
