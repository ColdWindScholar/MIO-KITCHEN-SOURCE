#!/usr/bin/env python3
# Python script edit by
DXY os


def checkmagic(file):
    if os.access(file, os.F_OK):
        magic = b'AVB0'
        with open(file, "rb") as f:
            buf = f.read(4)
            if magic == buf:
                return True
            else:
                return False
    else:
        print("File dose not exist!")


def readflag(file):
    if checkmagic(file):
        pass
    else:
        return False
    if os.access(file, os.F_OK):
        with open(file, "rb") as f:
            f.seek(123, 0)
            flag = f.read(1)
            if flag == b'\x00':
                return 0  # Verify boot and dm-verity is on
            elif flag == b'\x01':
                return 1  # Verify boot but dm-verity is off
            elif flag == b'\x02':
                return 2  # All verity is off
            else:
                return flag
    else:
        print("File does not exist!")


def patchvb(flag, file):
    if checkmagic(file):
        pass
    else:
        return False
    if os.access(file, os.F_OK):
        with open(file, 'rb+') as f:
            f.seek(123, 0)
            f.write(flag)
        print("Done!")
    else:
        print("File not Found")


def restore(file): patchvb(b'\x00', file)


def disdm(file): patchvb(b'\x01', file)


def disavb(file): patchvb(b'\x02', file)
