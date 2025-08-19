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
"""Unit tests for at_auth_unlock."""

import argparse
import filecmp
import os
import shutil
import subprocess
import unittest

from at_auth_unlock import *
from Crypto.PublicKey import RSA
from unittest.mock import patch


def dataPath(file):
  return os.path.join(os.path.dirname(__file__), 'data', file)


DATA_FILE_PIK_CERTIFICATE = dataPath('cert_pik_certificate.bin')
DATA_FILE_PUK_CERTIFICATE = dataPath('cert_puk_certificate.bin')
DATA_FILE_PUK_KEY = dataPath('testkey_cert_puk.pem')
DATA_FILE_UNLOCK_CHALLENGE = dataPath('cert_unlock_challenge.bin')
DATA_FILE_UNLOCK_CREDENTIAL = dataPath('cert_unlock_credential.bin')


def createTempZip(contents):
  tempzip = tempfile.NamedTemporaryFile()
  with zipfile.ZipFile(tempzip, 'w') as zip:
    for arcname in contents:
      zip.write(contents[arcname], arcname)
  return tempzip


def validUnlockCredsZip():
  return createTempZip({
      'pik_certificate_v1.bin': DATA_FILE_PIK_CERTIFICATE,
      'puk_certificate_v1.bin': DATA_FILE_PUK_CERTIFICATE,
      'puk_v1.pem': DATA_FILE_PUK_KEY
  })


