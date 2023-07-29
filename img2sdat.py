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


def main(INPUT_IMAGE, OUTDIR='.', VERSION=None, PREFIX='system'):
    __version__ = '1.7'
    print('img2sdat binary - version: %s\n' % __version__)
    if not os.path.isdir(OUTDIR):
        os.makedirs(OUTDIR)

    OUTDIR = OUTDIR + '/' + PREFIX

    if not VERSION:
        while True:
            print('''            1. Android Lollipop 5.0
            2. Android Lollipop 5.1
            3. Android Marshmallow 6.0
            4. Android Nougat 7.0/7.1/8.0/8.1
            ''')
            item = input('Choose system version: ')
            if 1 <= item <= 4 and item is int:
                VERSION = item
            else:
                VERSION = 4

    blockimgdiff.BlockImageDiff(sparse_img.SparseImage(INPUT_IMAGE, tempfile.mkstemp()[1], '0'), None, VERSION).Compute(OUTDIR)
    print('Done! Output files: %s' % os.path.dirname(OUTDIR))
    return
