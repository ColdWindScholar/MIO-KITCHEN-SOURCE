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

#ifndef __HASH_TREE_BUILDER_H__
#define __HASH_TREE_BUILDER_H__

#include <inttypes.h>
#include <stddef.h>

#include <functional>
#include <string>
#include <vector>

#include <openssl/evp.h>

// This class builds a verity hash tree based on the input data and a salt with
// the length of hash size. It also supports the streaming of input data while
// the total data size should be know in advance. Once all the data is ready,
// appropriate functions can be called to build the upper levels of the hash
// tree and output the tree to a file.
class HashTreeBuilder {
 public:
  HashTreeBuilder(size_t block_size, const EVP_MD* md);
  // Returns the size of the verity tree in bytes given the input data size.
  uint64_t CalculateSize(uint64_t input_size) const {
      return CalculateSize(input_size, block_size_, hash_size_);
  }
  static uint64_t CalculateSize(uint64_t input_size, size_t block_size, size_t hash_size);
  // Gets ready for the hash tree computation. We expect |expected_data_size|
  // bytes source data.
  bool Initialize(int64_t expected_data_size,
                  const std::vector<unsigned char>& salt);
  // Streams |len| bytes of source data to the hash tree builder. This function
  // can be called multiple until we processed all the source data. And the
  // accumulated data_size is expected to be exactly the |data_size_| when we
  // build the hash tree.
  bool Update(const unsigned char* data, size_t len);
  // Computes the upper levels of the hash tree based on the 0th level.
  bool BuildHashTree();
  // Check the built hash tree against |hash_tree|, return true if they match.
  bool CheckHashTree(const std::vector<unsigned char>& hash_tree) const;
  // Writes the computed hash tree top-down to |output|.
  bool WriteHashTreeToFile(const std::string& output) const;
  bool WriteHashTreeToFd(int fd, uint64_t offset) const;
  bool WriteHashTree(std::function<bool(const void*, size_t)> callback) const;

  size_t hash_size() const { return hash_size_; }
  const std::vector<unsigned char>& root_hash() const { return root_hash_; }
  // Converts |bytes| to string for hexdump.
  static std::string BytesArrayToString(
      const std::vector<unsigned char>& bytes);
  // Inverse of the above function. It parses the input hex string and stores
  // the result in |bytes|.
  static bool ParseBytesArrayFromString(const std::string& str,
                                        std::vector<unsigned char>* bytes);
  // Returns the hash function given the name of the hash algorithm. Returns
  // nullptr if the algorithm is unrecongnized or not supported.
  static const EVP_MD* HashFunction(const std::string& hash_name);

  // Calculates the digest of the root of a verity tree.
  bool CalculateRootDigest(const std::vector<unsigned char>& root_verity,
                           std::vector<unsigned char>* root_digest);

 private:
  friend class BuildVerityTreeTest;
  // Calculates the hash of one single block. Write the result to |out|, a
  // buffer allocated by the caller.
  bool HashBlock(const unsigned char* block, unsigned char* out);
  // Calculates the hash of |len| bytes of data starting from |data|. Append the
  // result to |output_vector|.
  bool HashBlocks(const unsigned char* data, size_t len,
                  std::vector<unsigned char>* output_vector);
  // Aligns |data| with block_size by padding 0s to the end.
  void AppendPaddings(std::vector<unsigned char>* data);

  size_t block_size_;
  // Expected size of the source data, which is used to compute the hash for the
  // base level.
  uint64_t data_size_;
  std::vector<unsigned char> salt_;
  const EVP_MD* md_;
  // The raw hash size of the hash algorithm specified by md_.
  size_t hash_size_raw_;
  // Hash size rounded up to the next power of 2. (e.g. 20 -> 32)
  size_t hash_size_;

  // Pre-calculated hash of a zero block.
  std::vector<unsigned char> zero_block_hash_;
  std::vector<unsigned char> root_hash_;
  // Storage of the verity tree. The base level hash stores in verity_tree_[0]
  // and the top level hash stores in verity_tree_.back().
  std::vector<std::vector<unsigned char>> verity_tree_;
  // The remaining data passed to the last call to Update() that's less than a
  // block.
  std::vector<unsigned char> leftover_;
};

#endif  // __HASH_TREE_BUILDER_H__
