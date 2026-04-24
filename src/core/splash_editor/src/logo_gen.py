#!/usr/bin/env python2
# Copyright (c) 2013,2015, The Linux Foundation. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above
#       copyright notice, this list of conditions and the following
#       disclaimer in the documentation and/or other materials provided
#       with the distribution.
#     * Neither the name of The Linux Foundation nor the names of its
#       contributors may be used to endorse or promote products derived
#       from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY EXPRESS OR IMPLIED
# WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NON-INFRINGEMENT
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS
# BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
# BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN
# IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

#===========================================================================

#  This script read the logo png and creates the logo.img

# when          who     what, where, why
# --------      ---     -------------------------------------------------------
# 2013-04       QRD     init
# 2015-04       QRD     support the RLE24 compression

# Environment requirement:
#     Python + PIL
#     PIL install:
#         (ubuntu)  sudo apt-get install python-imaging
#         (windows) (http://www.pythonware.com/products/pil/)

# limit:
#    a This script only support Python 2.7.x, 2.6.x,
#      Can't use in py3x for StringIO module
#    b This script's input can be a png, jpeg, bmp, gif file.
#    But if it is a gif, only get the first frame by default.
#
# description:
#    struct logo_header {
#       unsigned char[8]; // "SPLASH!!"
#       unsigned width;   // logo's width, little endian
#       unsigned height;  // logo's height, little endian
#       unsigned type;    // 0, Raw Image; 1, RLE24 Compressed Image
#       unsigned blocks;  // block number, real size / 512
#       ......
#    };

#    the logo Image layout:
#       logo_header + Payload data

# ===========================================================================*/
from __future__ import print_function
import sys, os
import struct
from io import BytesIO

from PIL import Image

SUPPORT_RLE24_COMPRESSIONT = True
bodyLength = 0
payloadLimit = 0  # 0 means no limit


## get header
def GetImgHeader(size: tuple[int, int], compressed=0, real_bytes=0) -> bytes:
    SECTOR_SIZE_IN_BYTES = 512  # Header size
    header = [0] * SECTOR_SIZE_IN_BYTES

    width, height = size

    if SUPPORT_RLE24_COMPRESSIONT == 1:
        real_size = (bodyLength + 511) / 512
    else:
        real_size = (real_bytes + 511) / 512

    # magic
    header[:8] = [ord('S'), ord('P'), ord('L'), ord('A'),
                  ord('S'), ord('H'), ord('!'), ord('!')]

    # width
    header[8] = (width & 0xFF)
    header[9] = ((width >> 8) & 0xFF)
    header[10] = ((width >> 16) & 0xFF)
    header[11] = ((width >> 24) & 0xFF)

    # height
    header[12] = (height & 0xFF)
    header[13] = ((height >> 8) & 0xFF)
    header[14] = ((height >> 16) & 0xFF)
    header[15] = ((height >> 24) & 0xFF)

    #type
    header[16] = (compressed & 0xFF)
    #header[17]= 0
    #header[18]= 0
    #header[19]= 0

    # block number

    real_size = int(real_size)
    header[20] = (real_size & 0xFF)
    header[21] = ((real_size >> 8) & 0xFF)
    header[22] = ((real_size >> 16) & 0xFF)
    header[23] = ((real_size >> 24) & 0xFF)
    return bytearray(header)



