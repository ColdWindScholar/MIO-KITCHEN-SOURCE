from ctypes import LittleEndianStructure, sizeof, memmove, string_at, addressof, byref, c_uint, c_char, \
    c_uint64


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


MpkMagic = b'!MPK'
FileEntryMagic = b'!F'


class MpkHeader(BasicStruct):
    _pack_ = 1
    _fields_ = [
        ("magic", c_uint),
        ("version", c_uint),
        ("crc32", c_uint),
        ("identifier", c_char * 256),
        ("name", c_char * 256),
        ("support_system", c_char * 8),
        ("support_machine", c_char * 8),
        ("signature", c_char * 512),
        ("icon", c_uint64 * 128),
        ("desc", c_uint64 * 124),
        ("files_count", c_uint)
    ]


class FileEntryHeader(BasicStruct):
    _fields_ = [
        ("magic", c_char * 2),
        ("path", c_char * 490),
        ("compress", c_uint),
        ("offset", c_uint64),
        ("size", c_uint64),
    ]
print(len(FileEntryHeader()))