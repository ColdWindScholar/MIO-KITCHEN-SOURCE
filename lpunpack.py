import argparse
import copy
import enum
import io
import json
import os
import struct
import sys
from dataclasses import dataclass, field
from string import Template
from timeit import default_timer as dti
from typing import IO, Dict, List, TypeVar, cast, BinaryIO, Tuple

SPARSE_HEADER_MAGIC = 0xED26FF3A
SPARSE_HEADER_SIZE = 28
SPARSE_CHUNK_HEADER_SIZE = 12

LP_PARTITION_RESERVED_BYTES = 4096
LP_METADATA_GEOMETRY_MAGIC = 0x616c4467
LP_METADATA_GEOMETRY_SIZE = 4096
LP_METADATA_HEADER_MAGIC = 0x414C5030
LP_SECTOR_SIZE = 512

LP_TARGET_TYPE_LINEAR = 0
LP_TARGET_TYPE_ZERO = 1

LP_PARTITION_ATTR_READONLY = (1 << 0)
LP_PARTITION_ATTR_SLOT_SUFFIXED = (1 << 1)
LP_PARTITION_ATTR_UPDATED = (1 << 2)
LP_PARTITION_ATTR_DISABLED = (1 << 3)

LP_BLOCK_DEVICE_SLOT_SUFFIXED = (1 << 0)

LP_GROUP_SLOT_SUFFIXED = (1 << 0)

PLAIN_TEXT_TEMPLATE = """Slot 0:
Metadata version: $metadata_version
Metadata size: $metadata_size bytes
Metadata max size: $metadata_max_size bytes
Metadata slot count: $metadata_slot_count
Header flags: $header_flags
Partition table:
------------------------
$partitions
------------------------
Super partition layout:
------------------------
$layouts
------------------------
Block device table:
------------------------
$blocks
------------------------
Group table:
------------------------
$groups
"""


def build_attribute_string(attributes: int) -> str:
    if attributes & LP_PARTITION_ATTR_READONLY:
        result = "readonly"
    elif attributes & LP_PARTITION_ATTR_SLOT_SUFFIXED:
        result = "slot-suffixed"
    elif attributes & LP_PARTITION_ATTR_UPDATED:
        result = "updated"
    elif attributes & LP_PARTITION_ATTR_DISABLED:
        result = "disabled"
    else:
        result = "none"
    return result


def build_block_device_flag_string(flags: int) -> str:
    return "slot-suffixed" if (flags & LP_BLOCK_DEVICE_SLOT_SUFFIXED) else "none"


def build_group_flag_string(flags: int) -> str:
    return "slot-suffixed" if (flags & LP_GROUP_SLOT_SUFFIXED) else "none"


class FormatType(enum.Enum):
    TEXT = "text"
    JSON = "json"


class EnumAction(argparse.Action):
    """Argparse action for handling Enums"""

    def __init__(self, **kwargs):
        enum_type = kwargs.pop("type", None)
        if enum_type is None:
            raise ValueError("Type must be assigned an Enum when using EnumAction")

        if not issubclass(enum_type, enum.Enum):
            raise TypeError("Type must be an Enum when using EnumAction")

        kwargs.setdefault("choices", tuple(e.value for e in enum_type))

        super(EnumAction, self).__init__(**kwargs)
        self._enum = enum_type

    def __call__(self, parser, namespace, values, option_string=None):
        value = self._enum(values)
        setattr(namespace, self.dest, value)


class ShowJsonInfo(json.JSONEncoder):
    def __init__(self, ignore_keys: List[str], **kwargs):
        super().__init__(**kwargs)
        self._ignore_keys = ignore_keys

    def _remove_ignore_keys(self, data: Dict):
        _data = copy.deepcopy(data)
        for field_key, v in data.items():
            if field_key in self._ignore_keys:
                _data.pop(field_key)
                continue

            if v == 0:
                _data.pop(field_key)
                continue

            if isinstance(v, int) and not isinstance(v, bool):
                _data.update({field_key: str(v)})
        return _data

    def encode(self, data: Dict) -> str:
        result = {
            "partitions": list(map(self._remove_ignore_keys, data["partition_table"])),
            "groups": list(map(self._remove_ignore_keys, data["group_table"])),
            "block_devices": list(map(self._remove_ignore_keys, data["block_devices"]))
        }
        return super().encode(result)