class UnlockCredentialsTest(unittest.TestCase):

  def testFromValidZipArchive(self):
    with validUnlockCredsZip() as zip:
      creds = UnlockCredentials.from_credential_archive(zip)
      self.assertIsNotNone(creds.intermediate_cert)
      self.assertIsNotNone(creds.unlock_cert)
      self.assertIsNotNone(creds.unlock_key)

  def testFromInvalidZipArchive(self):
    with self.assertRaises(zipfile.BadZipfile):
      UnlockCredentials.from_credential_archive(DATA_FILE_PUK_KEY)

  def testFromArchiveMissingPikCertificate(self):
    with createTempZip({
        'puk_certificate_v1.bin': DATA_FILE_PUK_CERTIFICATE,
        'puk_v1.pem': DATA_FILE_PUK_KEY
    }) as zip:
      with self.assertRaises(ValueError):
        UnlockCredentials.from_credential_archive(zip)

  def testFromArchiveMissingPukCertificate(self):
    with createTempZip({
        'pik_certificate_v1.bin': DATA_FILE_PIK_CERTIFICATE,
        'puk_v1.pem': DATA_FILE_PUK_KEY
    }) as zip:
      with self.assertRaises(ValueError):
        UnlockCredentials.from_credential_archive(zip)

  def testFromArchiveMissingPuk(self):
    with createTempZip({
        'pik_certificate_v1.bin': DATA_FILE_PIK_CERTIFICATE,
        'puk_certificate_v1.bin': DATA_FILE_PUK_CERTIFICATE,
    }) as zip:
      with self.assertRaises(ValueError):
        UnlockCredentials.from_credential_archive(zip)

  def testFromArchiveMultiplePikCertificates(self):
    with createTempZip({
        'pik_certificate_v1.bin': DATA_FILE_PIK_CERTIFICATE,
        'pik_certificate_v2.bin': DATA_FILE_PIK_CERTIFICATE,
        'puk_certificate_v1.bin': DATA_FILE_PUK_CERTIFICATE,
        'puk_v1.pem': DATA_FILE_PUK_KEY
    }) as zip:
      with self.assertRaises(ValueError):
        UnlockCredentials.from_credential_archive(zip)

  def testFromArchiveMultiplePukCertificates(self):
    with createTempZip({
        'pik_certificate_v1.bin': DATA_FILE_PIK_CERTIFICATE,
        'puk_certificate_v1.bin': DATA_FILE_PUK_CERTIFICATE,
        'puk_certificate_v2.bin': DATA_FILE_PUK_CERTIFICATE,
        'puk_v1.pem': DATA_FILE_PUK_KEY
    }) as zip:
      with self.assertRaises(ValueError):
        UnlockCredentials.from_credential_archive(zip)

  def testFromArchiveMultiplePuks(self):
    with createTempZip({
        'pik_certificate_v1.bin': DATA_FILE_PIK_CERTIFICATE,
        'puk_certificate_v1.bin': DATA_FILE_PUK_CERTIFICATE,
        'puk_v1.pem': DATA_FILE_PUK_KEY,
        'puk_v2.pem': DATA_FILE_PUK_KEY
    }) as zip:
      with self.assertRaises(ValueError):
        UnlockCredentials.from_credential_archive(zip)

  def testFromFiles(self):
    creds = UnlockCredentials(
        intermediate_cert_file=DATA_FILE_PIK_CERTIFICATE,
        unlock_cert_file=DATA_FILE_PUK_CERTIFICATE,
        unlock_key_file=DATA_FILE_PUK_KEY)
    self.assertIsNotNone(creds.intermediate_cert)
    self.assertIsNotNone(creds.unlock_cert)
    self.assertIsNotNone(creds.unlock_key)

  def testInvalidPuk(self):
    with self.assertRaises(ValueError):
      UnlockCredentials(
          intermediate_cert_file=DATA_FILE_PIK_CERTIFICATE,
          unlock_cert_file=DATA_FILE_PUK_CERTIFICATE,
          unlock_key_file=DATA_FILE_PUK_CERTIFICATE)

  def testPukNotPrivateKey(self):
    tempdir = tempfile.mkdtemp()
    try:
      with open(DATA_FILE_PUK_KEY, 'rb') as f:
        key = RSA.importKey(f.read())
      pubkey = os.path.join(tempdir, 'pubkey.pub')
      with open(pubkey, 'wb') as f:
        f.write(key.publickey().exportKey())
      with self.assertRaises(ValueError):
        UnlockCredentials(
            intermediate_cert_file=DATA_FILE_PIK_CERTIFICATE,
            unlock_cert_file=DATA_FILE_PUK_CERTIFICATE,
            unlock_key_file=pubkey)
    finally:
      shutil.rmtree(tempdir)

  def testWrongSizeCerts(self):
    pik_cert = DATA_FILE_PIK_CERTIFICATE
    tempdir = tempfile.mkdtemp()
    try:
      # Copy a valid cert and truncate a single byte from the end to create a
      # too-short cert.
      shortfile = os.path.join(tempdir, 'shortfile.bin')
      shutil.copy2(pik_cert, shortfile)
      with open(shortfile, 'ab') as f:
        f.seek(-1, os.SEEK_END)
        f.truncate()
      with self.assertRaises(ValueError):
        creds = UnlockCredentials(
            intermediate_cert_file=shortfile,
            unlock_cert_file=DATA_FILE_PUK_CERTIFICATE,
            unlock_key_file=DATA_FILE_PUK_KEY)
      with self.assertRaises(ValueError):
        creds = UnlockCredentials(
            intermediate_cert_file=DATA_FILE_PIK_CERTIFICATE,
            unlock_cert_file=shortfile,
            unlock_key_file=DATA_FILE_PUK_KEY)

      # Copy a valid cert and append an arbitrary byte on the end to create a
      # too-long cert.
      longfile = os.path.join(tempdir, 'longfile.bin')
      shutil.copy2(pik_cert, longfile)
      with open(longfile, 'ab') as f:
        f.write(b'\0')
      with self.assertRaises(ValueError):
        creds = UnlockCredentials(
            intermediate_cert_file=longfile,
            unlock_cert_file=DATA_FILE_PUK_CERTIFICATE,
            unlock_key_file=DATA_FILE_PUK_KEY)
      with self.assertRaises(ValueError):
        creds = UnlockCredentials(
            intermediate_cert_file=DATA_FILE_PIK_CERTIFICATE,
            unlock_cert_file=longfile,
            unlock_key_file=DATA_FILE_PUK_KEY)
    finally:
      shutil.rmtree(tempdir)


def writeFullUnlockChallenge(out_file, product_id_hash=None):
  """Helper function to create a file with a full AvbCertUnlockChallenge struct.

  Arguments:
    product_id_hash: [optional] 32 byte value to include in the challenge as the
      SHA256 hash of the product ID. If not provided, will default to the
      product ID hash from the subject of DATA_FILE_PUK_CERTIFICATE.
  """
  if product_id_hash is None:
    with open(DATA_FILE_PUK_CERTIFICATE, 'rb') as f:
      product_id_hash = GetCertCertificateSubject(f.read())
  assert len(product_id_hash) == 32

  with open(out_file, 'wb') as out:
    out.write(struct.pack('<I', 1))
    out.write(product_id_hash)
    with open(DATA_FILE_UNLOCK_CHALLENGE, 'rb') as f:
      out.write(f.read())


