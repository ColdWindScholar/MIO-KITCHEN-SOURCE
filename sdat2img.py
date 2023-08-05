#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ====================================================
#          FILE: sdat2img.py
#       AUTHORS: xpirt - luxi78 - howellzhu
#          DATE: 2018-10-27 10:33:21 CEST
# ====================================================

from __future__ import print_function

from os.path import realpath
from errno import EEXIST


def main(TRANSFER_LIST_FILE, NEW_DATA_FILE, OUTPUT_IMAGE_FILE):
    __version__ = '1.2'

    print('sdat2img binary - version: {}\n'.format(__version__))

    def rangeset(src):
        src_set = src.split(',')
        num_set = [int(item) for item in src_set]
        if len(num_set) != num_set[0] + 1:
            print('Error on parsing following data to rangeset:\n{}'.format(src))
            return

        return tuple([(num_set[i], num_set[i + 1]) for i in range(1, len(num_set), 2)])

    def parse_transfer_list_file(path):
        with open(TRANSFER_LIST_FILE, 'r') as trans_list:
            # First line in transfer list is the version number
            version = int(trans_list.readline())
            # Second line in transfer list is the total number of blocks we expect to write
            new_blocks = int(trans_list.readline())
            if version >= 2:
                # Third line is how many stash entries are needed simultaneously
                trans_list.readline()
                # Fourth line is the maximum number of blocks that will be stashed simultaneously
                trans_list.readline()
            # Subsequent lines are all individual transfer commands
            commands = []
            for line in trans_list:
                line = line.split(' ')
                cmd = line[0]
                if cmd in ['erase', 'new', 'zero']:
                    commands.append([cmd, rangeset(line[1])])
                else:
                    # Skip lines starting with numbers, they are not commands anyway
                    if not cmd[0].isdigit():
                        print('Command "{}" is not valid.'.format(cmd))
                        return
        return version, new_blocks, commands

    BLOCK_SIZE = 4096

    version, new_blocks, commands = parse_transfer_list_file(TRANSFER_LIST_FILE)

    if version == 1:
        print('Android Lollipop 5.0 detected!\n')
    elif version == 2:
        print('Android Lollipop 5.1 detected!\n')
    elif version == 3:
        print('Android Marshmallow 6.x detected!\n')
    elif version == 4:
        print('Android Nougat 7.x / Oreo 8.x detected!\n')
    else:
        print('Unknown Android version!\n')

    # Don't clobber existing files to avoid accidental data loss
    try:
        output_img = open(OUTPUT_IMAGE_FILE, 'wb')
    except IOError as e:
        if e.errno == EEXIST:
            print('Error: the output file "{}" already exists'.format(e.filename))
            print('Remove it, rename it, or choose a different file name.')
            return e.errno
        else:
            raise

    new_data_file = open(NEW_DATA_FILE, 'rb')
    all_block_sets = [i for command in commands for i in command[1]]
    max_file_size = max(pair[1] for pair in all_block_sets) * BLOCK_SIZE

    for command in commands:
        if command[0] == 'new':
            for block in command[1]:
                begin = block[0]
                end = block[1]
                block_count = end - begin
                print('Copying {} blocks into position {}...'.format(block_count, begin))

                # Position output file
                output_img.seek(begin * BLOCK_SIZE)

                # Copy one block at a time
                while block_count > 0:
                    output_img.write(new_data_file.read(BLOCK_SIZE))
                    block_count -= 1
        else:
            print('Skipping command {}...'.format(command[0]))

    # Make file larger if necessary
    if output_img.tell() < max_file_size:
        output_img.truncate(max_file_size)

    output_img.close()
    new_data_file.close()
    print('Done! Output image: {}'.format(realpath(output_img.name)))
