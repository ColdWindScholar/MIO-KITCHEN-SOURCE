#!/usr/bin/env python2
'''
An utility to decode the splash.img for Snapdragon devices, encoded using logo_gen.py, available at the CAF here:
https://source.codeaurora.org/quic/la/device/qcom/common/tree/display/logo?h=LA.BR.1.2.7_rb1.1

Created by Gokul NC @ XDA-Developers
Contact me @ http://about.me/GokulNC
'''

import sys, os
from PIL import Image

HEADER_TEXT = b"SPLASH!!"
BLOCK_SIZE = 512


def decodeRLE24(encoded_img, resolution, payload_dims=None):
    rgb_img = Image.new("RGB", resolution, (0, 0, 0))
    rows, columns = resolution
    #print("Resolution "+str(resolution))
    pixelsNew = rgb_img.load()
    i = j = 0

    '''
    How decoding works:
    The run-length encoding is column-wise, and is of format: list of (count, RGB_pixels)
    If count>127, it means all values in it are repeated, so fill all (255-count)+1 no. of pixels with same BGR value.
    Else, values are different. Fill (count)+1 no. of pixels with subsequent BGR values.
    '''

    byte = encoded_img.read(1)
    while byte:
        pixel_count = ord(chr(byte[0])) + 1
        if pixel_count > 128:
            b = ord(chr(encoded_img.read(1)[0]))
            g = ord(chr(encoded_img.read(1)[0]))
            r = ord(chr(encoded_img.read(1)[0]))
            color = (r, g, b)
            for _ in range(pixel_count - 128):
                pixelsNew[i, j] = color
                i = (i + 1) % rows
                if i == 0: j += 1
        else:
            for _ in range(pixel_count):
                b = ord(chr(encoded_img.read(1)[0]))
                g = ord(chr(encoded_img.read(1)[0]))
                r = ord(chr(encoded_img.read(1)[0]))
                pixelsNew[i, j] = (r, g, b)
                i = (i + 1) % rows
                if i == 0: j += 1
        if j == columns and i == 0:
            #print("Decoded successfully at %d"%encoded_img.tell())
            break
        byte = encoded_img.read(1)

    if payload_dims is not None and type(payload_dims) is tuple and len(payload_dims) == 2:
        encoded_img.seek(payload_dims[0] + payload_dims[1] - encoded_img.tell(), 1)
        #print("Stopped processing the file at %d"%encoded_img.tell())

    return rgb_img


def int_to_rgb24(val):
    r = (val >> 16) & 0xFF
    g = (val >> 8) & 0xFF
    b = val & 0xFF
    return r, g, b


def read_int32(bytes: bytes):
    assert len(bytes) == 4, "Incorrect no. of bytes passed for read_int32(). Pass an array of 4 bytes only."
    # Parse from little endian to integer
    value = ord(chr(bytes[3]))
    for i in range(2, -1, -1):
        value = (value << 8) | ord(chr(bytes[i]))

    return value


def process_splashimg(input_file, output_file):
    with open(input_file, "rb") as f:
        f.seek(1024)  # add by affggh for skip empty bytes
        i = 1
        while True:
            # Read HEADER_TEXT chunk. Ref: https://stackoverflow.com/a/1035419/5002496
            hdr_txt = f.read(len(HEADER_TEXT))
            # Check if they match. Ref: https://stackoverflow.com/a/606199/5002496
            if HEADER_TEXT != hdr_txt:
                if i == 1: print("This file is not supported.")
                return
            width = read_int32(f.read(4))
            height = read_int32(f.read(4))
            is_encoded = read_int32(f.read(4))
            assert is_encoded == 1, "The file is already not encoded"
            payload_size = read_int32(f.read(4)) * BLOCK_SIZE
            # Skip the remaining bytes in header
            f.seek(BLOCK_SIZE - (f.tell() % BLOCK_SIZE), 1)
            # print("Decoding from %d" % f.tell())
            decoded_img = decodeRLE24(f, (width, height), (f.tell(), payload_size))
            # Save the file now
            pos = output_file.rfind('.')
            if pos == -1:
                filename = output_file + str(i)
            else:
                filename = output_file[0:pos] + str(i) + output_file[pos:]
            print(f"Saving decoded image {i} to {filename}")
            decoded_img.save(filename)
            i += 1
            # Skip zeros if present at end
            byte = f.read(1)
            while byte and ord(chr(byte[0])) == 0: byte = f.read(1)
            f.seek(-1, 1)


def main():
    assert len(sys.argv) >= 3, f"Usage: python {sys.argv[0]} input_file output_file"
    assert os.path.exists(sys.argv[1]), f"Unable to access the file {sys.argv[1]}"
    process_splashimg(sys.argv[1], sys.argv[2])

if __name__ == "__main__":
    main()