class MakeCertUnlockCredentialTest(unittest.TestCase):

  def testCredentialIsCorrect(self):
    with validUnlockCredsZip() as zip:
      creds = UnlockCredentials.from_credential_archive(zip)

      tempdir = tempfile.mkdtemp()
      try:
        challenge_file = os.path.join(tempdir, 'challenge')
        writeFullUnlockChallenge(challenge_file)
        challenge = UnlockChallenge(challenge_file)
        out_cred = os.path.join(tempdir, 'credential')

        # Compare unlock credential generated by function with one generated
        # using 'avbtool make_cert_unlock_credential', to check correctness.
        MakeCertUnlockCredential(creds, challenge, out_cred)
        self.assertTrue(filecmp.cmp(out_cred, DATA_FILE_UNLOCK_CREDENTIAL))
      finally:
        shutil.rmtree(tempdir)

  def testWrongChallengeSize(self):
    with validUnlockCredsZip() as zip:
      creds = UnlockCredentials.from_credential_archive(zip)

      tempdir = tempfile.mkdtemp()
      try:
        out_cred = os.path.join(tempdir, 'credential')

        # The bundled unlock challenge is just the 16 byte challenge, not the
        # full AvbCertUnlockChallenge like this expects.
        with self.assertRaises(ValueError):
          challenge = UnlockChallenge(DATA_FILE_UNLOCK_CHALLENGE)
          MakeCertUnlockCredential(creds, challenge, out_cred)
      finally:
        shutil.rmtree(tempdir)


def makeFastbootCommandFake(testcase,
                            expect_serial=None,
                            error_on_command_number=None,
                            product_id_hash=None,
                            stay_locked=False):
  """Construct a fake fastboot command handler, to be used with unitttest.mock.Mock.side_effect.

  This can be used to create a callable that acts as a fake for a real device
  responding to the fastboot commands involved in an authenticated unlock. The
  returned callback is intended to be used with unittest.mock.Mock.side_effect.
  There are a number of optional arguments here that can be used to customize
  the behavior of the fake for a specific test.

  Arguments:
    testcase: unittest.TestCase object for the associated test
    expect_serial: [optional] Expect (and assert) that the fastboot command
      specifies a specific device serial to communicate with.
    error_on_command_number: [optional] Return a fastboot error (non-zero exit
      code) on the nth (0-based) command handled.
    stay_locked: [optional] Make the fake report that the device is still locked
      after an otherwise successful unlock attempt.
  """

  def handler(args, *extraArgs, **kwargs):
    if error_on_command_number is not None:
      handler.command_counter += 1
      if handler.command_counter - 1 == error_on_command_number:
        raise subprocess.CalledProcessError(
            returncode=1, cmd=args, output=b'Fake: ERROR')

    testcase.assertEqual(args.pop(0), 'fastboot')
    if expect_serial is not None:
      # This is a bit fragile in that, in reality, fastboot allows '-s SERIAL'
      # to not just be the first arguments, but it works for this use case.
      testcase.assertEqual(args.pop(0), '-s')
      testcase.assertEqual(args.pop(0), expect_serial)

    if args[0:2] == ['oem', 'at-get-vboot-unlock-challenge']:
      handler.challenge_staged = True
    elif args[0] == 'get_staged':
      if not handler.challenge_staged:
        raise subprocess.CalledProcessError(
            returncode=1, cmd=args, output=b'Fake: No data staged')

      writeFullUnlockChallenge(args[1], product_id_hash=product_id_hash)
      handler.challenge_staged = False
    elif args[0] == 'stage':
      handler.staged_file = args[1]
    elif args[0:2] == ['oem', 'at-unlock-vboot']:
      if handler.staged_file is None:
        raise subprocess.CalledProcessError(
            returncode=1, cmd=args, output=b'Fake: No unlock credential staged')

      # Validate the unlock credential as if this were a test key locked device,
      # which implies tests that want a successful unlock need to be set up to
      # use DATA_FILE_PUK_KEY to sign the challenge. Credentials generated using
      # other keys will be properly rejected.
      if not filecmp.cmp(handler.staged_file, DATA_FILE_UNLOCK_CREDENTIAL):
        raise subprocess.CalledProcessError(
            returncode=1, cmd=args, output=b'Fake: Incorrect unlock credential')

      handler.locked = True if stay_locked else False
    elif args[0:2] == ['getvar', 'at-vboot-state']:
      return b'avb-locked: ' + (b'1' if handler.locked else b'0')
    return b'Fake: OK'

  handler.command_counter = 0
  handler.challenge_staged = False
  handler.staged_file = None
  handler.locked = True
  return handler


