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

#include <android-base/logging.h>
#include <zstd.h>

namespace simpleperf {

namespace {

class CompressionOutBuffer {
 public:
  CompressionOutBuffer(size_t min_free_size)
      : min_free_size_(min_free_size), buffer_(min_free_size) {}

  const char* DataStart() const { return buffer_.data() + data_pos_; }
  size_t DataSize() const { return data_size_; }
  char* FreeStart() { return buffer_.data() + data_pos_ + data_size_; }
  size_t FreeSize() const { return buffer_.size() - data_pos_ - data_size_; }

  void PrepareForInput() {
    if (data_pos_ > 0) {
      if (data_size_ == 0) {
        data_pos_ = 0;
      } else {
        memmove(buffer_.data(), buffer_.data() + data_pos_, data_size_);
        data_pos_ = 0;
      }
    }
    if (FreeSize() < min_free_size_) {
      buffer_.resize(buffer_.size() * 2);
    }
  }

  void ProduceData(size_t size) {
    data_size_ += size;
    CHECK_LE(data_pos_ + data_size_, buffer_.size());
  }

  void ConsumeData(size_t size) {
    CHECK_LE(size, data_size_);
    data_pos_ += size;
    data_size_ -= size;
  }

 private:
  const size_t min_free_size_;
  std::vector<char> buffer_;
  size_t data_pos_ = 0;
  size_t data_size_ = 0;
};

using ZSTD_CCtx_pointer = std::unique_ptr<ZSTD_CCtx, decltype(&ZSTD_freeCCtx)>;

class ZstdCompressor : public Compressor {
 public:
  ZstdCompressor(ZSTD_CCtx_pointer cctx)
      : cctx_(std::move(cctx)), out_buffer_(ZSTD_CStreamOutSize()) {}

  bool AddInputData(const char* data, size_t size) override {
    ZSTD_inBuffer input = {data, size, 0};
    while (input.pos < input.size) {
      out_buffer_.PrepareForInput();
      ZSTD_outBuffer output = {out_buffer_.FreeStart(), out_buffer_.FreeSize(), 0};
      size_t remaining = ZSTD_compressStream2(cctx_.get(), &output, &input, ZSTD_e_continue);
      if (ZSTD_isError(remaining)) {
        LOG(ERROR) << "ZSTD_compressStream2() failed: " << ZSTD_getErrorName(remaining);
        return false;
      }
      out_buffer_.ProduceData(output.pos);
      total_output_size_ += output.pos;
    }
    total_input_size_ += size;
    return true;
  }

  bool FlushOutputData() override {
    if (flushed_input_size_ == total_input_size_) {
      return true;
    }
    flushed_input_size_ = total_input_size_;
    ZSTD_inBuffer input = {nullptr, 0, 0};
    size_t remaining = 0;
    do {
      out_buffer_.PrepareForInput();
      ZSTD_outBuffer output = {out_buffer_.FreeStart(), out_buffer_.FreeSize(), 0};
      remaining = ZSTD_compressStream2(cctx_.get(), &output, &input, ZSTD_e_end);
      if (ZSTD_isError(remaining)) {
        LOG(ERROR) << "ZSTD_compressStream2() failed: " << ZSTD_getErrorName(remaining);
        return false;
      }
      out_buffer_.ProduceData(output.pos);
      total_output_size_ += output.pos;
    } while (remaining != 0);
    return true;
  }

  std::string_view GetOutputData() override {
    return std::string_view(out_buffer_.DataStart(), out_buffer_.DataSize());
  }

  void ConsumeOutputData(size_t size) override { out_buffer_.ConsumeData(size); }

 private:
  ZSTD_CCtx_pointer cctx_;
  CompressionOutBuffer out_buffer_;
  uint64_t flushed_input_size_ = 0;
};

using ZSTD_DCtx_pointer = std::unique_ptr<ZSTD_DCtx, decltype(&ZSTD_freeDCtx)>;

class ZstdDecompressor : public Decompressor {
 public:
  ZstdDecompressor(ZSTD_DCtx_pointer dctx)
      : dctx_(std::move(dctx)), out_buffer_(ZSTD_DStreamOutSize()) {}

  bool AddInputData(const char* data, size_t size) override {
    ZSTD_inBuffer input = {data, size, 0};
    while (input.pos < input.size) {
      out_buffer_.PrepareForInput();
      ZSTD_outBuffer output = {out_buffer_.FreeStart(), out_buffer_.FreeSize(), 0};
      size_t remaining = ZSTD_decompressStream(dctx_.get(), &output, &input);
      if (ZSTD_isError(remaining)) {
        LOG(ERROR) << "ZSTD_decompressStream() failed: " << ZSTD_getErrorName(remaining);
        return false;
      }
      out_buffer_.ProduceData(output.pos);
    }
    return true;
  }

  std::string_view GetOutputData() override {
    return std::string_view(out_buffer_.DataStart(), out_buffer_.DataSize());
  }

  void ConsumeOutputData(size_t size) override { out_buffer_.ConsumeData(size); }

 private:
  ZSTD_DCtx_pointer dctx_;
  CompressionOutBuffer out_buffer_;
};

}  // namespace

Compressor::~Compressor() {}

Decompressor::~Decompressor() {}

std::unique_ptr<Compressor> CreateZstdCompressor(size_t compression_level) {
  ZSTD_CCtx_pointer cctx(ZSTD_createCCtx(), ZSTD_freeCCtx);
  if (!cctx) {
    LOG(ERROR) << "ZSTD_createCCtx() failed";
    return nullptr;
  }
  size_t err = ZSTD_CCtx_setParameter(cctx.get(), ZSTD_c_compressionLevel, compression_level);
  if (ZSTD_isError(err)) {
    LOG(ERROR) << "failed to set compression level: " << ZSTD_getErrorName(err);
    return nullptr;
  }
  return std::unique_ptr<Compressor>(new ZstdCompressor(std::move(cctx)));
}

std::unique_ptr<Decompressor> CreateZstdDecompressor() {
  ZSTD_DCtx_pointer dctx(ZSTD_createDCtx(), ZSTD_freeDCtx);
  if (!dctx) {
    LOG(ERROR) << "ZSTD_createDCtx() failed";
    return nullptr;
  }
  return std::unique_ptr<Decompressor>(new ZstdDecompressor(std::move(dctx)));
}

}  // namespace simpleperf
