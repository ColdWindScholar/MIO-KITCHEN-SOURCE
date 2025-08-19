#!/usr/bin/env python
#
# Copyright 2018 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
#
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Helper tool for performing an authenticated AVB unlock of an Android Things device.

This tool communicates with an Android Things device over fastboot to perform an
authenticated AVB unlock. The user provides unlock credentials valid for the
device they want to unlock, likely obtained from the Android Things Developer
Console. The tool handles the sequence of fastboot commands to complete the
challenge-response unlock protocol.

Unlock credentials can be provided to the tool in one of two ways:

  1) by providing paths to the individual credential files using the
     '--pik_cert', '--puk_cert', and '--puk' command line swtiches, or

  2) by providing a path to a zip archive containing the three credential files,
     named as follows:
       - Product Intermediate Key (PIK) certificate: 'pik_certificate.*\.bin'
       - Product Unlock Key (PUK) certificate: 'puk_certificate.*\.bin'
       - PUK private key: 'puk.*\.pem'

     You can also provide one or more archives and/or one or more directories
     containing such zip archives. In either scenario, the tool will search all
     of the provided credential archives for a match against the product ID of
     the device being unlocked and automatically use the first match.

This tool also clears the factory partition persistent digest unless the
--clear_factory_digest=false option is used. There is no harm to clear this
digest even if changes to the factory partition are not planned.

