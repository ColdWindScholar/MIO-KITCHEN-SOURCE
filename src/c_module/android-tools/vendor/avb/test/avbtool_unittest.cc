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
#include <base/strings/string_split.h>
#include <base/strings/string_util.h>
#include <base/strings/stringprintf.h>

#include <libavb/avb_sha.h>
#include <libavb/libavb.h>

#include "avb_unittest_util.h"
#include "fake_avb_ops.h"

namespace avb {

class AvbToolTest : public BaseAvbToolTest {
 public:
  AvbToolTest() {}

  virtual void SetUp() override {
    BaseAvbToolTest::SetUp();
    ops_.set_partition_dir(testdir_);
    ops_.set_stored_rollback_indexes({{0, 0}, {1, 0}, {2, 0}, {3, 0}});
    ops_.set_stored_is_device_unlocked(false);
  }

  void AddHashFooterTest(bool sparse_image);
  void CreateRootfsWithHashtreeFooter(bool sparse_image,
                                      const std::string& hash_algorithm,
                                      const std::string& root_digest,
                                      base::FilePath* rootfs_path);
  void AddHashtreeFooterTest(bool sparse_image);
  void AddHashtreeFooterFECTest(bool sparse_image);

  void GenerateImageWithHashAndHashtreeSetup();

  FakeAvbOps ops_;
};

// This test ensure that the version is increased in both
// avb_boot_image.h and the avb tool.
TEST_F(AvbToolTest, AvbVersionInSync) {
  base::FilePath path = testdir_.Append("version.txt");
  EXPECT_COMMAND(0, "./avbtool.py version > %s", path.value().c_str());
  std::string printed_version;
  ASSERT_TRUE(base::ReadFileToString(path, &printed_version));
  base::TrimWhitespaceASCII(printed_version, base::TRIM_ALL, &printed_version);
  // See comments in libavb/avb_version.c and avbtool's get_release_string()
  // about being in sync.
  EXPECT_EQ(printed_version,
            std::string("avbtool ") + std::string(avb_version_string()));
}

TEST_F(AvbToolTest, DefaultReleaseString) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"));

  // Default release string is "avbtool " + avb_version_string().
  AvbVBMetaImageHeader h;
  avb_vbmeta_image_header_to_host_byte_order(
      reinterpret_cast<AvbVBMetaImageHeader*>(vbmeta_image_.data()), &h);
  EXPECT_EQ(std::string("avbtool ") + std::string(avb_version_string()),
            std::string((const char*)h.release_string));
}

TEST_F(AvbToolTest, ReleaseStringAppend) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"),
                      "--append_to_release_string \"Woot XYZ\"");

  // Note that avbtool inserts the space by itself.
  std::string expected_str =
      std::string("avbtool ") + std::string(avb_version_string()) + " Woot XYZ";

  AvbVBMetaImageHeader h;
  avb_vbmeta_image_header_to_host_byte_order(
      reinterpret_cast<AvbVBMetaImageHeader*>(vbmeta_image_.data()), &h);
  EXPECT_EQ(expected_str, std::string((const char*)h.release_string));
}

TEST_F(AvbToolTest, ReleaseStringAppendTruncated) {
  // Append enough text that truncation is sure to happen.
  std::string append_str = "0123456789abcdef0123456789abcdef0123456789abcdef";
  std::string expected_str = std::string("avbtool ") +
                             std::string(avb_version_string()) + " " +
                             append_str;
  EXPECT_GT(expected_str.size(), (size_t)(AVB_RELEASE_STRING_SIZE - 1));
  expected_str.resize(AVB_RELEASE_STRING_SIZE - 1);

  GenerateVBMetaImage(
      "vbmeta.img",
      "SHA256_RSA2048",
      0,
      base::FilePath("test/data/testkey_rsa2048.pem"),
      std::string("--append_to_release_string \"") + append_str + "\"");

  // This checks that it ends with a NUL byte.
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_OK,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), nullptr, nullptr));

  // For good measure we also check here.
  AvbVBMetaImageHeader h;
  avb_vbmeta_image_header_to_host_byte_order(
      reinterpret_cast<AvbVBMetaImageHeader*>(vbmeta_image_.data()), &h);
  EXPECT_EQ(expected_str, std::string((const char*)h.release_string));
}

TEST_F(AvbToolTest, ExtractPublicKey) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"),
                      "--internal_release_string \"\"");

  std::string key_data =
      PublicKeyAVB(base::FilePath("test/data/testkey_rsa2048.pem"));

  AvbVBMetaImageHeader h;
  avb_vbmeta_image_header_to_host_byte_order(
      reinterpret_cast<AvbVBMetaImageHeader*>(vbmeta_image_.data()), &h);
  uint8_t* d = reinterpret_cast<uint8_t*>(vbmeta_image_.data());
  size_t auxiliary_data_block_offset =
      sizeof(AvbVBMetaImageHeader) + h.authentication_data_block_size;
  EXPECT_GT(h.auxiliary_data_block_size, key_data.size());
  EXPECT_EQ(0,
            memcmp(key_data.data(),
                   d + auxiliary_data_block_offset + h.public_key_offset,
                   key_data.size()));
}

TEST_F(AvbToolTest, CheckDescriptors) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"),
                      "--prop foo:brillo "
                      "--prop bar:chromeos "
                      "--prop prisoner:24601 "
                      "--prop hexnumber:0xcafe "
                      "--prop hexnumber_capital:0xCAFE "
                      "--prop large_hexnumber:0xfedcba9876543210 "
                      "--prop larger_than_uint64:0xfedcba98765432101 "
                      "--prop almost_a_number:423x "
                      "--prop_from_file blob:test/data/small_blob.bin "
                      "--internal_release_string \"\"");

  AvbVBMetaImageHeader h;
  avb_vbmeta_image_header_to_host_byte_order(
      reinterpret_cast<AvbVBMetaImageHeader*>(vbmeta_image_.data()), &h);

  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_OK,
            avb_vbmeta_image_verify(
                vbmeta_image_.data(), vbmeta_image_.size(), nullptr, nullptr));

  const char* s;
  size_t len;
  uint64_t val;

  // Basic.
  s = avb_property_lookup(
      vbmeta_image_.data(), vbmeta_image_.size(), "foo", 0, &len);
  EXPECT_EQ(0, strcmp(s, "brillo"));
  EXPECT_EQ(6U, len);
  s = avb_property_lookup(
      vbmeta_image_.data(), vbmeta_image_.size(), "bar", 0, &len);
  EXPECT_EQ(0, strcmp(s, "chromeos"));
  EXPECT_EQ(8U, len);
  s = avb_property_lookup(
      vbmeta_image_.data(), vbmeta_image_.size(), "non-existant", 0, &len);
  EXPECT_EQ(0U, len);
  EXPECT_EQ(NULL, s);

  // Numbers.
  EXPECT_NE(
      0,
      avb_property_lookup_uint64(
          vbmeta_image_.data(), vbmeta_image_.size(), "prisoner", 0, &val));
  EXPECT_EQ(24601U, val);

  EXPECT_NE(
      0,
      avb_property_lookup_uint64(
          vbmeta_image_.data(), vbmeta_image_.size(), "hexnumber", 0, &val));
  EXPECT_EQ(0xcafeU, val);

  EXPECT_NE(0,
            avb_property_lookup_uint64(vbmeta_image_.data(),
                                       vbmeta_image_.size(),
                                       "hexnumber_capital",
                                       0,
                                       &val));
  EXPECT_EQ(0xcafeU, val);

  EXPECT_NE(0,
            avb_property_lookup_uint64(vbmeta_image_.data(),
                                       vbmeta_image_.size(),
                                       "large_hexnumber",
                                       0,
                                       &val));
  EXPECT_EQ(0xfedcba9876543210U, val);

  // We could catch overflows and return an error ... but we currently don't.
  EXPECT_NE(0,
            avb_property_lookup_uint64(vbmeta_image_.data(),
                                       vbmeta_image_.size(),
                                       "larger_than_uint64",
                                       0,
                                       &val));
  EXPECT_EQ(0xedcba98765432101U, val);

  // Number-parsing failures.
  EXPECT_EQ(0,
            avb_property_lookup_uint64(
                vbmeta_image_.data(), vbmeta_image_.size(), "foo", 0, &val));

  EXPECT_EQ(0,
            avb_property_lookup_uint64(vbmeta_image_.data(),
                                       vbmeta_image_.size(),
                                       "almost_a_number",
                                       0,
                                       &val));

  // Blobs.
  //
  // test/data/small_blob.bin is 21 byte file full of NUL-bytes except
  // for the string "brillo ftw!" at index 2 and '\n' at the last
  // byte.
  s = avb_property_lookup(
      vbmeta_image_.data(), vbmeta_image_.size(), "blob", 0, &len);
  EXPECT_EQ(21U, len);
  EXPECT_EQ(0, memcmp(s, "\0\0", 2));
  EXPECT_EQ(0, memcmp(s + 2, "brillo ftw!", 11));
  EXPECT_EQ(0, memcmp(s + 13, "\0\0\0\0\0\0\0", 7));
  EXPECT_EQ('\n', s[20]);
}

TEST_F(AvbToolTest, Padding) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"),
                      "--internal_release_string \"\"");

  GenerateVBMetaImage("vbmeta_padded.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"),
                      "--internal_release_string \"\" --padding_size 4096");

  base::FilePath vbmeta_path = testdir_.Append("vbmeta.img");
  base::FilePath vbmeta_padded_path = testdir_.Append("vbmeta_padded.img");
  int64_t vbmeta_size, vbmeta_padded_size;
  ASSERT_TRUE(base::GetFileSize(vbmeta_path, &vbmeta_size));
  ASSERT_TRUE(base::GetFileSize(vbmeta_padded_path, &vbmeta_padded_size));

  EXPECT_NE(vbmeta_size, vbmeta_padded_size);

  // The padded size should be a multiple of 4096.
  EXPECT_EQ(vbmeta_padded_size % 4096, 0);

  // When rounded up the unpadded size should equal the padded size.
  int64_t vbmeta_size_rounded_up = ((vbmeta_size + 4095) / 4096) * 4096;
  EXPECT_EQ(vbmeta_size_rounded_up, vbmeta_padded_size);
}

TEST_F(AvbToolTest, CheckRollbackIndex) {
  uint64_t rollback_index = 42;
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      rollback_index,
                      base::FilePath("test/data/testkey_rsa2048.pem"),
                      "--internal_release_string \"\"");

  AvbVBMetaImageHeader h;
  avb_vbmeta_image_header_to_host_byte_order(
      reinterpret_cast<AvbVBMetaImageHeader*>(vbmeta_image_.data()), &h);

  EXPECT_EQ(rollback_index, h.rollback_index);
}

TEST_F(AvbToolTest, CheckRollbackIndexLocationOmitted) {
  uint32_t expected_rollback_index_location = 0;

  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"),
                      "--internal_release_string \"\"");

  AvbVBMetaImageHeader h;
  avb_vbmeta_image_header_to_host_byte_order(
      reinterpret_cast<AvbVBMetaImageHeader*>(vbmeta_image_.data()), &h);

  EXPECT_EQ(expected_rollback_index_location, h.rollback_index_location);
  EXPECT_EQ(1u, h.required_libavb_version_major);
  EXPECT_EQ(0u, h.required_libavb_version_minor);
}

TEST_F(AvbToolTest, CheckRollbackIndexLocation) {
  uint32_t rollback_index_location = 42;
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"),
                      base::StringPrintf("--rollback_index_location %d",
                                         rollback_index_location));

  AvbVBMetaImageHeader h;
  avb_vbmeta_image_header_to_host_byte_order(
      reinterpret_cast<AvbVBMetaImageHeader*>(vbmeta_image_.data()), &h);

  EXPECT_EQ(rollback_index_location, h.rollback_index_location);
  EXPECT_EQ(1u, h.required_libavb_version_major);
  EXPECT_EQ(2u, h.required_libavb_version_minor);
}

TEST_F(AvbToolTest, CheckPubkeyReturned) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"),
                      "--internal_release_string \"\"");

  const uint8_t* pubkey = NULL;
  size_t pubkey_length = 0;

  EXPECT_EQ(
      AVB_VBMETA_VERIFY_RESULT_OK,
      avb_vbmeta_image_verify(
          vbmeta_image_.data(), vbmeta_image_.size(), &pubkey, &pubkey_length));

  AvbVBMetaImageHeader h;
  avb_vbmeta_image_header_to_host_byte_order(
      reinterpret_cast<AvbVBMetaImageHeader*>(vbmeta_image_.data()), &h);

  EXPECT_EQ(pubkey_length, h.public_key_size);

  const uint8_t* expected_pubkey =
      vbmeta_image_.data() + sizeof(AvbVBMetaImageHeader) +
      h.authentication_data_block_size + h.public_key_offset;
  EXPECT_EQ(pubkey, expected_pubkey);
}

TEST_F(AvbToolTest, Info) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"),
                      "--prop foo:brillo "
                      "--prop bar:chromeos "
                      "--prop prisoner:24601 "
                      "--prop hexnumber:0xcafe "
                      "--prop hexnumber_capital:0xCAFE "
                      "--prop large_hexnumber:0xfedcba9876543210 "
                      "--prop larger_than_uint64:0xfedcba98765432101 "
                      "--prop almost_a_number:423x "
                      "--prop_from_file blob:test/data/small_blob.bin "
                      "--prop_from_file large_blob:test/data/large_blob.bin "
                      "--internal_release_string \"\"");

  ASSERT_EQ(
      "Minimum libavb version:   1.0\n"
      "Header Block:             256 bytes\n"
      "Authentication Block:     320 bytes\n"
      "Auxiliary Block:          3200 bytes\n"
      "Public key (sha1):        cdbb77177f731920bbe0a0f94f84d9038ae0617d\n"
      "Algorithm:                SHA256_RSA2048\n"
      "Rollback Index:           0\n"
      "Flags:                    0\n"
      "Rollback Index Location:  0\n"
      "Release String:           ''\n"
      "Descriptors:\n"
      "    Prop: foo -> 'brillo'\n"
      "    Prop: bar -> 'chromeos'\n"
      "    Prop: prisoner -> '24601'\n"
      "    Prop: hexnumber -> '0xcafe'\n"
      "    Prop: hexnumber_capital -> '0xCAFE'\n"
      "    Prop: large_hexnumber -> '0xfedcba9876543210'\n"
      "    Prop: larger_than_uint64 -> '0xfedcba98765432101'\n"
      "    Prop: almost_a_number -> '423x'\n"
      "    Prop: blob -> '\\x00\\x00brillo "
      "ftw!\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\n'\n"
      "    Prop: large_blob -> (2048 bytes)\n",
      InfoImage(vbmeta_image_path_));
}

static bool collect_descriptors(const AvbDescriptor* descriptor,
                                void* user_data) {
  std::vector<const AvbDescriptor*>* descriptors =
      reinterpret_cast<std::vector<const AvbDescriptor*>*>(user_data);
  descriptors->push_back(descriptor);
  return true;  // Keep iterating.
}

static std::string AddHashFooterGetExpectedVBMetaInfo(
    const bool sparse_image, const uint64_t partition_size) {
  return base::StringPrintf(
      "Footer version:           1.0\n"
      "Image size:               %" PRIu64
      " bytes\n"
      "Original image size:      1052672 bytes\n"
      "VBMeta offset:            1052672\n"
      "VBMeta size:              1280 bytes\n"
      "--\n"
      "Minimum libavb version:   1.0%s\n"
      "Header Block:             256 bytes\n"
      "Authentication Block:     320 bytes\n"
      "Auxiliary Block:          704 bytes\n"
      "Public key (sha1):        cdbb77177f731920bbe0a0f94f84d9038ae0617d\n"
      "Algorithm:                SHA256_RSA2048\n"
      "Rollback Index:           0\n"
      "Flags:                    0\n"
      "Rollback Index Location:  0\n"
      "Release String:           ''\n"
      "Descriptors:\n"
      "    Hash descriptor:\n"
      "      Image Size:            1052672 bytes\n"
      "      Hash Algorithm:        sha256\n"
      "      Partition Name:        foobar\n"
      "      Salt:                  d00df00d\n"
      "      Digest:                "
      "9a58cc996d405e08a1e00f96dbfe9104fedf41cb83b1f"
      "5e4ed357fbcf58d88d9\n"
      "      Flags:                 0\n",
      partition_size,
      sparse_image ? " (Sparse)" : "");
}

