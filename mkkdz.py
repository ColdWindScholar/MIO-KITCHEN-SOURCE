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
import argparse

import kdz


class KDZFileTools(kdz.KDZFile):
    """
	LGE KDZ File creation tool
	"""

    indir = "kdzextracted"


    def loadParams(self):
        """
		Loads the .kdz.params file for output, saves the values
		"""

        params = dict()
        file = open(os.path.join(self.indir, ".kdz.params"), "rt")
        line = file.readline()
        while len(line) > 0:
            line.lstrip()
            line = line.partition("#")[0]
            if len(line) == 0:
                line = file.readline()
                continue
            parts = line.partition("=")
            if len(parts[1]) == 0:
                print("[!] Bad line in {:s}'s parameter file".format(self.indir), file=sys.stderr)
            var = parts[0].rstrip()
            try:
                val = int(parts[2].strip())
            except ValueError:
                val = parts[2].strip()
            params[var] = val
            line = file.readline()

        file.close()

        for k in 'version', 'dataStart', 'payload0', 'payload0head':
            if k not in params:
                print("Parameter value \"{:s}\" is missing, unable to continue".format(k))
                sys.exit(1)

        if params['version'] != 2:
            print("[!] File format version not 2, cannot continue", file=sys.stderr)
            sys.exit(1)

        self.dataStart = params['dataStart']

        i = 0
        self.headers = []
        headers = {}
        self.payload = []
        self.files = {}
        name = "payload" + str(i)
        while name in params:
            self.payload.append(params[name])
            headers[params[name + "head"]] = params[name]
            i += 1
            name = "payload" + str(i)
        for i in range(i):
            self.headers.append(headers[i])

    def cmdCreateFile(self):
        """
		Create the specified KDZ file
		"""

        out = open(self.kdzfile, "wb")
        current = self.dataStart
        out.seek(current, os.SEEK_SET)

        for name in self.payload:
            print("[+] Writing {:s} to output file {:s}".format(name, self.kdzfile))
            inf = open(os.path.join(self.indir, name), "rb")
            buf = " "
            while len(buf) > 0:
                buf = inf.read(4096)
                out.write(buf)
            self.files[name] = [current, out.tell() - current]
            inf.close()
            current = out.tell()

        self.files[self.headers[-1]].append(0)

        print("\n[+] Writing headers to {:s}".format(self.kdzfile))

        out.seek(0, os.SEEK_SET)
        out.write(self._dz_header)
        for name in self.headers:
            # last record
            if len(self.files[name]) > 2:
                out.write(b'\x03')
            head = {
                'name': name.encode("utf8"),
                'length': self.files[name][1],
                'offset': self.files[name][0],
            }
            buf = self.packdict(head)
            out.write(buf)
        out.close()
        print("[+] Done!")

    def cmdList(self):
        pass

    @staticmethod
    def parseArgs():
        # Parse arguments
        parser = argparse.ArgumentParser(description='LG KDZ File creator by Elliott Mitchell')
        parser.add_argument('-f', '--file', help='KDZ File to read', action='store', required=True, dest='kdzfile')
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('-l', '--list', help='list partitions', action='store_true', dest='listOnly')
        group.add_argument('-m', '--make', help='extract all partitions', action='store_true', dest='createFile')
        parser.add_argument('-d', '--dir', help='input directory', action='store', dest='indir')

        return parser.parse_args()

    def main(self):
        args = self.parseArgs()
        self.kdzfile = args.kdzfile

        if args.indir:
            self.indir = args.indir

        self.loadParams()

        if args.listOnly:
            self.cmdList()

        elif args.createFile:
            self.cmdCreateFile()


if __name__ == "__main__":
    kdztools = KDZFileTools()
    kdztools.main()
