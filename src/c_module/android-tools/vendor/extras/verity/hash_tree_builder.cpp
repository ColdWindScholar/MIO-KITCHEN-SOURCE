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

#include "verity/hash_tree_builder.h"

#include <algorithm>
#include <functional>
#include <memory>

#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/stringprintf.h>
#include <android-base/strings.h>
#include <android-base/unique_fd.h>
#include <openssl/bn.h>

#include "build_verity_tree_utils.h"

const EVP_MD* HashTreeBuilder::HashFunction(const std::string& hash_name) {
  if (android::base::EqualsIgnoreCase(hash_name, "sha1")) {
    return EVP_sha1();
  }
  if (android::base::EqualsIgnoreCase(hash_name, "sha256")) {
    return EVP_sha256();
  }
  if (android::base::EqualsIgnoreCase(hash_name, "sha384")) {
    return EVP_sha384();
  }
  if (android::base::EqualsIgnoreCase(hash_name, "sha512")) {
    return EVP_sha512();
  }
  if (android::base::EqualsIgnoreCase(hash_name, "blake2b-256")) {
    return EVP_blake2b256();
  }

  LOG(ERROR) << "Unsupported hash algorithm " << hash_name;
  return nullptr;
}

HashTreeBuilder::HashTreeBuilder(size_t block_size, const EVP_MD* md)
    : block_size_(block_size), data_size_(0), md_(md) {
  CHECK(md_ != nullptr) << "Failed to initialize md";

  hash_size_raw_ = EVP_MD_size(md_);

  // Round up the hash size to the next power of 2.
  hash_size_ = 1;
  while (hash_size_ < hash_size_raw_) {
    hash_size_ = hash_size_ << 1;
  }
  CHECK_LT(hash_size_ * 2, block_size_);
}

std::string HashTreeBuilder::BytesArrayToString(
    const std::vector<unsigned char>& bytes) {
  std::string result;
  for (const auto& c : bytes) {
    result += android::base::StringPrintf("%02x", c);
  }
  return result;
}

bool HashTreeBuilder::ParseBytesArrayFromString(
    const std::string& hex_string, std::vector<unsigned char>* bytes) {
  if (hex_string.size() % 2 != 0) {
    LOG(ERROR) << "Hex string size must be even number " << hex_string;
    return false;
  }

  BIGNUM* bn = nullptr;
  if (!BN_hex2bn(&bn, hex_string.c_str())) {
    LOG(ERROR) << "Failed to parse hex in " << hex_string;
    return false;
  }
  std::unique_ptr<BIGNUM, decltype(&BN_free)> guard(bn, BN_free);

  size_t bytes_size = BN_num_bytes(bn);
  bytes->resize(bytes_size);
  if (BN_bn2bin(bn, bytes->data()) != bytes_size) {
    LOG(ERROR) << "Failed to convert hex to bytes " << hex_string;
    return false;
  }
  return true;
}

uint64_t HashTreeBuilder::CalculateSize(
    uint64_t input_size, size_t block_size, size_t hash_size) {
  uint64_t verity_blocks = 0;
  size_t level_blocks;
  size_t levels = 0;
  do {
    level_blocks =
        verity_tree_blocks(input_size, block_size, hash_size, levels);
    levels++;
    verity_blocks += level_blocks;
  } while (level_blocks > 1);

  return verity_blocks * block_size;
}

bool HashTreeBuilder::Initialize(int64_t expected_data_size,
                                 const std::vector<unsigned char>& salt) {
  data_size_ = expected_data_size;
  salt_ = salt;

  if (data_size_ % block_size_ != 0) {
    LOG(ERROR) << "file size " << data_size_
               << " is not a multiple of block size " << block_size_;
    return false;
  }

  // Reserve enough space for the hash of the input data.
  size_t base_level_blocks =
      verity_tree_blocks(data_size_, block_size_, hash_size_, 0);
  std::vector<unsigned char> base_level;
  base_level.reserve(base_level_blocks * block_size_);
  verity_tree_.emplace_back(std::move(base_level));

  // Save the hash of the zero block to avoid future recalculation.
  std::vector<unsigned char> zero_block(block_size_, 0);
  zero_block_hash_.resize(hash_size_);
  HashBlock(zero_block.data(), zero_block_hash_.data());

  return true;
}

bool HashTreeBuilder::HashBlock(const unsigned char* block,
                                unsigned char* out) {
  unsigned int s;
  int ret = 1;

  EVP_MD_CTX* mdctx = EVP_MD_CTX_create();
  CHECK(mdctx != nullptr);
  ret &= EVP_DigestInit_ex(mdctx, md_, nullptr);
  ret &= EVP_DigestUpdate(mdctx, salt_.data(), salt_.size());
  ret &= EVP_DigestUpdate(mdctx, block, block_size_);
  ret &= EVP_DigestFinal_ex(mdctx, out, &s);
  EVP_MD_CTX_destroy(mdctx);

  CHECK_EQ(1, ret);
  CHECK_EQ(hash_size_raw_, s);
  std::fill(out + s, out + hash_size_, 0);

  return true;
}

bool HashTreeBuilder::HashBlocks(const unsigned char* data, size_t len,
                                 std::vector<unsigned char>* output_vector) {
  if (len == 0) {
    return true;
  }
  CHECK_EQ(0, len % block_size_);

  if (data == nullptr) {
    for (size_t i = 0; i < len; i += block_size_) {
      output_vector->insert(output_vector->end(), zero_block_hash_.begin(),
                            zero_block_hash_.end());
    }
    return true;
  }

  for (size_t i = 0; i < len; i += block_size_) {
    unsigned char hash_buffer[hash_size_];
    if (!HashBlock(data + i, hash_buffer)) {
      return false;
    }
    output_vector->insert(output_vector->end(), hash_buffer,
                          hash_buffer + hash_size_);
  }

  return true;
}

