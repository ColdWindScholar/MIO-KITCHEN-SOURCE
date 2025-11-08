from ctypes import LittleEndianStructure, sizeof, memmove, string_at, addressof, byref, c_uint, c_ulonglong, c_char, \
    c_ushort, c_uint64


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


amlogic_magic = 0x27b51956


class VersionHeader(BasicStruct):
    _fields_ = [
        ("crc32", c_uint),
        ("version", c_uint),
    ]


class AmlHeader(BasicStruct):
    _pack_ = 1
    _fields_ = [
        ("crc32", c_uint),
        ("version", c_uint),
        # ---VersionHeader---
        ("magic", c_uint),
        ("imageSz", c_ulonglong),
        ("itemAlginSize", c_uint),
        ("itemNum", c_uint),
        ("reserve", c_char * 44),
    ]


class ItemInfo(BasicStruct):
    _pack_ = 1
    _fields_ = [
        ("itemId", c_uint),
        ("fileType", c_uint),
        ("curoffsetInItem", c_uint64),
        ("offsetInImage", c_uint64),
        ("itemMainType", c_char * 256),
        ("itemSubType", c_char * 256),
        ("verify", c_uint),
        ("isBackUpItem", c_ushort),
        ("backUpItemId", c_ushort),
        ("reserve", c_char * 32),
    ]


def generate_cfg(partitions_list: list, partitions_verify: list, output_file):
    partitions_normal = [i for i in partitions_list if i[1] not in partitions_verify]
    with open(output_file, "w", encoding='utf-8', newline='\n') as f:
        f.write('[LIST_NORMAL]\n')
        for i in partitions_normal:
            main_type, sub_type = i
            f.write(f'file="{sub_type}.{main_type}"		main_type="{main_type}"		sub_type="{sub_type}"\n')
        f.write('[LIST_VERIFY]\n')
        for i in partitions_list:
            if i[1] not in partitions_verify:
                continue
            main_type, sub_type = i
            f.write(f'file="{sub_type}.{main_type}"		main_type="{main_type}"		sub_type="{sub_type}"\n')


def main(filepath: str, output_path: str):
    partitions = []
    partitions_verify = []
    with open(filepath, "rb") as f:
        header = AmlHeader()
        print(d := f.read(len(header)))
        header.unpack(d)
        if header.magic != amlogic_magic:
            raise Exception("magic is not amlogic magic.")
        i = 0
        while i < header.itemNum:
            h2 = ItemInfo()
            h2.unpack(f.read(len(h2)))
            i += 1
            main_type = h2.itemMainType.decode()
            sub_type = h2.itemSubType.decode()
            if main_type == 'VERIFY':
                partitions_verify.append(sub_type)
                continue
            print(f"[{i}/{header.itemNum}] Extracting {sub_type}.{main_type}...")
            with open(output_path + f"/{sub_type}.{main_type}", "wb") as output_file:
                origin_position = f.tell()
                f.seek(h2.curoffsetInItem)
                output_file.write(f.read(h2.offsetInImage))
                f.seek(origin_position)
                partitions.append([main_type, sub_type])

    generate_cfg(partitions, partitions_verify, output_path + "/config/image.cfg")


if __name__ == "__main__":
    main(r"C:\Users\16612\Downloads\晶晨线刷解压工具\bin\111.img", r"C:\Users\16612\Downloads\晶晨线刷解压工具")
