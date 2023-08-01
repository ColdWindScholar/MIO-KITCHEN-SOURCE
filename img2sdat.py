#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ====================================================
#          FILE: img2sdat.py
#       AUTHORS: xpirt - luxi78 - howellzhu
#          DATE: 2018-05-25 12:19:12 CEST
# ====================================================

from __future__ import print_function

import sys, os, errno, tempfile
import common, blockimgdiff, sparse_img


def main(input_image, out_dir='.', version=None, prefix='system'):
    print('img2sdat binary - version: %s\n' % 1.7)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
        '''            
        1. Android Lollipop 5.0
        2. Android Lollipop 5.1
        3. Android Marshmallow 6.0
        4. Android Nougat 7.0/7.1/8.0/8.1
        '''

    blockimgdiff.BlockImageDiff(sparse_img.SparseImage(input_image, tempfile.mkstemp()[1], '0'), None, version).Compute(
        out_dir + '/' + prefix)
    print('Done! Output files: %s' % os.path.dirname(prefix))
