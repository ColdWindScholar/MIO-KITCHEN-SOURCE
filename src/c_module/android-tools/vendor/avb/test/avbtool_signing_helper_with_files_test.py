#!/usr/bin/env python3

#
# Copyright (C) 2017-2020 The Android Open Source Project
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use, copy,
# modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

import errno
import os
import subprocess
import sys


def rsa_signer_with_files(argv):
  if len(argv) != 4:
    sys.stderr.write('Wrong number of arguments: {} <alg> <pub key> <file>\n'
                     .format(argv[0]))
    return errno.EINVAL

  signing_file = open(argv[3], mode='rb+')
  data = signing_file.read()
  if not data:
    sys.stderr.write('There is no input data\n')
    return errno.EINVAL

  if os.environ.get('SIGNING_HELPER_GENERATE_WRONG_SIGNATURE'):
    # We're only called with this algorithm which signature size is 256.
    assert argv[1] == 'SHA256_RSA2048'
    signing_file.seek(0)
    signing_file.write(b'X' * 256)
    return 0

  if not os.getenv('SIGNING_HELPER_TEST'):
    sys.stderr.write('env SIGNING_HELPER_TEST is not set or empty\n')
    return errno.EINVAL

  test_file_name = os.environ['SIGNING_HELPER_TEST']
  if os.path.isfile(test_file_name) and not os.access(test_file_name, os.W_OK):
    sys.stderr.write('no permission to write into {} file\n'
                     .format(test_file_name))
    return errno.EACCES

  p = subprocess.Popen(
      ['openssl', 'rsautl', '-sign', '-inkey', argv[2], '-raw'],
      stdin=subprocess.PIPE, stdout=subprocess.PIPE)

  (pout, _) = p.communicate(data)
  retcode = p.wait()
  if retcode != 0:
    return retcode

  signing_file.seek(0)
  signing_file.write(pout)

  with open(test_file_name, 'w') as f:
    f.write('DONE')

  return 0

if __name__ == '__main__':
  sys.exit(rsa_signer_with_files(sys.argv))