void AvbToolTest::AddHashFooterTest(bool sparse_image) {
  const size_t rootfs_size = 1028 * 1024;
  const size_t partition_size = 1536 * 1024;
  const size_t resized_partition_size = 1280 * 1024;

  // Generate a 1028 KiB file with known content. Some content have
  // been arranged to ensure FILL_DATA segments in the sparse file.
  std::vector<uint8_t> rootfs;
  rootfs.resize(rootfs_size);
  for (size_t n = 0; n < rootfs_size; n++) {
    if ((n >= 5 * 1000 && n < 105 * 1000) ||
        (n >= 205 * 1000 && n < 305 * 1000) ||
        (n >= 505 * 1000 && n < 605 * 1000)) {
      rootfs[n] = uint8_t(n) & 0x03;
    } else {
      rootfs[n] = uint8_t(n);
    }
  }
  base::FilePath external_vbmeta_path = testdir_.Append("external_vbmeta.bin");
  base::FilePath extracted_vbmeta_path =
      testdir_.Append("extracted_vbmeta.bin");
  base::FilePath rootfs_path = testdir_.Append("rootfs.bin");
  EXPECT_EQ(rootfs_size,
            static_cast<const size_t>(
                base::WriteFile(rootfs_path,
                                reinterpret_cast<const char*>(rootfs.data()),
                                rootfs.size())));

  if (sparse_image) {
    EXPECT_COMMAND(0,
                   "mv %s %s.unsparse",
                   rootfs_path.value().c_str(),
                   rootfs_path.value().c_str());
    EXPECT_COMMAND(0,
                   "img2simg %s.unsparse %s",
                   rootfs_path.value().c_str(),
                   rootfs_path.value().c_str());
    EXPECT_COMMAND(0, "rm -f %s.unsparse", rootfs_path.value().c_str());
  }

  /* Do this twice to check that 'add_hash_footer' is idempotent. */
  for (int n = 0; n < 2; n++) {
    EXPECT_COMMAND(0,
                   "./avbtool.py add_hash_footer --salt d00df00d "
                   "--hash_algorithm sha256 --image %s "
                   "--partition_size %d --partition_name foobar "
                   "--algorithm SHA256_RSA2048 "
                   "--key test/data/testkey_rsa2048.pem "
                   "--output_vbmeta %s "
                   "--internal_release_string \"\"",
                   rootfs_path.value().c_str(),
                   (int)partition_size,
                   external_vbmeta_path.value().c_str());

    ASSERT_EQ(AddHashFooterGetExpectedVBMetaInfo(sparse_image, partition_size),
              InfoImage(rootfs_path));

    ASSERT_EQ(
        "Minimum libavb version:   1.0\n"
        "Header Block:             256 bytes\n"
        "Authentication Block:     320 bytes\n"
        "Auxiliary Block:          704 bytes\n"
        "Public key (sha1):        cdbb77177f731920bbe0a0f94f84d9038ae0617d\n"
        "Algorithm:                SHA256_RSA2048\n"
        "Rollback Index:           0\n"
        "Flags:                    0\n"
        "Rollback Index Location:  0\n"
        "Release String:           ''\n"
        "Descriptors:\n"
        "    Hash descriptor:\n"
        "      Image Size:            1052672 bytes\n"
        "      Hash Algorithm:        sha256\n"
        "      Partition Name:        foobar\n"
        "      Salt:                  d00df00d\n"
        "      Digest:                "
        "9a58cc996d405e08a1e00f96dbfe9104fedf41cb83b1f"
        "5e4ed357fbcf58d88d9\n"
        "      Flags:                 0\n",
        InfoImage(external_vbmeta_path));

    // Check that the extracted vbmeta matches the externally generally one.
    EXPECT_COMMAND(0,
                   "./avbtool.py extract_vbmeta_image --image %s "
                   "--output %s",
                   rootfs_path.value().c_str(),
                   extracted_vbmeta_path.value().c_str());
    EXPECT_COMMAND(0,
                   "diff %s %s",
                   external_vbmeta_path.value().c_str(),
                   extracted_vbmeta_path.value().c_str());
  }

  // Resize the image and check that the only thing that has changed
  // is where the footer is. First check that resizing to a smaller
  // size than the original rootfs fails. Then resize to something
  // larger than the original rootfs but smaller than the current
  // partition size.
  EXPECT_COMMAND(1,
                 "./avbtool.py resize_image --image %s "
                 "--partition_size %d",
                 rootfs_path.value().c_str(),
                 (int)(rootfs_size - 16 * 1024));
  EXPECT_COMMAND(0,
                 "./avbtool.py resize_image --image %s "
                 "--partition_size %d",
                 rootfs_path.value().c_str(),
                 (int)resized_partition_size);
  ASSERT_EQ(
      AddHashFooterGetExpectedVBMetaInfo(sparse_image, resized_partition_size),
      InfoImage(rootfs_path));

  if (sparse_image) {
    EXPECT_COMMAND(0,
                   "mv %s %s.sparse",
                   rootfs_path.value().c_str(),
                   rootfs_path.value().c_str());
    EXPECT_COMMAND(0,
                   "simg2img %s.sparse %s",
                   rootfs_path.value().c_str(),
                   rootfs_path.value().c_str());
    EXPECT_COMMAND(0, "rm -f %s.sparse", rootfs_path.value().c_str());
  }

  // Manually calculate the hash to check that it agrees with avbtool.
  AvbSHA256Ctx hasher_ctx;
  const uint8_t hasher_salt[4] = {0xd0, 0x0d, 0xf0, 0x0d};
  avb_sha256_init(&hasher_ctx);
  avb_sha256_update(&hasher_ctx, hasher_salt, 4);
  avb_sha256_update(&hasher_ctx, rootfs.data(), rootfs_size);
  uint8_t* hasher_digest = avb_sha256_final(&hasher_ctx);
  EXPECT_EQ("9a58cc996d405e08a1e00f96dbfe9104fedf41cb83b1f5e4ed357fbcf58d88d9",
            mem_to_hexstring(hasher_digest, AVB_SHA256_DIGEST_SIZE));

  // Now check that we can find the VBMeta block again from the footer.
  std::string part_data;
  ASSERT_TRUE(base::ReadFileToString(rootfs_path, &part_data));

  // Check footer contains correct data.
  AvbFooter f;
  EXPECT_NE(0,
            avb_footer_validate_and_byteswap(
                reinterpret_cast<const AvbFooter*>(
                    part_data.data() + part_data.size() - AVB_FOOTER_SIZE),
                &f));
  EXPECT_EQ(
      std::string(reinterpret_cast<const char*>(f.magic), AVB_FOOTER_MAGIC_LEN),
      AVB_FOOTER_MAGIC);
  EXPECT_EQ(AVB_FOOTER_VERSION_MAJOR, (int)f.version_major);
  EXPECT_EQ(AVB_FOOTER_VERSION_MINOR, (int)f.version_minor);
  EXPECT_EQ(1052672UL, f.original_image_size);
  EXPECT_EQ(1052672UL, f.vbmeta_offset);
  EXPECT_EQ(1280UL, f.vbmeta_size);

  // Check that the vbmeta image at |f.vbmeta_offset| checks out.
  const uint8_t* vbmeta_data =
      reinterpret_cast<const uint8_t*>(part_data.data() + f.vbmeta_offset);
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_OK,
            avb_vbmeta_image_verify(vbmeta_data, f.vbmeta_size, NULL, NULL));

  // Collect all descriptors.
  std::vector<const AvbDescriptor*> descriptors;
  avb_descriptor_foreach(
      vbmeta_data, f.vbmeta_size, collect_descriptors, &descriptors);

  // We should only have a single descriptor and it should be a
  // hash descriptor.
  EXPECT_EQ(1UL, descriptors.size());
  EXPECT_EQ(AVB_DESCRIPTOR_TAG_HASH, avb_be64toh(descriptors[0]->tag));
  AvbHashDescriptor d;
  EXPECT_NE(
      0,
      avb_hash_descriptor_validate_and_byteswap(
          reinterpret_cast<const AvbHashDescriptor*>(descriptors[0]), &d));
  EXPECT_EQ(1052672UL, d.image_size);
  EXPECT_EQ(6UL, d.partition_name_len);
  EXPECT_EQ(4UL, d.salt_len);
  EXPECT_EQ(32UL, d.digest_len);
  const uint8_t* desc_end = reinterpret_cast<const uint8_t*>(descriptors[0]) +
                            sizeof(AvbHashDescriptor);
  uint64_t o = 0;
  EXPECT_EQ("foobar",
            std::string(reinterpret_cast<const char*>(desc_end + o),
                        d.partition_name_len));
  o += d.partition_name_len;
  EXPECT_EQ("d00df00d", mem_to_hexstring(desc_end + o, d.salt_len));
  o += d.salt_len;
  EXPECT_EQ("9a58cc996d405e08a1e00f96dbfe9104fedf41cb83b1f5e4ed357fbcf58d88d9",
            mem_to_hexstring(desc_end + o, d.digest_len));

  // Check that the footer is correctly erased.
  EXPECT_COMMAND(
      0, "./avbtool.py erase_footer --image %s", rootfs_path.value().c_str());
  int64_t erased_footer_file_size;
  ASSERT_TRUE(base::GetFileSize(rootfs_path, &erased_footer_file_size));
  EXPECT_EQ(static_cast<size_t>(erased_footer_file_size), rootfs_size);

  // Check that --do_not_append_vbmeta_image works as intended.
  // In this case we don't modify the input image so it should work read-only.
  EXPECT_COMMAND(0, "chmod a-w %s", rootfs_path.value().c_str());
  EXPECT_COMMAND(0,
                 "./avbtool.py add_hash_footer --salt d00df00d "
                 "--hash_algorithm sha256 --image %s "
                 "--partition_size %d --partition_name foobar "
                 "--algorithm SHA256_RSA2048 "
                 "--key test/data/testkey_rsa2048.pem "
                 "--output_vbmeta %s_2nd_run --do_not_append_vbmeta_image "
                 "--internal_release_string \"\"",
                 rootfs_path.value().c_str(),
                 (int)partition_size,
                 external_vbmeta_path.value().c_str());
  int64_t file_size;
  ASSERT_TRUE(base::GetFileSize(rootfs_path, &file_size));
  EXPECT_EQ(static_cast<size_t>(file_size), rootfs_size);
  EXPECT_COMMAND(0,
                 "diff %s %s_2nd_run",
                 external_vbmeta_path.value().c_str(),
                 external_vbmeta_path.value().c_str());
}

TEST_F(AvbToolTest, AddHashFooter) {
  AddHashFooterTest(false);
}

TEST_F(AvbToolTest, AddHashFooterSparse) {
  AddHashFooterTest(true);
}

static std::string RemoveLinesStartingWith(const std::string& str,
                                           const std::string& prefix) {
  std::vector<std::string> lines;
  std::string ret;

  lines = base::SplitString(
      str, "\n", base::KEEP_WHITESPACE, base::SPLIT_WANT_NONEMPTY);
  for (const std::string& line : lines) {
    if (!base::StartsWith(line, prefix, base::CompareCase::SENSITIVE)) {
      ret += line;
      ret += '\n';
    }
  }
  return ret;
}

// NOTE: make_ext4fs was removed and there is no replacement for how we use
// it... so this is currently disabled..
TEST_F(AvbToolTest, DISABLED_AddHashFooterSparseWithHoleAtTheEnd) {
  const size_t partition_size = 10 * 1024 * 1024;
  const size_t metadata_size = 128 * 1024;

  // It's not enough to run img2simg on a file with a lot of zeroes at
  // the end since that will turn up as "Fill with value (for value =
  // 0x00000000)" and not "Don't care". Instead, use make_ext4fs for
  // this since it will put a big hole (e.g. "Don't care" chunk) at
  // the end.
  base::FilePath partition_path = testdir_.Append("partition.bin");
  EXPECT_COMMAND(0,
                 "make_ext4fs -s -L test -l %zd %s",
                 partition_size - metadata_size,
                 partition_path.value().c_str());

  EXPECT_COMMAND(0,
                 "./avbtool.py add_hash_footer --salt d00df00d "
                 "--hash_algorithm sha256 --image %s "
                 "--partition_size %d --partition_name foobar "
                 "--algorithm SHA256_RSA2048 "
                 "--key test/data/testkey_rsa2048.pem "
                 "--internal_release_string \"\"",
                 partition_path.value().c_str(),
                 (int)partition_size);

  // Since we may be using an arbritary version of make_ext4fs
  // (because of different branches) the contents of the resulting
  // disk image may slightly change. It's enough to just remove the
  // "Digest:" line from the output to work around this.
  std::string info =
      RemoveLinesStartingWith(InfoImage(partition_path), "      Digest:");
  ASSERT_EQ(
      "Footer version:           1.0\n"
      "Image size:               10485760 bytes\n"
      "Original image size:      10354688 bytes\n"
      "VBMeta offset:            10354688\n"
      "VBMeta size:              1280 bytes\n"
      "--\n"
      "Minimum libavb version:   1.0 (Sparse)\n"
      "Header Block:             256 bytes\n"
      "Authentication Block:     320 bytes\n"
      "Auxiliary Block:          704 bytes\n"
      "Public key (sha1):        cdbb77177f731920bbe0a0f94f84d9038ae0617d\n"
      "Algorithm:                SHA256_RSA2048\n"
      "Rollback Index:           0\n"
      "Flags:                    0\n"
      "Rollback Index Location:  0\n"
      "Release String:           ''\n"
      "Descriptors:\n"
      "    Hash descriptor:\n"
      "      Image Size:            10354688 bytes\n"
      "      Hash Algorithm:        sha256\n"
      "      Partition Name:        foobar\n"
      "      Salt:                  d00df00d\n"
      "      Flags:                 0\n",
      info);

  EXPECT_COMMAND(0,
                 "mv %s %s.sparse",
                 partition_path.value().c_str(),
                 partition_path.value().c_str());
  EXPECT_COMMAND(0,
                 "simg2img %s.sparse %s",
                 partition_path.value().c_str(),
                 partition_path.value().c_str());
  EXPECT_COMMAND(0, "rm -f %s.sparse", partition_path.value().c_str());
}

TEST_F(AvbToolTest, AddHashFooterCalcMaxImageSize) {
  const size_t partition_size = 10 * 1024 * 1024;
  base::FilePath output_path = testdir_.Append("max_size.txt");

  EXPECT_COMMAND(0,
                 "./avbtool.py add_hash_footer "
                 "--partition_size %zd "
                 "--calc_max_image_size > %s",
                 partition_size,
                 output_path.value().c_str());
  std::string max_image_size_data;
  EXPECT_TRUE(base::ReadFileToString(output_path, &max_image_size_data));
  EXPECT_EQ("10416128\n", max_image_size_data);
  size_t max_image_size = atoll(max_image_size_data.c_str());

  // Metadata takes up 68 KiB.
  EXPECT_EQ(68 * 1024ULL, partition_size - max_image_size);

  // Check that we can add a hash footer for an image this size for
  // such a partition size.
  base::FilePath boot_path = GenerateImage("boot", max_image_size);
  EXPECT_COMMAND(0,
                 "./avbtool.py add_hash_footer"
                 " --image %s"
                 " --partition_name boot"
                 " --partition_size %zd"
                 " --salt deadbeef"
                 " --algorithm SHA512_RSA4096 "
                 " --key test/data/testkey_rsa4096.pem"
                 " --internal_release_string \"\"",
                 boot_path.value().c_str(),
                 partition_size);
}

TEST_F(AvbToolTest, AddHashFooterWithPersistentDigest) {
  size_t partition_size = 1024 * 1024;
  base::FilePath path = GenerateImage("digest_location", 1024);
  EXPECT_COMMAND(0,
                 "./avbtool.py add_hash_footer "
                 "--hash_algorithm sha256 --image %s "
                 "--partition_size %d --partition_name foobar "
                 "--algorithm SHA256_RSA2048 "
                 "--key test/data/testkey_rsa2048.pem "
                 "--internal_release_string \"\" "
                 "--use_persistent_digest",
                 path.value().c_str(),
                 (int)partition_size);
  // There are two important bits specific to these flags:
  //   Minimum libavb version = 1.1
  //   Hash descriptor -> Digest = (empty)
  ASSERT_EQ(
      "Footer version:           1.0\n"
      "Image size:               1048576 bytes\n"
      "Original image size:      1024 bytes\n"
      "VBMeta offset:            4096\n"
      "VBMeta size:              1280 bytes\n"
      "--\n"
      "Minimum libavb version:   1.1\n"
      "Header Block:             256 bytes\n"
      "Authentication Block:     320 bytes\n"
      "Auxiliary Block:          704 bytes\n"
      "Public key (sha1):        cdbb77177f731920bbe0a0f94f84d9038ae0617d\n"
      "Algorithm:                SHA256_RSA2048\n"
      "Rollback Index:           0\n"
      "Flags:                    0\n"
      "Rollback Index Location:  0\n"
      "Release String:           ''\n"
      "Descriptors:\n"
      "    Hash descriptor:\n"
      "      Image Size:            1024 bytes\n"
      "      Hash Algorithm:        sha256\n"
      "      Partition Name:        foobar\n"
      "      Salt:                  \n"
      "      Digest:                \n"
      "      Flags:                 0\n",
      InfoImage(path));
}

TEST_F(AvbToolTest, AddHashFooterWithNoAB) {
  size_t partition_size = 1024 * 1024;
  base::FilePath path = GenerateImage("digest_location", 1024);
  EXPECT_COMMAND(0,
                 "./avbtool.py add_hash_footer --salt d00df00d "
                 "--hash_algorithm sha256 --image %s "
                 "--partition_size %d --partition_name foobar "
                 "--algorithm SHA256_RSA2048 "
                 "--key test/data/testkey_rsa2048.pem "
                 "--internal_release_string \"\" "
                 "--do_not_use_ab",
                 path.value().c_str(),
                 (int)partition_size);
  // There are two important bits specific to these flags:
  //   Minimum libavb version = 1.1
  //   Hash descriptor -> Flags = 1
  ASSERT_EQ(
      "Footer version:           1.0\n"
      "Image size:               1048576 bytes\n"
      "Original image size:      1024 bytes\n"
      "VBMeta offset:            4096\n"
      "VBMeta size:              1280 bytes\n"
      "--\n"
      "Minimum libavb version:   1.1\n"
      "Header Block:             256 bytes\n"
      "Authentication Block:     320 bytes\n"
      "Auxiliary Block:          704 bytes\n"
      "Public key (sha1):        cdbb77177f731920bbe0a0f94f84d9038ae0617d\n"
      "Algorithm:                SHA256_RSA2048\n"
      "Rollback Index:           0\n"
      "Flags:                    0\n"
      "Rollback Index Location:  0\n"
      "Release String:           ''\n"
      "Descriptors:\n"
      "    Hash descriptor:\n"
      "      Image Size:            1024 bytes\n"
      "      Hash Algorithm:        sha256\n"
      "      Partition Name:        foobar\n"
      "      Salt:                  d00df00d\n"
      "      Digest:                "
      "91386fea3e251ad0c2cb6859e4f4772f37fdb69f17d46636ddc9e7fbfd3bf3d0\n"
      "      Flags:                 1\n",
      InfoImage(path));
}

TEST_F(AvbToolTest, AddHashFooterWithPersistentDigestAndNoAB) {
  size_t partition_size = 1024 * 1024;
  base::FilePath path = GenerateImage("digest_location", 1024);
  EXPECT_COMMAND(0,
                 "./avbtool.py add_hash_footer "
                 "--hash_algorithm sha256 --image %s "
                 "--partition_size %d --partition_name foobar "
                 "--algorithm SHA256_RSA2048 "
                 "--key test/data/testkey_rsa2048.pem "
                 "--internal_release_string \"\" "
                 "--use_persistent_digest --do_not_use_ab",
                 path.value().c_str(),
                 (int)partition_size);
  // There are three important bits specific to these flags:
  //   Minimum libavb version = 1.1
  //   Hash descriptor -> Digest = (empty)
  //   Hash descriptor -> Flags = 1
  ASSERT_EQ(
      "Footer version:           1.0\n"
      "Image size:               1048576 bytes\n"
      "Original image size:      1024 bytes\n"
      "VBMeta offset:            4096\n"
      "VBMeta size:              1280 bytes\n"
      "--\n"
      "Minimum libavb version:   1.1\n"
      "Header Block:             256 bytes\n"
      "Authentication Block:     320 bytes\n"
      "Auxiliary Block:          704 bytes\n"
      "Public key (sha1):        cdbb77177f731920bbe0a0f94f84d9038ae0617d\n"
      "Algorithm:                SHA256_RSA2048\n"
      "Rollback Index:           0\n"
      "Flags:                    0\n"
      "Rollback Index Location:  0\n"
      "Release String:           ''\n"
      "Descriptors:\n"
      "    Hash descriptor:\n"
      "      Image Size:            1024 bytes\n"
      "      Hash Algorithm:        sha256\n"
      "      Partition Name:        foobar\n"
      "      Salt:                  \n"
      "      Digest:                \n"
      "      Flags:                 1\n",
      InfoImage(path));
}

