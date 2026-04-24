import logging
import struct
import uuid

from partition_types import PartitionTypes

class PartitionTableEntry(object):
    def __init__(self, raw_entry):
        part_type_uuid, part_id_uuid, first_lba, last_lba, attribs, name = struct.unpack('<16s16sQQQ72s', raw_entry)

        self._type_uuid = uuid.UUID(bytes=part_type_uuid)
        self._id_uuid = uuid.UUID(bytes=part_id_uuid)
        self._first_lba = first_lba
        self._last_lba = last_lba

        self._name = name.decode('utf-16').rstrip('\0')
        try:
            self._part_type = PartitionTypes(self._type_uuid)
        except ValueError:
            self._part_type = self._type_uuid

    def __repr__(self):
        if self._part_type == PartitionTypes.Unused:
            return '<EmptyPartitionTableEntry>'
        else:
            return '<PartitionTableEntry("{}") {} LBA:[{} -> {}], Type: {}>'.format(self._name, self._id_uuid,
                    self._first_lba, self._last_lba, self._part_type)

    @property
    def is_unused(self):
        return self._part_type == PartitionTypes.Unused

    @property
    def partition_type(self):
        return self._part_type

    @property
    def partition_id(self):
        return self._id_uuid

    @property
    def first_block(self):
        return self._first_lba

    @property
    def last_block(self):
        return self._last_lba

    @property
    def length(self):
        return self._last_lba + 1 - self._first_lba

    @property
    def name(self):
        return self._name
