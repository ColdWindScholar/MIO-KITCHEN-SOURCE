/*
 * Copyright (C) 2022 The Android Open Source Project
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

#pragma once

#include <stdio.h>

#include <memory>
#include <string>

#include <android-base/logging.h>

#include "environment.h"

namespace simpleperf {

class TempSymFile {
 public:
  static std::unique_ptr<TempSymFile> Create(std::string&& path, bool remove_in_destructor) {
    FILE* fp = fopen(path.data(), "web");
    if (fp == nullptr) {
      PLOG(ERROR) << "failed to create " << path;
      return nullptr;
    }
    if (remove_in_destructor) {
      ScopedTempFiles::RegisterTempFile(path);
    }
    std::unique_ptr<TempSymFile> symfile(new TempSymFile(std::move(path), fp));
    if (!symfile->WriteHeader()) {
      return nullptr;
    }
    return symfile;
  }

  bool WriteEntry(const char* data, size_t size) {
    if (fwrite(data, size, 1, fp_.get()) != 1) {
      PLOG(ERROR) << "failed to write to " << path_;
      return false;
    }
    file_offset_ += size;
    need_flush_ = true;
    return true;
  }

  bool Flush() {
    if (need_flush_) {
      if (fflush(fp_.get()) != 0) {
        PLOG(ERROR) << "failed to flush " << path_;
        return false;
      }
      need_flush_ = false;
    }
    return true;
  }

  const std::string& GetPath() const { return path_; }
  uint64_t GetOffset() const { return file_offset_; }

 private:
  TempSymFile(std::string&& path, FILE* fp) : path_(std::move(path)), fp_(fp, fclose) {}

  bool WriteHeader() {
    char magic[8] = "JIT_SYM";
    static_assert(sizeof(magic) == 8);
    if (fwrite(magic, sizeof(magic), 1, fp_.get()) != 1) {
      PLOG(ERROR) << "failed to write to " << path_;
      return false;
    }
    file_offset_ = sizeof(magic);
    return true;
  }

  const std::string path_;
  std::unique_ptr<FILE, decltype(&fclose)> fp_;
  uint64_t file_offset_ = 0;
  bool need_flush_ = false;
};

}  // namespace simpleperf