void AvbToolTest::CreateRootfsWithHashtreeFooter(
    bool sparse_image,
    const std::string& hash_algorithm,
    const std::string& root_digest,
    base::FilePath* output_rootfs_path) {
  const size_t rootfs_size = 1028 * 1024;
  const size_t partition_size = 1536 * 1024;

  // Generate a 1028 KiB file with known content.
  std::vector<uint8_t> rootfs;
  rootfs.resize(rootfs_size);
  for (size_t n = 0; n < rootfs_size; n++)
    rootfs[n] = uint8_t(n);
  base::FilePath external_vbmeta_path = testdir_.Append("external_vbmeta.bin");
  base::FilePath extracted_vbmeta_path =
      testdir_.Append("extracted_vbmeta.bin");
  base::FilePath rootfs_path = testdir_.Append("rootfs.bin");
  EXPECT_EQ(rootfs_size,
            static_cast<const size_t>(
                base::WriteFile(rootfs_path,
                                reinterpret_cast<const char*>(rootfs.data()),
                                rootfs.size())));

  if (sparse_image) {
    EXPECT_COMMAND(0,
                   "mv %s %s.unsparse",
                   rootfs_path.value().c_str(),
                   rootfs_path.value().c_str());
    EXPECT_COMMAND(0,
                   "img2simg %s.unsparse %s",
                   rootfs_path.value().c_str(),
                   rootfs_path.value().c_str());
    EXPECT_COMMAND(0, "rm -f %s.unsparse", rootfs_path.value().c_str());
  }

  /* Do this twice to check that 'add_hashtree_footer' is idempotent. */
  for (int n = 0; n < 2; n++) {
    EXPECT_COMMAND(0,
                   "./avbtool.py add_hashtree_footer --salt d00df00d --image %s "
                   "--hash_algorithm %s "
                   "--partition_size %d --partition_name foobar "
                   "--algorithm SHA256_RSA2048 "
                   "--key test/data/testkey_rsa2048.pem "
                   "--output_vbmeta_image %s "
                   "--internal_release_string \"\" "
                   "--do_not_generate_fec",
                   rootfs_path.value().c_str(),
                   hash_algorithm.c_str(),
                   (int)partition_size,
                   external_vbmeta_path.value().c_str());

    ASSERT_EQ(base::StringPrintf("Footer version:           1.0\n"
                                 "Image size:               1572864 bytes\n"
                                 "Original image size:      1052672 bytes\n"
                                 "VBMeta offset:            1069056\n"
                                 "VBMeta size:              1344 bytes\n"
                                 "--\n"
                                 "Minimum libavb version:   1.0%s\n"
                                 "Header Block:             256 bytes\n"
                                 "Authentication Block:     320 bytes\n"
                                 "Auxiliary Block:          768 bytes\n"
                                 "Public key (sha1):        "
                                 "cdbb77177f731920bbe0a0f94f84d9038ae0617d\n"
                                 "Algorithm:                SHA256_RSA2048\n"
                                 "Rollback Index:           0\n"
                                 "Flags:                    0\n"
                                 "Rollback Index Location:  0\n"
                                 "Release String:           ''\n"
                                 "Descriptors:\n"
                                 "    Hashtree descriptor:\n"
                                 "      Version of dm-verity:  1\n"
                                 "      Image Size:            1052672 bytes\n"
                                 "      Tree Offset:           1052672\n"
                                 "      Tree Size:             16384 bytes\n"
                                 "      Data Block Size:       4096 bytes\n"
                                 "      Hash Block Size:       4096 bytes\n"
                                 "      FEC num roots:         0\n"
                                 "      FEC offset:            0\n"
                                 "      FEC size:              0 bytes\n"
                                 "      Hash Algorithm:        %s\n"
                                 "      Partition Name:        foobar\n"
                                 "      Salt:                  d00df00d\n"
                                 "      Root Digest:           "
                                 "%s\n"
                                 "      Flags:                 0\n",
                                 sparse_image ? " (Sparse)" : "",
                                 hash_algorithm.c_str(),
                                 root_digest.c_str()),
              InfoImage(rootfs_path));

    ASSERT_EQ(base::StringPrintf("Minimum libavb version:   1.0\n"
                                 "Header Block:             256 bytes\n"
                                 "Authentication Block:     320 bytes\n"
                                 "Auxiliary Block:          768 bytes\n"
                                 "Public key (sha1):        "
                                 "cdbb77177f731920bbe0a0f94f84d9038ae0617d\n"
                                 "Algorithm:                SHA256_RSA2048\n"
                                 "Rollback Index:           0\n"
                                 "Flags:                    0\n"
                                 "Rollback Index Location:  0\n"
                                 "Release String:           ''\n"
                                 "Descriptors:\n"
                                 "    Hashtree descriptor:\n"
                                 "      Version of dm-verity:  1\n"
                                 "      Image Size:            1052672 bytes\n"
                                 "      Tree Offset:           1052672\n"
                                 "      Tree Size:             16384 bytes\n"
                                 "      Data Block Size:       4096 bytes\n"
                                 "      Hash Block Size:       4096 bytes\n"
                                 "      FEC num roots:         0\n"
                                 "      FEC offset:            0\n"
                                 "      FEC size:              0 bytes\n"
                                 "      Hash Algorithm:        %s\n"
                                 "      Partition Name:        foobar\n"
                                 "      Salt:                  d00df00d\n"
                                 "      Root Digest:           "
                                 "%s\n"
                                 "      Flags:                 0\n",
                                 hash_algorithm.c_str(),
                                 root_digest.c_str()),
              InfoImage(external_vbmeta_path));

    // Check that the extracted vbmeta matches the externally generally one.
    EXPECT_COMMAND(0,
                   "./avbtool.py extract_vbmeta_image --image %s "
                   "--output %s",
                   rootfs_path.value().c_str(),
                   extracted_vbmeta_path.value().c_str());
    EXPECT_COMMAND(0,
                   "diff %s %s",
                   external_vbmeta_path.value().c_str(),
                   extracted_vbmeta_path.value().c_str());
  }

  *output_rootfs_path = rootfs_path;
}

void AvbToolTest::AddHashtreeFooterTest(bool sparse_image) {
  base::FilePath rootfs_path;
  CreateRootfsWithHashtreeFooter(sparse_image,
                                 "sha1",
                                 "e811611467dcd6e8dc4324e45f706c2bdd51db67",
                                 &rootfs_path);

  /* Zero the hashtree on a copy of the image. */
  EXPECT_COMMAND(0,
                 "cp %s %s.zht",
                 rootfs_path.value().c_str(),
                 rootfs_path.value().c_str());
  EXPECT_COMMAND(0,
                 "./avbtool.py zero_hashtree --image %s.zht ",
                 rootfs_path.value().c_str());

  if (sparse_image) {
    EXPECT_COMMAND(0,
                   "mv %s %s.sparse",
                   rootfs_path.value().c_str(),
                   rootfs_path.value().c_str());
    EXPECT_COMMAND(0,
                   "simg2img %s.sparse %s",
                   rootfs_path.value().c_str(),
                   rootfs_path.value().c_str());
    EXPECT_COMMAND(0, "rm -f %s.sparse", rootfs_path.value().c_str());

    EXPECT_COMMAND(0,
                   "mv %s.zht %s.zht.sparse",
                   rootfs_path.value().c_str(),
                   rootfs_path.value().c_str());
    EXPECT_COMMAND(0,
                   "simg2img %s.zht.sparse %s.zht",
                   rootfs_path.value().c_str(),
                   rootfs_path.value().c_str());
    EXPECT_COMMAND(0, "rm -f %s.zht.sparse", rootfs_path.value().c_str());
  }

  // To check that we generate the correct hashtree we can use
  // veritysetup(1) - another codebase for working with dm-verity
  // hashtrees - to verify it.
  //
  // If we don't want to impose the requirement of having the
  // veritysetup(1) command available on builders we can comment this
  // out.
  EXPECT_COMMAND(0,
                 "veritysetup --no-superblock --format=1 --hash=sha1 "
                 "--data-block-size=4096 --hash-block-size=4096 "
                 "--salt=d00df00d "
                 "--data-blocks=257 "
                 "--hash-offset=1052672 "
                 "verify "
                 "%s %s "
                 "e811611467dcd6e8dc4324e45f706c2bdd51db67",
                 rootfs_path.value().c_str(),
                 rootfs_path.value().c_str());

  // Now check that we can find the VBMeta block again from the footer.
  std::string part_data;
  ASSERT_TRUE(base::ReadFileToString(rootfs_path, &part_data));

  // Also read the zeroed hash-tree version.
  std::string zht_part_data;
  ASSERT_TRUE(base::ReadFileToString(
      base::FilePath(rootfs_path.value() + ".zht"), &zht_part_data));

  // Check footer contains correct data.
  AvbFooter f;
  EXPECT_NE(0,
            avb_footer_validate_and_byteswap(
                reinterpret_cast<const AvbFooter*>(
                    part_data.data() + part_data.size() - AVB_FOOTER_SIZE),
                &f));
  EXPECT_EQ(
      std::string(reinterpret_cast<const char*>(f.magic), AVB_FOOTER_MAGIC_LEN),
      AVB_FOOTER_MAGIC);
  EXPECT_EQ(AVB_FOOTER_VERSION_MAJOR, (int)f.version_major);
  EXPECT_EQ(AVB_FOOTER_VERSION_MINOR, (int)f.version_minor);
  EXPECT_EQ(1052672UL, f.original_image_size);
  EXPECT_EQ(1069056UL, f.vbmeta_offset);
  EXPECT_EQ(1344UL, f.vbmeta_size);

  // Check that the vbmeta image at |f.vbmeta_offset| checks out.
  const uint8_t* vbmeta_data =
      reinterpret_cast<const uint8_t*>(part_data.data() + f.vbmeta_offset);
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_OK,
            avb_vbmeta_image_verify(vbmeta_data, f.vbmeta_size, NULL, NULL));

  // Collect all descriptors.
  std::vector<const AvbDescriptor*> descriptors;
  avb_descriptor_foreach(
      vbmeta_data, f.vbmeta_size, collect_descriptors, &descriptors);

  // We should only have a single descriptor and it should be a
  // hashtree descriptor.
  EXPECT_EQ(1UL, descriptors.size());
  EXPECT_EQ(AVB_DESCRIPTOR_TAG_HASHTREE, avb_be64toh(descriptors[0]->tag));
  AvbHashtreeDescriptor d;
  EXPECT_NE(
      0,
      avb_hashtree_descriptor_validate_and_byteswap(
          reinterpret_cast<const AvbHashtreeDescriptor*>(descriptors[0]), &d));
  EXPECT_EQ(1UL, d.dm_verity_version);
  EXPECT_EQ(1052672UL, d.image_size);
  EXPECT_EQ(1052672UL, d.tree_offset);
  EXPECT_EQ(16384UL, d.tree_size);
  EXPECT_EQ(4096UL, d.data_block_size);
  EXPECT_EQ(4096UL, d.hash_block_size);
  EXPECT_EQ(6UL, d.partition_name_len);
  EXPECT_EQ(4UL, d.salt_len);
  EXPECT_EQ(20UL, d.root_digest_len);
  const uint8_t* desc_end = reinterpret_cast<const uint8_t*>(descriptors[0]) +
                            sizeof(AvbHashtreeDescriptor);
  uint64_t o = 0;
  EXPECT_EQ("foobar",
            std::string(reinterpret_cast<const char*>(desc_end + o),
                        d.partition_name_len));
  o += d.partition_name_len;
  EXPECT_EQ("d00df00d", mem_to_hexstring(desc_end + o, d.salt_len));
  o += d.salt_len;
  EXPECT_EQ("e811611467dcd6e8dc4324e45f706c2bdd51db67",
            mem_to_hexstring(desc_end + o, d.root_digest_len));

  // Check that the zeroed hashtree version differ only by the hashtree + fec
  // being zeroed out.
  EXPECT_EQ(part_data.size(), zht_part_data.size());
  size_t zht_ht_begin = d.tree_offset;
  size_t zht_ht_end = zht_ht_begin + d.tree_size;
  size_t zht_fec_begin = zht_ht_end;
  size_t zht_fec_end = zht_fec_begin + d.fec_size;
  EXPECT_EQ(0, memcmp(part_data.data(), zht_part_data.data(), zht_ht_begin));
  EXPECT_NE(0,
            memcmp(part_data.data() + zht_ht_begin,
                   zht_part_data.data() + zht_ht_begin,
                   zht_fec_end - zht_ht_begin));
  EXPECT_EQ(0,
            memcmp(part_data.data() + zht_fec_end,
                   zht_part_data.data() + zht_fec_end,
                   zht_part_data.size() - zht_fec_end));
  EXPECT_EQ(0, strncmp(zht_part_data.data() + zht_ht_begin, "ZeRoHaSH", 8));
  for (size_t n = zht_ht_begin + 8; n < zht_ht_end; n++) {
    EXPECT_EQ(0, zht_part_data.data()[n]);
  }
  if (d.fec_size > 0) {
    EXPECT_EQ(0, strncmp(zht_part_data.data() + zht_fec_begin, "ZeRoHaSH", 8));
    for (size_t n = zht_fec_begin + 8; n < zht_fec_end; n++) {
      EXPECT_EQ(0, zht_part_data.data()[n]);
    }
  }

  // Check that we correctly generate dm-verity kernel cmdline
  // snippets, if requested.
  base::FilePath vbmeta_dmv_path = testdir_.Append("vbmeta_dm_verity_desc.bin");
  EXPECT_COMMAND(0,
                 "./avbtool.py make_vbmeta_image "
                 "--output %s "
                 "--setup_rootfs_from_kernel %s "
                 "--algorithm SHA256_RSA2048 "
                 "--key test/data/testkey_rsa2048.pem "
                 "--internal_release_string \"\"",
                 vbmeta_dmv_path.value().c_str(),
                 rootfs_path.value().c_str());

  ASSERT_EQ(
      "Minimum libavb version:   1.0\n"
      "Header Block:             256 bytes\n"
      "Authentication Block:     320 bytes\n"
      "Auxiliary Block:          896 bytes\n"
      "Public key (sha1):        cdbb77177f731920bbe0a0f94f84d9038ae0617d\n"
      "Algorithm:                SHA256_RSA2048\n"
      "Rollback Index:           0\n"
      "Flags:                    0\n"
      "Rollback Index Location:  0\n"
      "Release String:           ''\n"
      "Descriptors:\n"
      "    Kernel Cmdline descriptor:\n"
      "      Flags:                 1\n"
      "      Kernel Cmdline:        'dm=\"1 vroot none ro 1,0 2056 verity 1 "
      "PARTUUID=$(ANDROID_SYSTEM_PARTUUID) PARTUUID=$(ANDROID_SYSTEM_PARTUUID) "
      "4096 4096 257 257 sha1 e811611467dcd6e8dc4324e45f706c2bdd51db67 "
      "d00df00d 2 $(ANDROID_VERITY_MODE) ignore_zero_blocks\" root=/dev/dm-0'\n"
      "    Kernel Cmdline descriptor:\n"
      "      Flags:                 2\n"
      "      Kernel Cmdline:        "
      "'root=PARTUUID=$(ANDROID_SYSTEM_PARTUUID)'\n",
      InfoImage(vbmeta_dmv_path));

  // Check that the footer is correctly erased and the hashtree
  // remains - see above for why the constant 1069056 is used.
  EXPECT_COMMAND(0,
                 "./avbtool.py erase_footer --image %s --keep_hashtree",
                 rootfs_path.value().c_str());
  int64_t erased_footer_file_size;
  ASSERT_TRUE(base::GetFileSize(rootfs_path, &erased_footer_file_size));
  EXPECT_EQ(static_cast<size_t>(erased_footer_file_size), 1069056UL);

  const size_t rootfs_size = 1028 * 1024;
  const size_t partition_size = 1536 * 1024;
  base::FilePath external_vbmeta_path = testdir_.Append("external_vbmeta.bin");
  // Check that --do_not_append_vbmeta_image works as intended.
  //
  // For this we need to reset the size of the image to the original
  // size because it's not possible to identify the existing hashtree.
  EXPECT_COMMAND(
      0, "truncate -s %d %s", (int)rootfs_size, rootfs_path.value().c_str());
  EXPECT_COMMAND(0,
                 "./avbtool.py add_hashtree_footer --salt d00df00d --image %s "
                 "--partition_size %d --partition_name foobar "
                 "--algorithm SHA256_RSA2048 "
                 "--key test/data/testkey_rsa2048.pem "
                 "--output_vbmeta %s_2nd_run --do_not_append_vbmeta_image "
                 "--internal_release_string \"\" "
                 "--do_not_generate_fec",
                 rootfs_path.value().c_str(),
                 (int)partition_size,
                 external_vbmeta_path.value().c_str());
  int64_t file_size;
  ASSERT_TRUE(base::GetFileSize(rootfs_path, &file_size));
  EXPECT_EQ(static_cast<size_t>(file_size), 1069056UL);
  EXPECT_COMMAND(0,
                 "diff %s %s_2nd_run",
                 external_vbmeta_path.value().c_str(),
                 external_vbmeta_path.value().c_str());
}

TEST_F(AvbToolTest, AddHashtreeFooter) {
  AddHashtreeFooterTest(false);
}

TEST_F(AvbToolTest, AddHashtreeFooterSparse) {
  AddHashtreeFooterTest(true);
}

TEST_F(AvbToolTest, AddHashtreeFooterSparseWithBlake2b256) {
  base::FilePath rootfs_path;
  CreateRootfsWithHashtreeFooter(
      true,
      "blake2b-256",
      "9ed423dda921619181bf1889746fe2dd28ae1e673be8d802b4713122e3209513",
      &rootfs_path);
}

