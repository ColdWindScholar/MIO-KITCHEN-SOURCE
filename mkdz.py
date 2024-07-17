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
import os
import sys
import io
import hashlib
import argparse

from binascii import a2b_hex

import dz


class MKDZChunk(dz.DZChunk):
	"""
	Representation of an individual file chunk from a LGE DZ file
	This child includes code oriented towards constructing a DZ file
	"""

	def getStart(self):
		"""
		Return the block we start at
		"""
		return self.start

	def getEnd(self):
		"""
		Return the block we end at
		"""
		return self.end

	def getDev(self):
		"""
		Return which pass we're written during
		"""
		return self.dev

	def list(self, index):
		"""
		Output a listing of our block
		"""
		print("{:2d} : {:s}".format(index, self.chunkName))

	def write(self, file, name):
		"""
		Write our block to the file with the specified name
		"""
		input = io.FileIO(self.name, "rb")

		l = input.seek(0, io.SEEK_END)
		input.seek(0, io.SEEK_SET)

		print("[+] Writing {:s} to {:s} ({:d} bytes)".format(self.name, name, l))

		buf = b" "
		while len(buf) > 0:
			buf = input.read(4096)
			file.write(buf)

		input.close()

	def __init__(self, name, blockShift):
		"""
		Initialize MKDZChunk, a chunk of a DZ file
		"""

		super(MKDZChunk, self).__init__()

		self.name = name

		file = io.FileIO(name, "rb")

		self.buffer = file.read(self._dz_length)

		dz_item = self.unpackdict(self.buffer)

		self.chunkName = dz_item['chunkName'].rstrip(b'\x00').decode("utf8")

		self.start = dz_item['targetAddr']

		self.dev = dz_item['dev']

		if (dz_item['targetSize'] >> blockShift) > dz_item['trimCount']:
			print("[!] target size is more than number of blocks to wipe?!  Inconceivable!", file=sys.stderr)
			sys.exit(1)

		self.end = self.start + dz_item['trimCount']

		file.close()


class MKDZFile(dz.DZFile):
	"""
	Representation of the whole file/header from a LGE DZ file
	This child includes code oriented towards constructing a DZ file
	"""

	def loadParams(self):
		"""
		Load .dz.params, values found in the original DZ file needed
		for constructing new DZ file (but can be altered)
		"""

		params = dict()
		file = io.open(".dz.params", "rt")
		line = file.readline()
		while len(line) > 0:
			line.lstrip()
			line = line.partition("#")[0]
			if len(line) == 0:
				line = file.readline()
				continue
			parts = line.partition("=")
			if len(parts[1]) == 0:
				print("[!] Bad line in {:s} parameter file".format(".dz.params"), file=sys.stderr)
			var = parts[0].rstrip()
			try:
				val = int(parts[2].strip())
			except ValueError:
				val = parts[2].strip()
			params[var] = val
			line = file.readline()

		file.close()

		for new, old in (("androidVer", "android_version"), ("version", "factoryversion")):
			params[new] = params[old]
			del params[old]

		for k in [k for k in params.keys()]:
			t = k.partition('_')
			if t[1]:
				while t[1]:
					new = t[0] + t[2].capitalize()
					t = new.partition('_')
				params[new] = params[k]

		for k in self._dz_format_dict.keys():
			if k[0:8] == "reserved" or k == "header" or k == "pad" or k == "chunkCount" or k == "md5":
				continue
			if k not in params:
				print("[!] Parameter value \"{:s}\" is missing, unable to continue".format(k), file=sys.stderr)
				sys.exit(1)
			elif hasattr(params[k], "encode"):
				params[k] = params[k].encode("utf8")

		if params['formatMajor'] != 2:
			print("[!] File format version not 2, cannot continue", file=sys.stderr)
			sys.exit(1)

		if params['formatMinor'] != 1:
			print("[!] Warning: File appears to be a v{:d}.{:d} format file, compatibility uncertain!".format(params['format_major'], params['format_minor']), file=sys.stderr)

		for k in 'unknown1', 'unknown3':
			params[k] = a2b_hex(params[k])

		for k in 'blockShift',:
			if k not in params:
				print("[!] Parameter value \"{:s}\" is missing, unable to continue".format(k))
				sys.exit(1)

		self.blockShift = params['blockShift']
		self.dz_item = params

	def loadChunks(self):
		"""
		Scan directory for .chunk files, load them
		"""

		for name in os.listdir("."):
			if name[-6:] == ".chunk":
				self.chunks.append(MKDZChunk(name, self.blockShift))

		self.chunks.sort(key=lambda c: (c.getStart() + (c.getDev()<<48) + (1<<56 if c.chunkName[-4:] == ".img" else 0)))

	def checkChunks(self):
		"""
		Scan the chunk list, look for problematic issues
		"""

		dev = -1
		for chunk in self.chunks:
			if chunk.getDev() != dev:
				dev = chunk.getDev()
				last = 0
			if chunk.getStart() < last:
				print("[!] chunk {:s} overlaps!".format(chunk.chunkName), file=sys.stderr)
				sys.exit(1)
			last = chunk.getEnd()

	def computeChecksums(self):
		"""
		Compute the checksums used in the header
		"""

		md5 = hashlib.md5()

		for chunk in self.chunks:
			md5.update(chunk.buffer)

		self.md5Header = md5.digest()

	def listChunks(self):
		"""
		List the chunks to be written to the output file in order
		"""

		print("[+] Found {:d} chunks:".format(len(self.chunks)))
		print()

		index = 1

		for chunk in self.chunks:
			chunk.list(index)
			index += 1

	def writeFile(self, file, name):
		"""
		Write our created file to storage as the named file
		"""

		print("[+] Writing {:d} chunks to {:s}:".format(len(self.chunks), name))
		print()

		self.dz_item['md5'] = self.md5Header
		self.dz_item['chunkCount'] = len(self.chunks)

		# this date code looks like an integer, but is really a string!
		self.dz_item['oldDateCode'] = str(self.dz_item['oldDateCode'])

		buffer = self.packdict(self.dz_item)

		file.write(buffer)

		for chunk in self.chunks:
			chunk.write(file, name)

	def __init__(self, dirname):
		"""
		Initialize MKDZFile, the data for the overal DZ file
		"""

		super(MKDZFile, self).__init__()

		self.dirname = dirname

		os.chdir(dirname)

		self.loadParams()

		self.chunks = []

		self.loadChunks()

		self.checkChunks()

		self.computeChecksums()