class SparseHeader:
    def __init__(self, buffer):
        fmt = '<I4H4I'
        (
            self.magic,  # 0xed26ff3a
            self.major_version,  # (0x1) - reject images with higher major versions
            self.minor_version,  # (0x0) - allow images with higher minor versions
            self.file_hdr_sz,  # 28 bytes for first revision of the file format
            self.chunk_hdr_sz,  # 12 bytes for first revision of the file format
            self.blk_sz,  # block size in bytes, must be a multiple of 4 (4096)
            self.total_blks,  # total blocks in the non-sparse output image
            self.total_chunks,  # total chunks in the sparse input image
            self.image_checksum  # CRC32 checksum of the original data, counting "don't care"
        ) = struct.unpack(fmt, buffer[0:struct.calcsize(fmt)])


class SparseChunkHeader:
    """
        Following a Raw or Fill or CRC32 chunk is data.
        For a Raw chunk, it's the data in chunk_sz * blk_sz.
        For a Fill chunk, it's 4 bytes of the fill data.
        For a CRC32 chunk, it's 4 bytes of CRC32
     """

    def __init__(self, buffer):
        fmt = '<2H2I'
        (
            self.chunk_type,  # 0xCAC1 -> raw; 0xCAC2 -> fill; 0xCAC3 -> don't care */
            self.reserved,
            self.chunk_sz,  # in blocks in output image * /
            self.total_sz,  # in bytes of chunk input file including chunk header and data * /
        ) = struct.unpack(fmt, buffer[0:struct.calcsize(fmt)])


class LpMetadataBase:
    _fmt = None

    @classmethod
    @property
    def size(cls) -> int:
        return struct.calcsize(cls._fmt)


class LpMetadataGeometry(LpMetadataBase):
    """
    Offset 0: Magic signature

    Offset 4: Size of the `LpMetadataGeometry`

    Offset 8: SHA256 checksum

    Offset 40: Maximum amount of space a single copy of the metadata can use

    Offset 44: Number of copies of the metadata to keep

    Offset 48: Logical block size
    """

    _fmt = '<2I32s3I'

    def __init__(self, buffer):
        (
            self.magic,
            self.struct_size,
            self.checksum,
            self.metadata_max_size,
            self.metadata_slot_count,
            self.logical_block_size

        ) = struct.unpack(self._fmt, buffer[0:struct.calcsize(self._fmt)])
        # self.size


class LpMetadataTableDescriptor(LpMetadataBase):
    """
    Offset 0: Location of the table, relative to end of the metadata header.

    Offset 4: Number of entries in the table.

    Offset 8: Size of each entry in the table, in bytes.
    """

    _fmt = '<3I'

    def __init__(self, buffer):
        (
            self.offset,
            self.num_entries,
            self.entry_size

        ) = struct.unpack(self._fmt, buffer[:struct.calcsize(self._fmt)])


class LpMetadataPartition(LpMetadataBase):
    """
    Offset 0: Name of this partition in ASCII characters. Any unused characters in
              the buffer must be set to 0. Characters may only be alphanumeric or _.
              The name must include at least one ASCII character, and it must be unique
              across all partition names. The length (36) is the same as the maximum
              length of a GPT partition name.

    Offset 36: Attributes for the partition (see LP_PARTITION_ATTR_* flags above).

    Offset 40: Index of the first extent owned by this partition. The extent will
               start at logical sector 0. Gaps between extents are not allowed.

    Offset 44: Number of extents in the partition. Every partition must have at least one extent.

    Offset 48: Group this partition belongs to.
    """

    _fmt = '<36s4I'

    def __init__(self, buffer):
        (
            self.name,
            self.attributes,
            self.first_extent_index,
            self.num_extents,
            self.group_index

        ) = struct.unpack(self._fmt, buffer[0:struct.calcsize(self._fmt)])

        self.name = self.name.decode("utf-8").strip('\x00')

    @property
    def filename(self) -> str:
        return f'{self.name}.img'


class LpMetadataExtent(LpMetadataBase):
    """
    Offset 0: Length of this extent, in 512-byte sectors.

    Offset 8: Target type for device-mapper (see LP_TARGET_TYPE_* values).

    Offset 12: Contents depends on target_type. LINEAR: The sector on the physical partition that this extent maps onto.
               ZERO: This field must be 0.

    Offset 20: Contents depends on target_type. LINEAR: Must be an index into the block devices table.
    """

    _fmt = '<QIQI'

    def __init__(self, buffer):
        (
            self.num_sectors,
            self.target_type,
            self.target_data,
            self.target_source

        ) = struct.unpack(self._fmt, buffer[0:struct.calcsize(self._fmt)])