void AvbToolTest::AddHashtreeFooterFECTest(bool sparse_image) {
  const size_t rootfs_size = 1028 * 1024;
  const size_t partition_size = 1536 * 1024;

  // Generate a 1028 KiB file with known content.
  std::vector<uint8_t> rootfs;
  rootfs.resize(rootfs_size);
  for (size_t n = 0; n < rootfs_size; n++)
    rootfs[n] = uint8_t(n);
  base::FilePath rootfs_path = testdir_.Append("rootfs.bin");
  EXPECT_EQ(rootfs_size,
            static_cast<const size_t>(
                base::WriteFile(rootfs_path,
                                reinterpret_cast<const char*>(rootfs.data()),
                                rootfs.size())));

  if (sparse_image) {
    EXPECT_COMMAND(0,
                   "mv %s %s.unsparse",
                   rootfs_path.value().c_str(),
                   rootfs_path.value().c_str());
    EXPECT_COMMAND(0,
                   "img2simg %s.unsparse %s",
                   rootfs_path.value().c_str(),
                   rootfs_path.value().c_str());
    EXPECT_COMMAND(0, "rm -f %s.unsparse", rootfs_path.value().c_str());
  }

  /* Do this twice to check that 'add_hashtree_footer' is idempotent. */
  for (int n = 0; n < 2; n++) {
    EXPECT_COMMAND(0,
                   "./avbtool.py add_hashtree_footer --salt d00df00d --image %s "
                   "--partition_size %d --partition_name foobar "
                   "--algorithm SHA256_RSA2048 "
                   "--key test/data/testkey_rsa2048.pem "
                   "--internal_release_string \"\"",
                   rootfs_path.value().c_str(),
                   (int)partition_size);

    ASSERT_EQ(base::StringPrintf("Footer version:           1.0\n"
                                 "Image size:               1572864 bytes\n"
                                 "Original image size:      1052672 bytes\n"
                                 "VBMeta offset:            1085440\n"
                                 "VBMeta size:              1344 bytes\n"
                                 "--\n"
                                 "Minimum libavb version:   1.0%s\n"
                                 "Header Block:             256 bytes\n"
                                 "Authentication Block:     320 bytes\n"
                                 "Auxiliary Block:          768 bytes\n"
                                 "Public key (sha1):        "
                                 "cdbb77177f731920bbe0a0f94f84d9038ae0617d\n"
                                 "Algorithm:                SHA256_RSA2048\n"
                                 "Rollback Index:           0\n"
                                 "Flags:                    0\n"
                                 "Rollback Index Location:  0\n"
                                 "Release String:           ''\n"
                                 "Descriptors:\n"
                                 "    Hashtree descriptor:\n"
                                 "      Version of dm-verity:  1\n"
                                 "      Image Size:            1052672 bytes\n"
                                 "      Tree Offset:           1052672\n"
                                 "      Tree Size:             16384 bytes\n"
                                 "      Data Block Size:       4096 bytes\n"
                                 "      Hash Block Size:       4096 bytes\n"
                                 "      FEC num roots:         2\n"
                                 "      FEC offset:            1069056\n"
                                 "      FEC size:              16384 bytes\n"
                                 "      Hash Algorithm:        sha1\n"
                                 "      Partition Name:        foobar\n"
                                 "      Salt:                  d00df00d\n"
                                 "      Root Digest:           "
                                 "e811611467dcd6e8dc4324e45f706c2bdd51db67\n"
                                 "      Flags:                 0\n",
                                 sparse_image ? " (Sparse)" : ""),
              InfoImage(rootfs_path));
  }

  /* Zero the hashtree and FEC on a copy of the image. */
  EXPECT_COMMAND(0,
                 "cp %s %s.zht",
                 rootfs_path.value().c_str(),
                 rootfs_path.value().c_str());
  EXPECT_COMMAND(0,
                 "./avbtool.py zero_hashtree --image %s.zht ",
                 rootfs_path.value().c_str());

  if (sparse_image) {
    EXPECT_COMMAND(0,
                   "mv %s %s.sparse",
                   rootfs_path.value().c_str(),
                   rootfs_path.value().c_str());
    EXPECT_COMMAND(0,
                   "simg2img %s.sparse %s",
                   rootfs_path.value().c_str(),
                   rootfs_path.value().c_str());
    EXPECT_COMMAND(0, "rm -f %s.sparse", rootfs_path.value().c_str());

    EXPECT_COMMAND(0,
                   "mv %s.zht %s.zht.sparse",
                   rootfs_path.value().c_str(),
                   rootfs_path.value().c_str());
    EXPECT_COMMAND(0,
                   "simg2img %s.zht.sparse %s.zht",
                   rootfs_path.value().c_str(),
                   rootfs_path.value().c_str());
    EXPECT_COMMAND(0, "rm -f %s.zht.sparse", rootfs_path.value().c_str());
  }

  /* TODO: would be nice to verify that the FEC data is correct. */

  // Now check that we can find the VBMeta block again from the footer.
  std::string part_data;
  ASSERT_TRUE(base::ReadFileToString(rootfs_path, &part_data));

  // Also read the zeroed hash-tree version.
  std::string zht_part_data;
  ASSERT_TRUE(base::ReadFileToString(
      base::FilePath(rootfs_path.value() + ".zht"), &zht_part_data));

  // Check footer contains correct data.
  AvbFooter f;
  EXPECT_NE(0,
            avb_footer_validate_and_byteswap(
                reinterpret_cast<const AvbFooter*>(
                    part_data.data() + part_data.size() - AVB_FOOTER_SIZE),
                &f));
  EXPECT_EQ(
      std::string(reinterpret_cast<const char*>(f.magic), AVB_FOOTER_MAGIC_LEN),
      AVB_FOOTER_MAGIC);
  EXPECT_EQ(AVB_FOOTER_VERSION_MAJOR, (int)f.version_major);
  EXPECT_EQ(AVB_FOOTER_VERSION_MINOR, (int)f.version_minor);
  EXPECT_EQ(1052672UL, f.original_image_size);
  EXPECT_EQ(1085440UL, f.vbmeta_offset);
  EXPECT_EQ(1344UL, f.vbmeta_size);

  // Check that the vbmeta image at |f.vbmeta_offset| checks out.
  const uint8_t* vbmeta_data =
      reinterpret_cast<const uint8_t*>(part_data.data() + f.vbmeta_offset);
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_OK,
            avb_vbmeta_image_verify(vbmeta_data, f.vbmeta_size, NULL, NULL));

  // Collect all descriptors.
  std::vector<const AvbDescriptor*> descriptors;
  avb_descriptor_foreach(
      vbmeta_data, f.vbmeta_size, collect_descriptors, &descriptors);

  // We should only have a single descriptor and it should be a
  // hashtree descriptor.
  EXPECT_EQ(1UL, descriptors.size());
  EXPECT_EQ(AVB_DESCRIPTOR_TAG_HASHTREE, avb_be64toh(descriptors[0]->tag));
  AvbHashtreeDescriptor d;
  EXPECT_NE(
      0,
      avb_hashtree_descriptor_validate_and_byteswap(
          reinterpret_cast<const AvbHashtreeDescriptor*>(descriptors[0]), &d));
  EXPECT_EQ(1UL, d.dm_verity_version);
  EXPECT_EQ(1052672UL, d.image_size);
  EXPECT_EQ(1052672UL, d.tree_offset);
  EXPECT_EQ(16384UL, d.tree_size);
  EXPECT_EQ(4096UL, d.data_block_size);
  EXPECT_EQ(2UL, d.fec_num_roots);
  EXPECT_EQ(1069056UL, d.fec_offset);
  EXPECT_EQ(16384UL, d.fec_size);
  EXPECT_EQ(6UL, d.partition_name_len);
  EXPECT_EQ(4UL, d.salt_len);
  EXPECT_EQ(20UL, d.root_digest_len);
  const uint8_t* desc_end = reinterpret_cast<const uint8_t*>(descriptors[0]) +
                            sizeof(AvbHashtreeDescriptor);
  uint64_t o = 0;
  EXPECT_EQ("foobar",
            std::string(reinterpret_cast<const char*>(desc_end + o),
                        d.partition_name_len));
  o += d.partition_name_len;
  EXPECT_EQ("d00df00d", mem_to_hexstring(desc_end + o, d.salt_len));
  o += d.salt_len;
  EXPECT_EQ("e811611467dcd6e8dc4324e45f706c2bdd51db67",
            mem_to_hexstring(desc_end + o, d.root_digest_len));

  // Check that the zeroed hashtree version differ only by the hashtree + fec
  // being zeroed out.
  EXPECT_EQ(part_data.size(), zht_part_data.size());
  size_t zht_ht_begin = d.tree_offset;
  size_t zht_ht_end = zht_ht_begin + d.tree_size;
  size_t zht_fec_begin = zht_ht_end;
  size_t zht_fec_end = zht_fec_begin + d.fec_size;
  EXPECT_EQ(0, memcmp(part_data.data(), zht_part_data.data(), zht_ht_begin));
  EXPECT_NE(0,
            memcmp(part_data.data() + zht_ht_begin,
                   zht_part_data.data() + zht_ht_begin,
                   zht_fec_end - zht_ht_begin));
  EXPECT_EQ(0,
            memcmp(part_data.data() + zht_fec_end,
                   zht_part_data.data() + zht_fec_end,
                   zht_part_data.size() - zht_fec_end));
  EXPECT_EQ(0, strncmp(zht_part_data.data() + zht_ht_begin, "ZeRoHaSH", 8));
  for (size_t n = zht_ht_begin + 8; n < zht_ht_end; n++) {
    EXPECT_EQ(0, zht_part_data.data()[n]);
  }
  if (d.fec_size > 0) {
    EXPECT_EQ(0, strncmp(zht_part_data.data() + zht_fec_begin, "ZeRoHaSH", 8));
    for (size_t n = zht_fec_begin + 8; n < zht_fec_end; n++) {
      EXPECT_EQ(0, zht_part_data.data()[n]);
    }
  }

  // Check that we correctly generate dm-verity kernel cmdline
  // snippets, if requested.
  base::FilePath vbmeta_dmv_path = testdir_.Append("vbmeta_dm_verity_desc.bin");
  EXPECT_COMMAND(0,
                 "./avbtool.py make_vbmeta_image "
                 "--output %s "
                 "--setup_rootfs_from_kernel %s "
                 "--algorithm SHA256_RSA2048 "
                 "--key test/data/testkey_rsa2048.pem "
                 "--internal_release_string \"\"",
                 vbmeta_dmv_path.value().c_str(),
                 rootfs_path.value().c_str());

  ASSERT_EQ(
      "Minimum libavb version:   1.0\n"
      "Header Block:             256 bytes\n"
      "Authentication Block:     320 bytes\n"
      "Auxiliary Block:          960 bytes\n"
      "Public key (sha1):        cdbb77177f731920bbe0a0f94f84d9038ae0617d\n"
      "Algorithm:                SHA256_RSA2048\n"
      "Rollback Index:           0\n"
      "Flags:                    0\n"
      "Rollback Index Location:  0\n"
      "Release String:           ''\n"
      "Descriptors:\n"
      "    Kernel Cmdline descriptor:\n"
      "      Flags:                 1\n"
      "      Kernel Cmdline:        'dm=\"1 vroot none ro 1,0 2056 verity 1 "
      "PARTUUID=$(ANDROID_SYSTEM_PARTUUID) PARTUUID=$(ANDROID_SYSTEM_PARTUUID) "
      "4096 4096 257 257 sha1 e811611467dcd6e8dc4324e45f706c2bdd51db67 "
      "d00df00d 10 $(ANDROID_VERITY_MODE) ignore_zero_blocks "
      "use_fec_from_device "
      "PARTUUID=$(ANDROID_SYSTEM_PARTUUID) fec_roots 2 fec_blocks 261 "
      "fec_start 261\" root=/dev/dm-0'\n"
      "    Kernel Cmdline descriptor:\n"
      "      Flags:                 2\n"
      "      Kernel Cmdline:        "
      "'root=PARTUUID=$(ANDROID_SYSTEM_PARTUUID)'\n",
      InfoImage(vbmeta_dmv_path));

  // Check that the footer is correctly erased and the hashtree and
  // FEC data remains. The constant 1085440 is used because it's where
  // the FEC data ends (it's at offset 1069056 and size 16384).
  EXPECT_COMMAND(0,
                 "./avbtool.py erase_footer --image %s --keep_hashtree",
                 rootfs_path.value().c_str());
  int64_t erased_footer_file_size;
  ASSERT_TRUE(base::GetFileSize(rootfs_path, &erased_footer_file_size));
  EXPECT_EQ(static_cast<size_t>(erased_footer_file_size), 1085440UL);
}

TEST_F(AvbToolTest, AddHashtreeFooterFEC) {
  AddHashtreeFooterFECTest(false);
}

TEST_F(AvbToolTest, AddHashtreeFooterFECSparse) {
  AddHashtreeFooterFECTest(true);
}

TEST_F(AvbToolTest, AddHashtreeFooterCalcMaxImageSize) {
  const size_t partition_size = 10 * 1024 * 1024;
  base::FilePath output_path = testdir_.Append("max_size.txt");

  EXPECT_COMMAND(0,
                 "./avbtool.py add_hashtree_footer "
                 "--partition_size %zd --calc_max_image_size "
                 "--do_not_generate_fec > %s",
                 partition_size,
                 output_path.value().c_str());
  std::string max_image_size_data;
  EXPECT_TRUE(base::ReadFileToString(output_path, &max_image_size_data));
  EXPECT_EQ("10330112\n", max_image_size_data);
  size_t max_image_size = atoll(max_image_size_data.c_str());

  // Hashtree and metadata takes up 152 KiB - compare to below with
  // FEC which is 244 KiB.
  EXPECT_EQ(152 * 1024ULL, partition_size - max_image_size);

  // Check that we can add a hashtree with an image this size for such
  // a partition size.
  base::FilePath system_path = GenerateImage("system", max_image_size);
  EXPECT_COMMAND(0,
                 "./avbtool.py add_hashtree_footer"
                 " --image %s"
                 " --partition_name system"
                 " --partition_size %zd"
                 " --salt deadbeef"
                 " --algorithm SHA512_RSA4096 "
                 " --key test/data/testkey_rsa4096.pem"
                 " --internal_release_string \"\" "
                 "--do_not_generate_fec",
                 system_path.value().c_str(),
                 partition_size);
}

TEST_F(AvbToolTest, AddHashtreeFooterCalcMaxImageSizeWithFEC) {
  const size_t partition_size = 10 * 1024 * 1024;
  base::FilePath output_path = testdir_.Append("max_size.txt");

  EXPECT_COMMAND(0,
                 "./avbtool.py add_hashtree_footer "
                 "--partition_size %zd --calc_max_image_size > %s",
                 partition_size,
                 output_path.value().c_str());
  std::string max_image_size_data;
  EXPECT_TRUE(base::ReadFileToString(output_path, &max_image_size_data));
  EXPECT_EQ("10235904\n", max_image_size_data);
  size_t max_image_size = atoll(max_image_size_data.c_str());

  // Hashtree, FEC codes, and metadata takes up 244 KiB - compare to
  // above wihtout FEC which is 152 KiB.
  EXPECT_EQ(244 * 1024ULL, partition_size - max_image_size);

  // Check that we can add a hashtree with an image this size for such
  // a partition size.
  base::FilePath system_path = GenerateImage("system", max_image_size);
  EXPECT_COMMAND(0,
                 "./avbtool.py add_hashtree_footer"
                 " --image %s"
                 " --partition_name system"
                 " --partition_size %zd"
                 " --salt deadbeef"
                 " --algorithm SHA512_RSA4096 "
                 " --key test/data/testkey_rsa4096.pem"
                 " --internal_release_string \"\"",
                 system_path.value().c_str(),
                 partition_size);
}

TEST_F(AvbToolTest, AddHashtreeFooterCalcMaxImageSizeWithNoHashtree) {
  const size_t partition_size = 10 * 1024 * 1024;
  base::FilePath output_path = testdir_.Append("max_size.txt");

  EXPECT_COMMAND(0,
                 "./avbtool.py add_hashtree_footer "
                 "--no_hashtree "
                 "--partition_size %zd --calc_max_image_size > %s",
                 partition_size,
                 output_path.value().c_str());
  std::string max_image_size_data;
  EXPECT_TRUE(base::ReadFileToString(output_path, &max_image_size_data));
  EXPECT_EQ("10416128\n", max_image_size_data);
  size_t max_image_size = atoll(max_image_size_data.c_str());

  // vbmeta(64) + footer(4) takes up 68 KiB
  EXPECT_EQ(68 * 1024ULL, partition_size - max_image_size);

  // Check that we can add a hashtree with an image this size for such
  // a partition size.
  base::FilePath system_path = GenerateImage("system", max_image_size);
  EXPECT_COMMAND(0,
                 "./avbtool.py add_hashtree_footer"
                 " --image %s"
                 " --no_hashtree"
                 " --partition_name system"
                 " --partition_size %zd"
                 " --salt deadbeef"
                 " --algorithm SHA512_RSA4096 "
                 " --key test/data/testkey_rsa4096.pem"
                 " --internal_release_string \"\"",
                 system_path.value().c_str(),
                 partition_size);
  // with --no_hashtree, Tree/FEC sizes are 0 bytes
  ASSERT_EQ(
      "Footer version:           1.0\n"
      "Image size:               10485760 bytes\n"
      "Original image size:      10416128 bytes\n"
      "VBMeta offset:            10416128\n"
      "VBMeta size:              2112 bytes\n"
      "--\n"
      "Minimum libavb version:   1.0\n"
      "Header Block:             256 bytes\n"
      "Authentication Block:     576 bytes\n"
      "Auxiliary Block:          1280 bytes\n"
      "Public key (sha1):        2597c218aae470a130f61162feaae70afd97f011\n"
      "Algorithm:                SHA512_RSA4096\n"
      "Rollback Index:           0\n"
      "Flags:                    0\n"
      "Rollback Index Location:  0\n"
      "Release String:           ''\n"
      "Descriptors:\n"
      "    Hashtree descriptor:\n"
      "      Version of dm-verity:  1\n"
      "      Image Size:            10416128 bytes\n"
      "      Tree Offset:           10416128\n"
      "      Tree Size:             0 bytes\n"
      "      Data Block Size:       4096 bytes\n"
      "      Hash Block Size:       4096 bytes\n"
      "      FEC num roots:         2\n"
      "      FEC offset:            10416128\n"
      "      FEC size:              0 bytes\n"
      "      Hash Algorithm:        sha1\n"
      "      Partition Name:        system\n"
      "      Salt:                  deadbeef\n"
      "      Root Digest:           4215bd42bcc99636f42956ce3d2c7884d6a8093b\n"
      "      Flags:                 0\n",
      InfoImage(system_path));
}