bool HashTreeBuilder::Update(const unsigned char* data, size_t len) {
  CHECK_GT(data_size_, 0);

  if (!leftover_.empty()) {
    CHECK_LT(leftover_.size(), block_size_);
    size_t append_len = std::min(len, block_size_ - leftover_.size());
    if (data == nullptr) {
      leftover_.insert(leftover_.end(), append_len, 0);
    } else {
      leftover_.insert(leftover_.end(), data, data + append_len);
    }
    if (leftover_.size() < block_size_) {
      return true;
    }
    if (!HashBlocks(leftover_.data(), leftover_.size(), &verity_tree_[0])) {
      return false;
    }
    leftover_.clear();
    if (data != nullptr) {
      data += append_len;
    }
    len -= append_len;
  }
  if (len % block_size_ != 0) {
    if (data == nullptr) {
      leftover_.assign(len % block_size_, 0);
    } else {
      leftover_.assign(data + len - len % block_size_, data + len);
    }
    len -= len % block_size_;
  }
  return HashBlocks(data, len, &verity_tree_[0]);
}

bool HashTreeBuilder::CalculateRootDigest(const std::vector<unsigned char>& root_verity,
                                          std::vector<unsigned char>* root_digest) {
  if (root_verity.size() != block_size_) {
    return false;
  }
  return HashBlocks(root_verity.data(), block_size_, root_digest);
}

bool HashTreeBuilder::BuildHashTree() {
  // Expects only the base level in the verity_tree_.
  CHECK_EQ(1, verity_tree_.size());

  if (!leftover_.empty()) {
    LOG(ERROR) << leftover_.size() << " bytes data left from last Update().";
    return false;
  }

  // Expects the base level to have the same size as the total hash size of
  // input data.
  AppendPaddings(&verity_tree_.back());
  size_t base_level_blocks =
      verity_tree_blocks(data_size_, block_size_, hash_size_, 0);
  CHECK_EQ(base_level_blocks * block_size_, verity_tree_[0].size());

  while (verity_tree_.back().size() > block_size_) {
    const auto& current_level = verity_tree_.back();
    // Computes the next level of the verity tree based on the hash of the
    // current level.
    size_t next_level_blocks =
        verity_tree_blocks(current_level.size(), block_size_, hash_size_, 0);
    std::vector<unsigned char> next_level;
    next_level.reserve(next_level_blocks * block_size_);

    HashBlocks(current_level.data(), current_level.size(), &next_level);
    AppendPaddings(&next_level);

    // Checks the size of the next level.
    CHECK_EQ(next_level_blocks * block_size_, next_level.size());
    verity_tree_.emplace_back(std::move(next_level));
  }

  CHECK_EQ(block_size_, verity_tree_.back().size());
  return CalculateRootDigest(verity_tree_.back(), &root_hash_);
}

bool HashTreeBuilder::CheckHashTree(
    const std::vector<unsigned char>& hash_tree) const {
  size_t offset = 0;
  // Reads reversely to output the verity tree top-down.
  for (size_t i = verity_tree_.size(); i > 0; i--) {
    const auto& level_blocks = verity_tree_[i - 1];
    if (offset + level_blocks.size() > hash_tree.size()) {
      LOG(ERROR) << "Hash tree too small: " << hash_tree.size();
      return false;
    }
    auto iter = std::mismatch(level_blocks.begin(), level_blocks.end(),
                              hash_tree.begin() + offset)
                    .first;
    if (iter != level_blocks.end()) {
      LOG(ERROR) << "Mismatch found at the hash tree level " << i << " offset "
                 << std::distance(level_blocks.begin(), iter);
      return false;
    }
    offset += level_blocks.size();
  }
  if (offset != hash_tree.size()) {
    LOG(ERROR) << "Hash tree size mismatch: " << hash_tree.size()
               << " != " << offset;
    return false;
  }
  return true;
}

bool HashTreeBuilder::WriteHashTreeToFile(const std::string& output) const {
  android::base::unique_fd output_fd(
      open(output.c_str(), O_WRONLY | O_CREAT | O_TRUNC, 0666));
  if (output_fd == -1) {
    PLOG(ERROR) << "Failed to open output file " << output;
    return false;
  }

  return WriteHashTreeToFd(output_fd, 0);
}

bool HashTreeBuilder::WriteHashTree(
    std::function<bool(const void*, size_t)> callback) const {
  CHECK(!verity_tree_.empty());

  // Reads reversely to output the verity tree top-down.
  for (size_t i = verity_tree_.size(); i > 0; i--) {
    const auto& level_blocks = verity_tree_[i - 1];
    if (!callback(level_blocks.data(), level_blocks.size())) {
      PLOG(ERROR) << "Failed to write the hash tree level " << i;
      return false;
    }
  }

  return true;
}

bool HashTreeBuilder::WriteHashTreeToFd(int fd, uint64_t offset) const {
  CHECK(!verity_tree_.empty());

  if (lseek(fd, offset, SEEK_SET) != offset) {
    PLOG(ERROR) << "Failed to seek the output fd, offset: " << offset;
    return false;
  }

  return WriteHashTree([fd](auto data, auto size) {
    return android::base::WriteFully(fd, data, size);
  });
}

void HashTreeBuilder::AppendPaddings(std::vector<unsigned char>* data) {
  size_t remainder = data->size() % block_size_;
  if (remainder != 0) {
    data->resize(data->size() + block_size_ - remainder, 0);
  }
}
