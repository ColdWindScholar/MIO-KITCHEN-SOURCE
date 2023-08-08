#!/usr/bin/env python
# sefcontext_parser.py
# Copyright 2017 Jake Valletta (@jake_valletta)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Parser for "file_contexts.bin" for Nougat+ devices"""

from __future__ import absolute_import, print_function

import operator
import os.path
import struct

SELINUX_MAGIC_COMPILED_FCONTEXT = 0xf97cff8a

F_MODE = {0x1000: '-p',  # S_IFFIFO
          0x2000: '-c',  # S_IFCHR
          0x4000: '-d',  # S_IFDIR
          0x6000: '-b',  # S_IFBLK
          0x8000: '--',  # S_IFREG
          0xa000: '-l',  # S_IFLNK
          0xc000: '-s'}  # S_IFSOCK

NULL_MODE = 0x0000


class Entry(object):
    """Class representation of an entry"""

    regex = ""
    context = ""
    mode_bits = NULL_MODE
    mode = ""

    def __init__(self, regex, context, mode_bits):

        """Initialize blank entry"""

        self.regex = regex
        self.context = context
        self.mode_bits = mode_bits

        if mode_bits == NULL_MODE:
            self.mode = ""
        else:
            self.mode = self.convert_binary_mode(mode_bits)

    def __str__(self):

        """Prepare string formatted"""

        return "{}\t{}".format(self.regex,
                               self.context)

    @classmethod
    def convert_binary_mode(cls, mode_bits):

        """Convert binary mode bits to F_MODE"""

        return F_MODE[mode_bits]


class SefContextParser(object):
    """Parser class"""

    debugging = False
    file_contexts_file = None

    def __init__(self, file_name, debugging=False):

        """Open file and validate"""

        self.file_contexts_file = open(file_name, "rb")
        self.debugging = debugging

    def debug(self, msg):

        """Print a message if in debug mode"""

        if self.debugging:
            print(msg)

    def get_offset(self):

        """Get the offset into the binary file"""

        return self.file_contexts_file.tell()

    def __read_u32(self):

        """Read 4 bytes as unsigned int"""

        return struct.unpack('I', self.file_contexts_file.read(4))[0]

    def __read_s32(self):

        """Read 4 bytes as signed int"""

        return struct.unpack('i', self.file_contexts_file.read(4))[0]

    def __read_string(self, length):

        """Read string of length n (no null terminator)"""

        return struct.unpack("%is" % length,
                             self.file_contexts_file.read(length))[0]

    def __read_nstring(self, length):

        """Read a null terminated string"""

        return self.__read_string(length + 1)[:-1]

    def process_file(self):

        """Validate and process our file"""

        entries = list()

        magic = self.__read_u32()
        self.debug("Magic: 0x%x" % magic)

        if magic != SELINUX_MAGIC_COMPILED_FCONTEXT:
            raise TypeError("Invalid Magic")

        version = self.__read_u32()
        self.debug("Version: %d" % version)

        len_of_pcre = self.__read_u32()

        pcre_version = self.__read_string(len_of_pcre)
        self.debug("PCRE Version: %s" % pcre_version.decode('UTF-8'))

        # Version 5 adds arch
        if version > 4:
            len_of_arch = self.__read_u32()
            regex_arch = self.__read_string(len_of_arch)
            self.debug("PCRE Regex Arch: %s" % regex_arch.decode('UTF-8'))

        num_of_stems = self.__read_u32()

        cur_stem = 0
        while cur_stem < num_of_stems:
            length_of_stem = self.__read_u32()
            stem_name = self.__read_nstring(length_of_stem)

            cur_stem += 1

        num_regexes = self.__read_u32()

        cur_regex = 0
        while cur_regex < num_regexes:

            # Grab the context
            context_len = self.__read_u32()
            raw_context = self.__read_string(context_len)[:-1].decode('UTF-8')

            # Get the regex string
            regex_str_len = self.__read_u32()
            org_regex_string = self.__read_string(
                regex_str_len)[:-1].decode('UTF-8')

            self.debug("Processing: %s" % org_regex_string)

            # Parse the mode bits
            mode_bits = self.__read_u32()

            # The rest really doesn't matter.
            stem_id = self.__read_s32()
            has_meta_characters = self.__read_u32()
            prefix_len = self.__read_u32()

            # Version <=4 is slightly different
            if version <= 4:
                data_len = self.__read_u32()
                raw_pcre = self.__read_string(data_len)

                study_data_len = self.__read_u32()
                study_data = self.__read_string(study_data_len)

            # Version 5+
            else:
                pattern_len = self.__read_u32()
                pattern = self.__read_string(pattern_len)

            entry = Entry(org_regex_string, raw_context, mode_bits)
            entries.append(entry)

            # Process next entry
            cur_regex += 1

        return sorted(entries, key=operator.attrgetter('regex'))


def main(input_f, outfile, debug=False):
    """Main loop"""

    # Does the file even exist?
    if not os.path.isfile(input_f):
        print("Error: input file '%s' doesn't exist!"
              % input_f)
        return 1

    sef_parser = SefContextParser(input_f,
                                  debugging=debug)

    out_file = open(outfile, "w")

    entries = sef_parser.process_file()

    print("Writing %d entries to '%s'..." % (len(entries), out_file.name))

    for entry in entries:
        out_file.write("%s\n" % str(entry))

    out_file.close()

    return 0