Dependencies:
  - Python 2.7.x, 3.2.x, or newer (for argparse)
  - PyCrypto 2.5 or newer (for PKCS1_v1_5 and RSA PKCS#8 PEM key import)
  - Android SDK Platform Tools (for fastboot), in PATH
    - https://developer.android.com/studio/releases/platform-tools
"""

HELP_DESCRIPTION = """Performs an authenticated AVB unlock of an Android Things device over
fastboot, given valid unlock credentials for the device."""

HELP_USAGE = """
  %(prog)s [-h] [-v] [-s SERIAL] [--clear_factory_digest=true|false] unlock_creds.zip [unlock_creds_2.zip ...]
  %(prog)s --pik_cert pik_cert.bin --puk_cert puk_cert.bin --puk puk.pem"""

HELP_EPILOG = """examples:
  %(prog)s unlock_creds.zip
  %(prog)s unlock_creds.zip unlock_creds_2.zip -s SERIAL
  %(prog)s path_to_dir_with_multiple_unlock_creds/
  %(prog)s --pik_cert pik_cert.bin --puk_cert puk_cert.bin --puk puk.pem"""

import sys

ver = sys.version_info
if (ver[0] < 2) or (ver[0] == 2 and ver[1] < 7) or (ver[0] == 3 and ver[1] < 2):
  print('This script requires Python 2.7+ or 3.2+')
  sys.exit(1)

import argparse
import binascii
import os
import re
import shutil
import struct
import subprocess
import tempfile
import zipfile

# Requires PyCrypto 2.5 (or newer) for PKCS1_v1_5 and support for importing
# PEM-encoded RSA keys
try:
  from Crypto.Hash import SHA512
  from Crypto.PublicKey import RSA
  from Crypto.Signature import PKCS1_v1_5
except ImportError as e:
  print('PyCrypto 2.5 or newer required, missing or too old: ' + str(e))


class UnlockCredentials(object):
  """Helper data container class for the 3 unlock credentials involved in an AVB authenticated unlock operation.

  """

  def __init__(self,
               intermediate_cert_file,
               unlock_cert_file,
               unlock_key_file,
               source_file=None):
    # The certificates are AvbCertCertificate structs as defined in libavb_cert,
    # not an X.509 certificate. Do a basic length sanity check when reading
    # them.
    EXPECTED_CERTIFICATE_SIZE = 1620

    with open(intermediate_cert_file, 'rb') as f:
      self._intermediate_cert = f.read()
    if len(self._intermediate_cert) != EXPECTED_CERTIFICATE_SIZE:
      raise ValueError('Invalid intermediate key certificate length.')

    with open(unlock_cert_file, 'rb') as f:
      self._unlock_cert = f.read()
    if len(self._unlock_cert) != EXPECTED_CERTIFICATE_SIZE:
      raise ValueError('Invalid product unlock key certificate length.')

    with open(unlock_key_file, 'rb') as f:
      self._unlock_key = RSA.importKey(f.read())
      if not self._unlock_key.has_private():
        raise ValueError('Unlock key was not an RSA private key.')

    self._source_file = source_file

  @property
  def intermediate_cert(self):
    return self._intermediate_cert

  @property
  def unlock_cert(self):
    return self._unlock_cert

  @property
  def unlock_key(self):
    return self._unlock_key

  @property
  def source_file(self):
    return self._source_file

  @classmethod
  def from_credential_archive(cls, archive):
    """Create UnlockCredentials from an unlock credential zip archive.

    The zip archive must contain the following three credential files, named as
    follows:
      - Product Intermediate Key (PIK) certificate: 'pik_certificate.*\.bin'
      - Product Unlock Key (PUK) certificate: 'puk_certificate.*\.bin'
      - PUK private key: 'puk.*\.pem'

    This uses @contextlib.contextmanager so we can clean up the tempdir created
    to unpack the zip contents into.

    Arguments:
      - archive: Filename of zip archive containing unlock credentials.

    Raises:
      ValueError: If archive is either missing a required file or contains
      multiple files matching one of the filename formats.
    """

    def _find_one_match(contents, regex, desc):
      r = re.compile(regex)
      matches = list(filter(r.search, contents))
      if not matches:
        raise ValueError(
            "Couldn't find {} file (matching regex '{}') in archive {}".format(
                desc, regex, archive))
      elif len(matches) > 1:
        raise ValueError(
            "Found multiple files for {} (matching regex '{}') in archive {}"
            .format(desc, regex, archive))
      return matches[0]

    tempdir = tempfile.mkdtemp()
    try:
      with zipfile.ZipFile(archive, mode='r') as zip:
        contents = zip.namelist()

        pik_cert_re = r'^pik_certificate.*\.bin$'
        pik_cert = _find_one_match(contents, pik_cert_re,
                                   'intermediate key (PIK) certificate')

        puk_cert_re = r'^puk_certificate.*\.bin$'
        puk_cert = _find_one_match(contents, puk_cert_re,
                                   'unlock key (PUK) certificate')

        puk_re = r'^puk.*\.pem$'
        puk = _find_one_match(contents, puk_re, 'unlock key (PUK)')

        zip.extractall(path=tempdir, members=[pik_cert, puk_cert, puk])

        return cls(
            intermediate_cert_file=os.path.join(tempdir, pik_cert),
            unlock_cert_file=os.path.join(tempdir, puk_cert),
            unlock_key_file=os.path.join(tempdir, puk),
            source_file=archive)
    finally:
      shutil.rmtree(tempdir)


class UnlockChallenge(object):
  """Helper class for parsing the AvbCertUnlockChallenge struct returned from 'fastboot oem at-get-vboot-unlock-challenge'.

     The file provided to the constructor should be the full 52-byte
     AvbCertUnlockChallenge struct, not just the challenge itself.
  """

  def __init__(self, challenge_file):
    CHALLENGE_STRUCT_SIZE = 52
    PRODUCT_ID_HASH_SIZE = 32
    CHALLENGE_DATA_SIZE = 16
    with open(challenge_file, 'rb') as f:
      data = f.read()
      if len(data) != CHALLENGE_STRUCT_SIZE:
        raise ValueError('Invalid unlock challenge length.')

      self._version, self._product_id_hash, self._challenge_data = struct.unpack(
          '<I{}s{}s'.format(PRODUCT_ID_HASH_SIZE, CHALLENGE_DATA_SIZE), data)

  @property
  def version(self):
    return self._version

  @property
  def product_id_hash(self):
    return self._product_id_hash

  @property
  def challenge_data(self):
    return self._challenge_data


def GetCertCertificateSubject(cert):
  """Parses and returns the subject field from the given AvbCertCertificate struct."""
  CERT_SUBJECT_OFFSET = 4 + 1032  # Format version and public key come before subject
  CERT_SUBJECT_LENGTH = 32
  return cert[CERT_SUBJECT_OFFSET:CERT_SUBJECT_OFFSET + CERT_SUBJECT_LENGTH]


def SelectMatchingUnlockCredential(all_creds, challenge):
  """Find and return the first UnlockCredentials object whose product ID matches that of the unlock challenge.

  The Product Unlock Key (PUK) certificate's subject field contains the
  SHA256 hash of the product ID that it can be used to unlock. This same
  value (SHA256 hash of the product ID) is contained in the unlock challenge.

  Arguments:
    all_creds: List of UnlockCredentials objects to be searched for a match
      against the given challenge.
    challenge: UnlockChallenge object created from challenge obtained via
      'fastboot oem at-get-vboot-unlock-challenge'.
  """
  for creds in all_creds:
    if GetCertCertificateSubject(creds.unlock_cert) == challenge.product_id_hash:
      return creds


def MakeCertUnlockCredential(creds, challenge, out_file):
  """Simple reimplementation of 'avbtool make_cert_unlock_credential'.

  Generates an Android Things authenticated unlock credential to authorize
  unlocking AVB on a device.

  This is reimplemented locally for simplicity, which avoids the need to bundle
  this tool with the full avbtool. avbtool also uses openssl by default whereas
  this uses PyCrypto, which makes it easier to support Windows since there are
  no officially supported openssl binary distributions.

  Arguments:
    creds: UnlockCredentials object wrapping the PIK certificate, PUK
      certificate, and PUK private key.
    challenge: UnlockChallenge object created from challenge obtained via
      'fastboot oem at-get-vboot-unlock-challenge'.
    out_file: Output filename to write the AvbCertUnlockCredential struct to.

  Raises:
    ValueError: If challenge has wrong length.
  """
  hash = SHA512.new(challenge.challenge_data)
  signer = PKCS1_v1_5.new(creds.unlock_key)
  signature = signer.sign(hash)

  with open(out_file, 'wb') as out:
    out.write(struct.pack('<I', 1))  # Format Version
    out.write(creds.intermediate_cert)
    out.write(creds.unlock_cert)
    out.write(signature)


def AuthenticatedUnlock(all_creds, serial=None, verbose=False):
  """Performs an authenticated AVB unlock of a device over fastboot.

  Arguments:
    all_creds: List of UnlockCredentials objects wrapping the PIK certificate,
      PUK certificate, and PUK private key. The list will be searched to find
      matching credentials for the device being unlocked.
    serial: [optional] A device serial number or other valid value to be passed
      to fastboot's '-s' switch to select the device to unlock.
    verbose: [optional] Enable verbose output, which prints the fastboot
      commands and their output as the commands are run.
  """

  tempdir = tempfile.mkdtemp()
  try:
    challenge_file = os.path.join(tempdir, 'challenge')
    credential_file = os.path.join(tempdir, 'credential')

    def fastboot_cmd(args):
      args = ['fastboot'] + (['-s', serial] if serial else []) + args
      if verbose:
        print('\n$ ' + ' '.join(args))

      out = subprocess.check_output(
          args, stderr=subprocess.STDOUT).decode('utf-8')

      if verbose:
        print(out)
      return out

    try:
      fastboot_cmd(['oem', 'at-get-vboot-unlock-challenge'])
      fastboot_cmd(['get_staged', challenge_file])

      challenge = UnlockChallenge(challenge_file)
      print('Product ID SHA256 hash = {}'.format(
          binascii.hexlify(challenge.product_id_hash)))

      selected_cred = SelectMatchingUnlockCredential(all_creds, challenge)
      if not selected_cred:
        print(
            'ERROR: None of the provided unlock credentials match this device.')
        return False
      if selected_cred.source_file:
        print('Found matching unlock credentials: {}'.format(
            selected_cred.source_file))
      MakeCertUnlockCredential(selected_cred, challenge, credential_file)

      fastboot_cmd(['stage', credential_file])
      fastboot_cmd(['oem', 'at-unlock-vboot'])

      res = fastboot_cmd(['getvar', 'at-vboot-state'])
      if re.search(r'avb-locked(:\s*|=)0', res) is not None:
        print('Device successfully AVB unlocked')
        return True
      else:
        print('ERROR: Commands succeeded but device still locked')
        return False
    except subprocess.CalledProcessError as e:
      print(e.output.decode('utf-8'))
      print("Command '{}' returned non-zero exit status {}".format(
          ' '.join(e.cmd), e.returncode))
      return False
  finally:
    shutil.rmtree(tempdir)


def FindUnlockCredentialsInDirectory(dir, verbose=False):
  if not os.path.isdir(dir):
    raise ValueError('Not a directory: ' + dir)

  creds = []
  for file in os.listdir(dir):
    path = os.path.join(dir, file)
    if os.path.isfile(path):
      try:
        creds.append(UnlockCredentials.from_credential_archive(path))
        if verbose:
          print('Found valid unlock credential bundle: ' + path)
      except (IOError, ValueError, zipfile.BadZipfile) as e:
        if verbose:
          print(
              "Ignoring file which isn't a valid unlock credential zip bundle: "
              + path)
  return creds


def ClearFactoryPersistentDigest(serial=None, verbose=False):
  """Clears the factory partition persistent digest using fastboot.

  Most of the time this should be cleared when unlocking a device because
  otherwise any attempts to update the factory partition will be rejected once
  the device is again locked, causing confusion. There is no harm to clear this
  digest even if factory partition updates are not planned.

  Arguments:
    serial: [optional] A device serial number or other valid value to be passed
      to fastboot's '-s' switch to select the device to unlock.
    verbose: [optional] Enable verbose output, which prints the fastboot
      commands and their output as the commands are run.
  """
  FACTORY_PERSISTENT_DIGEST_NAME = 'avb.persistent_digest.factory'

  tempdir = tempfile.mkdtemp()
  try:
    digest_data = os.path.join(tempdir, 'digest_data')

    with open(digest_data, 'wb') as out:
      out.write(struct.pack('<I', len(FACTORY_PERSISTENT_DIGEST_NAME)))
      out.write(FACTORY_PERSISTENT_DIGEST_NAME)
      # Sending a zero length digest will clear the existing digest.
      out.write(struct.pack('<I', 0))

    def fastboot_cmd(args):
      args = ['fastboot'] + (['-s', serial] if serial else []) + args
      if verbose:
        print('$ ' + ' '.join(args))

      out = subprocess.check_output(
          args, stderr=subprocess.STDOUT).decode('utf-8')

      if verbose:
        print(out)

    try:
      fastboot_cmd(['stage', digest_data])
      fastboot_cmd(['oem', 'at-write-persistent-digest'])
      print("Successfully cleared the factory partition persistent digest.")
      return True
    except subprocess.CalledProcessError as e:
      print(e.output.decode('utf-8'))
      print("Command '{}' returned non-zero exit status {}".format(
          ' '.join(e.cmd), e.returncode))
      print("Warning: Failed to clear factory partition persistent digest.")
      return False

  finally:
    shutil.rmtree(tempdir)


def parse_boolean(value):
  if value.strip().lower() in ('true', 't', 'yes', 'y', 'on', '1'):
      return True
  elif value.strip().lower() in ('false', 'f', 'no', 'n', 'off', '0'):
      return False
  else:
      raise argparse.ArgumentTypeError('Unexpected boolean value: %s' % value)

def main(in_args):
  parser = argparse.ArgumentParser(
      description=HELP_DESCRIPTION,
      usage=HELP_USAGE,
      epilog=HELP_EPILOG,
      formatter_class=argparse.RawDescriptionHelpFormatter)

  # General optional arguments.
  parser.add_argument(
      '-v',
      '--verbose',
      action='store_true',
      help=
      'enable verbose output, e.g. prints fastboot commands and their output')
  parser.add_argument(
      '-s',
      '--serial',
      help=
      "specify device to unlock, either by serial or any other valid value for fastboot's -s arg"
  )
  parser.add_argument(
      '--clear_factory_digest',
      nargs='?',
      type=parse_boolean,
      default='true',
      const='true',
      help='Defaults to true. Set to false to prevent clearing the factory persistent digest')

  # User must provide either a unlock credential bundle, or the individual files
  # normally contained in such a bundle.
  # argparse doesn't support specifying this argument format - two groups of
  # mutually exclusive arguments, where one group requires all arguments in that
  # group to be specified - so we define them as optional arguments and do the
  # validation ourselves below.

  # Argument group #1 - Unlock credential zip archive(s) (or directory
  # containing multiple such archives)
  parser.add_argument(
      'bundle',
      metavar='unlock_creds.zip',
      nargs='*',
      help=
      'Unlock using a zip bundle/archive of credentials (e.g. from Developer '
      'Console). You can optionally provide multiple archives and/or a  '
      'directory of such bundles and the tool will automatically select the '
      'correct one to use based on matching the product ID against the device '
      'being unlocked.')

  # Argument group #2 - Individual credential files
  parser.add_argument(
      '--pik_cert',
      metavar='pik_cert.bin',
      help='Path to product intermediate key (PIK) certificate file')
  parser.add_argument(
      '--puk_cert',
      metavar='puk_cert.bin',
      help='Path to product unlock key (PUK) certificate file')
  parser.add_argument(
      '--puk',
      metavar='puk.pem',
      help='Path to product unlock key in PEM format')

  # Print help if no args given
  args = parser.parse_args(in_args if in_args else ['-h'])

  # Do the custom validation described above.
  if args.pik_cert is not None or args.puk_cert is not None or args.puk is not None:
    # Check mutual exclusion with bundle positional argument
    if len(args.bundle):
      parser.error(
          'bundle argument is mutually exclusive with --pik_cert, --puk_cert, and --puk'
      )

    # Check for 'mutual inclusion' of individual file options
    if args.pik_cert is None:
      parser.error("--pik_cert is required if --puk_cert or --puk' is given")
    if args.puk_cert is None:
      parser.error("--puk_cert is required if --pik_cert or --puk' is given")
    if args.puk is None:
      parser.error("--puk is required if --pik_cert or --puk_cert' is given")
  elif not len(args.bundle):
    parser.error(
        'must provide either credentials bundle or individual credential files')

  # Parse arguments into UnlockCredentials objects
  if len(args.bundle):
    creds = []
    for path in args.bundle:
      if os.path.isfile(path):
        creds.append(UnlockCredentials.from_credential_archive(path))
      elif os.path.isdir(path):
        creds.extend(
            FindUnlockCredentialsInDirectory(path, verbose=args.verbose))
      else:
        parser.error("path argument '{}' does not exist".format(path))

    if len(creds) == 0:
      parser.error('No unlock credentials were found in any of the given paths')
  else:
    creds = [UnlockCredentials(args.pik_cert, args.puk_cert, args.puk)]

  ret = AuthenticatedUnlock(creds, serial=args.serial, verbose=args.verbose)
  if ret and args.clear_factory_digest:
    ret = ClearFactoryPersistentDigest(serial=args.serial, verbose=args.verbose)
  return 0 if ret else 1


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