class LpMetadataHeader(LpMetadataBase):
    """
    +-----------------------------------------+
    | Header data - fixed size                |
    +-----------------------------------------+
    | Partition table - variable size         |
    +-----------------------------------------+
    | Partition table extents - variable size |
    +-----------------------------------------+

    Offset 0: Four bytes equal to `LP_METADATA_HEADER_MAGIC`

    Offset 4: Version number required to read this metadata. If the version is not
              equal to the library version, the metadata should be considered incompatible.

    Offset 6: Minor version. A library supporting newer features should be able to
              read metadata with an older minor version. However, an older library
              should not support reading metadata if its minor version is higher.

    Offset 8: The size of this header struct.

    Offset 12: SHA256 checksum of the header, up to |header_size| bytes, computed as if this field were set to 0.

    Offset 44: The total size of all tables. This size is contiguous; tables may not
               have gaps in between, and they immediately follow the header.

    Offset 48: SHA256 checksum of all table contents.

    Offset 80: Partition table descriptor.

    Offset 92: Extent table descriptor.

    Offset 104: Updateable group descriptor.

    Offset 116: Block device table.

    Offset 128: Header flags are independent of the version number and intended to be informational only.
                New flags can be added without bumping the version.

    Offset 132: Reserved (zero), pad to 256 bytes.
    """

    _fmt = '<I2hI32sI32s'

    partitions: LpMetadataTableDescriptor = field(default=None)
    extents: LpMetadataTableDescriptor = field(default=None)
    groups: LpMetadataTableDescriptor = field(default=None)
    block_devices: LpMetadataTableDescriptor = field(default=None)

    def __init__(self, buffer):
        (
            self.magic,
            self.major_version,
            self.minor_version,
            self.header_size,
            self.header_checksum,
            self.tables_size,
            self.tables_checksum

        ) = struct.unpack(self._fmt, buffer[0:struct.calcsize(self._fmt)])
        self.flags = 0
        # self.size


class LpMetadataPartitionGroup(LpMetadataBase):
    """
    Offset 0: Name of this group. Any unused characters must be 0.

    Offset 36: Flags (see LP_GROUP_*).

    Offset 40: Maximum size in bytes. If 0, the group has no maximum size.
    """
    _fmt = '<36sIQ'

    def __init__(self, buffer):
        (
            self.name,
            self.flags,
            self.maximum_size
        ) = struct.unpack(self._fmt, buffer[0:struct.calcsize(self._fmt)])

        self.name = self.name.decode("utf-8").strip('\x00')


class LpMetadataBlockDevice(LpMetadataBase):
    """
    Offset 0: First usable sector for allocating logical partitions. this will be
              the first sector after the initial geometry blocks, followed by the
              space consumed by metadata_max_size*metadata_slot_count*2.

    Offset 8: Alignment for defining partitions or partition extents. For example,
              an alignment of 1MiB will require that all partitions have a size evenly
              divisible by 1MiB, and that the smallest unit the partition can grow by is 1MiB.

              Alignment is normally determined at runtime when growing or adding
              partitions. If for some reason the alignment cannot be determined, then
              this predefined alignment in the geometry is used instead. By default, it is set to 1MiB.

    Offset 12: Alignment offset for "stacked" devices. For example, if the "super"
               partition itself is not aligned within the parent block device's
               partition table, then we adjust for this in deciding where to place
               |first_logical_sector|.

               Similar to |alignment|, this will be derived from the operating system.
               If it cannot be determined, it is assumed to be 0.

    Offset 16: Block device size, as specified when the metadata was created.
               This can be used to verify the geometry against a target device.

    Offset 24: Partition name in the GPT. Any unused characters must be 0.

    Offset 60: Flags (see LP_BLOCK_DEVICE_* flags below).
    """

    _fmt = '<Q2IQ36sI'

    def __init__(self, buffer):
        (
            self.first_logical_sector,
            self.alignment,
            self.alignment_offset,
            self.block_device_size,
            self.partition_name,
            self.flags
        ) = struct.unpack(self._fmt, buffer[0:struct.calcsize(self._fmt)])

        self.partition_name = self.partition_name.decode("utf-8").strip('\x00')


