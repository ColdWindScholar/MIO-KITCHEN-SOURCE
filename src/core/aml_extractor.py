from io import SEEK_END
from socket import ntohl


def convert(test, loc: int):
    return ntohl((test[loc] << 24) | (test[loc + 1] << 16) | (test[loc + 2] << 8) | test[loc + 3])

def read_until_0(buffer, start):
    char = ''
    index = start
    while (data:=buffer[index]) != 0:
        char += chr(data)
        print(data)
        index += 1
    return char

def main(firmware, out_put):
    with open(firmware, 'rb') as fileptr:
        fileptr.seek(0, SEEK_END)
        filelen = fileptr.tell()
        fileptr.seek(0, 0)
        buffer = fileptr.read(filelen)
        record = 0
        while record < buffer[0x18] & 0xffffffff:
            record_loc = 0x40 + (record * 0x240)
            filename = f"{out_put}/{read_until_0(buffer,record_loc+0x120)}.{read_until_0(buffer,record_loc+0x20)}"
            file_loc = convert(buffer, record_loc + 0x10)
            file_size = convert(buffer, record_loc + 0x18)
            with open(filename, 'wb') as f:
                f.write(buffer[file_loc:file_loc + file_size])
            record += 1

if __name__ == '__main__':
    main("/home/xzz/下载/Telegram Desktop/X88Pro-s905x5m_D4_LGX6521_1000M_20250415_r3.img", "/media/xzz/47de93ec-4be1-4944-aadc-a97dcbdd9c4f/1")