class MKDZFileTools:
	"""
	LGE Compressed DZ File tools
	"""

	# Setup variables
	indir = "dzextracted"


	def cmdListChunks(self):
		"""
		"""
		self.dz_file.listChunks()

	def cmdCreateFile(self, file, name):
		"""
		"""
		self.dz_file.writeFile(file, os.path.basename(name))

	def parseArgs(self):
		# Parse arguments
		parser = argparse.ArgumentParser(description='LG Compressed DZ File Creator by Elliott Mitchell')
		parser.add_argument('-f', '--file', help='DZ File to create', action='store', required=True, dest='dzfile')
		group = parser.add_mutually_exclusive_group(required=True)
		group.add_argument('-l', '--list', help='list slices/partitions', action='store_true', dest='listOnly')
		group.add_argument('-m', '--make', help='make DZ file from chunks in directory', action='store_true', dest='createFile')
		parser.add_argument('-d', '--dir', help='input location', action='store', dest='indir')
#		parser.add_argument('-b', '--blocksize', help='blocksize used on the device', action='store', dest='blocksize')

		return parser.parse_args()



	def main(self):
		args = self.parseArgs()
#		cmd = args[0]
#		files = args[1]

		cwd = os.getcwd()

		if args.indir:
			self.indir = args.indir

#		if args.blocksize:
#			cmd.blocksize = int(cmd.blocksize)
#			if cmd.blocksize & (cmd.blocksize-1):
#				print("[!] Error: Specified block size is not a power of 2", file=sys.stderr)
#				sys.exit(1)
#			size = cmd.blocksize
#			result = 0
#			shift = 32
#			while shift > 0:
#				if (size>>shift)>0:
#					size>>=shift
#					result+=shift
#				shift>>=1
#			self.shiftLBA = result

		self.dz_file = MKDZFile(self.indir)

		if args.listOnly:
			self.cmdListChunks()
			sys.exit(0)

		# Extracting chunk(s)
		if args.createFile:
			file = io.FileIO(os.path.join(cwd, args.dzfile), "wb")
			self.cmdCreateFile(file, args.dzfile)
			file.close()


if __name__ == "__main__":
	dztools = MKDZFileTools()
	dztools.main()