@dataclass
class Metadata:
    header: LpMetadataHeader = field(default=None)
    geometry: LpMetadataGeometry = field(default=None)
    partitions: List[LpMetadataPartition] = field(default_factory=list)
    extents: List[LpMetadataExtent] = field(default_factory=list)
    groups: List[LpMetadataPartitionGroup] = field(default_factory=list)
    block_devices: List[LpMetadataBlockDevice] = field(default_factory=list)

    @property
    def info(self) -> Dict:
        return self._get_info()

    @property
    def metadata_region(self) -> int:
        if self.geometry is None:
            return 0

        return LP_PARTITION_RESERVED_BYTES + (
                LP_METADATA_GEOMETRY_SIZE + self.geometry.metadata_max_size * self.geometry.metadata_slot_count
        ) * 2

    def _get_extents_string(self, partition: LpMetadataPartition) -> List[str]:
        result = []
        first_sector = 0
        for extent_number in range(partition.num_extents):
            index = partition.first_extent_index + extent_number
            extent = self.extents[index]

            _base = f"{first_sector} .. {first_sector + extent.num_sectors - 1}"
            first_sector += extent.num_sectors

            if extent.target_type == LP_TARGET_TYPE_LINEAR:
                result.append(
                    f"{_base} linear {self.block_devices[extent.target_source].partition_name} {extent.target_data}"
                )
            elif extent.target_type == LP_TARGET_TYPE_ZERO:
                result.append(f"{_base} zero")

        return result

    def _get_partition_layout(self) -> List[str]:
        result = []

        for partition in self.partitions:
            for extent_number in range(partition.num_extents):
                index = partition.first_extent_index + extent_number
                extent = self.extents[index]

                block_device_name = ""

                if extent.target_type == LP_TARGET_TYPE_LINEAR:
                    block_device_name = self.block_devices[extent.target_source].partition_name

                result.append(
                    f"{block_device_name}: {extent.target_data} .. {extent.target_data + extent.num_sectors}: "
                    f"{partition.name} ({extent.num_sectors} sectors)"
                )

        return result

    def get_offsets(self, slot_number: int = 0) -> List[int]:
        base = LP_PARTITION_RESERVED_BYTES + (LP_METADATA_GEOMETRY_SIZE * 2)
        _tmp_offset = self.geometry.metadata_max_size * slot_number
        primary_offset = base + _tmp_offset
        backup_offset = base + self.geometry.metadata_max_size * self.geometry.metadata_slot_count + _tmp_offset
        return [primary_offset, backup_offset]

    def _get_info(self) -> Dict:
        # TODO 25.01.2023: Liblp version 1.2 build_header_flag_string check header version 1.2
        result = {}
        try:
            result = {
                "metadata_version": f"{self.header.major_version}.{self.header.minor_version}",
                "metadata_size": self.header.header_size + self.header.tables_size,
                "metadata_max_size": self.geometry.metadata_max_size,
                "metadata_slot_count": self.geometry.metadata_slot_count,
                "header_flags": "none",
                "block_devices": [
                    {
                        "name": item.partition_name,
                        "first_sector": item.first_logical_sector,
                        "size": item.block_device_size,
                        "block_size": self.geometry.logical_block_size,
                        "flags": build_block_device_flag_string(item.flags),
                        "alignment": item.alignment,
                        "alignment_offset": item.alignment_offset
                    } for item in self.block_devices
                ],
                "group_table": [
                    {
                        "name": self.groups[index].name,
                        "maximum_size": self.groups[index].maximum_size,
                        "flags": build_group_flag_string(self.groups[index].flags)
                    } for index in range(0, self.header.groups.num_entries)
                ],
                "partition_table": [
                    {
                        "name": item.name,
                        "group_name": self.groups[item.group_index].name,
                        "is_dynamic": True,
                        "size": self.extents[item.first_extent_index].num_sectors * LP_SECTOR_SIZE,
                        "attributes": build_attribute_string(item.attributes),
                        "extents": self._get_extents_string(item)
                    } for item in self.partitions
                ],
                "partition_layout": self._get_partition_layout()
            }
        except Exception:
            ...
        finally:
            return result

    @property
    def get_info2(self):
        parts = {}
        for item in self.partitions:
            parts[self.groups[item.group_index].name] = parts[self.groups[item.group_index].name] + item.name
        return parts

    def to_json(self) -> str:
        data = self._get_info()
        if not data:
            return ""

        return json.dumps(
            data,
            indent=1,
            cls=ShowJsonInfo,
            ignore_keys=[
                'metadata_version', 'metadata_size', 'metadata_max_size', 'metadata_slot_count', 'header_flags',
                'partition_layout',
                'attributes', 'extents', 'flags', 'first_sector'
            ])

    def __str__(self):
        data = self._get_info()
        if not data:
            return ""

        template = Template(PLAIN_TEXT_TEMPLATE)
        layouts = "\n".join(data["partition_layout"])
        partitions = "------------------------\n".join(
            [
                "  Name: {}\n  Group: {}\n  Attributes: {}\n  Extents:\n    {}\n".format(item["name"],
                                                                                         item["group_name"],
                                                                                         item["attributes"],
                                                                                         "\n".join(item["extents"])) for
                item in data["partition_table"]
            ]
        )[:-1]
        blocks = "\n".join(
            [
                f"  Partition name: {item['name']}\n  First sector: {item['first_sector']}\n  Size: {item['size']} bytes\n  Flags: {item['flags']}"
                for item in data["block_devices"]
            ]
        )
        groups = "------------------------\n".join(
            [
                f"  Name: {item['name']}\n  Maximum size: {item['maximum_size']} bytes\n  Flags: {item['flags']}\n" for
                item in data["group_table"]
            ]
        )[:-1]
        return template.substitute(partitions=partitions, layouts=layouts, blocks=blocks, groups=groups, **data)


