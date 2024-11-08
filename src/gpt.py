#!/usr/bin/env python

"""
Copyright (C) 2016 Elliott Mitchell <ehem+android@m5p.com>

	This program is free software: you can redistribute it and/or modify
	it under the terms of the GNU General Public License as published by
	the Free Software Foundation, either version 3 of the License, or
	(at your option) any later version.

	This program is distributed in the hope that it will be useful,
	but WITHOUT ANY WARRANTY; without even the implied warranty of
	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
	GNU General Public License for more details.

	You should have received a copy of the GNU General Public License
	along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from __future__ import print_function

import io
import sys
from binascii import crc32
from collections import OrderedDict
from struct import Struct
from uuid import UUID

verbose = lambda msg: None


class NoGPT(Exception):
    def __init__(self, errmsg):
        self.errmsg = errmsg

    def __str__(self):
        return self.errmsg


class GPTSlice:
    """
	Class for handling invidual slices^Wpartitions of a GUID table
	"""

    _gpt_slice_length = 128  # this is *default*!

    # Format string dict
    #   itemName is the new dict key for the data to be stored under
    #   formatString is the Python formatstring for struct.unpack()
    # Example:
    #   ('itemName', ('formatString'))
    _gpt_slice_fmt = OrderedDict([
        ('type', '16s'),
        ('uuid', '16s'),
        ('startLBA', 'Q'),
        ('endLBA', 'Q'),
        ('flags', 'Q'),
        ('name', '72s')
    ])

    # Generate the formatstring for struct.unpack()
    _gpt_struct = Struct("<" + "".join([x for x in _gpt_slice_fmt.values()]))

    def display(self, idx):
        """
		Display the data for this slice of a GPT
		"""

        if self.type == UUID(int=0):
            verbose("Name: <empty entry>")
            return None

        verbose("Name({:d}): \"{:s}\" start={:d} end={:d} count={:d}".format(idx, self.name, self.startLBA, self.endLBA,
                                                                             self.endLBA - self.startLBA + 1))
        verbose("typ={:s} id={:s}".format(str(self.type), str(self.uuid)))

    def __init__(self, buf):
        """
		Initialize the GPTSlice class
		"""

        data = dict(zip(
            self._gpt_slice_fmt.keys(),
            self._gpt_struct.unpack(buf)
        ))

        self.type = UUID(bytes=data['type'])
        self.uuid = UUID(bytes=data['uuid'])
        self.startLBA = data['startLBA']
        self.endLBA = data['endLBA']
        self.flags = data['flags']
        self.name = data['name'].decode("utf16").rstrip('\x00')


class GPT:
    """
	Class for handling of GUID Partition Tables
	(https://en.wikipedia.org/wiki/GUID_Partition_Table)
	"""

    _gpt_header = b"EFI PART"
    _gpt_size = 0x5C  # default, can be overridden by headerSize

    # Format string dict
    #   itemName is the new dict key for the data to be stored under
    #   formatString is the Python formatstring for struct.unpack()
    # Example:
    #   ('itemName', ('formatString'))
    _gpt_head_fmt = OrderedDict([
        ('header', '8s'),  # magic number
        ('revision', 'I'),  # actually 2 shorts, Struct...
        ('headerSize', 'I'),
        ('crc32', 'I'),
        ('reserved', 'I'),
        ('myLBA', 'Q'),
        ('altLBA', 'Q'),
        ('dataStartLBA', 'Q'),
        ('dataEndLBA', 'Q'),
        ('uuid', '16s'),
        ('entryStart', 'Q'),
        ('entryCount', 'I'),
        ('entrySize', 'I'),
        ('entryCrc32', 'I'),
    ])

    # Generate the formatstring for struct.unpack()
    _gpt_struct = Struct("<" + "".join([x for x in _gpt_head_fmt.values()]))

    def display(self):
        """
		Display the data in the particular GPT
		"""

        verbose("")

        verbose("block size is {:d} bytes (shift {:d})".format(1 << self.shiftLBA, self.shiftLBA))
        verbose("device={:s}".format(str(self.uuid)))
        verbose("myLBA={:d} altLBA={:d} dataStart={:d} dataEnd={:d}".format(self.myLBA, self.altLBA, self.dataStartLBA,
                                                                            self.dataEndLBA))

        verbose("")

        if self.myLBA == 1:
            if self.entryStart != 2:
                verbose("Note: {:d} unused blocks between GPT header and entry table".format(self.entryStart - 2))
            endEntry = self.entryStart + (
                    (self.entrySize * self.entryCount + (1 << self.shiftLBA) - 1) >> self.shiftLBA)
            if endEntry < self.dataStartLBA:
                verbose("Note: {:d} unused slice entry blocks before first usable block".format(
                    self.dataStartLBA - endEntry))
        else:
            if self.entryStart != self.dataEndLBA + 1:
                verbose("Note: {:d} unused slice entry blocks after last usable block".format(
                    self.entryStart - self.dataEndLBA - 1))
            endEntry = self.entryStart + (
                    (self.entrySize * self.entryCount + (1 << self.shiftLBA) - 1) >> self.shiftLBA)
            if endEntry < self.myLBA - 1:
                verbose("Note: {:d} unused blocks between GPT header and entry table".format(self.myLBA - endEntry + 1))

        current = self.dataStartLBA
        idx = 1
        for slice in self.slices:
            if slice.type != UUID(int=0):
                if slice.startLBA != current:
                    verbose("Note: non-contiguous ({:d} unused)".format(slice.startLBA - current))
                current = slice.endLBA + 1
            slice.display(idx)
            idx += 1
        current -= 1
        if self.dataEndLBA != current:
            verbose("Note: empty LBAs at end ({:d} unused)".format(self.dataEndLBA - current))

    def tryParseHeader(self, buf):
        """
		Try to parse a buffer as a GPT header, return None on failure
		"""

        if len(buf) < self._gpt_size:
            raise NoGPT("Failed to locate GPT")

        data = dict(zip(
            self._gpt_head_fmt.keys(),
            self._gpt_struct.unpack(buf[0:self._gpt_size])
        ))

        if data['header'] != self._gpt_header:
            return None

        tmp = data['crc32']
        data['crc32'] = 0

        crc = crc32(self._gpt_struct.pack(*[data[k] for k in self._gpt_head_fmt.keys()]))

        data['crc32'] = tmp

        # just in case future ones are larger
        crc = crc32(buf[self._gpt_size:data['headerSize']], crc)
        crc &= 0xFFFFFFFF

        if crc != data['crc32']:
            verbose("Warning: Found GPT candidate with bad CRC")
            return None

        return data

    def __init__(self, buf, type=None, lbaMinShift=9, lbaMaxShift=16):
        """
		Initialize the GPT class
		"""

        # sanity checking
        if self._gpt_struct.size != self._gpt_size:
            raise NoGPT("GPT format string wrong!")

        # we assume we're searching, start with the bottom end
        shiftLBA = lbaMinShift
        lbaSize = 1 << shiftLBA

        shiftLBA -= 1
        # search for the GPT, since block size is unknown
        while shiftLBA < lbaMaxShift:
            # non power of 2 sizes are illegal
            shiftLBA += 1
            lbaSize = 1 << shiftLBA

            # try for a primary GPT
            hbuf = buf[lbaSize:lbaSize << 1]

            data = self.tryParseHeader(hbuf)

            if data:
                verbose("Found Primary GPT")
                break

            # try for a backup GPT
            hbuf = buf[-lbaSize:]

            data = self.tryParseHeader(hbuf)

            if data:
                verbose("Found Backup GPT")
                break

        else:
            raise NoGPT("Failed to locate GPT")

        self.shiftLBA = shiftLBA

        if data['reserved'] != 0:
            verbose("Warning: Reserved area non-zero")

        self.revision = data['revision']
        self.headerSize = data['headerSize']
        self.reserved = data['reserved']
        self.myLBA = data['myLBA']
        self.altLBA = data['altLBA']
        self.dataStartLBA = data['dataStartLBA']
        self.dataEndLBA = data['dataEndLBA']
        self.uuid = UUID(bytes=data['uuid'])
        self.entryStart = data['entryStart']
        self.entryCount = data['entryCount']
        self.entrySize = data['entrySize']
        self.entryCrc32 = data['entryCrc32']

        if self.revision >> 16 != 1:
            raise NoGPT("Error: GPT major version isn't 1")
        elif self.revision & 0xFFFF != 0:
            verbose("Warning: Newer GPT revision")

        # these tests were against our version and may well fail
        elif self.reserved != 0:
            verbose("Warning: Reserved area non-zero")

        # this is an error according to the specs
        if (self.myLBA != 1) and (self.altLBA != 1):
            raise NoGPT("Error: No GPT at LBA 1 ?!")

        # this is an error according to the specs
        if self.entrySize & (self.entrySize - 1):
            raise NoGPT("Error: entry size is not a power of 2")

        if self.myLBA == 1:
            sliceAddr = self.entryStart << self.shiftLBA
        else:
            sliceAddr = (self.entryStart - self.myLBA - 1) << self.shiftLBA

        self.slices = []
        crc = 0
        for i in range(self.entryCount):
            sbuf = buf[sliceAddr:sliceAddr + self.entrySize]
            crc = crc32(sbuf, crc)
            slice = GPTSlice(sbuf)
            self.slices.append(slice)

            sliceAddr += self.entrySize

        crc &= 0xFFFFFFFF

        if crc != self.entryCrc32:
            raise NoGPT("Error: bad slice entry CRC")

        last = 0
        for slice in self.slices:
            if slice.type == UUID(int=0):
                continue
            if slice.startLBA <= last:
                verbose("Note: slices are out of order in GPT")
                self.ordered = False
                break
            last = slice.endLBA
        else:
            self.ordered = True


if __name__ == "__main__":
    verbose = lambda msg: print(msg)

    progname = sys.argv[0]
    del sys.argv[0]

    for arg in sys.argv:
        if arg == "-":
            file = sys.stdin
        else:
            file = io.FileIO(arg, "rb")

        # header is always in second LBA, slice entries in third
        # if you run out of slice entries with a 64KB LBA, oy vey!
        buf = file.read(1 << 17 + 1 << 16)

        try:
            gpt = GPT(buf)
            gpt.display()
        except NoGPT:
            print(NoGPT, file=sys.stderr)
