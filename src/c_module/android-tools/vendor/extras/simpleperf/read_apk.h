/*
 * Copyright (C) 2016 The Android Open Source Project
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

#ifndef SIMPLE_PERF_READ_APK_H_
#define SIMPLE_PERF_READ_APK_H_

#include <stdint.h>

#include <memory>
#include <string>
#include <tuple>
#include <unordered_map>

#include "read_elf.h"

namespace simpleperf {

// Container for info an on ELF file embedded into an APK file
class EmbeddedElf {
 public:
  EmbeddedElf() : entry_offset_(0), entry_size_(0) {}

  EmbeddedElf(const std::string& filepath, const std::string& entry_name, uint64_t entry_offset,
              size_t entry_size)
      : filepath_(filepath),
        entry_name_(entry_name),
        entry_offset_(entry_offset),
        entry_size_(entry_size) {}

  // Path to APK file
  const std::string& filepath() const { return filepath_; }

  // Entry name within zip archive
  const std::string& entry_name() const { return entry_name_; }

  // Offset of zip entry from start of containing APK file
  uint64_t entry_offset() const { return entry_offset_; }

  // Size of zip entry (length of embedded ELF)
  uint32_t entry_size() const { return entry_size_; }

 private:
  std::string filepath_;    // containing APK path
  std::string entry_name_;  // name of entry in zip index of embedded elf file
  uint64_t entry_offset_;   // offset of ELF from start of containing APK file
  uint32_t entry_size_;     // size of ELF file in zip
};

// APK inspector helper class
class ApkInspector {
 public:
  static EmbeddedElf* FindElfInApkByOffset(const std::string& apk_path, uint64_t file_offset);
  static EmbeddedElf* FindElfInApkByName(const std::string& apk_path,
                                         const std::string& entry_name);

 private:
  static std::unique_ptr<EmbeddedElf> FindElfInApkByOffsetWithoutCache(const std::string& apk_path,
                                                                       uint64_t file_offset);
  static std::unique_ptr<EmbeddedElf> FindElfInApkByNameWithoutCache(const std::string& apk_path,
                                                                     const std::string& entry_name);

  struct ApkNode {
    // Map from entry_offset to EmbeddedElf.
    std::unordered_map<uint64_t, std::unique_ptr<EmbeddedElf>> offset_map;
    // Map from entry_name to EmbeddedElf.
    std::unordered_map<std::string, EmbeddedElf*> name_map;
  };
  static std::unordered_map<std::string, ApkNode> embedded_elf_cache_;
};

std::string GetUrlInApk(const std::string& apk_path, const std::string& elf_filename);
std::tuple<bool, std::string, std::string> SplitUrlInApk(const std::string& path);

// Parse path like "[anon:dalvik-classes.dex extracted in memory from /..base.apk] (deleted)",
// or "/dev/ashmem/dalvik-classes.dex extracted in memory from /..base.apk (deleted)" on Android P.
bool ParseExtractedInMemoryPath(const std::string& path, std::string* zip_path,
                                std::string* entry_name);

}  // namespace simpleperf

#endif  // SIMPLE_PERF_READ_APK_H_