class AuthenticatedUnlockTest(unittest.TestCase):

  @patch('subprocess.check_output')
  def testUnlockWithZipArchive(self, mock_subp_check_output):
    with validUnlockCredsZip() as zip:
      mock_subp_check_output.side_effect = makeFastbootCommandFake(self)
      self.assertEqual(main([zip.name]), 0)
      self.assertNotEqual(mock_subp_check_output.call_count, 0)

  @patch('subprocess.check_output')
  def testUnlockDeviceBySerial(self, mock_subp_check_output):
    with validUnlockCredsZip() as zip:
      SERIAL = 'abcde12345'
      mock_subp_check_output.side_effect = makeFastbootCommandFake(
          self, expect_serial=SERIAL)
      self.assertEqual(main([zip.name, '-s', SERIAL]), 0)
      self.assertNotEqual(mock_subp_check_output.call_count, 0)

  @patch('subprocess.check_output')
  def testUnlockWithIndividualFiles(self, mock_subp_check_output):
    mock_subp_check_output.side_effect = makeFastbootCommandFake(self)
    self.assertEqual(
        main([
            '--pik_cert', DATA_FILE_PIK_CERTIFICATE, '--puk_cert',
            DATA_FILE_PUK_CERTIFICATE, '--puk', DATA_FILE_PUK_KEY
        ]), 0)
    self.assertNotEqual(mock_subp_check_output.call_count, 0)

  @patch('subprocess.check_output')
  def testFastbootError(self, mock_subp_check_output):
    """Verify that errors are handled properly if fastboot commands error out."""
    with validUnlockCredsZip() as zip:
      for n in range(5):
        mock_subp_check_output.reset_mock()
        mock_subp_check_output.side_effect = makeFastbootCommandFake(
            self, error_on_command_number=n)
        self.assertNotEqual(main([zip.name]), 0)
        self.assertNotEqual(mock_subp_check_output.call_count, 0)

  @patch('subprocess.check_output')
  def testDoesntActuallyUnlock(self, mock_subp_check_output):
    """Verify fails if fake set to not actually unlock."""
    with validUnlockCredsZip() as zip:
      mock_subp_check_output.side_effect = makeFastbootCommandFake(
          self, stay_locked=True)
      self.assertNotEqual(main([zip.name]), 0)
      self.assertNotEqual(mock_subp_check_output.call_count, 0)

  @patch('subprocess.check_output')
  def testNoCredentialsMatchDeviceProductID(self, mock_subp_check_output):
    """Test two cases where fake responds with a challenge that has a product ID hash which doesn't match the credentials used."""
    # Case 1: Change the product ID hash that the fake responds with.
    with validUnlockCredsZip() as zip:
      mock_subp_check_output.side_effect = makeFastbootCommandFake(
          self, product_id_hash=b'\x00' * 32)
      self.assertNotEqual(main([zip.name]), 0)
      self.assertNotEqual(mock_subp_check_output.call_count, 0)

    # Case 2: Use credentials with a different product ID.
    with createTempZip({
        'pik_certificate_v1.bin': DATA_FILE_PIK_CERTIFICATE,
        # Note: PIK cert used as PUK cert so subject (i.e. product ID hash) is
        # different
        'puk_certificate_v1.bin': DATA_FILE_PIK_CERTIFICATE,
        'puk_v1.pem': DATA_FILE_PUK_KEY
    }) as zip:
      mock_subp_check_output.side_effect = makeFastbootCommandFake(self)
      self.assertNotEqual(main([zip.name]), 0)
      self.assertNotEqual(mock_subp_check_output.call_count, 0)

  @patch('subprocess.check_output')
  def testMatchingCredentialSelectedFromZipArchives(self,
                                                    mock_subp_check_output):
    """Test correct credential based on product ID hash used if multiple provided directly through arguments."""
    with validUnlockCredsZip() as correctCreds, createTempZip({
        'pik_certificate_v1.bin': DATA_FILE_PIK_CERTIFICATE,
        # Note: PIK cert used as PUK cert so subject (i.e. product ID hash)
        # doesn't match
        'puk_certificate_v1.bin': DATA_FILE_PIK_CERTIFICATE,
        'puk_v1.pem': DATA_FILE_PUK_KEY
    }) as wrongCreds:
      mock_subp_check_output.side_effect = makeFastbootCommandFake(self)
      self.assertEqual(main([wrongCreds.name, correctCreds.name]), 0)
      self.assertNotEqual(mock_subp_check_output.call_count, 0)

  @patch('subprocess.check_output')
  def testMatchingCredentialSelectedFromDirectory(self, mock_subp_check_output):
    """Test correct credential based on product ID hash used if multiple provided indirectly through a directory argument."""
    with validUnlockCredsZip() as correctCreds, createTempZip({
        'pik_certificate_v1.bin': DATA_FILE_PIK_CERTIFICATE,
        # Note: PIK cert used as PUK cert so subject (i.e. product ID hash)
        # doesn't match
        'puk_certificate_v1.bin': DATA_FILE_PIK_CERTIFICATE,
        'puk_v1.pem': DATA_FILE_PUK_KEY
    }) as wrongCreds:
      tempdir = tempfile.mkdtemp()
      try:
        shutil.copy2(correctCreds.name, tempdir)
        shutil.copy2(wrongCreds.name, tempdir)

        mock_subp_check_output.side_effect = makeFastbootCommandFake(self)
        self.assertEqual(main([tempdir]), 0)
        self.assertNotEqual(mock_subp_check_output.call_count, 0)
      finally:
        shutil.rmtree(tempdir)

  @patch('subprocess.check_output')
  def testMatchingCredentialSelectedFromEither(self, mock_subp_check_output):
    """Test correct credential based on product ID hash used if arguments give some combination of file and directory arguments."""
    with validUnlockCredsZip() as correctCreds, createTempZip({
        'pik_certificate_v1.bin': DATA_FILE_PIK_CERTIFICATE,
        # Note: PIK cert used as PUK cert so subject (i.e. product ID hash)
        # doesn't match
        'puk_certificate_v1.bin': DATA_FILE_PIK_CERTIFICATE,
        'puk_v1.pem': DATA_FILE_PUK_KEY
    }) as wrongCreds:
      # Case 1: Correct creds in directory, wrong in file arg
      tempdir = tempfile.mkdtemp()
      try:
        shutil.copy2(correctCreds.name, tempdir)

        mock_subp_check_output.side_effect = makeFastbootCommandFake(self)
        self.assertEqual(main([wrongCreds.name, tempdir]), 0)
        self.assertNotEqual(mock_subp_check_output.call_count, 0)

      finally:
        shutil.rmtree(tempdir)

      # Case 2: Correct creds in file arg, wrong in directory
      tempdir = tempfile.mkdtemp()
      try:
        shutil.copy2(wrongCreds.name, tempdir)

        mock_subp_check_output.side_effect = makeFastbootCommandFake(self)
        self.assertEqual(main([tempdir, correctCreds.name]), 0)
        self.assertNotEqual(mock_subp_check_output.call_count, 0)

        # Case 2: Correct creds in file arg, wrong in directory
      finally:
        shutil.rmtree(tempdir)

  @patch('argparse.ArgumentParser.error')
  def testArgparseDirectoryWithNoCredentials(self, mock_parser_error):
    """Test """
    tempdir = tempfile.mkdtemp()
    try:
      # Make sure random files are ignored.
      with open(os.path.join(tempdir, 'so_random'), 'w') as f:
        f.write("I'm a random file")

      mock_parser_error.side_effect = ValueError('ArgumentParser.error')
      with self.assertRaises(ValueError):
        main([tempdir])
      self.assertEqual(mock_parser_error.call_count, 1)
    finally:
      shutil.rmtree(tempdir)

  @patch('argparse.ArgumentParser.error')
  def testArgparseMutualExclusionArchiveAndFiles(self, mock_parser_error):
    mock_parser_error.side_effect = ValueError('ArgumentParser.error')
    with self.assertRaises(ValueError):
      main(['dummy.zip', '--pik_cert', DATA_FILE_PIK_CERTIFICATE])
    self.assertEqual(mock_parser_error.call_count, 1)

  @patch('argparse.ArgumentParser.error')
  def testArgparseMutualInclusionOfFileArgs(self, mock_parser_error):
    mock_parser_error.side_effect = ValueError('ArgumentParser.error')
    with self.assertRaises(ValueError):
      main(['--pik_cert', 'pik_cert.bin', '--puk_cert', 'puk_cert.bin'])
    self.assertEqual(mock_parser_error.call_count, 1)

    mock_parser_error.reset_mock()
    with self.assertRaises(ValueError):
      main(['--pik_cert', 'pik_cert.bin', '--puk', 'puk.pem'])
    self.assertEqual(mock_parser_error.call_count, 1)

    mock_parser_error.reset_mock()
    with self.assertRaises(ValueError):
      main(['--puk_cert', 'puk_cert.bin', '--puk', 'puk.pem'])
    self.assertEqual(mock_parser_error.call_count, 1)

  @patch('argparse.ArgumentParser.error')
  def testArgparseMissingBundleAndFiles(self, mock_parser_error):
    mock_parser_error.side_effect = ValueError('ArgumentParser.error')
    with self.assertRaises(ValueError):
      main(['-s', '1234abcd'])
    self.assertEqual(mock_parser_error.call_count, 1)


if __name__ == '__main__':
  unittest.main(verbosity=3)
