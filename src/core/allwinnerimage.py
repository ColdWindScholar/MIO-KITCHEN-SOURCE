from ctypes import LittleEndianStructure, sizeof, memmove, string_at, addressof, byref, c_uint, c_ulonglong, c_char, \
    c_ushort, c_uint64, c_uint32, Union



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


magic = b"IMAGEWTY"
magic_len = 8
IMAGEWTY_VERSION = 0x100234
IMAGEWTY_FILEHDR_LEN = 1024

#Header
"""
		struct {
			uint32_t pid;			/* USB peripheral ID (from image.cfg) */
			uint32_t vid;			/* USB vendor ID (from image.cfg) */
			uint32_t hardware_id;		/* Hardware ID (from image.cfg) */
			uint32_t firmware_id;		/* Firmware ID (from image.cfg) */
			uint32_t val1;			/* */
			uint32_t val1024;		/* */
			uint32_t num_files;		/* Total number of files embedded */
			uint32_t val1024_2;		/* */
			uint32_t val0;			/* */
			uint32_t val0_2;		/* */
			uint32_t val0_3;		/* */
			uint32_t val0_4;		/* */
			/* 0x0050 */
		} v1;
		struct {
			uint32_t unknown;
			uint32_t pid;			/* USB peripheral ID (from image.cfg) */
			uint32_t vid;			/* USB vendor ID (from image.cfg) */
			uint32_t hardware_id;		/* Hardware ID (from image.cfg) */
			uint32_t firmware_id;		/* Firmware ID (from image.cfg) */
			uint32_t val1;			/* */
			uint32_t val1024;		/* */
			uint32_t num_files;		/* Total number of files embedded */
			uint32_t val1024_2;		/* */
			uint32_t val0;			/* */
			uint32_t val0_2;		/* */
			uint32_t val0_3;		/* */
			uint32_t val0_4;		/* */
			/* 0x0060 */
		} v3;
"""
class V1(BasicStruct):
    _fields_ = [
        ("pid", c_uint32),
        ("vid", c_uint32),
        ("hardware_id", c_uint32),
        ("firmware_id", c_uint32),
        ("val1", c_uint32),
        ("val1024", c_uint32),
        ("num_files", c_uint32),
        ("val1024_2", c_uint32),
        ("val0", c_uint32),
        ("val0_2", c_uint32),
        ("val0_3", c_uint32),
        ("val0_4", c_uint32)
    ]
class V3(BasicStruct):
    _fields_ = [
        ("unknown", c_uint32),
        ("pid", c_uint32),
        ("vid", c_uint32),
        ("hardware_id", c_uint32),
        ("firmware_id", c_uint32),
        ("val1", c_uint32),
        ("val1024", c_uint32),
        ("num_files", c_uint32),
        ("val1024_2", c_uint32),
        ("val0", c_uint32),
        ("val0_2", c_uint32),
        ("val0_3", c_uint32),
        ("val0_4", c_uint32)
    ]

class ImagewtyHeader(BasicStruct):
    _fields_ = [
        ("magic", c_char * magic_len),
        ("header_version", c_uint32),
        ("header_size", c_uint32),
        ("ram_base", c_uint32),
        ("version", c_uint32),
        ("image_size", c_uint32),
        ("image_header_size", c_uint32),
    ]

def main():
    with open(r"", 'rb') as f:
        h = ImagewtyHeader()
        data = f.read(len(h))
        h.unpack(data)
        flag_encryption_enabled = not h.magic == magic

        print(h.header_version, h.version)

main()