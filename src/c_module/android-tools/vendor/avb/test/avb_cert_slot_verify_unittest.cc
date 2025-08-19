/*
 * Copyright (C) 2017 The Android Open Source Project
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

#include "examples/cert/avb_cert_slot_verify.h"

#include <base/files/file_util.h>
#include <gtest/gtest.h>
#include <openssl/sha.h>
#include <stdio.h>
#include <string.h>

#include "avb_unittest_util.h"
#include "fake_avb_ops.h"

namespace {

const char kMetadataPath[] = "test/data/cert_metadata.bin";
const char kPermanentAttributesPath[] =
    "test/data/cert_permanent_attributes.bin";
const uint64_t kNewRollbackValue = 42;

} /* namespace */

namespace avb {

// A fixture for testing avb_cert_slot_verify() with libavb_cert. This test is
// parameterized on the initial stored rollback index (same value used in all
// relevant locations).
class AvbCertSlotVerifyExampleTest
    : public BaseAvbToolTest,
      public FakeAvbOpsDelegateWithDefaults,
      public ::testing::WithParamInterface<uint64_t> {
 public:
  ~AvbCertSlotVerifyExampleTest() override = default;

  void SetUp() override {
    BaseAvbToolTest::SetUp();
    ReadCertDefaultData();
    ops_.set_partition_dir(testdir_);
    ops_.set_delegate(this);
    ops_.set_permanent_attributes(attributes_);
    ops_.set_stored_is_device_unlocked(false);
  }

  // FakeAvbOpsDelegate overrides.
  AvbIOResult validate_vbmeta_public_key(AvbOps* ops,
                                         const uint8_t* public_key_data,
                                         size_t public_key_length,
                                         const uint8_t* public_key_metadata,
                                         size_t public_key_metadata_length,
                                         bool* out_key_is_trusted) override {
    // Send to libavb_cert implementation.
    ++num_cert_calls_;
    return avb_cert_validate_vbmeta_public_key(ops,
                                               public_key_data,
                                               public_key_length,
                                               public_key_metadata,
                                               public_key_metadata_length,
                                               out_key_is_trusted);
  }

  AvbIOResult write_rollback_index(AvbOps* ops,
                                   size_t rollback_index_slot,
                                   uint64_t rollback_index) override {
    num_write_rollback_calls_++;
    return ops_.write_rollback_index(ops, rollback_index_slot, rollback_index);
  }

  void set_key_version(size_t rollback_index_location,
                       uint64_t key_version) override {
    num_key_version_calls_++;
    return ops_.set_key_version(rollback_index_location, key_version);
  }

  AvbIOResult get_random(size_t num_bytes, uint8_t* output) override {
    return ops_.get_random(num_bytes, output);
  }

  void RunSlotVerify() {
    ops_.set_stored_rollback_indexes(
        {{0, initial_rollback_value_},
         {AVB_CERT_PIK_VERSION_LOCATION, initial_rollback_value_},
         {AVB_CERT_PSK_VERSION_LOCATION, initial_rollback_value_}});
    std::string metadata_option = "--public_key_metadata=";
    metadata_option += kMetadataPath;
    GenerateVBMetaImage("vbmeta_a.img",
                        "SHA512_RSA4096",
                        kNewRollbackValue,
                        base::FilePath("test/data/testkey_cert_psk.pem"),
                        metadata_option);
    SHA256(vbmeta_image_.data(), vbmeta_image_.size(), expected_vbh_extension_);

    ops_.set_expected_public_key(
        PublicKeyAVB(base::FilePath("test/data/testkey_cert_psk.pem")));

    AvbSlotVerifyData* slot_data = NULL;
    EXPECT_EQ(expected_result_,
              avb_cert_slot_verify(ops_.avb_cert_ops(),
                                   "_a",
                                   lock_state_,
                                   slot_state_,
                                   oem_data_state_,
                                   &slot_data,
                                   actual_vbh_extension_));
    if (expected_result_ == AVB_SLOT_VERIFY_RESULT_OK) {
      EXPECT_NE(nullptr, slot_data);
      avb_slot_verify_data_free(slot_data);
      // Make sure libavb_cert is being run.
      EXPECT_EQ(1, num_cert_calls_);
      // Make sure we're hooking set_key_version.
      EXPECT_EQ(0, num_key_version_calls_);
    }
  }

  void CheckVBH() {
    if (expected_result_ != AVB_SLOT_VERIFY_RESULT_OK ||
        lock_state_ == AVB_CERT_UNLOCKED) {
      memset(&expected_vbh_extension_, 0, AVB_SHA256_DIGEST_SIZE);
    }
    // Check that the VBH was correctly calculated.
    EXPECT_EQ(0,
              memcmp(actual_vbh_extension_,
                     expected_vbh_extension_,
                     AVB_SHA256_DIGEST_SIZE));
  }

  void CheckNewRollbackState() {
    uint64_t expected_rollback_value = kNewRollbackValue;
    if (expected_result_ != AVB_SLOT_VERIFY_RESULT_OK ||
        lock_state_ == AVB_CERT_UNLOCKED ||
        slot_state_ != AVB_CERT_SLOT_MARKED_SUCCESSFUL) {
      // Check that rollback indexes were unmodified.
      expected_rollback_value = initial_rollback_value_;
    }
    // Check that all rollback indexes have the expected value.
    std::map<size_t, uint64_t> stored_rollback_indexes =
        ops_.get_stored_rollback_indexes();
    EXPECT_EQ(expected_rollback_value, stored_rollback_indexes[0]);
    EXPECT_EQ(expected_rollback_value,
              stored_rollback_indexes[AVB_CERT_PIK_VERSION_LOCATION]);
    EXPECT_EQ(expected_rollback_value,
              stored_rollback_indexes[AVB_CERT_PSK_VERSION_LOCATION]);
    // Check that if the rollback did not need to change, there were no writes.
    if (initial_rollback_value_ == kNewRollbackValue ||
        initial_rollback_value_ == expected_rollback_value) {
      EXPECT_EQ(0, num_write_rollback_calls_);
    } else {
      EXPECT_NE(0, num_write_rollback_calls_);
    }
  }

 protected:
  AvbCertPermanentAttributes attributes_;
  int num_cert_calls_ = 0;
  int num_key_version_calls_ = 0;
  int num_write_rollback_calls_ = 0;
  AvbSlotVerifyResult expected_result_ = AVB_SLOT_VERIFY_RESULT_OK;
  uint64_t initial_rollback_value_ = 0;
  AvbCertLockState lock_state_ = AVB_CERT_LOCKED;
  AvbCertSlotState slot_state_ = AVB_CERT_SLOT_MARKED_SUCCESSFUL;
  AvbCertOemDataState oem_data_state_ = AVB_CERT_OEM_DATA_NOT_USED;
  uint8_t expected_vbh_extension_[AVB_SHA256_DIGEST_SIZE] = {};
  uint8_t actual_vbh_extension_[AVB_SHA256_DIGEST_SIZE] = {};

 private:
  void ReadCertDefaultData() {
    std::string tmp;
    ASSERT_TRUE(
        base::ReadFileToString(base::FilePath(kPermanentAttributesPath), &tmp));
    ASSERT_EQ(tmp.size(), sizeof(AvbCertPermanentAttributes));
    memcpy(&attributes_, tmp.data(), tmp.size());
  }
};

TEST_P(AvbCertSlotVerifyExampleTest, RunWithStartingIndex) {
  initial_rollback_value_ = GetParam();
  RunSlotVerify();
  CheckVBH();
  CheckNewRollbackState();
}

INSTANTIATE_TEST_CASE_P(P,
                        AvbCertSlotVerifyExampleTest,
                        ::testing::Values(0,
                                          1,
                                          kNewRollbackValue / 2,
                                          kNewRollbackValue - 1,
                                          kNewRollbackValue));

TEST_F(AvbCertSlotVerifyExampleTest, RunUnlocked) {
  lock_state_ = AVB_CERT_UNLOCKED;
  RunSlotVerify();
  CheckVBH();
  CheckNewRollbackState();
}

TEST_F(AvbCertSlotVerifyExampleTest, RunWithSlotNotMarkedSuccessful) {
  slot_state_ = AVB_CERT_SLOT_NOT_MARKED_SUCCESSFUL;
  RunSlotVerify();
  CheckVBH();
  CheckNewRollbackState();
}

TEST_F(AvbCertSlotVerifyExampleTest, RunWithOemData) {
  oem_data_state_ = AVB_CERT_OEM_DATA_USED;
  RunSlotVerify();
  CheckVBH();
  CheckNewRollbackState();
}

}  // namespace avb
