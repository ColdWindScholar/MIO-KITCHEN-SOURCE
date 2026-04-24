import os
import logging

class GPTFile(object):
    """
    Simple wrapper to abstract accessing blocks of a file using LBA
    """
    def __init__(self, filename, blocksz=512):
        """
        Initialize a GPTFile wrapper for the given file, using the specified block size
        """
        self._blocksz = blocksz
        self._filename = filename
        self._nr_bytes = os.path.getsize(filename)

        if self._nr_bytes < blocksz:
            raise Exception('The image file is less than one block in size. Aborting.')

        self._total_blocks = self._nr_bytes // blocksz

        logging.debug('There are {} blocks in this file'.format(self._total_blocks))

        self._file = open(filename, 'rb')

        self._offset = 0

    def read_blocks(self, lba_start, nr_blocks=1):
        """
        Read a number of LBA-sized blocks from the file.

        If the starting LBA is negative, it's assumed you want last block + lba_start as
        the starting block
        """
        start_block = lba_start
        if start_block < 0:
            # Effectively, subtract this from the total blocks in the file
            start_block = self._total_blocks + lba_start

        if start_block < 0 or start_block > self._total_blocks:
            raise Exception('Requested block out of range (there are {} blocks, requested block {})'.format(self._total_blocks, lba_start))

        if start_block + nr_blocks > self._total_blocks:
            logging.debug("start-block {} requested-blocks {} total-blocks {}".format(start_block, nr_blocks, self._total_blocks))
            raise Exception('Total requested blocks out of range')

        if self._offset != start_block * self._blocksz:
            self._file.seek(start_block * self._blocksz)
            self._offset = start_block * self._blocksz

        data = self._file.read(nr_blocks * self._blocksz)

        self._offset += nr_blocks * self._blocksz

        return data

    def blocks_in_range(self, lba_start, nr_blocks):
        for i in range(0, nr_blocks):
            yield self.read_blocks(lba_start + i, 1)

    @property
    def sector_size(self):
        return self._blocksz