class LpUnpackError(Exception):
    """Raised any error unpacking"""

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


@dataclass
class UnpackJob:
    name: str
    geometry: LpMetadataGeometry
    parts: List[Tuple[int, int]] = field(default_factory=list)
    total_size: int = field(default=0)


class SparseImage:
    def __init__(self, fd):
        self._fd = fd
        self.header = None

    def check(self):
        self._fd.seek(0)
        self.header = SparseHeader(self._fd.read(SPARSE_HEADER_SIZE))
        return False if self.header.magic != SPARSE_HEADER_MAGIC else True

    def _read_data(self, chunk_data_size: int):
        if self.header.chunk_hdr_sz > SPARSE_CHUNK_HEADER_SIZE:
            self._fd.seek(self.header.chunk_hdr_sz - SPARSE_CHUNK_HEADER_SIZE, 1)

        return self._fd.read(chunk_data_size)

    def unsparse(self):
        if not self.header:
            self._fd.seek(0)
            self.header = SparseHeader(self._fd.read(SPARSE_HEADER_SIZE))
        chunks = self.header.total_chunks
        self._fd.seek(self.header.file_hdr_sz - SPARSE_HEADER_SIZE, 1)
        unsparse_file_dir = os.path.dirname(self._fd.name)
        unsparse_file = os.path.join(unsparse_file_dir,
                                     "{}.unsparse.img".format(os.path.splitext(os.path.basename(self._fd.name))[0]))
        with open(str(unsparse_file), 'wb') as out:
            sector_base = 82528
            output_len = 0
            while chunks > 0:
                chunk_header = SparseChunkHeader(self._fd.read(SPARSE_CHUNK_HEADER_SIZE))
                sector_size = (chunk_header.chunk_sz * self.header.blk_sz) >> 9
                chunk_data_size = chunk_header.total_sz - self.header.chunk_hdr_sz
                if chunk_header.chunk_type == 0xCAC1:
                    data = self._read_data(chunk_data_size)
                    len_data = len(data)
                    if len_data == (sector_size << 9):
                        out.write(data)
                        output_len += len_data
                        sector_base += sector_size
                elif chunk_header.chunk_type == 0xCAC2:
                    data = self._read_data(chunk_data_size)
                    len_data = sector_size << 9
                    out.truncate(out.tell() + len_data)
                    out.seek(0, 2)
                    output_len += len(data)
                    sector_base += sector_size
                elif chunk_header.chunk_type == 0xCAC3:
                    data = self._read_data(chunk_data_size)
                    len_data = sector_size << 9
                    out.truncate(out.tell() + len_data)
                    out.seek(0, 2)
                    output_len += len(data)
                    sector_base += sector_size
                else:
                    len_data = sector_size << 9
                    out.truncate(out.tell() + len_data)
                    out.seek(0, 2)
                    sector_base += sector_size
                chunks -= 1
        return unsparse_file