TEST_F(AvbToolTest, AddHashtreeFooterWithPersistentDigest) {
  size_t partition_size = 10 * 1024 * 1024;
  base::FilePath path = GenerateImage("digest_location", partition_size / 2);
  EXPECT_COMMAND(0,
                 "./avbtool.py add_hashtree_footer "
                 "--hash_algorithm sha256 --image %s "
                 "--partition_size %d --partition_name foobar "
                 "--algorithm SHA256_RSA2048 "
                 "--key test/data/testkey_rsa2048.pem "
                 "--internal_release_string \"\" "
                 "--use_persistent_digest",
                 path.value().c_str(),
                 (int)partition_size);
  // There are two important bits here specific to --use_persistent_digest:
  //   Minimum libavb version = 1.1
  //   Hashtree descriptor -> Root Digest = (empty)
  ASSERT_EQ(
      "Footer version:           1.0\n"
      "Image size:               10485760 bytes\n"
      "Original image size:      5242880 bytes\n"
      "VBMeta offset:            5337088\n"
      "VBMeta size:              1344 bytes\n"
      "--\n"
      "Minimum libavb version:   1.1\n"
      "Header Block:             256 bytes\n"
      "Authentication Block:     320 bytes\n"
      "Auxiliary Block:          768 bytes\n"
      "Public key (sha1):        cdbb77177f731920bbe0a0f94f84d9038ae0617d\n"
      "Algorithm:                SHA256_RSA2048\n"
      "Rollback Index:           0\n"
      "Flags:                    0\n"
      "Rollback Index Location:  0\n"
      "Release String:           ''\n"
      "Descriptors:\n"
      "    Hashtree descriptor:\n"
      "      Version of dm-verity:  1\n"
      "      Image Size:            5242880 bytes\n"
      "      Tree Offset:           5242880\n"
      "      Tree Size:             45056 bytes\n"
      "      Data Block Size:       4096 bytes\n"
      "      Hash Block Size:       4096 bytes\n"
      "      FEC num roots:         2\n"
      "      FEC offset:            5287936\n"
      "      FEC size:              49152 bytes\n"
      "      Hash Algorithm:        sha256\n"
      "      Partition Name:        foobar\n"
      "      Salt:                  \n"
      "      Root Digest:           \n"
      "      Flags:                 0\n",
      InfoImage(path));
}

TEST_F(AvbToolTest, AddHashtreeFooterWithNoAB) {
  size_t partition_size = 10 * 1024 * 1024;
  base::FilePath path = GenerateImage("digest_location", partition_size / 2);
  EXPECT_COMMAND(0,
                 "./avbtool.py add_hashtree_footer --salt d00df00d "
                 "--hash_algorithm sha256 --image %s "
                 "--partition_size %d --partition_name foobar "
                 "--algorithm SHA256_RSA2048 "
                 "--key test/data/testkey_rsa2048.pem "
                 "--internal_release_string \"\" "
                 "--do_not_use_ab",
                 path.value().c_str(),
                 (int)partition_size);
  // There are two important bits here we're expecting with --do_not_use_ab:
  //   Minimum libavb version = 1.1
  //   Hashtree descriptor -> Flags = 1
  ASSERT_EQ(
      "Footer version:           1.0\n"
      "Image size:               10485760 bytes\n"
      "Original image size:      5242880 bytes\n"
      "VBMeta offset:            5337088\n"
      "VBMeta size:              1344 bytes\n"
      "--\n"
      "Minimum libavb version:   1.1\n"
      "Header Block:             256 bytes\n"
      "Authentication Block:     320 bytes\n"
      "Auxiliary Block:          768 bytes\n"
      "Public key (sha1):        cdbb77177f731920bbe0a0f94f84d9038ae0617d\n"
      "Algorithm:                SHA256_RSA2048\n"
      "Rollback Index:           0\n"
      "Flags:                    0\n"
      "Rollback Index Location:  0\n"
      "Release String:           ''\n"
      "Descriptors:\n"
      "    Hashtree descriptor:\n"
      "      Version of dm-verity:  1\n"
      "      Image Size:            5242880 bytes\n"
      "      Tree Offset:           5242880\n"
      "      Tree Size:             45056 bytes\n"
      "      Data Block Size:       4096 bytes\n"
      "      Hash Block Size:       4096 bytes\n"
      "      FEC num roots:         2\n"
      "      FEC offset:            5287936\n"
      "      FEC size:              49152 bytes\n"
      "      Hash Algorithm:        sha256\n"
      "      Partition Name:        foobar\n"
      "      Salt:                  d00df00d\n"
      "      Root Digest:           "
      "d0e31526f5a3f8e3f59acf726bd31ae7861ee78f9baa9195356bf479c6f9119d\n"
      "      Flags:                 1\n",
      InfoImage(path));
}

TEST_F(AvbToolTest, AddHashtreeFooterWithPersistentDigestAndNoAB) {
  size_t partition_size = 10 * 1024 * 1024;
  base::FilePath path = GenerateImage("digest_location", partition_size / 2);
  EXPECT_COMMAND(0,
                 "./avbtool.py add_hashtree_footer "
                 "--hash_algorithm sha256 --image %s "
                 "--partition_size %d --partition_name foobar "
                 "--algorithm SHA256_RSA2048 "
                 "--key test/data/testkey_rsa2048.pem "
                 "--internal_release_string \"\" "
                 "--use_persistent_digest --do_not_use_ab",
                 path.value().c_str(),
                 (int)partition_size);
  // There are three important bits specific to these flags:
  //   Minimum libavb version = 1.1
  //   Hashtree descriptor -> Root Digest = (empty)
  //   Hashtree descriptor -> Flags = 1
  ASSERT_EQ(
      "Footer version:           1.0\n"
      "Image size:               10485760 bytes\n"
      "Original image size:      5242880 bytes\n"
      "VBMeta offset:            5337088\n"
      "VBMeta size:              1344 bytes\n"
      "--\n"
      "Minimum libavb version:   1.1\n"
      "Header Block:             256 bytes\n"
      "Authentication Block:     320 bytes\n"
      "Auxiliary Block:          768 bytes\n"
      "Public key (sha1):        cdbb77177f731920bbe0a0f94f84d9038ae0617d\n"
      "Algorithm:                SHA256_RSA2048\n"
      "Rollback Index:           0\n"
      "Flags:                    0\n"
      "Rollback Index Location:  0\n"
      "Release String:           ''\n"
      "Descriptors:\n"
      "    Hashtree descriptor:\n"
      "      Version of dm-verity:  1\n"
      "      Image Size:            5242880 bytes\n"
      "      Tree Offset:           5242880\n"
      "      Tree Size:             45056 bytes\n"
      "      Data Block Size:       4096 bytes\n"
      "      Hash Block Size:       4096 bytes\n"
      "      FEC num roots:         2\n"
      "      FEC offset:            5287936\n"
      "      FEC size:              49152 bytes\n"
      "      Hash Algorithm:        sha256\n"
      "      Partition Name:        foobar\n"
      "      Salt:                  \n"
      "      Root Digest:           \n"
      "      Flags:                 1\n",
      InfoImage(path));
}

TEST_F(AvbToolTest, AddHashtreeFooterNoSizeOrName) {
  // Size must be a multiple of block size (4096 bytes)
  size_t file_size = 72 * 1024;
  base::FilePath path = GenerateImage("data.bin", file_size);

  // Note how there is no --partition_size or --partition_name here.
  EXPECT_COMMAND(0,
                 "./avbtool.py add_hashtree_footer --salt d00df00d "
                 "--image %s "
                 "--algorithm SHA256_RSA2048 "
                 "--key test/data/testkey_rsa2048.pem "
                 "--internal_release_string \"\" ",
                 path.value().c_str());

  ASSERT_EQ(
      "Footer version:           1.0\n"
      "Image size:               94208 bytes\n"
      "Original image size:      73728 bytes\n"
      "VBMeta offset:            86016\n"
      "VBMeta size:              1344 bytes\n"
      "--\n"
      "Minimum libavb version:   1.0\n"
      "Header Block:             256 bytes\n"
      "Authentication Block:     320 bytes\n"
      "Auxiliary Block:          768 bytes\n"
      "Public key (sha1):        cdbb77177f731920bbe0a0f94f84d9038ae0617d\n"
      "Algorithm:                SHA256_RSA2048\n"
      "Rollback Index:           0\n"
      "Flags:                    0\n"
      "Rollback Index Location:  0\n"
      "Release String:           ''\n"
      "Descriptors:\n"
      "    Hashtree descriptor:\n"
      "      Version of dm-verity:  1\n"
      "      Image Size:            73728 bytes\n"
      "      Tree Offset:           73728\n"
      "      Tree Size:             4096 bytes\n"
      "      Data Block Size:       4096 bytes\n"
      "      Hash Block Size:       4096 bytes\n"
      "      FEC num roots:         2\n"
      "      FEC offset:            77824\n"
      "      FEC size:              8192 bytes\n"
      "      Hash Algorithm:        sha1\n"
      "      Partition Name:        \n"
      "      Salt:                  d00df00d\n"
      "      Root Digest:           2f73fb340e982794643e1121d82d5195677c2b31\n"
      "      Flags:                 0\n",
      InfoImage(path));

  // Check that at least avbtool can verify the image and hashtree.
  EXPECT_COMMAND(0,
                 "./avbtool.py verify_image "
                 "--image %s ",
                 path.value().c_str());
}

TEST_F(AvbToolTest, AddHashtreeFooterSingleBlock) {
  // Tests a special case that the file size is just one block.
  size_t file_size = 4096;
  base::FilePath path = GenerateImage("data.bin", file_size);

  // Note how there is no --partition_size or --partition_name here.
  EXPECT_COMMAND(0,
                 "./avbtool.py add_hashtree_footer --salt d00df00d "
                 "--image %s "
                 "--algorithm SHA256_RSA2048 "
                 "--key test/data/testkey_rsa2048.pem "
                 "--internal_release_string \"\" ",
                 path.value().c_str());

  ASSERT_EQ(
      "Footer version:           1.0\n"
      "Image size:               20480 bytes\n"
      "Original image size:      4096 bytes\n"
      "VBMeta offset:            12288\n"
      "VBMeta size:              1344 bytes\n"
      "--\n"
      "Minimum libavb version:   1.0\n"
      "Header Block:             256 bytes\n"
      "Authentication Block:     320 bytes\n"
      "Auxiliary Block:          768 bytes\n"
      "Public key (sha1):        cdbb77177f731920bbe0a0f94f84d9038ae0617d\n"
      "Algorithm:                SHA256_RSA2048\n"
      "Rollback Index:           0\n"
      "Flags:                    0\n"
      "Rollback Index Location:  0\n"
      "Release String:           ''\n"
      "Descriptors:\n"
      "    Hashtree descriptor:\n"
      "      Version of dm-verity:  1\n"
      "      Image Size:            4096 bytes\n"
      "      Tree Offset:           4096\n"
      "      Tree Size:             0 bytes\n"
      "      Data Block Size:       4096 bytes\n"
      "      Hash Block Size:       4096 bytes\n"
      "      FEC num roots:         2\n"
      "      FEC offset:            4096\n"
      "      FEC size:              8192 bytes\n"
      "      Hash Algorithm:        sha1\n"
      "      Partition Name:        \n"
      "      Salt:                  d00df00d\n"
      "      Root Digest:           4bd1e1f0aa1c2c793bb9f3e52de6ae7393889e61\n"
      "      Flags:                 0\n",
      InfoImage(path));

  // Check that at least avbtool can verify the image and hashtree.
  EXPECT_COMMAND(0,
                 "./avbtool.py verify_image "
                 "--image %s ",
                 path.value().c_str());
}

TEST_F(AvbToolTest, AddHashtreeFooterNoSizeWrongSize) {
  // Size must be a multiple of block size (4096 bytes) and this one isn't...
  size_t file_size = 70 * 1024;
  base::FilePath path = GenerateImage("data.bin", file_size);

  // ... so we expect this command to fail.
  EXPECT_COMMAND(1,
                 "./avbtool.py add_hashtree_footer --salt d00df00d "
                 "--image %s "
                 "--algorithm SHA256_RSA2048 "
                 "--key test/data/testkey_rsa2048.pem "
                 "--internal_release_string \"\" ",
                 path.value().c_str());
}

TEST_F(AvbToolTest, AddHashtreeFooterRoundImageSize) {
  // Image size needs not to be a multiple of block size (4096 bytes) if
  // --partition_size is specified. avbtool will round the image size being
  // a multiple of block size, prior to add an AVB footer.
  size_t image_size = 70 * 1024;
  base::FilePath path = GenerateImage("data.bin", image_size);

  size_t partition_size = 10 * 1024 * 1024;
  // Note that there is --partition_size here.
  EXPECT_COMMAND(0,
                 "./avbtool.py add_hashtree_footer --salt d00df00d "
                 "--image %s "
                 "--algorithm SHA256_RSA2048 "
                 "--key test/data/testkey_rsa2048.pem "
                 "--partition_size %d --partition_name foobar "
                 "--internal_release_string \"\" ",
                 path.value().c_str(),
                 (int)partition_size);
}

TEST_F(AvbToolTest, AddHashtreeFooterNoWrongPartitionSize) {
  // Partition size must be a multiple of block size (4096 bytes) and this
  // one isn't...
  size_t partition_size = 10 * 1024 * 1024 + 1024;

  // Image size doesn't matter in this case.
  size_t image_size = 70 * 1024;
  base::FilePath path = GenerateImage("data.bin", image_size);

  // ... so we expect this command to fail.
  EXPECT_COMMAND(1,
                 "./avbtool.py add_hashtree_footer --salt d00df00d "
                 "--image %s "
                 "--algorithm SHA256_RSA2048 "
                 "--key test/data/testkey_rsa2048.pem "
                 "--partition_size %d --partition_name foobar "
                 "--internal_release_string \"\" ",
                 path.value().c_str(),
                 (int)partition_size);
}

TEST_F(AvbToolTest, AddHashtreeFooterWithCheckAtMostOnce) {
  size_t partition_size = 10 * 1024 * 1024;
  base::FilePath path = GenerateImage("digest_location", partition_size / 2);
  EXPECT_COMMAND(0,
                 "./avbtool.py add_hashtree_footer --salt d00df00d "
                 "--hash_algorithm sha256 --image %s "
                 "--partition_size %d --partition_name foobar "
                 "--algorithm SHA256_RSA2048 "
                 "--key test/data/testkey_rsa2048.pem "
                 "--internal_release_string \"\" "
                 "--check_at_most_once",
                 path.value().c_str(),
                 (int)partition_size);
  // There are two important bits here we're expecting with --check_at_most_once:
  //   Minimum libavb version = 1.1
  //   Hashtree descriptor -> Flags = 2
  ASSERT_EQ(
      "Footer version:           1.0\n"
      "Image size:               10485760 bytes\n"
      "Original image size:      5242880 bytes\n"
      "VBMeta offset:            5337088\n"
      "VBMeta size:              1344 bytes\n"
      "--\n"
      "Minimum libavb version:   1.1\n"
      "Header Block:             256 bytes\n"
      "Authentication Block:     320 bytes\n"
      "Auxiliary Block:          768 bytes\n"
      "Public key (sha1):        cdbb77177f731920bbe0a0f94f84d9038ae0617d\n"
      "Algorithm:                SHA256_RSA2048\n"
      "Rollback Index:           0\n"
      "Flags:                    0\n"
      "Rollback Index Location:  0\n"
      "Release String:           ''\n"
      "Descriptors:\n"
      "    Hashtree descriptor:\n"
      "      Version of dm-verity:  1\n"
      "      Image Size:            5242880 bytes\n"
      "      Tree Offset:           5242880\n"
      "      Tree Size:             45056 bytes\n"
      "      Data Block Size:       4096 bytes\n"
      "      Hash Block Size:       4096 bytes\n"
      "      FEC num roots:         2\n"
      "      FEC offset:            5287936\n"
      "      FEC size:              49152 bytes\n"
      "      Hash Algorithm:        sha256\n"
      "      Partition Name:        foobar\n"
      "      Salt:                  d00df00d\n"
      "      Root Digest:           "
      "d0e31526f5a3f8e3f59acf726bd31ae7861ee78f9baa9195356bf479c6f9119d\n"
      "      Flags:                 2\n",
      InfoImage(path));
}

TEST_F(AvbToolTest, KernelCmdlineDescriptor) {
  base::FilePath vbmeta_path =
      testdir_.Append("vbmeta_kernel_cmdline_desc.bin");

  EXPECT_COMMAND(0,
                 "./avbtool.py make_vbmeta_image "
                 "--output %s "
                 "--kernel_cmdline 'foo bar baz' "
                 "--kernel_cmdline 'second cmdline' "
                 "--algorithm SHA256_RSA2048 "
                 "--key test/data/testkey_rsa2048.pem "
                 "--internal_release_string \"\"",
                 vbmeta_path.value().c_str());

  ASSERT_EQ(
      "Minimum libavb version:   1.0\n"
      "Header Block:             256 bytes\n"
      "Authentication Block:     320 bytes\n"
      "Auxiliary Block:          640 bytes\n"
      "Public key (sha1):        cdbb77177f731920bbe0a0f94f84d9038ae0617d\n"
      "Algorithm:                SHA256_RSA2048\n"
      "Rollback Index:           0\n"
      "Flags:                    0\n"
      "Rollback Index Location:  0\n"
      "Release String:           ''\n"
      "Descriptors:\n"
      "    Kernel Cmdline descriptor:\n"
      "      Flags:                 0\n"
      "      Kernel Cmdline:        'foo bar baz'\n"
      "    Kernel Cmdline descriptor:\n"
      "      Flags:                 0\n"
      "      Kernel Cmdline:        'second cmdline'\n",
      InfoImage(vbmeta_path));

  // Now check the VBMeta image.
  std::string image_data;
  ASSERT_TRUE(base::ReadFileToString(vbmeta_path, &image_data));

  const uint8_t* vbmeta_data =
      reinterpret_cast<const uint8_t*>(image_data.data());
  const size_t vbmeta_size = image_data.length();
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_OK,
            avb_vbmeta_image_verify(vbmeta_data, vbmeta_size, NULL, NULL));

  // Collect all descriptors.
  std::vector<const AvbDescriptor*> descriptors;
  avb_descriptor_foreach(
      vbmeta_data, vbmeta_size, collect_descriptors, &descriptors);

  // We should have two descriptors - check them.
  EXPECT_EQ(2UL, descriptors.size());
  AvbKernelCmdlineDescriptor d;
  EXPECT_EQ(AVB_DESCRIPTOR_TAG_KERNEL_CMDLINE,
            avb_be64toh(descriptors[0]->tag));
  EXPECT_NE(
      0,
      avb_kernel_cmdline_descriptor_validate_and_byteswap(
          reinterpret_cast<const AvbKernelCmdlineDescriptor*>(descriptors[0]),
          &d));
  EXPECT_EQ("foo bar baz",
            std::string(reinterpret_cast<const char*>(descriptors[0]) +
                            sizeof(AvbKernelCmdlineDescriptor),
                        d.kernel_cmdline_length));
  EXPECT_EQ(AVB_DESCRIPTOR_TAG_KERNEL_CMDLINE,
            avb_be64toh(descriptors[1]->tag));
  EXPECT_NE(
      0,
      avb_kernel_cmdline_descriptor_validate_and_byteswap(
          reinterpret_cast<const AvbKernelCmdlineDescriptor*>(descriptors[1]),
          &d));
  EXPECT_EQ("second cmdline",
            std::string(reinterpret_cast<const char*>(descriptors[1]) +
                            sizeof(AvbKernelCmdlineDescriptor),
                        d.kernel_cmdline_length));
}

