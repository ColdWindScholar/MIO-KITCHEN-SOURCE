/*
 * Copyright (C) 2018 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include <stdlib.h>

#include <algorithm>
#include <memory>
#include <string>
#include <vector>

#include <gtest/gtest.h>
#include <openssl/evp.h>

#include "build_verity_tree_utils.h"
#include "verity/hash_tree_builder.h"

// The hex string we are using in build_image.py
// aee087a5be3b982978c923f566a94613496b417f2af592639bc80d141e34dfe7
constexpr unsigned char kSaltHex[] = {
    0xae, 0xe0, 0x87, 0xa5, 0xbe, 0x3b, 0x98, 0x29, 0x78, 0xc9, 0x23,
    0xf5, 0x66, 0xa9, 0x46, 0x13, 0x49, 0x6b, 0x41, 0x7f, 0x2a, 0xf5,
    0x92, 0x63, 0x9b, 0xc8, 0x0d, 0x14, 0x1e, 0x34, 0xdf, 0xe7};

class BuildVerityTreeTest : public ::testing::Test {
 protected:
  void SetUp() override {
    salt_hex =
        std::vector<unsigned char>(kSaltHex, kSaltHex + sizeof(kSaltHex));
    builder.reset(new HashTreeBuilder(4096, EVP_sha256()));
  }

  const std::vector<unsigned char>& zero_block_hash() const {
    return builder->zero_block_hash_;
  }
  const std::vector<std::vector<unsigned char>>& verity_tree() const {
    return builder->verity_tree_;
  }

  void GenerateHashTree(const std::vector<unsigned char>& data,
                        const std::vector<unsigned char>& salt) {
    ASSERT_TRUE(builder->Initialize(data.size(), salt));
    ASSERT_TRUE(builder->Update(data.data(), data.size()));
    ASSERT_TRUE(builder->BuildHashTree());
  }

  std::vector<unsigned char> salt_hex;
  std::unique_ptr<HashTreeBuilder> builder;
};

TEST_F(BuildVerityTreeTest, CalculateSize) {
  // The hash of source data will occupy at least one block
  ASSERT_EQ(4096u, builder->CalculateSize(1));
  // Sha256 hash of 128 blocks fits into one block.
  ASSERT_EQ(4096u, builder->CalculateSize(128 * 4096));
  // Requires 3 blocks to hold more data.
  ASSERT_EQ(12288u, builder->CalculateSize(128 * 4096 + 1));

  ASSERT_EQ(20811776u, builder->CalculateSize(2641915904));
}

TEST_F(BuildVerityTreeTest, InitializeBuilder) {
  // data_size should be divisible by 4096
  ASSERT_FALSE(builder->Initialize(4095, salt_hex));

  ASSERT_TRUE(builder->Initialize(4096, salt_hex));
  ASSERT_EQ(1u, verity_tree().size());
  ASSERT_EQ("6eb8c4e1bce842d137f18b27beb857d3b43899d178090537ad7a0fbe3bf4126a",
            HashTreeBuilder::BytesArrayToString(zero_block_hash()));
}

TEST_F(BuildVerityTreeTest, HashSingleBlock) {
  std::vector<unsigned char> data(4096, 1);

  GenerateHashTree(data, salt_hex);

  ASSERT_EQ(1u, verity_tree().size());
  ASSERT_EQ("e69eb527b16f933483768e92de9bca45f6cc09208525d408436bb362eb865d32",
            HashTreeBuilder::BytesArrayToString(builder->root_hash()));
}

TEST_F(BuildVerityTreeTest, HashSingleLevel) {
  std::vector<unsigned char> data(128 * 4096, 0);

  GenerateHashTree(data, salt_hex);

  ASSERT_EQ(1u, verity_tree().size());
  ASSERT_EQ("62a4fbe8c9036168ba77fe3e3fd78dd6ed963aeb8aaaa36e84f5c7f9107c6b78",
            HashTreeBuilder::BytesArrayToString(builder->root_hash()));
}

TEST_F(BuildVerityTreeTest, HashSingleLevel_blake2b256) {
  std::vector<unsigned char> data(128 * 4096, 0x0);

  builder.reset(
      new HashTreeBuilder(4096, HashTreeBuilder::HashFunction("blake2b-256")));

  GenerateHashTree(data, salt_hex);
  ASSERT_EQ(1u, verity_tree().size());
  ASSERT_EQ("6d5b006af5308523f7db6956c60b2650ff3e7edab1e2194cc8ee19b1a1398c03",
            HashTreeBuilder::BytesArrayToString(builder->root_hash()));
}

TEST_F(BuildVerityTreeTest, HashMultipleLevels) {
  std::vector<unsigned char> data(129 * 4096, 0xff);

  GenerateHashTree(data, salt_hex);

  ASSERT_EQ(2u, verity_tree().size());
  ASSERT_EQ(2 * 4096u, verity_tree()[0].size());
  ASSERT_EQ("9e74f2d47a990c276093760f01de5e9039883e808286ee9492c9cafe9e4ff825",
            HashTreeBuilder::BytesArrayToString(builder->root_hash()));
}

TEST_F(BuildVerityTreeTest, StreamingDataMultipleBlocks) {
  std::vector<unsigned char> data(256 * 4096);
  for (size_t i = 0; i < 256; i++) {
    std::fill_n(data.begin() + i * 4096, 4096, i);
  }

  ASSERT_TRUE(builder->Initialize(data.size(), salt_hex));

  size_t offset = 0;
  while (offset < data.size()) {
    size_t data_length =
        std::min<size_t>(rand() % 10 * 4096, data.size() - offset);
    ASSERT_TRUE(builder->Update(data.data() + offset, data_length));
    offset += data_length;
  }

  ASSERT_TRUE(builder->BuildHashTree());
  ASSERT_EQ(2u, verity_tree().size());
  ASSERT_EQ(2 * 4096u, verity_tree()[0].size());
  ASSERT_EQ("6e73d59b0b6baf026e921814979a7db02244c95a46b869a17aa1310dad066deb",
            HashTreeBuilder::BytesArrayToString(builder->root_hash()));
}

TEST_F(BuildVerityTreeTest, StreamingDataPartialBlocks) {
  std::vector<unsigned char> data(256 * 4096);
  for (size_t i = 0; i < 256; i++) {
    std::fill_n(data.begin() + i * 4096, 4096, i);
  }

  ASSERT_TRUE(builder->Initialize(data.size(), salt_hex));

  size_t offset = 0;
  while (offset < data.size()) {
    size_t data_length = std::min<size_t>(rand() % 40960, data.size() - offset);
    ASSERT_TRUE(builder->Update(data.data() + offset, data_length));
    offset += data_length;
  }

  ASSERT_TRUE(builder->BuildHashTree());
  ASSERT_EQ(2u, verity_tree().size());
  ASSERT_EQ(2 * 4096u, verity_tree()[0].size());
  ASSERT_EQ("6e73d59b0b6baf026e921814979a7db02244c95a46b869a17aa1310dad066deb",
            HashTreeBuilder::BytesArrayToString(builder->root_hash()));
}

TEST_F(BuildVerityTreeTest, CalculateRootDigest) {
  std::vector<unsigned char> data(256 * 4096);
  for (size_t i = 0; i < 256; i++) {
    std::fill_n(data.begin() + i * 4096, 4096, i);
  }

  ASSERT_TRUE(builder->Initialize(data.size(), salt_hex));

  size_t offset = 0;
  while (offset < data.size()) {
    size_t data_length = std::min<size_t>(rand() % 40960, data.size() - offset);
    ASSERT_TRUE(builder->Update(data.data() + offset, data_length));
    offset += data_length;
  }

  ASSERT_TRUE(builder->BuildHashTree());
  ASSERT_EQ(2u, verity_tree().size());
  ASSERT_EQ(2 * 4096u, verity_tree()[0].size());
  std::string expected_root_digest =  HashTreeBuilder::BytesArrayToString(builder->root_hash());

  std::vector<unsigned char> actual_root_digest;
  ASSERT_TRUE(builder->CalculateRootDigest(verity_tree().back(), &actual_root_digest));
  ASSERT_EQ(expected_root_digest, HashTreeBuilder::BytesArrayToString(actual_root_digest));
}

TEST_F(BuildVerityTreeTest, SHA1MultipleBlocks) {
  std::vector<unsigned char> data(128 * 4096, 0xff);

  builder.reset(
      new HashTreeBuilder(4096, HashTreeBuilder::HashFunction("SHA1")));

  GenerateHashTree(data, salt_hex);
  ASSERT_EQ(1u, verity_tree().size());
  ASSERT_EQ("7ea287e6167929988810077abaafbc313b2b8593000000000000000000000000",
            HashTreeBuilder::BytesArrayToString(builder->root_hash()));
}
