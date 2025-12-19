from ctypes import LittleEndianStructure, sizeof, memmove, byref, string_at, addressof, c_long, c_char
from io import SEEK_END, SEEK_SET


class BasicStruct(LittleEndianStructure):
    @property
    def _size(self):
        return sizeof(type(self))

    def __len__(self):
        return self._size

    def unpack(self, data: bytes):
        if len(data) < self._size:
            raise Exception("Input data size less than struct size.")
        if not isinstance(data, (bytes, bytearray)):
            raise Exception("Input data must be byte data or bytearray.")

        return memmove(byref(self), data, self._size)

    def pack(self):
        return string_at(addressof(self), sizeof(self))


class nb0_header_item(BasicStruct):
    _fields_ = [
        ("offset", c_long),
        ("size", c_long),
        ("name", c_char * 49),
        ("nb0_file_offset", c_long)
    ]


nb0_count: int
nb0_headers = {}


def read_dword(fd):
    a = fd.read(1)
    b = fd.read(1)
    c = fd.read(1)
    d = fd.read(1)
    result = int.from_bytes(a) | int.from_bytes(b) << 8 | int.from_bytes(c) << 16 | int.from_bytes(d) << 24
    return result


def write_dword(fd, l):
    fd.write(chr(l & 0xff).encode())
    fd.write(chr((l >> 8) & 0xff).encode())
    fd.write(chr((l >> 16) & 0xff).encode())
    fd.write(chr((l >> 24) & 0xff).encode())


def read_header(header: nb0_header_item, fd):
    header.offset = read_dword(fd)
    header.size = read_dword(fd)
    read_dword(fd)
    read_dword(fd)
    header.name = fd.read(48)
    header.name[48] = b'\0'
    i = 48
    while i >= 0:
        if header.name[i] == b' ':
            header.name = b'\0'
        else:
            break


buffer_size = 1024 ** 2


def extract_nb0(file_name: str, extract_to: str) -> int:
    if extract_to:
        with open(f'{extract_to}/list', 'w'):
            ...
    with open(file_name, 'rb') as f:
        f.seek(0, SEEK_END)
        fsize = f.tell()
        f.seek(0, 0)
        size = read_dword(f)
        if size > (fsize / 64):
            print("ERROR invalid nb0 file")
            return 1
        print(f"File count: {size}")
        lastoffset = 0
        i = 0
        while i < size:
            nb = nb0_header_item()
            nb0_headers[i] = nb
            read_header(nb, f)
            f.seek(f.tell() - 1)
            if not len(f.read(1)) or nb.offset < lastoffset:
                print("ERROR invalid nb0 file")
                return -1
            print(f"offset = {nb.offset:08x} size = {nb.size:08x} name: '{nb.name}'\n")
            i += 1
        f.seek(64 * size + 4, SEEK_SET)
        print(f"fileops {f.tell()}")
        i = 0
        while i < size:
            nb = nb0_headers[i]
            nb.nb0_file_offset = f.tell()
            if extract_to:
                buf = f"{extract_to}/{nb.name}"
                print(f"extracting to {buf} ({nb.size} bytes)\n")
                with open(f'{extract_to}/list', 'a') as list_file:
                    list_file.write(f"{nb.name}\n")
                sz = nb.size
                while sz > 0:
                    f.seek(f.tell() - 1)
                    if not len(f.read(1)):
                        print("ERROR unexpected end of file")
                        return 1
                    toread = buffer_size if sz > buffer_size else sz
                    buffer = f.read(toread)
                    rd = len(buffer)
                    if rd <= 0:
                        return -1
                    sz -= rd
                    if extract_to:
                        with open(buf, 'wb') as out:
                            out.write(buffer)
            i += 1
    return 0
