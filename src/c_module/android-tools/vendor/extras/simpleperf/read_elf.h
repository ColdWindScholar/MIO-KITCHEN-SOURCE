/*
 * Copyright (C) 2015 The Android Open Source Project
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

#ifndef SIMPLE_PERF_READ_ELF_H_
#define SIMPLE_PERF_READ_ELF_H_

#include <functional>
#include <ostream>
#include <string>
#include "build_id.h"

namespace llvm {
class MemoryBuffer;
}

namespace simpleperf {

// Read ELF functions are called in different situations, so it is hard to
// decide whether to report error or not. So read ELF functions don't report
// error when something wrong happens, instead they return ElfStatus, which
// identifies different errors met while reading elf file.
enum class ElfStatus {
  NO_ERROR,
  FILE_NOT_FOUND,
  READ_FAILED,
  FILE_MALFORMED,
  NO_SYMBOL_TABLE,
  NO_BUILD_ID,
  BUILD_ID_MISMATCH,
  SECTION_NOT_FOUND,
};

std::ostream& operator<<(std::ostream& os, const ElfStatus& status);

ElfStatus GetBuildIdFromNoteFile(const std::string& filename, BuildId* build_id);

// The symbol prefix used to indicate that the symbol belongs to android linker.
static const std::string linker_prefix = "__dl_";

struct ElfFileSymbol {
  uint64_t vaddr;
  uint64_t len;
  bool is_func;
  bool is_label;
  bool is_in_text_section;
  std::string name;

  ElfFileSymbol() : vaddr(0), len(0), is_func(false), is_label(false), is_in_text_section(false) {}
};

struct ElfSegment {
  uint64_t vaddr = 0;
  uint64_t file_offset = 0;
  uint64_t file_size = 0;
  bool is_executable = false;
  bool is_load = false;
};

struct ElfSection {
  std::string name;
  uint64_t vaddr = 0;
  uint64_t file_offset = 0;
  uint64_t size = 0;
};

class ElfFile {
 public:
  // Report error instead of returning status.
  static std::unique_ptr<ElfFile> Open(const std::string& filename);
  static std::unique_ptr<ElfFile> Open(const std::string& filename, ElfStatus* status) {
    return Open(filename, nullptr, status);
  }

  static std::unique_ptr<ElfFile> Open(const std::string& filename,
                                       const BuildId* expected_build_id, ElfStatus* status);
  static std::unique_ptr<ElfFile> Open(const char* data, size_t size, ElfStatus* status);
  virtual ~ElfFile() {}

  virtual bool Is64Bit() = 0;
  virtual llvm::MemoryBuffer* GetMemoryBuffer() = 0;
  virtual std::vector<ElfSegment> GetProgramHeader() = 0;
  virtual std::vector<ElfSection> GetSectionHeader() = 0;
  virtual ElfStatus GetBuildId(BuildId* build_id) = 0;

  using ParseSymbolCallback = std::function<void(const ElfFileSymbol&)>;
  virtual ElfStatus ParseSymbols(const ParseSymbolCallback& callback) = 0;
  virtual void ParseDynamicSymbols(const ParseSymbolCallback& callback) = 0;

  virtual ElfStatus ReadSection(const std::string& section_name, std::string* content) = 0;
  virtual uint64_t ReadMinExecutableVaddr(uint64_t* file_offset_of_min_vaddr) = 0;
  virtual bool VaddrToOff(uint64_t vaddr, uint64_t* file_offset) = 0;

 protected:
  ElfFile() {}
};

bool IsArmMappingSymbol(const char* name);
ElfStatus IsValidElfFile(int fd, uint64_t file_offset = 0);
bool IsValidElfFileMagic(const char* buf, size_t buf_size);
bool GetBuildIdFromNoteSection(const char* section, size_t section_size, BuildId* build_id);

}  // namespace simpleperf

#endif  // SIMPLE_PERF_READ_ELF_H_
