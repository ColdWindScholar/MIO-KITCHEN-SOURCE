import ctypes
from io import SEEK_END


class EndianUnion(ctypes.Union):
    _fields_ = [
        ("c", ctypes.c_char * 4),
        ("mylong", ctypes.c_ulong)
    ]


endian_test = EndianUnion()
endian_test.c = b'l??b'

ENDIANNESS = chr(endian_test.mylong & 0xFF)


def Swap32(A):
    uint32_a = int.from_bytes(A)
    return (uint32_a & 0xff000000) >> 24 | (uint32_a & 0x00ff0000) >> 8 | (uint32_a & 0x0000ff00) << 8 | (
                uint32_a & 0x000000ff) << 24


def ntohl(hl):
    if ENDIANNESS == 'l':
        return Swap32(hl)
    else:
        return hl


def convert(test, loc: int):
    return ntohl((test[loc] << 24) | (test[loc + 1] << 16) | (test[loc + 2] << 8) | test[loc + 3])


def main(firmware, out_put):
    with open(firmware, 'rb') as fileptr:
        fileptr.seek(0, SEEK_END)
        filelen = fileptr.tell()
        fileptr.seek(0, 0)
        buffer = fileptr.read(filelen)
        record = 0
        while record < buffer[0x18]:
            record_loc = 0x40 + (record * 0x240)

            def read_c_string(buf, start):
                end = buf.find(b'\x00', start)
                return buf[start:end].decode('utf-8') if end != -1 else buf[start:].decode('utf-8')

            name_part = read_c_string(buffer, record_loc + 0x120)
            ext_part = read_c_string(buffer, record_loc + 0x20)

            filename = f"{out_put}/{name_part}.{ext_part}"
            file_loc = convert(buffer, record_loc + 0x10)
            file_size = convert(buffer, record_loc + 0x18)
            with open(filename, 'wb') as f:
                f.write(buffer[file_loc:file_loc + file_size])
            record += 1