TEST_F(AvbToolTest, CalculateKernelCmdline) {
  base::FilePath vbmeta_path = testdir_.Append("vbmeta.bin");
  EXPECT_COMMAND(0,
                 "./avbtool.py make_vbmeta_image "
                 "--output %s "
                 "--kernel_cmdline 'foo bar baz' "
                 "--kernel_cmdline 'second cmdline' "
                 "--algorithm SHA256_RSA2048 "
                 "--key test/data/testkey_rsa2048.pem "
                 "--internal_release_string \"\"",
                 vbmeta_path.value().c_str());

  base::FilePath out_path = testdir_.Append("out.txt");
  std::string out;
  EXPECT_COMMAND(0,
                 "./avbtool.py calculate_kernel_cmdline --image %s > %s",
                 vbmeta_path.value().c_str(),
                 out_path.value().c_str());
  ASSERT_TRUE(base::ReadFileToString(out_path, &out));
  EXPECT_EQ(out, "foo bar baz second cmdline");
}

TEST_F(AvbToolTest, CalculateKernelCmdlineChainedAndWithFlags) {
  const size_t rootfs_size = 1028 * 1024;
  const size_t partition_size = 1536 * 1024;

  base::FilePath pk_path = testdir_.Append("testkey_rsa2048.avbpubkey");

  // Generate a 1028 KiB file with known content, add a hashtree, and cmdline
  // descriptors for setting up this hashtree. Notably this will create *two*
  // cmdline descriptors so we can test calculate_kernel_cmdline's
  // --hashtree_disabled option.
  std::vector<uint8_t> rootfs;
  rootfs.resize(rootfs_size);
  for (size_t n = 0; n < rootfs_size; n++)
    rootfs[n] = uint8_t(n);
  base::FilePath rootfs_path = testdir_.Append("rootfs.bin");
  EXPECT_EQ(rootfs_size,
            static_cast<const size_t>(
                base::WriteFile(rootfs_path,
                                reinterpret_cast<const char*>(rootfs.data()),
                                rootfs.size())));

  EXPECT_COMMAND(
      0,
      "./avbtool.py extract_public_key --key test/data/testkey_rsa2048.pem"
      " --output %s",
      pk_path.value().c_str());

  EXPECT_COMMAND(0,
                 "./avbtool.py add_hashtree_footer --salt d00df00d --image %s "
                 "--partition_size %d --partition_name rootfs "
                 "--algorithm SHA256_RSA2048 "
                 "--key test/data/testkey_rsa2048.pem "
                 "--internal_release_string \"\" "
                 "--setup_as_rootfs_from_kernel",
                 rootfs_path.value().c_str(),
                 (int)partition_size);
  EXPECT_EQ(
      "Footer version:           1.0\n"
      "Image size:               1572864 bytes\n"
      "Original image size:      1052672 bytes\n"
      "VBMeta offset:            1085440\n"
      "VBMeta size:              1792 bytes\n"
      "--\n"
      "Minimum libavb version:   1.0\n"
      "Header Block:             256 bytes\n"
      "Authentication Block:     320 bytes\n"
      "Auxiliary Block:          1216 bytes\n"
      "Public key (sha1):        cdbb77177f731920bbe0a0f94f84d9038ae0617d\n"
      "Algorithm:                SHA256_RSA2048\n"
      "Rollback Index:           0\n"
      "Flags:                    0\n"
      "Rollback Index Location:  0\n"
      "Release String:           ''\n"
      "Descriptors:\n"
      "    Hashtree descriptor:\n"
      "      Version of dm-verity:  1\n"
      "      Image Size:            1052672 bytes\n"
      "      Tree Offset:           1052672\n"
      "      Tree Size:             16384 bytes\n"
      "      Data Block Size:       4096 bytes\n"
      "      Hash Block Size:       4096 bytes\n"
      "      FEC num roots:         2\n"
      "      FEC offset:            1069056\n"
      "      FEC size:              16384 bytes\n"
      "      Hash Algorithm:        sha1\n"
      "      Partition Name:        rootfs\n"
      "      Salt:                  d00df00d\n"
      "      Root Digest:           e811611467dcd6e8dc4324e45f706c2bdd51db67\n"
      "      Flags:                 0\n"
      "    Kernel Cmdline descriptor:\n"
      "      Flags:                 1\n"
      "      Kernel Cmdline:        'dm=\"1 vroot none ro 1,0 2056 verity 1 "
      "PARTUUID=$(ANDROID_SYSTEM_PARTUUID) PARTUUID=$(ANDROID_SYSTEM_PARTUUID) "
      "4096 4096 257 257 sha1 e811611467dcd6e8dc4324e45f706c2bdd51db67 "
      "d00df00d 10 $(ANDROID_VERITY_MODE) ignore_zero_blocks "
      "use_fec_from_device PARTUUID=$(ANDROID_SYSTEM_PARTUUID) fec_roots 2 "
      "fec_blocks 261 fec_start 261\" root=/dev/dm-0'\n"
      "    Kernel Cmdline descriptor:\n"
      "      Flags:                 2\n"
      "      Kernel Cmdline:        "
      "'root=PARTUUID=$(ANDROID_SYSTEM_PARTUUID)'\n",
      InfoImage(rootfs_path));

  // Chain to the rootfs.img and include two cmdline descriptors.
  base::FilePath vbmeta_path = testdir_.Append("vbmeta.bin");
  EXPECT_COMMAND(0,
                 "./avbtool.py make_vbmeta_image "
                 "--output %s "
                 "--kernel_cmdline 'foo bar baz' "
                 "--kernel_cmdline 'second cmdline' "
                 "--chain_partition rootfs:1:%s "
                 "--algorithm SHA256_RSA2048 "
                 "--key test/data/testkey_rsa2048.pem "
                 "--internal_release_string \"\"",
                 vbmeta_path.value().c_str(),
                 pk_path.value().c_str());
  EXPECT_EQ(
      "Minimum libavb version:   1.0\n"
      "Header Block:             256 bytes\n"
      "Authentication Block:     320 bytes\n"
      "Auxiliary Block:          1280 bytes\n"
      "Public key (sha1):        cdbb77177f731920bbe0a0f94f84d9038ae0617d\n"
      "Algorithm:                SHA256_RSA2048\n"
      "Rollback Index:           0\n"
      "Flags:                    0\n"
      "Rollback Index Location:  0\n"
      "Release String:           ''\n"
      "Descriptors:\n"
      "    Chain Partition descriptor:\n"
      "      Partition Name:          rootfs\n"
      "      Rollback Index Location: 1\n"
      "      Public key (sha1):       "
      "cdbb77177f731920bbe0a0f94f84d9038ae0617d\n"
      "      Flags:                   0\n"
      "    Kernel Cmdline descriptor:\n"
      "      Flags:                 0\n"
      "      Kernel Cmdline:        'foo bar baz'\n"
      "    Kernel Cmdline descriptor:\n"
      "      Flags:                 0\n"
      "      Kernel Cmdline:        'second cmdline'\n",
      InfoImage(vbmeta_path));

  base::FilePath out_path = testdir_.Append("out.txt");
  std::string out;

  // First check the kernel cmdline without --hashtree_disabled - compare with
  // above info_image output.
  EXPECT_COMMAND(0,
                 "./avbtool.py calculate_kernel_cmdline --image %s > %s",
                 vbmeta_path.value().c_str(),
                 out_path.value().c_str());
  ASSERT_TRUE(base::ReadFileToString(out_path, &out));
  EXPECT_EQ(
      "dm=\"1 vroot none ro 1,0 2056 verity 1 "
      "PARTUUID=$(ANDROID_SYSTEM_PARTUUID) PARTUUID=$(ANDROID_SYSTEM_PARTUUID) "
      "4096 4096 257 257 sha1 e811611467dcd6e8dc4324e45f706c2bdd51db67 "
      "d00df00d 10 $(ANDROID_VERITY_MODE) ignore_zero_blocks "
      "use_fec_from_device PARTUUID=$(ANDROID_SYSTEM_PARTUUID) fec_roots 2 "
      "fec_blocks 261 fec_start 261\" root=/dev/dm-0 foo bar baz second "
      "cmdline",
      out);

  // Then check the kernel cmdline with --hashtree_disabled - compare with above
  // info_image output.
  EXPECT_COMMAND(
      0,
      "./avbtool.py calculate_kernel_cmdline --image %s --hashtree_disabled > %s",
      vbmeta_path.value().c_str(),
      out_path.value().c_str());
  ASSERT_TRUE(base::ReadFileToString(out_path, &out));
  EXPECT_EQ(
      "root=PARTUUID=$(ANDROID_SYSTEM_PARTUUID) foo bar baz second cmdline",
      out);
}

TEST_F(AvbToolTest, AddHashFooterSmallImageWithExternalVbmeta) {
  const size_t image_size = 37;
  const size_t partition_size = 20 * 4096;

  std::vector<uint8_t> image(image_size, 0);
  for (size_t n = 0; n < image_size; n++) {
    image[n] = uint8_t(n);
  }

  base::FilePath ext_vbmeta_path = testdir_.Append("ext_vbmeta.bin");
  base::FilePath image_path = testdir_.Append("kernel.bin");
  EXPECT_EQ(image_size,
            static_cast<const size_t>(
                base::WriteFile(image_path,
                                reinterpret_cast<const char*>(image.data()),
                                image.size())));
  EXPECT_COMMAND(0,
                 "./avbtool.py add_hash_footer --salt d00df00d "
                 "--hash_algorithm sha256 --image %s "
                 "--partition_size %zu --partition_name kernel "
                 "--algorithm SHA256_RSA2048 "
                 "--key test/data/testkey_rsa2048.pem "
                 "--output_vbmeta %s "
                 "--do_not_append_vbmeta_image "
                 "--internal_release_string \"\"",
                 image_path.value().c_str(),
                 partition_size,
                 ext_vbmeta_path.value().c_str());

  // It is not this unit test's job to check the vbmeta content.

  int64_t file_size;
  ASSERT_TRUE(base::GetFileSize(image_path, &file_size));
  EXPECT_EQ(static_cast<size_t>(file_size), image_size);
}

TEST_F(AvbToolTest, IncludeDescriptor) {
  base::FilePath vbmeta1_path = testdir_.Append("vbmeta_id1.bin");
  base::FilePath vbmeta2_path = testdir_.Append("vbmeta_id2.bin");
  base::FilePath vbmeta3_path = testdir_.Append("vbmeta_id3.bin");

  EXPECT_COMMAND(0,
                 "./avbtool.py make_vbmeta_image "
                 "--output %s "
                 "--kernel_cmdline 'something' "
                 "--prop name:value "
                 "--internal_release_string \"\"",
                 vbmeta1_path.value().c_str());

  EXPECT_COMMAND(0,
                 "./avbtool.py make_vbmeta_image "
                 "--output %s "
                 "--prop name2:value2 "
                 "--prop name3:value3 "
                 "--internal_release_string \"\"",
                 vbmeta2_path.value().c_str());

  EXPECT_COMMAND(0,
                 "./avbtool.py make_vbmeta_image "
                 "--output %s "
                 "--prop name4:value4 "
                 "--include_descriptors_from_image %s "
                 "--include_descriptors_from_image %s "
                 "--internal_release_string \"\"",
                 vbmeta3_path.value().c_str(),
                 vbmeta1_path.value().c_str(),
                 vbmeta2_path.value().c_str());

  ASSERT_EQ(
      "Minimum libavb version:   1.0\n"
      "Header Block:             256 bytes\n"
      "Authentication Block:     0 bytes\n"
      "Auxiliary Block:          256 bytes\n"
      "Algorithm:                NONE\n"
      "Rollback Index:           0\n"
      "Flags:                    0\n"
      "Rollback Index Location:  0\n"
      "Release String:           ''\n"
      "Descriptors:\n"
      "    Prop: name4 -> 'value4'\n"
      "    Prop: name -> 'value'\n"
      "    Kernel Cmdline descriptor:\n"
      "      Flags:                 0\n"
      "      Kernel Cmdline:        'something'\n"
      "    Prop: name2 -> 'value2'\n"
      "    Prop: name3 -> 'value3'\n",
      InfoImage(vbmeta3_path));
}

TEST_F(AvbToolTest, ChainedPartition) {
  base::FilePath vbmeta_path = testdir_.Append("vbmeta_cp.bin");

  base::FilePath pk_path = testdir_.Append("testkey_rsa2048.avbpubkey");

  EXPECT_COMMAND(
      0,
      "./avbtool.py extract_public_key --key test/data/testkey_rsa2048.pem"
      " --output %s",
      pk_path.value().c_str());

  EXPECT_COMMAND(
      0,
      "./avbtool.py make_vbmeta_image "
      "--output %s "
      "--chain_partition system:1:%s "
      "--algorithm SHA256_RSA2048 --key test/data/testkey_rsa2048.pem "
      "--internal_release_string \"\"",
      vbmeta_path.value().c_str(),
      pk_path.value().c_str());

  ASSERT_EQ(
      "Minimum libavb version:   1.0\n"
      "Header Block:             256 bytes\n"
      "Authentication Block:     320 bytes\n"
      "Auxiliary Block:          1152 bytes\n"
      "Public key (sha1):        cdbb77177f731920bbe0a0f94f84d9038ae0617d\n"
      "Algorithm:                SHA256_RSA2048\n"
      "Rollback Index:           0\n"
      "Flags:                    0\n"
      "Rollback Index Location:  0\n"
      "Release String:           ''\n"
      "Descriptors:\n"
      "    Chain Partition descriptor:\n"
      "      Partition Name:          system\n"
      "      Rollback Index Location: 1\n"
      "      Public key (sha1):       "
      "cdbb77177f731920bbe0a0f94f84d9038ae0617d\n"
      "      Flags:                   0\n",
      InfoImage(vbmeta_path));

  // Now check the VBMeta image.
  std::string image_data;
  ASSERT_TRUE(base::ReadFileToString(vbmeta_path, &image_data));

  const uint8_t* vbmeta_data =
      reinterpret_cast<const uint8_t*>(image_data.data());
  const size_t vbmeta_size = image_data.length();
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_OK,
            avb_vbmeta_image_verify(vbmeta_data, vbmeta_size, NULL, NULL));

  // Collect all descriptors.
  std::vector<const AvbDescriptor*> descriptors;
  avb_descriptor_foreach(
      vbmeta_data, vbmeta_size, collect_descriptors, &descriptors);

  // We should have one descriptor - check it.
  EXPECT_EQ(1UL, descriptors.size());

  std::string pk_data;
  ASSERT_TRUE(base::ReadFileToString(pk_path, &pk_data));

  AvbChainPartitionDescriptor d;
  EXPECT_EQ(AVB_DESCRIPTOR_TAG_CHAIN_PARTITION,
            avb_be64toh(descriptors[0]->tag));
  EXPECT_NE(
      0,
      avb_chain_partition_descriptor_validate_and_byteswap(
          reinterpret_cast<const AvbChainPartitionDescriptor*>(descriptors[0]),
          &d));
  const uint8_t* desc_end = reinterpret_cast<const uint8_t*>(descriptors[0]) +
                            sizeof(AvbChainPartitionDescriptor);
  uint64_t o = 0;
  EXPECT_EQ("system",
            std::string(reinterpret_cast<const char*>(desc_end + o),
                        d.partition_name_len));
  o += d.partition_name_len;
  EXPECT_EQ(pk_data,
            std::string(reinterpret_cast<const char*>(descriptors[0]) +
                            sizeof(AvbChainPartitionDescriptor) + o,
                        d.public_key_len));
}

TEST_F(AvbToolTest, ChainedPartitionNoAB) {
  base::FilePath vbmeta_path = testdir_.Append("vbmeta_cp.bin");

  base::FilePath pk_path = testdir_.Append("testkey_rsa2048.avbpubkey");

  EXPECT_COMMAND(
      0,
      "./avbtool.py extract_public_key --key test/data/testkey_rsa2048.pem"
      " --output %s",
      pk_path.value().c_str());

  EXPECT_COMMAND(
      0,
      "./avbtool.py make_vbmeta_image "
      "--output %s "
      "--chain_partition_do_not_use_ab system:1:%s "
      "--algorithm SHA256_RSA2048 --key test/data/testkey_rsa2048.pem "
      "--internal_release_string \"\"",
      vbmeta_path.value().c_str(),
      pk_path.value().c_str());

  ASSERT_EQ(
      "Minimum libavb version:   1.3\n"
      "Header Block:             256 bytes\n"
      "Authentication Block:     320 bytes\n"
      "Auxiliary Block:          1152 bytes\n"
      "Public key (sha1):        cdbb77177f731920bbe0a0f94f84d9038ae0617d\n"
      "Algorithm:                SHA256_RSA2048\n"
      "Rollback Index:           0\n"
      "Flags:                    0\n"
      "Rollback Index Location:  0\n"
      "Release String:           ''\n"
      "Descriptors:\n"
      "    Chain Partition descriptor:\n"
      "      Partition Name:          system\n"
      "      Rollback Index Location: 1\n"
      "      Public key (sha1):       "
      "cdbb77177f731920bbe0a0f94f84d9038ae0617d\n"
      "      Flags:                   1\n",
      InfoImage(vbmeta_path));

  // Now check the VBMeta image.
  std::string image_data;
  ASSERT_TRUE(base::ReadFileToString(vbmeta_path, &image_data));

  const uint8_t* vbmeta_data =
      reinterpret_cast<const uint8_t*>(image_data.data());
  const size_t vbmeta_size = image_data.length();
  EXPECT_EQ(AVB_VBMETA_VERIFY_RESULT_OK,
            avb_vbmeta_image_verify(vbmeta_data, vbmeta_size, NULL, NULL));

  // Collect all descriptors.
  std::vector<const AvbDescriptor*> descriptors;
  avb_descriptor_foreach(
      vbmeta_data, vbmeta_size, collect_descriptors, &descriptors);

  // We should have one descriptor - check it.
  EXPECT_EQ(1UL, descriptors.size());

  std::string pk_data;
  ASSERT_TRUE(base::ReadFileToString(pk_path, &pk_data));

  AvbChainPartitionDescriptor d;
  EXPECT_EQ(AVB_DESCRIPTOR_TAG_CHAIN_PARTITION,
            avb_be64toh(descriptors[0]->tag));
  EXPECT_NE(
      0,
      avb_chain_partition_descriptor_validate_and_byteswap(
          reinterpret_cast<const AvbChainPartitionDescriptor*>(descriptors[0]),
          &d));
  const uint8_t* desc_end = reinterpret_cast<const uint8_t*>(descriptors[0]) +
                            sizeof(AvbChainPartitionDescriptor);
  uint64_t o = 0;
  EXPECT_EQ("system",
            std::string(reinterpret_cast<const char*>(desc_end + o),
                        d.partition_name_len));
  o += d.partition_name_len;
  EXPECT_EQ(pk_data,
            std::string(reinterpret_cast<const char*>(descriptors[0]) +
                            sizeof(AvbChainPartitionDescriptor) + o,
                        d.public_key_len));
}

