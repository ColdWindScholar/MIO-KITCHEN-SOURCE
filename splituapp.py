#!/usr/bin/env python

# splituapp for Python2/3 by SuperR. @XDA
#
# For extracting img files from UPDATE.APP

# Based on the app_structure file in split_updata.pl by McSpoon

from __future__ import print_function

from string import printable
from struct import unpack
import sys
from os import makedirs, name, sep, path


class extract(object):
    def __init__(self, source, flist):

        bytenum = 4
        outdir = 'output'
        img_files = []

        try:
            makedirs(outdir)
        except:
            pass

        py2 = None
        if sys.version_info.major < 3:
            py2 = 1

        with open(source, 'rb') as f:
            while True:
                i = f.read(bytenum)

                if not i:
                    break
                elif i != b'\x55\xAA\x5A\xA5':
                    continue

                headersize = list(unpack('<L', f.read(bytenum)))[0]
                f.seek(16, 1)
                filesize = list(unpack('<L', f.read(bytenum)))[0]
                f.seek(32, 1)

                try:
                    filename = str(f.read(16).decode())
                    filename = ''.join(f for f in filename if f in printable).lower()
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
                    except Exception as e:
                        print('ERROR: Failed to create ' + filename + '.img:%s\n' % e)
                        return

                    img_files.append(filename)

                    if name != 'nt':
                        if path.isfile('crc'):
                            print('Calculating crc value for ' + filename + '.img ...\n')

                            crc_val = []
                            if py2:
                                for i in crcdata:
                                    crc_val.append('%02X' % int(i))
                            else:
                                for i in crcdata:
                                    crc_val.append('%02X' % i)

                else:
                    f.seek(filesize, 1)

                xbytes = bytenum - f.tell() % bytenum
                if xbytes < bytenum:
                    f.seek(xbytes, 1)

        print('\nExtraction complete')
