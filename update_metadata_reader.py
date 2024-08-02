import blackboxprotobuf
import enum
from json import loads


class Type(enum.EnumType):
    REPLACE = 0
    REPLACE_BZ = 1
    MOVE = 2
    BSDIFF = 3
    SOURCE_COPY = 4
    SOURCE_BSDIFF = 5
    REPLACE_XZ = 8
    ZERO = 6
    DISCARD = 7
    BROTLI_BSDIFF = 10
    PUFFDIFF = 9
    ZUCCHINI = 11
    LZ4DIFF_BSDIFF = 12
    LZ4DIFF_PUFFDIFF = 13
    REPLACE_ZSTD = 14


class Metadata:
    def __init__(self, data):
        json_data: dict = loads(blackboxprotobuf.protobuf_to_json(data)[0])
        self.block_size = int(json_data.get('3', 4096))
        self.partitions = json_data.get('13', [])
