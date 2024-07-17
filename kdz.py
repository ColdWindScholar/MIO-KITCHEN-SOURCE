#!/usr/bin/env python

"""
Copyright (C) 2016 Elliott Mitchell <ehem+android@m5p.com>
Copyright (C) 2013 IOMonster (thecubed on XDA)

	This program is free software: you can redistribute it and/or modify
	it under the terms of the GNU General Public License as published by
	the Free Software Foundation, either version 3 of the License, or
	(at your option) any later version.

	This program is distributed in the hope that it will be useful,
	but WITHOUT ANY WARRANTY; without even the implied warranty of
	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
	GNU General Public License for more details.

	You should have received a copy of the GNU General Public License
	along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""


from collections import OrderedDict

import dz


class KDZFile(dz.DZStruct):
    """LGE KDZ File tools"""

    _dz_length = 272
    _dz_header = b'(\x05\x00\x00$8"%'

    # Format string dict
    #   itemName is the new dict key for the data to be stored under
    #   formatString is the Python formatstring for struct.unpack()
    #   collapse is boolean that controls whether extra \x00 's should be stripped
    # Example:
    #   ('itemName', ('formatString', collapse))
    _dz_format_dict = OrderedDict([
        ('name', ('256s', True)),
        ('length', ('Q', False)),
        ('offset', ('Q', False)),
    ])

    def __init__(self):
        """Initializer for KDZFile, gets DZStruct to fill remaining values"""
        super(KDZFile, self).__init__(KDZFile)
