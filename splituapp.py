#!/usr/bin/env python

# splituapp for Python2/3 by SuperR. @XDA
#
# For extracting img files from UPDATE.APP

# Based on the app_structure file in split_updata.pl by McSpoon

from __future__ import print_function

# import os
from os import makedirs, name, sep, path
import re
import sys
import string
import struct
from subprocess import check_output


class extract(object):
    def __init__(self, source, flist):
        def cmd(command):
            try:
                test1 = check_output(command).strip().decode()
            except:
                test1 = ''

            return test1

        bytenum = 4
        outdir = 'output'
        img_files = []

        try:
            makedirs(outdir)
        except:
            pass

        py2 = None
        if int(''.join(str(i) for i in sys.version_info[0:2])) < 30:
            py2 = 1

        with open(source, 'rb') as f:
            while True:
                i = f.read(bytenum)

                if not i:
                    break
                elif i != b'\x55\xAA\x5A\xA5':
                    continue

                headersize = f.read(bytenum)
                headersize = list(struct.unpack('<L', headersize))[0]
                f.seek(16, 1)
                filesize = f.read(bytenum)
                filesize = list(struct.unpack('<L', filesize))[0]
                f.seek(32, 1)
                filename = f.read(16)

                try:
                    filename = str(filename.decode())
                    filename = ''.join(f for f in filename if f in string.printable).lower()
                except:
                    filename = ''

                f.seek(22, 1)
                crcdata = f.read(headersize - 98)

                if not flist or filename in flist:
                    if filename in img_files:
                        filename = filename + '_2'

                    print(f'Extracting {filename}.img ...')

                    chunk = 10240

                    try:
                        with open(outdir + sep + filename + '.img', 'wb') as o:
                            while filesize > 0:
                                if chunk > filesize:
                                    chunk = filesize

                                o.write(f.read(chunk))
                                filesize -= chunk
                    except:
                        print('ERROR: Failed to create ' + filename + '.img\n')
                        return

                    img_files.append(filename)

                    if name != 'nt':
                        if path.isfile('crc'):
                            print('Calculating crc value for ' + filename + '.img ...\n')

                            crcval = []
                            if py2:
                                for i in crcdata:
                                    crcval.append('%02X' % ord(i))
                            else:
                                for i in crcdata:
                                    crcval.append('%02X' % i)

                            crcval = ''.join(crcval)
                            crcact = cmd('./crc output/{0}.img'.format(filename))

                            if crcval != crcact:
                                print('ERROR: crc value for {0}.img does not match\n'.format(filename))
                                return
                else:
                    f.seek(filesize, 1)

                xbytes = bytenum - f.tell() % bytenum
                if xbytes < bytenum:
                    f.seek(xbytes, 1)

        print('\nExtraction complete')
        return


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Split UPDATE.APP file into img files", add_help=False)
    required = parser.add_argument_group('Required')
    required.add_argument("-f", "--filename", required=True, help="Path to update.app file")
    optional = parser.add_argument_group('Optional')
    optional.add_argument("-h", "--help", action="help", help="show this help message and exit")
    optional.add_argument("-l", "--list", nargs="*", metavar=('img1', 'img2'), help="List of img files to extract")
    args = parser.parse_args()

    extract(args.filename, args.list)
