import logging
import math
import struct
import uuid
import zlib

from partition_table_entry import PartitionTableEntry

PARTITION_TABLE_HEADER_DEFAULT_BLOCK = 1
PARTITION_TABLE_HEADER_BACKUP_BLOCK = -1

PARTITION_TABLE_DEFAULT_LENGTH = 92

PARTITION_TABLE_DEFAULT_PARTITION_ENTRY_SIZE = 128

class PartitionTableHeader(object):
    """
    Class that represents a partition table header and the associated partition entry array
    """
    def __init__(self, gptfile, little_endian=True):
        """
        Initialize a new partition table header, loading the file from disk
        """
        if not little_endian:
            raise Exception('Big endian GPT is not supported, yet')

        self._gptfile = gptfile
        self._backup_pth = False
        self._partitions = []
        self._load_pth()

    def valid_entries(self):
        for partition in self._partitions:
            if partition.is_unused:
                continue
            yield partition

    def _append_partition_entry(self, raw_entry):
        new_partition = PartitionTableEntry(raw_entry)
        logging.debug('Part: {}'.format(new_partition))
        self._partitions.append(new_partition)

    def _parse_pth(self, pth_raw):
        magic, revision, hdr_sz, hdr_crc32 = struct.unpack('<8sLLL', pth_raw[0:20])
        logging.debug('Magic: {} revision: {} length: 0x{} bytes, crc32: {:08x}'.format(magic, revision, hdr_sz, hdr_crc32))

        if magic != b'EFI PART':
            logging.debug('This is not an EFI partition, aborting')
            return False

        if hdr_sz != PARTITION_TABLE_DEFAULT_LENGTH:
            logging.warning('EFI partition is {} bytes long, normally expecting {}, proceed with caution'.format(hdr_sz, PARTITION_TABLE_DEFAULT_LENGTH))

        # Check the CRC32 of the header, first zeroing out the crc32 value
        raw_hdr = bytearray(pth_raw[0:hdr_sz])
        raw_hdr[16] = 0
        raw_hdr[17] = 0
        raw_hdr[18] = 0
        raw_hdr[19] = 0

        hdr_crc32_calc = zlib.crc32(raw_hdr)

        if hdr_crc32_calc != hdr_crc32:
            logging.debug('Header CRC calculation mismatch, skipping this header')
            return False

        # Get the current LBA as a sanity check
        current_lba, backup_lba, first_lba, last_lba, uuid_raw, partition_start, self._nr_part_entries, self._part_entry_sz, part_entries_crc = struct.unpack('<QQQQ16sQLLL', raw_hdr[24:])
        self._disk_uuid = uuid.UUID(bytes=uuid_raw)
        logging.debug('Current: {} Backup: {} First Usable: {} Last Usable: {} UUID: {}'.format(
            current_lba, backup_lba, first_lba, last_lba, self._disk_uuid))
        logging.debug('  Partition LBA Start: {} Number of Entries: {} Size of an entry: {} crc32 of entries {:08x}'.format(
            partition_start, self._nr_part_entries, self._part_entry_sz, part_entries_crc))

        if self._part_entry_sz != PARTITION_TABLE_DEFAULT_PARTITION_ENTRY_SIZE:
            logging.debug('Unsupported partition entry size: {}'.format(self._part_entry_sz))
            return False

        # Now we're ready to load the partition entries
        nr_blocks = math.ceil((self._nr_part_entries * self._part_entry_sz)/self._gptfile.sector_size)
        raw_partition_data = self._gptfile.read_blocks(partition_start, nr_blocks)

        part_entries_crc_calc = zlib.crc32(raw_partition_data)

        if part_entries_crc_calc != part_entries_crc:
            logging.debug('Error: partition table CRC calculation failed, aborting.')

        raw_entries = [raw_partition_data[i:i + self._part_entry_sz] for i in range(0, len(raw_partition_data), self._part_entry_sz)]

        for entry in raw_entries:
            self._append_partition_entry(entry)

        return True

    def _find_load_pth(self):
        # Start with the main PTH
        pth_raw = self._gptfile.read_blocks(PARTITION_TABLE_HEADER_DEFAULT_BLOCK, 1)

        if self._parse_pth(pth_raw):
            return

        # Try the backup PTH
        pth_raw = self._gptfile.read_blocks(PARTITION_TABLE_HEADER_BACKUP_BLOCK, 1)

        if self._parse_pth(pth_raw):
            self._backup_pth = True
            return

        raise Exception('Could not find a GPT in the given file, aborting.')

    def _load_pth(self):
        """
        Load a partition table from the currently mapped GPTFile
        """
        self._find_load_pth()