TEST_F(AvbToolTest, ChainedPartitionNoLocationCollision) {
  base::FilePath vbmeta_path = testdir_.Append("vbmeta_cp.bin");

  base::FilePath pk_path = testdir_.Append("testkey_rsa2048.avbpubkey");

  EXPECT_COMMAND(
      0,
      "./avbtool.py extract_public_key --key test/data/testkey_rsa2048.pem"
      " --output %s",
      pk_path.value().c_str());

  // Check that avbtool bails if the same Rollback Index Location is
  // used for multiple chained partitions.
  EXPECT_COMMAND(
      1,
      "./avbtool.py make_vbmeta_image "
      "--output %s "
      "--chain_partition system:1:%s "
      "--chain_partition other:1:%s "
      "--algorithm SHA256_RSA2048 --key test/data/testkey_rsa2048.pem "
      "--internal_release_string \"\"",
      vbmeta_path.value().c_str(),
      pk_path.value().c_str(),
      pk_path.value().c_str());
}

TEST_F(AvbToolTest, AppendVBMetaImage) {
  size_t boot_size = 5 * 1024 * 1024;
  size_t boot_partition_size = 32 * 1024 * 1024;
  base::FilePath boot_path = GenerateImage("boot", boot_size);

  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"),
                      std::string("--append_to_release_string \"\" "
                                  "--kernel_cmdline foo"));

  EXPECT_COMMAND(0,
                 "./avbtool.py append_vbmeta_image "
                 "--image %s "
                 "--partition_size %d "
                 "--vbmeta_image %s ",
                 boot_path.value().c_str(),
                 (int)boot_partition_size,
                 vbmeta_image_path_.value().c_str());

  std::string vbmeta_contents = InfoImage(vbmeta_image_path_);
  std::string boot_contents = InfoImage(boot_path);

  // Check that boot.img has the same vbmeta blob as from vbmeta.img -
  // we do this by inspecting 'avbtool info_image' output combined
  // with the known footer location given boot.img has 5 MiB known
  // content and the partition size is 32 MiB.
  ASSERT_EQ(
      "Minimum libavb version:   1.0\n"
      "Header Block:             256 bytes\n"
      "Authentication Block:     320 bytes\n"
      "Auxiliary Block:          576 bytes\n"
      "Public key (sha1):        cdbb77177f731920bbe0a0f94f84d9038ae0617d\n"
      "Algorithm:                SHA256_RSA2048\n"
      "Rollback Index:           0\n"
      "Flags:                    0\n"
      "Rollback Index Location:  0\n"
      "Release String:           'avbtool 1.3.0 '\n"
      "Descriptors:\n"
      "    Kernel Cmdline descriptor:\n"
      "      Flags:                 0\n"
      "      Kernel Cmdline:        'foo'\n",
      vbmeta_contents);
  std::string known_footer =
      "Footer version:           1.0\n"
      "Image size:               33554432 bytes\n"
      "Original image size:      5242880 bytes\n"
      "VBMeta offset:            5242880\n"
      "VBMeta size:              1152 bytes\n"
      "--\n";
  ASSERT_EQ(known_footer + vbmeta_contents, boot_contents);

  // Also verify that the blobs are the same, bit for bit.
  base::File f =
      base::File(boot_path, base::File::FLAG_OPEN | base::File::FLAG_READ);
  std::vector<uint8_t> loaded_vbmeta;
  loaded_vbmeta.resize(1152);
  EXPECT_EQ(
      f.Read(
          5 * 1024 * 1024, reinterpret_cast<char*>(loaded_vbmeta.data()), 1152),
      1152);
  EXPECT_EQ(vbmeta_image_, loaded_vbmeta);
}

TEST_F(AvbToolTest, SigningHelperBasic) {
  base::FilePath vbmeta_path = testdir_.Append("vbmeta.bin");
  base::FilePath signing_helper_test_path =
      testdir_.Append("signing_helper_test");
  EXPECT_COMMAND(
      0,
      "SIGNING_HELPER_TEST=\"%s\" ./avbtool.py make_vbmeta_image "
      "--output %s "
      "--algorithm SHA256_RSA2048 --key test/data/testkey_rsa2048.pem "
      "--signing_helper test/avbtool_signing_helper_test.py "
      "--internal_release_string \"\"",
      signing_helper_test_path.value().c_str(),
      vbmeta_path.value().c_str());

  // Now check the value in test file.
  std::string value;
  ASSERT_TRUE(base::ReadFileToString(signing_helper_test_path, &value));
  EXPECT_EQ("DONE", value);
}

TEST_F(AvbToolTest, SigningHelperWithFilesBasic) {
  base::FilePath vbmeta_path = testdir_.Append("vbmeta.bin");
  base::FilePath signing_helper_test_path =
      testdir_.Append("signing_helper_test");
  EXPECT_COMMAND(
      0,
      "SIGNING_HELPER_TEST=\"%s\" ./avbtool.py make_vbmeta_image "
      "--output %s "
      "--algorithm SHA256_RSA2048 --key test/data/testkey_rsa2048.pem "
      "--signing_helper_with_files "
      "test/avbtool_signing_helper_with_files_test.py "
      "--internal_release_string \"\"",
      signing_helper_test_path.value().c_str(),
      vbmeta_path.value().c_str());

  // Now check the value in test file.
  std::string value;
  ASSERT_TRUE(base::ReadFileToString(signing_helper_test_path, &value));
  EXPECT_EQ("DONE", value);
}

TEST_F(AvbToolTest, SigningHelperReturnError) {
  base::FilePath vbmeta_path = testdir_.Append("vbmeta.bin");
  EXPECT_COMMAND(
      1,
      "./avbtool.py make_vbmeta_image "
      "--output %s "
      "--algorithm SHA256_RSA2048 --key test/data/testkey_rsa2048.pem "
      "--signing_helper test/avbtool_signing_helper_test.py "
      "--internal_release_string \"\"",
      vbmeta_path.value().c_str());
}

TEST_F(AvbToolTest, SigningHelperWithFilesReturnError) {
  base::FilePath vbmeta_path = testdir_.Append("vbmeta.bin");
  EXPECT_COMMAND(
      1,
      "./avbtool.py make_vbmeta_image "
      "--output %s "
      "--algorithm SHA256_RSA2048 --key test/data/testkey_rsa2048.pem "
      "--signing_helper_with_files "
      "test/avbtool_signing_helper_with_files_test.py "
      "--internal_release_string \"\"",
      vbmeta_path.value().c_str());
}

TEST_F(AvbToolTest, VerifyImageNoSignature) {
  GenerateVBMetaImage("vbmeta.img",
                      "",  // NONE
                      0,
                      base::FilePath());

  EXPECT_COMMAND(0,
                 "./avbtool.py verify_image "
                 "--image %s ",
                 vbmeta_image_path_.value().c_str());
}

TEST_F(AvbToolTest, VerifyImageValidSignature) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"));

  EXPECT_COMMAND(0,
                 "./avbtool.py verify_image "
                 "--image %s ",
                 vbmeta_image_path_.value().c_str());
}

TEST_F(AvbToolTest, VerifyImageCorruptedVBMeta) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"));

  // Corrupt four bytes of data in the end of the image. Since the aux
  // data is at the end and this data is signed, this will change the
  // value of the computed hash.
  uint8_t corrupt_data[4] = {0xff, 0xff, 0xff, 0xff};
  EXPECT_EQ(AVB_IO_RESULT_OK,
            ops_.avb_ops()->write_to_partition(ops_.avb_ops(),
                                               "vbmeta",
                                               -4,  // offset from end
                                               sizeof corrupt_data,
                                               corrupt_data));

  EXPECT_COMMAND(1,
                 "./avbtool.py verify_image "
                 "--image %s ",
                 vbmeta_image_path_.value().c_str());
}

TEST_F(AvbToolTest, VerifyImageOtherKeyMatching) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"));

  EXPECT_COMMAND(0,
                 "./avbtool.py verify_image "
                 "--image %s --key test/data/testkey_rsa2048.pem",
                 vbmeta_image_path_.value().c_str());
}

TEST_F(AvbToolTest, VerifyImageOtherKeyNotMatching) {
  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"));

  EXPECT_COMMAND(1,
                 "./avbtool.py verify_image "
                 "--image %s --key test/data/testkey_rsa4096.pem",
                 vbmeta_image_path_.value().c_str());
}

TEST_F(AvbToolTest, VerifyImageBrokenSignature) {
  base::FilePath vbmeta_path = testdir_.Append("vbmeta.bin");
  base::FilePath signing_helper_test_path =
      testdir_.Append("signing_helper_test");

  // Intentionally make the signer generate a wrong signature.
  EXPECT_COMMAND(
      0,
      "SIGNING_HELPER_GENERATE_WRONG_SIGNATURE=1 ./avbtool.py make_vbmeta_image "
      "--output %s "
      "--algorithm SHA256_RSA2048 --key test/data/testkey_rsa2048.pem "
      "--signing_helper test/avbtool_signing_helper_test.py "
      "--internal_release_string \"\"",
      vbmeta_path.value().c_str());

  EXPECT_COMMAND(1,
                 "./avbtool.py verify_image "
                 "--image %s ",
                 vbmeta_path.value().c_str());
}

// Helper to generate boot.img, unsparse system.img, and vbmeta.img.
void AvbToolTest::GenerateImageWithHashAndHashtreeSetup() {
  const size_t boot_partition_size = 16 * 1024 * 1024;
  const size_t boot_image_size = 5 * 1024 * 1024;
  base::FilePath boot_path = GenerateImage("boot.img", boot_image_size);
  EXPECT_COMMAND(0,
                 "./avbtool.py add_hash_footer"
                 " --image %s"
                 " --rollback_index 0"
                 " --partition_name boot"
                 " --partition_size %zd"
                 " --salt deadbeef"
                 " --internal_release_string \"\"",
                 boot_path.value().c_str(),
                 boot_partition_size);

  const size_t system_partition_size = 10 * 1024 * 1024;
  const size_t system_image_size = 8 * 1024 * 1024;
  base::FilePath system_path = GenerateImage("system.img", system_image_size);
  EXPECT_COMMAND(0,
                 "./avbtool.py add_hashtree_footer --salt d00df00d --image %s "
                 "--partition_size %zd --partition_name system "
                 "--internal_release_string \"\" ",
                 system_path.value().c_str(),
                 system_partition_size);

  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"),
                      base::StringPrintf("--include_descriptors_from_image %s "
                                         "--include_descriptors_from_image %s",
                                         boot_path.value().c_str(),
                                         system_path.value().c_str()));
}

TEST_F(AvbToolTest, VerifyImageWithHashAndHashtree) {
  GenerateImageWithHashAndHashtreeSetup();

  // Do two checks - one for system.img not sparse, and one where it
  // is sparse.
  for (int n = 0; n < 2; n++) {
    EXPECT_COMMAND(0,
                   "./avbtool.py verify_image "
                   "--image %s ",
                   vbmeta_image_path_.value().c_str());
    if (n == 0) {
      EXPECT_COMMAND(0,
                     "img2simg %s %s.sparse",
                     testdir_.Append("system.img").value().c_str(),
                     testdir_.Append("system.img").value().c_str());
      EXPECT_COMMAND(0,
                     "mv %s.sparse %s",
                     testdir_.Append("system.img").value().c_str(),
                     testdir_.Append("system.img").value().c_str());
    }
  }
}

TEST_F(AvbToolTest, VerifyImageWithHashAndZeroedHashtree) {
  const size_t system_partition_size = 10 * 1024 * 1024;
  const size_t system_image_size = 8 * 1024 * 1024;
  base::FilePath system_path = GenerateImage("system.img", system_image_size);
  EXPECT_COMMAND(0,
                 "./avbtool.py add_hashtree_footer --salt d00df00d --image %s "
                 "--partition_size %zd --partition_name system "
                 "--internal_release_string \"\" ",
                 system_path.value().c_str(),
                 system_partition_size);

  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"),
                      base::StringPrintf("--include_descriptors_from_image %s ",
                                         system_path.value().c_str()));

  EXPECT_COMMAND(0,
                 "./avbtool.py verify_image --image %s --accept_zeroed_hashtree",
                 vbmeta_image_path_.value().c_str());

  EXPECT_COMMAND(
      0, "./avbtool.py zero_hashtree --image %s", system_path.value().c_str());

  EXPECT_COMMAND(1,
                 "./avbtool.py verify_image --image %s",
                 vbmeta_image_path_.value().c_str());

  EXPECT_COMMAND(0,
                 "./avbtool.py verify_image --image %s --accept_zeroed_hashtree",
                 vbmeta_image_path_.value().c_str());
}

TEST_F(AvbToolTest, VerifyImageWithNoHashtree) {
  const size_t system_partition_size = 10 * 1024 * 1024;
  const size_t system_image_size = 8 * 1024 * 1024;
  base::FilePath system_path = GenerateImage("system.img", system_image_size);
  EXPECT_COMMAND(0,
                 "./avbtool.py add_hashtree_footer --salt d00df00d --image %s "
                 "--partition_size %zd --partition_name system "
                 "--no_hashtree "
                 "--internal_release_string \"\" ",
                 system_path.value().c_str(),
                 system_partition_size);

  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"),
                      base::StringPrintf("--include_descriptors_from_image %s ",
                                         system_path.value().c_str()));

  EXPECT_COMMAND(1,
                 "./avbtool.py verify_image --image %s",
                 vbmeta_image_path_.value().c_str());

  EXPECT_COMMAND(0,
                 "./avbtool.py verify_image --image %s --accept_zeroed_hashtree",
                 vbmeta_image_path_.value().c_str());
}

TEST_F(AvbToolTest, VerifyImageWithHashAndHashtreeCorruptHash) {
  GenerateImageWithHashAndHashtreeSetup();

  // Corrupt four bytes of data in the middle of boot.img.
  uint8_t corrupt_data[4] = {0xff, 0xff, 0xff, 0xff};
  EXPECT_EQ(AVB_IO_RESULT_OK,
            ops_.avb_ops()->write_to_partition(ops_.avb_ops(),
                                               "boot",
                                               105 * 1024,  // offset from start
                                               sizeof corrupt_data,
                                               corrupt_data));

  EXPECT_COMMAND(1,
                 "./avbtool.py verify_image "
                 "--image %s ",
                 vbmeta_image_path_.value().c_str());
}

TEST_F(AvbToolTest, VerifyImageWithHashAndHashtreeCorruptHashtree) {
  GenerateImageWithHashAndHashtreeSetup();

  // Corrupt four bytes of data in the middle of system.img.
  uint8_t corrupt_data[4] = {0xff, 0xff, 0xff, 0xff};
  EXPECT_EQ(AVB_IO_RESULT_OK,
            ops_.avb_ops()->write_to_partition(ops_.avb_ops(),
                                               "system",
                                               123 * 1024,  // offset from start
                                               sizeof corrupt_data,
                                               corrupt_data));

  // Do two checks - one for system.img not sparse, and one where it
  // is sparse.
  for (int n = 0; n < 2; n++) {
    EXPECT_COMMAND(1,
                   "./avbtool.py verify_image "
                   "--image %s ",
                   vbmeta_image_path_.value().c_str());
    if (n == 0) {
      EXPECT_COMMAND(0,
                     "img2simg %s %s.sparse",
                     testdir_.Append("system.img").value().c_str(),
                     testdir_.Append("system.img").value().c_str());
      EXPECT_COMMAND(0,
                     "mv %s.sparse %s",
                     testdir_.Append("system.img").value().c_str(),
                     testdir_.Append("system.img").value().c_str());
    }
  }
}

TEST_F(AvbToolTest, VerifyImageChainPartition) {
  base::FilePath pk4096_path = testdir_.Append("testkey_rsa4096.avbpubkey");
  EXPECT_COMMAND(
      0,
      "./avbtool.py extract_public_key --key test/data/testkey_rsa4096.pem"
      " --output %s",
      pk4096_path.value().c_str());

  base::FilePath pk8192_path = testdir_.Append("testkey_rsa8192.avbpubkey");
  EXPECT_COMMAND(
      0,
      "./avbtool.py extract_public_key --key test/data/testkey_rsa8192.pem"
      " --output %s",
      pk8192_path.value().c_str());

  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"),
                      base::StringPrintf("--chain_partition system:1:%s ",
                                         pk4096_path.value().c_str()));

  // Should not fail (name, rollback_index, contents all correct).
  EXPECT_COMMAND(0,
                 "./avbtool.py verify_image "
                 "--image %s "
                 "--expected_chain_partition system:1:%s",
                 vbmeta_image_path_.value().c_str(),
                 pk4096_path.value().c_str());

  // Should fail because we didn't use --expected_chain_partition.
  EXPECT_COMMAND(1,
                 "./avbtool.py verify_image "
                 "--image %s ",
                 vbmeta_image_path_.value().c_str());

  // Should fail because partition name is wrong.
  EXPECT_COMMAND(1,
                 "./avbtool.py verify_image "
                 "--image %s "
                 "--expected_chain_partition xyz:1:%s",
                 vbmeta_image_path_.value().c_str(),
                 pk4096_path.value().c_str());

  // Should fail because rollback index location is wrong.
  EXPECT_COMMAND(1,
                 "./avbtool.py verify_image "
                 "--image %s "
                 "--expected_chain_partition system:2:%s",
                 vbmeta_image_path_.value().c_str(),
                 pk4096_path.value().c_str());

  // Should fail because public key blob is wrong.
  EXPECT_COMMAND(1,
                 "./avbtool.py verify_image "
                 "--image %s "
                 "--expected_chain_partition system:1:%s",
                 vbmeta_image_path_.value().c_str(),
                 pk8192_path.value().c_str());
}

