/*
 * Copyright (C) 2024 The Android Open Source Project
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

#include "ZstdUtil.h"

#include <gtest/gtest.h>
#include <vector>

using namespace simpleperf;

// @CddTest = 6.1/C-0-2
TEST(ZstdUtil, smoke) {
  std::unique_ptr<Compressor> compressor = CreateZstdCompressor();
  ASSERT_TRUE(compressor);
  std::unique_ptr<Decompressor> decompressor = CreateZstdDecompressor();
  ASSERT_TRUE(decompressor);

  // Compress and decompress input_a.
  std::vector<char> input_a(65536);
  for (size_t i = 0; i < input_a.size(); i++) {
    input_a[i] = static_cast<char>(i % 256);
  }

  std::vector<char> compressed_output;
  auto get_compressor_output = [&]() {
    std::string_view output = compressor->GetOutputData();
    compressed_output.insert(compressed_output.end(), output.begin(), output.end());
    compressor->ConsumeOutputData(output.size());
  };

  std::vector<char> decompressed_output;
  auto get_decompressor_output = [&]() {
    std::string_view output = decompressor->GetOutputData();
    decompressed_output.insert(decompressed_output.end(), output.begin(), output.end());
    decompressor->ConsumeOutputData(output.size());
  };

  ASSERT_TRUE(compressor->AddInputData(input_a.data(), input_a.size() / 2));
  get_compressor_output();
  ASSERT_TRUE(compressor->AddInputData(input_a.data() + input_a.size() / 2,
                                       input_a.size() - input_a.size() / 2));
  ASSERT_TRUE(compressor->FlushOutputData());
  get_compressor_output();
  ASSERT_NE(compressed_output.size(), 0);
  ASSERT_EQ(compressor->TotalInputSize(), input_a.size());
  ASSERT_EQ(compressor->TotalOutputSize(), compressed_output.size());

  // Flush with no new input doesn't affect output.
  ASSERT_TRUE(compressor->FlushOutputData());
  ASSERT_TRUE(compressor->GetOutputData().empty());

  ASSERT_TRUE(decompressor->AddInputData(compressed_output.data(), compressed_output.size() / 2));
  get_decompressor_output();
  ASSERT_TRUE(decompressor->AddInputData(compressed_output.data() + compressed_output.size() / 2,
                                         compressed_output.size() - compressed_output.size() / 2));
  get_decompressor_output();
  ASSERT_EQ(decompressed_output, input_a);

  // Compress and decompress input_b.
  std::vector<char> input_b(65536);
  for (size_t i = 0; i < input_b.size(); i++) {
    input_b[i] = static_cast<char>(i % 32);
  }
  compressed_output.clear();
  decompressed_output.clear();
  ASSERT_TRUE(compressor->AddInputData(input_b.data(), input_b.size()));
  ASSERT_TRUE(compressor->FlushOutputData());
  get_compressor_output();
  ASSERT_NE(compressed_output.size(), 0);
  ASSERT_TRUE(decompressor->AddInputData(compressed_output.data(), compressed_output.size()));
  get_decompressor_output();
  ASSERT_EQ(decompressed_output, input_b);
}
