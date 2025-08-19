/*
 * Copyright (C) 2016 The Android Open Source Project
 *
 * Permission is hereby granted, free of charge, to any person
 * obtaining a copy of this software and associated documentation
 * files (the "Software"), to deal in the Software without
 * restriction, including without limitation the rights to use, copy,
 * modify, merge, publish, distribute, sublicense, and/or sell copies
 * of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be
 * included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 * EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
 * NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
 * BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
 * ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

#include <iostream>

#include <endian.h>
#include <inttypes.h>
#include <string.h>

#include <base/files/file_util.h>
#include <base/strings/string_util.h>
#include <base/strings/stringprintf.h>

#include <libavb/libavb.h>

#include "avb_unittest_util.h"

namespace avb {

class VerifyTest : public BaseAvbToolTest {
 public:
  VerifyTest() {}

 protected:
  // Helper function for ModificationDetection test. Modifies
  // boot_image_ in a number of places in the sub-array at |offset| of
  // size |length| and checks that avb_vbmeta_image_verify() returns
  // |expected_result|.
  bool test_modification(AvbVBMetaVerifyResult expected_result,
                         size_t offset,
                         size_t length);
};

TEST_F(VerifyTest, BootImageStructSize) {
  EXPECT_EQ(256UL, sizeof(AvbVBMetaImageHeader));
}

TEST_F(VerifyTest, CheckSHA256RSA2048) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"));
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_OK,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));
}

TEST_F(VerifyTest, CheckSHA256RSA4096) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA4096",
                      0,
                      base::FilePath("test/data/testkey_rsa4096.pem"));
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_OK,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));
}

TEST_F(VerifyTest, CheckSHA256RSA8192) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA8192",
                      0,
                      base::FilePath("test/data/testkey_rsa8192.pem"));
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_OK,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));
}

TEST_F(VerifyTest, CheckSHA512RSA2048) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA512_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"));
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_OK,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));
}

TEST_F(VerifyTest, CheckSHA512RSA4096) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA512_RSA4096",
                      0,
                      base::FilePath("test/data/testkey_rsa4096.pem"));
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_OK,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));
}

TEST_F(VerifyTest, CheckSHA512RSA8192) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA512_RSA8192",
                      0,
                      base::FilePath("test/data/testkey_rsa8192.pem"));
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_OK,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));
}

TEST_F(VerifyTest, CheckUnsigned) {
  GenerateVBMetaImage("vbmeta.img", "", 0, base::FilePath(""));
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_OK_NOT_SIGNED,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));
}

TEST_F(VerifyTest, CheckBiggerLength) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"));
  // Check that it's OK if we pass a bigger length than what the
  // header indicates.
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_OK,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size() + 8192, NULL, NULL));
}

TEST_F(VerifyTest, BadMagic) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"));
  vbmeta_image_[0] = 'Z';
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_INVALID_VBMETA_HEADER,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));
}

TEST_F(VerifyTest, MajorVersionCheck) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"));

  // Bail if it's a different major version.
  AvbVBMetaImageHeader* h =
      reinterpret_cast<AvbVBMetaImageHeader*>(vbmeta_image_.data());
  h->required_libavb_version_major = htobe32(1 + AVB_VERSION_MAJOR);
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_UNSUPPORTED_VERSION,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));
}

TEST_F(VerifyTest, MinorVersionCheck) {
  GenerateVBMetaImage("vbmeta.img", "", 0, base::FilePath(""));

  // Bail if required_libavb_version_minor exceeds our libavb version.
  AvbVBMetaImageHeader* h =
      reinterpret_cast<AvbVBMetaImageHeader*>(vbmeta_image_.data());
  h->required_libavb_version_minor = htobe32(1 + AVB_VERSION_MINOR);
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_UNSUPPORTED_VERSION,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));
}

TEST_F(VerifyTest, NulTerminatedReleaseString) {
  GenerateVBMetaImage("vbmeta.img", "", 0, base::FilePath(""));

  // Bail if |release_string| isn't NUL-terminated.
  AvbVBMetaImageHeader* h =
      reinterpret_cast<AvbVBMetaImageHeader*>(vbmeta_image_.data());
  for (size_t n = 0; n < AVB_RELEASE_STRING_SIZE; n++) {
    h->release_string[n] = 'a';
  }
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_INVALID_VBMETA_HEADER,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));
}

TEST_F(VerifyTest, BlockSizesAddUpToLessThanLength) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"));

  AvbVBMetaImageHeader* h =
      reinterpret_cast<AvbVBMetaImageHeader*>(vbmeta_image_.data());
  AvbVBMetaImageHeader backup = *h;

  // Check that the sum of the two block lengths is less than passed
  // in size. Use a size that's a multiple of 64 to avoid failure on
  // earlier check.
  uint64_t size = vbmeta_image_.size() & (~0x3f);

  h->authentication_data_block_size = htobe64(size);
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_INVALID_VBMETA_HEADER,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));
  *h = backup;

  h->auxiliary_data_block_size = htobe64(size);
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_INVALID_VBMETA_HEADER,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));
  *h = backup;

  // Overflow checks - choose overflow candidate so it's a multiple of
  // 64 otherwise we'll fail on an earlier check.
  size = 0xffffffffffffffc0UL;

  h->authentication_data_block_size = htobe64(size);
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_INVALID_VBMETA_HEADER,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));
  *h = backup;

  h->auxiliary_data_block_size = htobe64(size);
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_INVALID_VBMETA_HEADER,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));
  *h = backup;

  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_OK,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));
}

TEST_F(VerifyTest, BlockSizesMultipleOf64) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"));

  AvbVBMetaImageHeader* h =
      reinterpret_cast<AvbVBMetaImageHeader*>(vbmeta_image_.data());
  AvbVBMetaImageHeader backup = *h;

  h->authentication_data_block_size =
      htobe32(be32toh(h->authentication_data_block_size) - 32);
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_INVALID_VBMETA_HEADER,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size() - 32, NULL, NULL));
  *h = backup;

  h->auxiliary_data_block_size =
      htobe32(be32toh(h->auxiliary_data_block_size) - 32);
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_INVALID_VBMETA_HEADER,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size() - 32, NULL, NULL));
  *h = backup;

  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_OK,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));
}

TEST_F(VerifyTest, HashOutOfBounds) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"));

  AvbVBMetaImageHeader* h =
      reinterpret_cast<AvbVBMetaImageHeader*>(vbmeta_image_.data());

  // Check we catch when hash data goes out of bounds.
  h->hash_offset = htobe64(4);
  h->hash_size = htobe64(be64toh(h->authentication_data_block_size));
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_INVALID_VBMETA_HEADER,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));

  // Overflow checks.
  h->hash_offset = htobe64(4);
  h->hash_size = htobe64(0xfffffffffffffffeUL);
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_INVALID_VBMETA_HEADER,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));
}

TEST_F(VerifyTest, SignatureOutOfBounds) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"));

  AvbVBMetaImageHeader* h =
      reinterpret_cast<AvbVBMetaImageHeader*>(vbmeta_image_.data());

  // Check we catch when signature data goes out of bounds.
  h->signature_offset = htobe64(4);
  h->signature_size = htobe64(be64toh(h->authentication_data_block_size));
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_INVALID_VBMETA_HEADER,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));

  // Overflow checks.
  h->signature_offset = htobe64(4);
  h->signature_size = htobe64(0xfffffffffffffffeUL);
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_INVALID_VBMETA_HEADER,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));
}

TEST_F(VerifyTest, PublicKeyOutOfBounds) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"));

  AvbVBMetaImageHeader* h =
      reinterpret_cast<AvbVBMetaImageHeader*>(vbmeta_image_.data());

  // Check we catch when public key data goes out of bounds.
  h->public_key_offset = htobe64(4);
  h->public_key_size = htobe64(be64toh(h->auxiliary_data_block_size));
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_INVALID_VBMETA_HEADER,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));

  // Overflow checks.
  h->public_key_offset = htobe64(4);
  h->public_key_size = htobe64(0xfffffffffffffffeUL);
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_INVALID_VBMETA_HEADER,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));
}

TEST_F(VerifyTest, PublicKeyMetadataOutOfBounds) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"));

  AvbVBMetaImageHeader* h =
      reinterpret_cast<AvbVBMetaImageHeader*>(vbmeta_image_.data());

  // Check we catch when public key metadata data goes out of bounds.
  h->public_key_metadata_offset = htobe64(4);
  h->public_key_metadata_size = htobe64(be64toh(h->auxiliary_data_block_size));
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_INVALID_VBMETA_HEADER,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));

  // Overflow checks.
  h->public_key_metadata_offset = htobe64(4);
  h->public_key_metadata_size = htobe64(0xfffffffffffffffeUL);
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_INVALID_VBMETA_HEADER,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));
}

TEST_F(VerifyTest, InvalidAlgorithmField) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"));

  AvbVBMetaImageHeader* h =
      reinterpret_cast<AvbVBMetaImageHeader*>(vbmeta_image_.data());
  AvbVBMetaImageHeader backup = *h;

  // Check we bail on unknown algorithm.
  h->algorithm_type = htobe32(_AVB_ALGORITHM_NUM_TYPES);
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_INVALID_VBMETA_HEADER,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));
  *h = backup;
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_OK,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));
}

TEST_F(VerifyTest, PublicKeyBlockTooSmall) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"));

  AvbVBMetaImageHeader* h =
      reinterpret_cast<AvbVBMetaImageHeader*>(vbmeta_image_.data());
  AvbVBMetaImageHeader backup = *h;

  // Check we bail if the auxiliary data block is too small.
  uint64_t change = be64toh(h->auxiliary_data_block_size) - 64;
  h->auxiliary_data_block_size = htobe64(change);
  EXPECT_EQ(
      AVB_VBMETA_VERIFY_RESULT_INVALID_VBMETA_HEADER,
      avb_vbmeta_image_verify(
          vbmeta_image_.data(), vbmeta_image_.size() - change, NULL, NULL));
  *h = backup;
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_OK,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));
}

TEST_F(VerifyTest, VbmetaImageSmallerThanMagic) {
  uint8_t vbmeta_onebyte[1] = {0};
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_INVALID_VBMETA_HEADER,
            avb_vbmeta_image_verify(
                vbmeta_onebyte, 1, NULL, NULL));
}

bool VerifyTest::test_modification(AvbVBMetaVerifyResult expected_result,
                                   size_t offset,
                                   size_t length) {
  uint8_t* d = reinterpret_cast<uint8_t*>(vbmeta_image_.data());
  const int kNumCheckpoints = 16;

  // Test |kNumCheckpoints| modifications in the start, middle, and
  // end of given sub-array.
  for (int n = 0; n <= kNumCheckpoints; n++) {
    size_t o = std::min(length * n / kNumCheckpoints, length - 1) + offset;
    d[o] ^= 0x80;
    AvbVBMetaVerifyResult result = avb_vbmeta_image_verify(
        vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL);
    d[o] ^= 0x80;
    if (result != expected_result) {
      return false;
    }
  }

  return true;
}

TEST_F(VerifyTest, ModificationDetection) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"));

  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_OK,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), NULL, NULL));

  AvbVBMetaImageHeader h;
  avb_vbmeta_image_header_to_host_byte_order(
      reinterpret_cast<AvbVBMetaImageHeader*>(vbmeta_image_.data()), &h);

  size_t header_block_offset = 0;
  size_t authentication_block_offset =
      header_block_offset + sizeof(AvbVBMetaImageHeader);
  size_t auxiliary_block_offset =
      authentication_block_offset + h.authentication_data_block_size;

  // Ensure we detect modification of the header data block. Do this
  // in a field that's not validated so INVALID_VBMETA_HEADER
  // isn't returned.
  EXPECT_TRUE(test_modification(
      AVB_VBMETA_VERIFY_RESULT_HASH_MISMATCH,
      offsetof(AvbVBMetaImageHeader, reserved),
      sizeof(AvbVBMetaImageHeader) - offsetof(AvbVBMetaImageHeader, reserved)));
  // Also check the |reserved| field.
  EXPECT_TRUE(test_modification(AVB_VBMETA_VERIFY_RESULT_HASH_MISMATCH,
                                offsetof(AvbVBMetaImageHeader, reserved),
                                sizeof(AvbVBMetaImageHeader().reserved)));

  // Ensure we detect modifications in the auxiliary data block.
  EXPECT_TRUE(test_modification(AVB_VBMETA_VERIFY_RESULT_HASH_MISMATCH,
                                auxiliary_block_offset,
                                h.auxiliary_data_block_size));

  // Modifications in the hash part of the Authentication data block
  // should also yield HASH_MISMATCH. This is because the hash check
  // compares the calculated hash against the stored hash.
  EXPECT_TRUE(test_modification(AVB_VBMETA_VERIFY_RESULT_HASH_MISMATCH,
                                authentication_block_offset + h.hash_offset,
                                h.hash_size));

  // Modifications in the signature part of the Authentication data
  // block, should not cause a hash mismatch ... but will cause a
  // signature mismatch.
  EXPECT_TRUE(
      test_modification(AVB_VBMETA_VERIFY_RESULT_SIGNATURE_MISMATCH,
                        authentication_block_offset + h.signature_offset,
                        h.signature_size));

  // Mofications outside the hash and signature parts of the
  // Authentication data block are not detected. This is because it's
  // not part of the hash calculation.
  uint64_t offset = h.signature_offset + h.signature_size;
  ASSERT_LT(h.hash_offset, h.signature_offset);
  ASSERT_LT(offset + 1, h.authentication_data_block_size);
  EXPECT_TRUE(test_modification(AVB_VBMETA_VERIFY_RESULT_OK,
                                authentication_block_offset + offset,
                                h.authentication_data_block_size - offset));
}

TEST_F(VerifyTest, VBMetaHeaderByteswap) {
  AvbVBMetaImageHeader h;
  AvbVBMetaImageHeader s;
  uint32_t n32;
  uint64_t n64;

  n32 = 0x11223344;
  n64 = 0x1122334455667788;

  h.required_libavb_version_major = htobe32(n32);
  n32++;
  h.required_libavb_version_minor = htobe32(n32);
  n32++;
  h.authentication_data_block_size = htobe64(n64);
  n64++;
  h.auxiliary_data_block_size = htobe64(n64);
  n64++;
  h.algorithm_type = htobe32(n32);
  n32++;
  h.hash_offset = htobe64(n64);
  n64++;
  h.hash_size = htobe64(n64);
  n64++;
  h.signature_offset = htobe64(n64);
  n64++;
  h.signature_size = htobe64(n64);
  n64++;
  h.public_key_offset = htobe64(n64);
  n64++;
  h.public_key_size = htobe64(n64);
  n64++;
  h.public_key_metadata_offset = htobe64(n64);
  n64++;
  h.public_key_metadata_size = htobe64(n64);
  n64++;
  h.descriptors_offset = htobe64(n64);
  n64++;
  h.descriptors_size = htobe64(n64);
  n64++;
  h.rollback_index = htobe64(n64);
  n64++;
  h.flags = htobe32(n32);
  n32++;

  avb_vbmeta_image_header_to_host_byte_order(&h, &s);

  n32 = 0x11223344;
  n64 = 0x1122334455667788;

  EXPECT_EQ(n32, s.required_libavb_version_major);
  n32++;
  EXPECT_EQ(n32, s.required_libavb_version_minor);
  n32++;
  EXPECT_EQ(n64, s.authentication_data_block_size);
  n64++;
  EXPECT_EQ(n64, s.auxiliary_data_block_size);
  n64++;
  EXPECT_EQ(n32, s.algorithm_type);
  n32++;
  EXPECT_EQ(n64, s.hash_offset);
  n64++;
  EXPECT_EQ(n64, s.hash_size);
  n64++;
  EXPECT_EQ(n64, s.signature_offset);
  n64++;
  EXPECT_EQ(n64, s.signature_size);
  n64++;
  EXPECT_EQ(n64, s.public_key_offset);
  n64++;
  EXPECT_EQ(n64, s.public_key_size);
  n64++;
  EXPECT_EQ(n64, s.public_key_metadata_offset);
  n64++;
  EXPECT_EQ(n64, s.public_key_metadata_size);
  n64++;
  EXPECT_EQ(n64, s.descriptors_offset);
  n64++;
  EXPECT_EQ(n64, s.descriptors_size);
  n64++;
  EXPECT_EQ(n64, s.rollback_index);
  n64++;
  EXPECT_EQ(n32, s.flags);
  n32++;

  // If new fields are added, the following will fail. This is to
  // remind that byteswapping code (in avb_util.c) and unittests for
  // this should be updated.
  static_assert(offsetof(AvbVBMetaImageHeader, reserved) == 176,
                "Remember to unittest byteswapping of newly added fields");
}

}  // namespace avb