TEST_F(AvbToolTest, VerifyImageChainPartitionWithFollow) {
  base::FilePath pk4096_path = testdir_.Append("testkey_rsa4096.avbpubkey");
  EXPECT_COMMAND(
      0,
      "./avbtool.py extract_public_key --key test/data/testkey_rsa4096.pem"
      " --output %s",
      pk4096_path.value().c_str());

  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"),
                      base::StringPrintf("--chain_partition system:1:%s ",
                                         pk4096_path.value().c_str()));

  const size_t system_partition_size = 10 * 1024 * 1024;
  const size_t system_image_size = 8 * 1024 * 1024;
  base::FilePath system_path = GenerateImage("system.img", system_image_size);
  EXPECT_COMMAND(0,
                 "./avbtool.py add_hashtree_footer --salt d00df00d --image %s "
                 "--partition_size %zd --partition_name system "
                 "--algorithm SHA256_RSA4096 "
                 "--key test/data/testkey_rsa4096.pem "
                 "--internal_release_string \"\" ",
                 system_path.value().c_str(),
                 system_partition_size);

  // Even without --expected_chain_partition this shouldn't fail because we use
  // --follow_chain_partitions and system.img exists... to avoid unstable paths
  // (e.g. /tmp/libavb.12345) in the output we need to run this from the test
  // directory itself. It's a little ugly but it works.
  char cwdbuf[PATH_MAX];
  ASSERT_NE(nullptr, getcwd(cwdbuf, sizeof cwdbuf));
  EXPECT_COMMAND(0,
                 "cd %s && (%s/avbtool.py verify_image "
                 "--image vbmeta.img --follow_chain_partitions > out.txt)",
                 testdir_.value().c_str(),
                 cwdbuf);
  base::FilePath out_path = testdir_.Append("out.txt");
  std::string out;
  ASSERT_TRUE(base::ReadFileToString(out_path, &out));
  EXPECT_EQ(
      "Verifying image vbmeta.img using embedded public key\n"
      "vbmeta: Successfully verified SHA256_RSA2048 vbmeta struct in "
      "vbmeta.img\n"
      "system: Chained but ROLLBACK_SLOT (which is 1) and KEY (which has sha1 "
      "2597c218aae470a130f61162feaae70afd97f011) not specified\n"
      "--\n"
      "Verifying image system.img using embedded public key\n"
      "vbmeta: Successfully verified footer and SHA256_RSA4096 vbmeta struct "
      "in system.img\n"
      "system: Successfully verified sha1 hashtree of system.img for image of "
      "8388608 bytes\n",
      out);

  // Make sure we also follow partitions *even* when specifying
  // --expect_chain_partition. The output is slightly different from above.
  EXPECT_COMMAND(0,
                 "cd %s && (%s/avbtool.py verify_image "
                 "--image vbmeta.img --expected_chain_partition system:1:%s "
                 "--follow_chain_partitions > out.txt)",
                 testdir_.value().c_str(),
                 cwdbuf,
                 pk4096_path.value().c_str());
  ASSERT_TRUE(base::ReadFileToString(out_path, &out));
  EXPECT_EQ(
      "Verifying image vbmeta.img using embedded public key\n"
      "vbmeta: Successfully verified SHA256_RSA2048 vbmeta struct in "
      "vbmeta.img\n"
      "system: Successfully verified chain partition descriptor matches "
      "expected data\n"
      "--\n"
      "Verifying image system.img using embedded public key\n"
      "vbmeta: Successfully verified footer and SHA256_RSA4096 vbmeta struct "
      "in system.img\n"
      "system: Successfully verified sha1 hashtree of system.img for image of "
      "8388608 bytes\n",
      out);
}

TEST_F(AvbToolTest, VerifyImageChainPartitionOtherVBMeta) {
  base::FilePath pk4096_path = testdir_.Append("testkey_rsa4096.avbpubkey");
  EXPECT_COMMAND(
      0,
      "./avbtool.py extract_public_key --key test/data/testkey_rsa4096.pem"
      " --output %s",
      pk4096_path.value().c_str());

  const size_t system_partition_size = 10 * 1024 * 1024;
  const size_t system_image_size = 8 * 1024 * 1024;
  base::FilePath system_path = GenerateImage("system.img", system_image_size);
  EXPECT_COMMAND(0,
                 "./avbtool.py add_hashtree_footer --salt d00df00d --image %s "
                 "--partition_size %zd --partition_name system "
                 "--internal_release_string \"\" "
                 "--algorithm SHA256_RSA4096 "
                 "--key test/data/testkey_rsa4096.pem ",
                 system_path.value().c_str(),
                 system_partition_size,
                 pk4096_path.value().c_str());

  GenerateVBMetaImage(
      "vbmeta.img",
      "SHA256_RSA2048",
      0,
      base::FilePath("test/data/testkey_rsa2048.pem"),
      base::StringPrintf("--chain_partition vbmeta_google:1:%s ",
                         pk4096_path.value().c_str()));

  // Should not fail (name, rollback_index, contents all correct).
  EXPECT_COMMAND(0,
                 "./avbtool.py verify_image "
                 "--image %s "
                 "--expected_chain_partition vbmeta_google:1:%s",
                 vbmeta_image_path_.value().c_str(),
                 pk4096_path.value().c_str());

  // Should not fail (looks in system.img image).
  EXPECT_COMMAND(0,
                 "./avbtool.py verify_image "
                 "--image %s ",
                 system_path.value().c_str());

  // Extract the vbmeta blob from the footer in system.img, put it into
  // vbmeta_google.img, and erase the footer from system.img (but keep
  // the hash tree in system.img)
  base::FilePath vbmeta_google_path = GenerateImage("vbmeta_google.img", 0);
  EXPECT_COMMAND(0,
                 "./avbtool.py extract_vbmeta_image"
                 " --image %s"
                 " --output %s",
                 system_path.value().c_str(),
                 vbmeta_google_path.value().c_str());
  EXPECT_COMMAND(0,
                 "./avbtool.py erase_footer"
                 " --image %s --keep_hashtree",
                 system_path.value().c_str());

  // Should not fail - looks in system.img's detached vbmeta (vbmeta_google.img)
  // for vbmeta blob and system.img for the actual hashtree.
  EXPECT_COMMAND(0,
                 "./avbtool.py verify_image "
                 "--image %s ",
                 vbmeta_google_path.value().c_str());
}

TEST_F(AvbToolTest, PrintPartitionDigests) {
  base::FilePath pk4096_path = testdir_.Append("testkey_rsa4096.avbpubkey");
  EXPECT_COMMAND(
      0,
      "./avbtool.py extract_public_key --key test/data/testkey_rsa4096.pem"
      " --output %s",
      pk4096_path.value().c_str());

  const size_t boot_partition_size = 16 * 1024 * 1024;
  const size_t boot_image_size = 5 * 1024 * 1024;
  base::FilePath boot_path = GenerateImage("boot.img", boot_image_size);
  EXPECT_COMMAND(0,
                 "./avbtool.py add_hash_footer"
                 " --image %s"
                 " --rollback_index 0"
                 " --partition_name boot"
                 " --partition_size %zd"
                 " --salt deadbeef"
                 " --internal_release_string \"\"",
                 boot_path.value().c_str(),
                 boot_partition_size);

  GenerateVBMetaImage("vbmeta.img",
                      "SHA256_RSA2048",
                      0,
                      base::FilePath("test/data/testkey_rsa2048.pem"),
                      base::StringPrintf("--chain_partition system:1:%s "
                                         "--include_descriptors_from_image %s",
                                         pk4096_path.value().c_str(),
                                         boot_path.value().c_str()));

  const size_t system_partition_size = 10 * 1024 * 1024;
  const size_t system_image_size = 8 * 1024 * 1024;
  base::FilePath system_path = GenerateImage("system.img", system_image_size);
  EXPECT_COMMAND(0,
                 "./avbtool.py add_hashtree_footer --salt d00df00d --image %s "
                 "--partition_size %zd --partition_name system "
                 "--algorithm SHA256_RSA4096 "
                 "--key test/data/testkey_rsa4096.pem "
                 "--internal_release_string \"\" ",
                 system_path.value().c_str(),
                 system_partition_size);

  base::FilePath out_path = testdir_.Append("out.txt");
  std::string out;

  // Normal output
  EXPECT_COMMAND(0,
                 "./avbtool.py print_partition_digests --image %s --output %s",
                 vbmeta_image_path_.value().c_str(),
                 out_path.value().c_str());
  ASSERT_TRUE(base::ReadFileToString(out_path, &out));
  EXPECT_EQ(
      "system: d52d93c988d336a79abe1c05240ae9a79a9b7d61\n"
      "boot: "
      "184cb36243adb8b87d2d8c4802de32125fe294ec46753d732144ee65df68a23d\n",
      out);

  // JSON output
  EXPECT_COMMAND(
      0,
      "./avbtool.py print_partition_digests --image %s --json --output %s",
      vbmeta_image_path_.value().c_str(),
      out_path.value().c_str());
  ASSERT_TRUE(base::ReadFileToString(out_path, &out));
  // The trailing whitespace comes from python. If they fix that bug we need
  // to update this test...
  EXPECT_EQ(
      "{\n"
      "  \"partitions\": [\n"
      "    {\n"
      "      \"name\": \"system\",\n"
      "      \"digest\": \"d52d93c988d336a79abe1c05240ae9a79a9b7d61\"\n"
      "    },\n"
      "    {\n"
      "      \"name\": \"boot\",\n"
      "      \"digest\": "
      "\"184cb36243adb8b87d2d8c4802de32125fe294ec46753d732144ee65df68a23d\"\n"
      "    }\n"
      "  ]\n"
      "}",
      out);
}

class AvbToolTest_PrintRequiredVersion : public AvbToolTest {
 protected:
  const char* kOutputFile = "versions.txt";

  void PrintWithAddHashFooter(int target_required_minor_version) {
    std::string extra_args;
    if (target_required_minor_version == 1) {
      // The --do_not_use_ab option will require 1.1.
      extra_args = "--do_not_use_ab";
    } else if (target_required_minor_version == 2) {
      extra_args = "--rollback_index_location 2";
    }

    const size_t boot_partition_size = 16 * 1024 * 1024;
    base::FilePath output_path = testdir_.Append(kOutputFile);
    EXPECT_COMMAND(0,
                   "./avbtool.py add_hash_footer"
                   " --rollback_index 0"
                   " --partition_name boot"
                   " --partition_size %zd"
                   " --salt deadbeef"
                   " --internal_release_string \"\""
                   " %s"
                   " --print_required_libavb_version > %s",
                   boot_partition_size,
                   extra_args.c_str(),
                   output_path.value().c_str());
    CheckVersion(target_required_minor_version);
  }

  void PrintWithAddHashtreeFooter(int target_required_minor_version) {
    std::string extra_args;
    if (target_required_minor_version == 1) {
      // The --do_not_use_ab option will require 1.1.
      extra_args = "--do_not_use_ab --check_at_most_once";
    } else if (target_required_minor_version == 2) {
      extra_args = "--rollback_index_location 2";
    }
    const size_t system_partition_size = 10 * 1024 * 1024;
    base::FilePath output_path = testdir_.Append(kOutputFile);
    EXPECT_COMMAND(0,
                   "./avbtool.py add_hashtree_footer --salt d00df00d "
                   "--partition_size %zd --partition_name system "
                   "--internal_release_string \"\""
                   " %s"
                   " --print_required_libavb_version > %s",
                   system_partition_size,
                   extra_args.c_str(),
                   output_path.value().c_str());
    CheckVersion(target_required_minor_version);
  }

  void PrintWithMakeVbmetaImage(int target_required_minor_version) {
    std::string extra_args;
    if (target_required_minor_version == 1) {
      // An included descriptor that requires 1.1 will require 1.1 for vbmeta.
      const size_t boot_partition_size = 16 * 1024 * 1024;
      base::FilePath image_path = GenerateImage("test_print_version", 1024);
      EXPECT_COMMAND(0,
                     "./avbtool.py add_hash_footer --salt d00df00d "
                     "--hash_algorithm sha256 --image %s "
                     "--partition_size %d --partition_name foobar "
                     "--algorithm SHA256_RSA2048 "
                     "--key test/data/testkey_rsa2048.pem "
                     "--internal_release_string \"\" "
                     "--do_not_use_ab",
                     image_path.value().c_str(),
                     (int)boot_partition_size);
      extra_args = base::StringPrintf("--include_descriptors_from_image %s",
                                      image_path.value().c_str());
    } else if (target_required_minor_version == 2) {
      extra_args = "--rollback_index_location 2";
    }

    base::FilePath output_path = testdir_.Append(kOutputFile);
    EXPECT_COMMAND(0,
                   "./avbtool.py make_vbmeta_image "
                   "--algorithm SHA256_RSA2048 "
                   "--key test/data/testkey_rsa2048.pem "
                   "--internal_release_string \"\""
                   " %s"
                   " --print_required_libavb_version > %s",
                   extra_args.c_str(),
                   output_path.value().c_str());
    CheckVersion(target_required_minor_version);
  }

  void CheckVersion(int expected_required_minor_version) {
    base::FilePath output_path = testdir_.Append(kOutputFile);
    std::string output;
    ASSERT_TRUE(base::ReadFileToString(output_path, &output));
    EXPECT_EQ(output,
              base::StringPrintf("1.%d\n", expected_required_minor_version));
  }
};

TEST_F(AvbToolTest_PrintRequiredVersion, HashFooter_1_0) {
  PrintWithAddHashFooter(0);
}

TEST_F(AvbToolTest_PrintRequiredVersion, HashFooter_1_1) {
  PrintWithAddHashFooter(1);
}

TEST_F(AvbToolTest_PrintRequiredVersion, HashFooter_1_2) {
  PrintWithAddHashFooter(2);
}

TEST_F(AvbToolTest_PrintRequiredVersion, HashtreeFooter_1_0) {
  PrintWithAddHashtreeFooter(0);
}

TEST_F(AvbToolTest_PrintRequiredVersion, HashtreeFooter_1_1) {
  PrintWithAddHashtreeFooter(1);
}

TEST_F(AvbToolTest_PrintRequiredVersion, HashtreeFooter_1_2) {
  PrintWithAddHashtreeFooter(2);
}

TEST_F(AvbToolTest_PrintRequiredVersion, Vbmeta_1_0) {
  PrintWithMakeVbmetaImage(0);
}

TEST_F(AvbToolTest_PrintRequiredVersion, Vbmeta_1_1) {
  PrintWithMakeVbmetaImage(1);
}

TEST_F(AvbToolTest_PrintRequiredVersion, Vbmeta_1_2) {
  PrintWithMakeVbmetaImage(2);
}

TEST_F(AvbToolTest, MakeCertPikCertificate) {
  base::FilePath subject_path = testdir_.Append("tmp_subject");
  ASSERT_TRUE(base::WriteFile(subject_path, "fake PIK subject", 16));
  base::FilePath pubkey_path = testdir_.Append("tmp_pubkey.pem");
  EXPECT_COMMAND(
      0,
      "openssl pkey -pubout -in test/data/testkey_cert_pik.pem -out %s",
      pubkey_path.value().c_str());

  base::FilePath output_path = testdir_.Append("tmp_certificate.bin");
  EXPECT_COMMAND(0,
                 "./avbtool.py make_certificate"
                 " --subject %s"
                 " --subject_key %s"
                 " --subject_key_version 42"
                 " --subject_is_intermediate_authority"
                 " --authority_key test/data/testkey_cert_prk.pem"
                 " --output %s",
                 subject_path.value().c_str(),
                 pubkey_path.value().c_str(),
                 output_path.value().c_str());

  EXPECT_COMMAND(0,
                 "diff test/data/cert_pik_certificate.bin %s",
                 output_path.value().c_str());
}

TEST_F(AvbToolTest, MakeCertPskCertificate) {
  base::FilePath pubkey_path = testdir_.Append("tmp_pubkey.pem");
  EXPECT_COMMAND(
      0,
      "openssl pkey -pubout -in test/data/testkey_cert_psk.pem -out %s",
      pubkey_path.value().c_str());

  base::FilePath output_path = testdir_.Append("tmp_certificate.bin");
  EXPECT_COMMAND(0,
                 "./avbtool.py make_certificate"
                 " --subject test/data/cert_product_id.bin"
                 " --subject_key %s"
                 " --subject_key_version 42"
                 " --authority_key test/data/testkey_cert_pik.pem"
                 " --output %s",
                 pubkey_path.value().c_str(),
                 output_path.value().c_str());

  EXPECT_COMMAND(0,
                 "diff test/data/cert_psk_certificate.bin %s",
                 output_path.value().c_str());
}

TEST_F(AvbToolTest, MakeCertPukCertificate) {
  base::FilePath pubkey_path = testdir_.Append("tmp_pubkey.pem");
  EXPECT_COMMAND(
      0,
      "openssl pkey -pubout -in test/data/testkey_cert_puk.pem -out %s",
      pubkey_path.value().c_str());

  base::FilePath output_path = testdir_.Append("tmp_certificate.bin");

  // Test with both legacy manual unlock --usage as well as --usage_for_unlock.
  std::string usage_args[] = {"--usage com.google.android.things.vboot.unlock",
                              "--usage_for_unlock"};
  for (const auto& usage : usage_args) {
    EXPECT_COMMAND(0,
                   "./avbtool.py make_certificate"
                   " --subject test/data/cert_product_id.bin"
                   " --subject_key %s"
                   " --subject_key_version 42"
                   " %s"
                   " --authority_key test/data/testkey_cert_pik.pem"
                   " --output %s",
                   pubkey_path.value().c_str(),
                   usage.c_str(),
                   output_path.value().c_str());

    EXPECT_COMMAND(0,
                   "diff test/data/cert_puk_certificate.bin %s",
                   output_path.value().c_str());
  }
}

TEST_F(AvbToolTest, MakeCertPermanentAttributes) {
  base::FilePath pubkey_path = testdir_.Append("tmp_pubkey.pem");
  EXPECT_COMMAND(
      0,
      "openssl pkey -pubout -in test/data/testkey_cert_prk.pem -out %s",
      pubkey_path.value().c_str());

  base::FilePath output_path = testdir_.Append("tmp_attributes.bin");
  EXPECT_COMMAND(0,
                 "./avbtool.py make_cert_permanent_attributes"
                 " --root_authority_key %s"
                 " --product_id test/data/cert_product_id.bin"
                 " --output %s",
                 pubkey_path.value().c_str(),
                 output_path.value().c_str());

  EXPECT_COMMAND(0,
                 "diff test/data/cert_permanent_attributes.bin %s",
                 output_path.value().c_str());
}

TEST_F(AvbToolTest, MakeCertMetadata) {
  base::FilePath output_path = testdir_.Append("tmp_metadata.bin");

  EXPECT_COMMAND(
      0,
      "./avbtool.py make_cert_metadata"
      " --intermediate_key_certificate test/data/cert_pik_certificate.bin"
      " --product_key_certificate test/data/cert_psk_certificate.bin"
      " --output %s",
      output_path.value().c_str());

  EXPECT_COMMAND(
      0, "diff test/data/cert_metadata.bin %s", output_path.value().c_str());
}

TEST_F(AvbToolTest, MakeCertUnlockCredential) {
  base::FilePath output_path = testdir_.Append("tmp_credential.bin");

  EXPECT_COMMAND(
      0,
      "./avbtool.py make_cert_unlock_credential"
      " --intermediate_key_certificate test/data/cert_pik_certificate.bin"
      " --unlock_key_certificate test/data/cert_puk_certificate.bin"
      " --challenge test/data/cert_unlock_challenge.bin"
      " --unlock_key test/data/testkey_cert_puk.pem"
      " --output %s",
      output_path.value().c_str());

  EXPECT_COMMAND(0,
                 "diff test/data/cert_unlock_credential.bin %s",
                 output_path.value().c_str());
}

}  // namespace avb
