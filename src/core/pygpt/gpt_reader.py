from gpt_file import GPTFile
from partition_table_header import PartitionTableHeader

import logging
import binascii

class GPTReader(object):
    def __init__(self, filename, sector_size=512, little_endian=True):
        self._filename = filename
        self._sector_size = sector_size
        self._file = GPTFile(filename, sector_size)
        self._pth = PartitionTableHeader(self._file, little_endian)

    @property
    def partition_table(self):
        return self._pth

    @property
    def block_reader(self):
        return self._file

def _setup_logging(verbose):
    """
    Set logging verbosity, 
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

def main():
    import argparse
    import os

    parser = argparse.ArgumentParser(description='Test reading a GPT file image')
    parser.add_argument('-v', '--verbose', help='verbose output', action='store_true')
    parser.add_argument('-S', '--sector-size', help='Sector size (in bytes) for LBA', type=int, default=512)
    parser.add_argument('-O', '--output-dir', help='Output directory to write each partition to', type=str, default='')
    parser.add_argument('-b', '--burst', help='Break the partitions out into individual files', action='store_true')
    parser.add_argument('image', help='The image to analyze the GPT from')
    args = parser.parse_args()

    _setup_logging(args.verbose)

    logging.debug('Reading from file {} with sector size {}'.format(args.image, args.sector_size))

    reader = GPTReader(args.image, sector_size=args.sector_size)

    if args.output_dir != '' and args.burst:
        os.makedirs(args.output_dir, 0o777, True)

    for partition in reader.partition_table.valid_entries():
        print('guid/type={} first-block={} size={} name={}'.format(
            partition.partition_type, partition.first_block, partition.length, partition.name))

        if args.burst:
            file_base_name = partition.name
            if '' == file_base_name:
                file_base_name = str(partition.partition_id)

            out_file = os.path.join(args.output_dir, '{}.bin'.format(partition.name))
            logging.debug('Writing partition to file {}'.format(out_file))

            with open(out_file, 'wb+') as fout:
                for block in reader.block_reader.blocks_in_range(partition.first_block, partition.length):
                    fout.write(block)

if __name__ == '__main__':
    main()