def encode(line):
    count = 0
    lst = []
    repeat = -1
    run = []
    total = len(line) - 1
    for index, current in enumerate(line[:-1]):
        if current != line[index + 1]:
            run.append(current)
            count += 1
            if repeat == 1:
                entry = (count + 128, run)
                lst.append(entry)
                count = 0
                run = []
                repeat = -1
                if index == total - 1:
                    run = [line[index + 1]]
                    entry = (1, run)
                    lst.append(entry)
            else:
                repeat = 0

                if count == 128:
                    entry = (128, run)
                    lst.append(entry)
                    count = 0
                    run = []
                    repeat = -1
                if index == total - 1:
                    run.append(line[index + 1])
                    entry = (count + 1, run)
                    lst.append(entry)
        else:
            if repeat == 0:
                entry = (count, run)
                lst.append(entry)
                count = 0
                run = []
                repeat = -1
                if index == total - 1:
                    run.append(line[index + 1])
                    run.append(line[index + 1])
                    entry = (2 + 128, run)
                    lst.append(entry)
                    break
            run.append(current)
            repeat = 1
            count += 1
            if count == 128:
                entry = (256, run)
                lst.append(entry)
                count = 0
                run = []
                repeat = -1
            if index == total - 1:
                if count == 0:
                    run = [line[index + 1]]
                    entry = (1, run)
                    lst.append(entry)
                else:
                    run.append(current)
                    entry = (count + 1 + 128, run)
                    lst.append(entry)
    return lst


def encodeRLE24(img):
    width, height = img.size
    output = BytesIO()
    bytesProcessedInBody = 0
    global bodyLength
    global payloadLimit

    for h in range(height):
        line = []
        for w in range(width):
            (r, g, b) = img.getpixel((w, h))
            line.append((r << 16) + (g << 8) + b)
        result = encode(line)
        for count, pixel in result:
            output.write(struct.pack("B", count - 1))
            bytesProcessedInBody += 1
            if count > 128:
                output.write(struct.pack("B", (pixel[0]) & 0xFF))
                output.write(struct.pack("B", ((pixel[0]) >> 8) & 0xFF))
                output.write(struct.pack("B", ((pixel[0]) >> 16) & 0xFF))
                bytesProcessedInBody += 3
            else:
                for item in pixel:
                    output.write(struct.pack("B", item & 0xFF))
                    output.write(struct.pack("B", (item >> 8) & 0xFF))
                    output.write(struct.pack("B", (item >> 16) & 0xFF))
                    bytesProcessedInBody += 3

    bodyLength = len(output.getvalue())

    if payloadLimit != 0:
        assert bytesProcessedInBody <= payloadLimit, "\n\n\nPICTURE IS LARGE IN SIZE..\nQuitting..."
        while bytesProcessedInBody < payloadLimit:
            output.write(struct.pack("B", 0x00))
            bytesProcessedInBody += 1
    content = output.getvalue()
    output.close()
    return content


## get payload data : BGR Interleaved
def GetImageBody(img, compressed: bool = False):
    color = (0, 0, 0)
    if img.mode == "RGB":
        background = img
    elif img.mode == "RGBA":
        background = Image.new("RGB", img.size, color)
        img.load()
        background.paste(img, mask=img.split()[3])  # alpha channel
    elif img.mode == "P" or img.mode == "L":
        background = Image.new("RGB", img.size, color)
        img.load()
        background.paste(img)
        #background.save("splash.png")
    else:
        print("sorry, can't support this format")
        sys.exit()

    background.load()

    if compressed:
        return encodeRLE24(background)
    else:
        r, g, b = background.split()
        return Image.merge("RGB", (b, g, r)).tostring()


## make a image

def MakeLogoImage(logo):
    with Image.open(logo) as img:
        body = GetImageBody(img, SUPPORT_RLE24_COMPRESSIONT)
        data = GetImgHeader(img.size, SUPPORT_RLE24_COMPRESSIONT, len(body))
        data += body
        return data

def GenerateLogoImg(infile:str, payloadLimitValue:int):
    if SUPPORT_RLE24_COMPRESSIONT:
        global payloadLimit
        payloadLimit = payloadLimitValue
    data = MakeLogoImage(infile)
    return data

## main
if __name__ == "__main__":
    num = len(sys.argv)

    if num < 2:
        print(" usage: python logo_gen.py [logo.png] payload_max_size")
        sys.exit()  # error arg

    infile = sys.argv[1]
    if SUPPORT_RLE24_COMPRESSIONT and num == 3:
        payloadLimit = int(sys.argv[2])

    if not os.access(infile, os.R_OK):
        print(" usage: python logo_gen.py [logo.png] payload_max_size")
        sys.exit()  # error file
    with open("output.img", 'wb') as f:
        MakeLogoImage(infile)
