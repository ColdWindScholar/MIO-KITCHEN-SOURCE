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

#include "JITDebugReader.h"
#include "JITDebugReader_impl.h"

#include <sys/mman.h>

#include <android-base/file.h>
#include <android-base/scopeguard.h>
#include <android-base/strings.h>
#include <android-base/test_utils.h>
#include <android-base/unique_fd.h>
#include "get_test_data.h"
#include "utils.h"

#include <gtest/gtest.h>

using namespace simpleperf;
using namespace simpleperf::JITDebugReader_impl;

// @CddTest = 6.1/C-0-2
TEST(TempSymFile, smoke) {
  TemporaryFile tmpfile;
  std::unique_ptr<TempSymFile> symfile = TempSymFile::Create(tmpfile.path, false);
  ASSERT_TRUE(symfile);
  // If we write entries starting from offset 0, libunwindstack will treat the whole file as an elf
  // file in its elf cache. So make sure we don't start from offset 0.
  uint64_t offset = symfile->GetOffset();
  ASSERT_NE(offset, 0u);

  // Write data and read it back.
  const std::string test_data = "test_data";
  ASSERT_TRUE(symfile->WriteEntry(test_data.c_str(), test_data.size()));
  ASSERT_TRUE(symfile->Flush());

  char buf[16];
  ASSERT_TRUE(android::base::ReadFullyAtOffset(tmpfile.fd, buf, test_data.size(), offset));
  ASSERT_EQ(strncmp(test_data.c_str(), buf, test_data.size()), 0);
}

// @CddTest = 6.1/C-0-2
TEST(JITDebugReader, read_dex_file_in_memory) {
  // 1. Create dex file in memory. Use mmap instead of malloc, to avoid the pointer from
  // being modified by memory tag (or pointer authentication?) on ARM64.
  std::string dex_file = GetTestData("base.vdex");
  uint64_t file_size = GetFileSize(dex_file);
  const uint64_t dex_file_offset = 0x28;
  ASSERT_GT(file_size, dex_file_offset);
  uint64_t symfile_size = file_size - dex_file_offset;
  void* symfile_addr =
      mmap(nullptr, symfile_size, PROT_READ | PROT_WRITE, MAP_ANONYMOUS | MAP_PRIVATE, -1, 0);
  ASSERT_NE(symfile_addr, nullptr);
  android::base::ScopeGuard g([&]() { munmap(symfile_addr, symfile_size); });
  android::base::unique_fd fd(open(dex_file.c_str(), O_RDONLY | O_CLOEXEC));
  ASSERT_TRUE(fd.ok());
  ASSERT_TRUE(android::base::ReadFullyAtOffset(fd, symfile_addr, symfile_size, dex_file_offset));

  // 2. Create CodeEntry pointing to the dex file in memory.
  Process process;
  process.pid = getpid();
  process.initialized = true;
  std::vector<CodeEntry> code_entries(1);
  code_entries[0].addr = reinterpret_cast<uintptr_t>(&code_entries[0]);
  code_entries[0].symfile_addr = reinterpret_cast<uintptr_t>(symfile_addr);
  code_entries[0].symfile_size = symfile_size;
  code_entries[0].timestamp = 0;

  // 3. Test reading symbols from dex file in memory.
  JITDebugReader reader("", JITDebugReader::SymFileOption::kDropSymFiles,
                        JITDebugReader::SyncOption::kNoSync);
  std::vector<JITDebugInfo> debug_info;
  reader.ReadDexFileDebugInfo(process, code_entries, &debug_info);
  ASSERT_EQ(debug_info.size(), 1);
  const JITDebugInfo& info = debug_info[0];
  ASSERT_TRUE(info.dex_file_map);
  ASSERT_EQ(info.dex_file_map->start_addr, reinterpret_cast<uintptr_t>(symfile_addr));
  ASSERT_EQ(info.dex_file_map->len, symfile_size);
  ASSERT_TRUE(android::base::StartsWith(info.dex_file_map->name, kDexFileInMemoryPrefix));
  ASSERT_EQ(info.symbols.size(), 12435);
  // 4. Test if the symbols are sorted.
  uint64_t prev_addr = 0;
  for (const auto& symbol : info.symbols) {
    ASSERT_LE(prev_addr, symbol.addr);
    prev_addr = symbol.addr;
  }
}
