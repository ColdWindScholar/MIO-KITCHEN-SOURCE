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

#include <memory>
#include <string_view>

namespace simpleperf {

class Compressor {
 public:
  virtual ~Compressor();

  virtual bool AddInputData(const char* data, size_t size) = 0;
  virtual bool FlushOutputData() = 0;
  virtual std::string_view GetOutputData() = 0;
  virtual void ConsumeOutputData(size_t size) = 0;

  uint64_t TotalInputSize() const { return total_input_size_; }
  uint64_t TotalOutputSize() const { return total_output_size_; }

 protected:
  uint64_t total_input_size_ = 0;
  uint64_t total_output_size_ = 0;
};

class Decompressor {
 public:
  virtual ~Decompressor();

  virtual bool AddInputData(const char* data, size_t size) = 0;
  virtual std::string_view GetOutputData() = 0;
  virtual void ConsumeOutputData(size_t size) = 0;

  bool HasOutputData() { return !GetOutputData().empty(); }
};

std::unique_ptr<Compressor> CreateZstdCompressor(size_t compression_level = 3);
std::unique_ptr<Decompressor> CreateZstdDecompressor();

}  // namespace simpleperf