T = TypeVar('T')


class LpUnpack:
    def __init__(self, **kwargs):
        self._partition_name = kwargs.get('NAME')
        self._show_info = kwargs.get('SHOW_INFO', True)
        self._show_info_format = kwargs.get('SHOW_INFO_FORMAT', FormatType.TEXT)
        self._config = kwargs.get('CONFIG', None)
        self._slot_num = None
        self._fd: BinaryIO = open(kwargs.get('SUPER_IMAGE'), 'rb')
        self._out_dir = kwargs.get('OUTPUT_DIR', None)

    def _check_out_dir_exists(self):
        if self._out_dir is None:
            return

        if not os.path.exists(self._out_dir):
            os.makedirs(self._out_dir, exist_ok=True)

    def _extract_partition(self, unpack_job: UnpackJob):
        self._check_out_dir_exists()
        start = dti()
        print(f'Extracting partition [{unpack_job.name}]')
        out_file = os.path.join(self._out_dir, f'{unpack_job.name}.img')
        with open(str(out_file), 'wb') as out:
            for part in unpack_job.parts:
                offset, size = part
                self._write_extent_to_file(out, offset, size, unpack_job.geometry.logical_block_size)

        print(f'Done:[{dti() - start}]')

    def _extract(self, partition, metadata):
        unpack_job = UnpackJob(name=partition.name, geometry=metadata.geometry)

        if partition.num_extents != 0:
            for extent_number in range(partition.num_extents):
                index = partition.first_extent_index + extent_number
                extent = metadata.extents[index]

                if extent.target_type != LP_TARGET_TYPE_LINEAR:
                    raise LpUnpackError(f'Unsupported target type in extent: {extent.target_type}')

                offset = extent.target_data * LP_SECTOR_SIZE
                size = extent.num_sectors * LP_SECTOR_SIZE
                unpack_job.parts.append((offset, size))
                unpack_job.total_size += size

        self._extract_partition(unpack_job)

    def _get_data(self, count: int, size: int, clazz: T) -> List[T]:
        result = []
        while count > 0:
            result.append(clazz(self._fd.read(size)))
            count -= 1
        return result

    def _read_chunk(self, block_size):
        while True:
            data = self._fd.read(block_size)
            if not data:
                break
            yield data

    def _read_metadata_header(self, metadata: Metadata):
        offsets = metadata.get_offsets()
        for index, offset in enumerate(offsets):
            self._fd.seek(offset, io.SEEK_SET)
            header = LpMetadataHeader(self._fd.read(80))
            header.partitions = LpMetadataTableDescriptor(self._fd.read(12))
            header.extents = LpMetadataTableDescriptor(self._fd.read(12))
            header.groups = LpMetadataTableDescriptor(self._fd.read(12))
            header.block_devices = LpMetadataTableDescriptor(self._fd.read(12))

            if header.magic != LP_METADATA_HEADER_MAGIC:
                check_index = index + 1
                if check_index > len(offsets):
                    raise LpUnpackError('Logical partition metadata has invalid magic value.')
                else:
                    print(f'Read Backup header by offset 0x{offsets[check_index]:x}')
                    continue

            metadata.header = header
            self._fd.seek(offset + header.header_size, io.SEEK_SET)

    def _read_metadata(self):
        self._fd.seek(LP_PARTITION_RESERVED_BYTES, io.SEEK_SET)
        metadata = Metadata(geometry=self._read_primary_geometry())

        if metadata.geometry.magic != LP_METADATA_GEOMETRY_MAGIC:
            raise LpUnpackError('Logical partition metadata has invalid geometry magic signature.')

        if metadata.geometry.metadata_slot_count == 0:
            raise LpUnpackError('Logical partition metadata has invalid slot count.')

        if metadata.geometry.metadata_max_size % LP_SECTOR_SIZE != 0:
            raise LpUnpackError('Metadata max size is not sector-aligned.')

        self._read_metadata_header(metadata)

        metadata.partitions = self._get_data(
            metadata.header.partitions.num_entries,
            metadata.header.partitions.entry_size,
            LpMetadataPartition
        )

        metadata.extents = self._get_data(
            metadata.header.extents.num_entries,
            metadata.header.extents.entry_size,
            LpMetadataExtent
        )

        metadata.groups = self._get_data(
            metadata.header.groups.num_entries,
            metadata.header.groups.entry_size,
            LpMetadataPartitionGroup
        )

        metadata.block_devices = self._get_data(
            metadata.header.block_devices.num_entries,
            metadata.header.block_devices.entry_size,
            LpMetadataBlockDevice
        )

        try:
            super_device: LpMetadataBlockDevice = cast(LpMetadataBlockDevice, iter(metadata.block_devices).__next__())
            if metadata.metadata_region > super_device.first_logical_sector * LP_SECTOR_SIZE:
                raise LpUnpackError('Logical partition metadata overlaps with logical partition contents.')
        except StopIteration:
            raise LpUnpackError('Metadata does not specify a super device.')

        return metadata

    def _read_primary_geometry(self) -> LpMetadataGeometry:
        geometry = LpMetadataGeometry(self._fd.read(LP_METADATA_GEOMETRY_SIZE))
        if geometry is not None:
            return geometry
        else:
            return LpMetadataGeometry(self._fd.read(LP_METADATA_GEOMETRY_SIZE))

    def _write_extent_to_file(self, fd: IO, offset: int, size: int, block_size: int):
        self._fd.seek(offset)
        for block in self._read_chunk(block_size):
            if size == 0:
                break

            fd.write(block)

            size -= block_size

    def get_info(self):
        try:
            if SparseImage(self._fd).check():
                print('Sparse image detected.')
                print('Process conversion to non sparse image...')
                unsparse_file = SparseImage(self._fd).unsparse()
                self._fd.close()
                self._fd = open(str(unsparse_file), 'rb')
                print('Result:[ok]')

            self._fd.seek(0)
            metadata = self._read_metadata()

            filter_partition = []
            for index, partition in enumerate(metadata.partitions):
                filter_partition.append(partition.name)

            if not filter_partition:
                raise LpUnpackError(f'Could not find partition: {self._partition_name}')

            return filter_partition

        except LpUnpackError as e:
            print(e.message)
            sys.exit(1)

        finally:
            self._fd.close()

    def unpack(self):
        try:
            if SparseImage(self._fd).check():
                print('Sparse image detected.')
                print('Process conversion to non sparse image...')
                unsparse_file = SparseImage(self._fd).unsparse()
                self._fd.close()
                self._fd = open(str(unsparse_file), 'rb')
                print('Result:[ok]')

            self._fd.seek(0)
            metadata = self._read_metadata()

            if self._partition_name:
                filter_partition = []
                for index, partition in enumerate(metadata.partitions):
                    if partition.name in self._partition_name:
                        filter_partition.append(partition)

                if not filter_partition:
                    raise LpUnpackError(f'Could not find partition: {self._partition_name}')

                metadata.partitions = filter_partition

            if self._slot_num:
                if self._slot_num > metadata.geometry.metadata_slot_count:
                    raise LpUnpackError(f'Invalid metadata slot number: {self._slot_num}')

            if self._show_info:
                if self._show_info_format == FormatType.TEXT:
                    print(metadata)
                elif self._show_info_format == FormatType.JSON:
                    print(f"{metadata.to_json()}\n")

            if not self._show_info and self._out_dir is None:
                raise LpUnpackError(message='Not specified directory for extraction')

            if self._out_dir:
                for partition in metadata.partitions:
                    self._extract(partition, metadata)

        except LpUnpackError as e:
            print(e.message)
            sys.exit(1)

        finally:
            self._fd.close()


def unpack(file: str, out: str, parts: list = None):
    namespace = argparse.Namespace(SUPER_IMAGE=file, OUTPUT_DIR=out, SHOW_INFO=False, NAME=parts)
    if not os.path.exists(namespace.SUPER_IMAGE):
        raise FileNotFoundError("%s Cannot Find" % namespace.SUPER_IMAGE)
    else:
        LpUnpack(**vars(namespace)).unpack()


def get_parts(file_):
    namespace = argparse.Namespace(SUPER_IMAGE=file_, SHOW_INFO=False)
    if not os.path.exists(namespace.SUPER_IMAGE):
        raise FileNotFoundError("%s Cannot Find" % namespace.SUPER_IMAGE)
    else:
        return LpUnpack(**vars(namespace)).get_info()
