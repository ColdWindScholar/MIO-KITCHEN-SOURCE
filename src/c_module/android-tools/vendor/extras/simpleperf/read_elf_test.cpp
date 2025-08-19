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

#include "read_elf.h"

#include <gtest/gtest.h>

#include <map>

#include <android-base/file.h>

#include "get_test_data.h"
#include "read_apk.h"
#include "test_util.h"
#include "utils.h"

#define ELF_NOTE_GNU "GNU"
#define NT_GNU_BUILD_ID 3

using namespace simpleperf;

// @CddTest = 6.1/C-0-2
TEST(read_elf, GetBuildIdFromNoteSection) {
  BuildId build_id;
  std::vector<char> data;
  // Fail to read build id for no data.
  ASSERT_FALSE(GetBuildIdFromNoteSection(data.data(), 0, &build_id));

  // Read build id from data starting from different alignment addresses.
  char build_id_data[20];
  for (int i = 0; i < 20; ++i) {
    build_id_data[i] = i;
  }
  BuildId expected_build_id(build_id_data, 20);
  data.resize(100, '\0');

  for (size_t alignment = 0; alignment <= 3; ++alignment) {
    char* start = data.data() + alignment;
    char* p = start;
    uint32_t type = NT_GNU_BUILD_ID;
    uint32_t namesz = 4;
    uint32_t descsz = 20;
    MoveToBinaryFormat(namesz, p);
    MoveToBinaryFormat(descsz, p);
    MoveToBinaryFormat(type, p);
    MoveToBinaryFormat(ELF_NOTE_GNU, 4, p);
    MoveToBinaryFormat(build_id_data, 20, p);
    ASSERT_TRUE(GetBuildIdFromNoteSection(start, p - start, &build_id));
    ASSERT_TRUE(build_id == expected_build_id);
  }
}

// @CddTest = 6.1/C-0-2
TEST(read_elf, GetBuildIdFromElfFile) {
  BuildId build_id;
  ElfStatus status;
  auto elf = ElfFile::Open(GetTestData(ELF_FILE), &status);
  ASSERT_EQ(status, ElfStatus::NO_ERROR);
  ASSERT_EQ(ElfStatus::NO_ERROR, elf->GetBuildId(&build_id));
  ASSERT_EQ(build_id, BuildId(elf_file_build_id));
}

// @CddTest = 6.1/C-0-2
TEST(read_elf, GetBuildIdFromEmbeddedElfFile) {
  BuildId build_id;
  ElfStatus status;
  std::string path = GetUrlInApk(APK_FILE, NATIVELIB_IN_APK);
  auto elf = ElfFile::Open(GetTestData(path), &status);
  ASSERT_EQ(status, ElfStatus::NO_ERROR);
  ASSERT_EQ(ElfStatus::NO_ERROR, elf->GetBuildId(&build_id));
  ASSERT_EQ(build_id, native_lib_build_id);
}

void ParseSymbol(const ElfFileSymbol& symbol, std::map<std::string, ElfFileSymbol>* symbols) {
  (*symbols)[symbol.name] = symbol;
}

static void CheckGlobalVariableSymbols(const std::map<std::string, ElfFileSymbol>& symbols) {
  auto pos = symbols.find("GlobalVar");
  ASSERT_NE(pos, symbols.end());
  ASSERT_FALSE(pos->second.is_func);
}

static void CheckFunctionSymbols(const std::map<std::string, ElfFileSymbol>& symbols) {
  auto pos = symbols.find("GlobalFunc");
  ASSERT_NE(pos, symbols.end());
  ASSERT_TRUE(pos->second.is_func);
  ASSERT_TRUE(pos->second.is_in_text_section);
}

void CheckElfFileSymbols(const std::map<std::string, ElfFileSymbol>& symbols) {
  CheckGlobalVariableSymbols(symbols);
  CheckFunctionSymbols(symbols);
}

// @CddTest = 6.1/C-0-2
TEST(read_elf, parse_symbols_from_elf_file_with_correct_build_id) {
  std::map<std::string, ElfFileSymbol> symbols;
  ElfStatus status;
  auto elf = ElfFile::Open(GetTestData(ELF_FILE), &elf_file_build_id, &status);
  ASSERT_EQ(ElfStatus::NO_ERROR, status);
  ASSERT_EQ(ElfStatus::NO_ERROR,
            elf->ParseSymbols(std::bind(ParseSymbol, std::placeholders::_1, &symbols)));
  CheckElfFileSymbols(symbols);
}

// @CddTest = 6.1/C-0-2
TEST(read_elf, parse_symbols_from_elf_file_without_build_id) {
  std::map<std::string, ElfFileSymbol> symbols;
  ElfStatus status;
  // Test no build_id.
  auto elf = ElfFile::Open(GetTestData(ELF_FILE), &status);
  ASSERT_EQ(ElfStatus::NO_ERROR, status);
  ASSERT_EQ(ElfStatus::NO_ERROR,
            elf->ParseSymbols(std::bind(ParseSymbol, std::placeholders::_1, &symbols)));
  CheckElfFileSymbols(symbols);

  // Test empty build id.
  symbols.clear();
  BuildId build_id;
  elf = ElfFile::Open(GetTestData(ELF_FILE), &build_id, &status);
  ASSERT_EQ(ElfStatus::NO_ERROR, status);
  ASSERT_EQ(ElfStatus::NO_ERROR,
            elf->ParseSymbols(std::bind(ParseSymbol, std::placeholders::_1, &symbols)));
  CheckElfFileSymbols(symbols);
}

// @CddTest = 6.1/C-0-2
TEST(read_elf, parse_symbols_from_elf_file_with_wrong_build_id) {
  BuildId build_id("01010101010101010101");
  std::map<std::string, ElfFileSymbol> symbols;
  ElfStatus status;
  auto elf = ElfFile::Open(GetTestData(ELF_FILE), &build_id, &status);
  ASSERT_EQ(ElfStatus::BUILD_ID_MISMATCH, status);
}

// @CddTest = 6.1/C-0-2
TEST(read_elf, ParseSymbolsFromEmbeddedElfFile) {
  std::map<std::string, ElfFileSymbol> symbols;
  ElfStatus status;
  std::string path = GetUrlInApk(APK_FILE, NATIVELIB_IN_APK);
  auto elf = ElfFile::Open(GetTestData(path), &native_lib_build_id, &status);
  ASSERT_EQ(status, ElfStatus::NO_ERROR);
  ASSERT_EQ(ElfStatus::NO_SYMBOL_TABLE,
            elf->ParseSymbols(std::bind(ParseSymbol, std::placeholders::_1, &symbols)));
  CheckElfFileSymbols(symbols);
}

// @CddTest = 6.1/C-0-2
TEST(read_elf, ParseSymbolFromMiniDebugInfoElfFile) {
  std::map<std::string, ElfFileSymbol> symbols;
  ElfStatus status;
  auto elf = ElfFile::Open(GetTestData(ELF_FILE_WITH_MINI_DEBUG_INFO), &status);
  ASSERT_EQ(ElfStatus::NO_ERROR, status);
  ASSERT_EQ(ElfStatus::NO_ERROR,
            elf->ParseSymbols(std::bind(ParseSymbol, std::placeholders::_1, &symbols)));
  CheckFunctionSymbols(symbols);
}

// @CddTest = 6.1/C-0-2
TEST(read_elf, arm_mapping_symbol) {
  ASSERT_TRUE(IsArmMappingSymbol("$a"));
  ASSERT_FALSE(IsArmMappingSymbol("$b"));
  ASSERT_TRUE(IsArmMappingSymbol("$a.anything"));
  ASSERT_FALSE(IsArmMappingSymbol("$a_no_dot"));
}

// @CddTest = 6.1/C-0-2
TEST(read_elf, ElfFile_Open) {
  auto IsValidElfPath = [](const std::string& path) {
    ElfStatus status;
    ElfFile::Open(path, &status);
    return status;
  };
  ASSERT_NE(ElfStatus::NO_ERROR, IsValidElfPath("/dev/zero"));
  TemporaryFile tmp_file;
  ASSERT_EQ(ElfStatus::READ_FAILED, IsValidElfPath(tmp_file.path));
  ASSERT_TRUE(android::base::WriteStringToFile("wrong format for elf", tmp_file.path));
  ASSERT_EQ(ElfStatus::FILE_MALFORMED, IsValidElfPath(tmp_file.path));
  ASSERT_EQ(ElfStatus::NO_ERROR, IsValidElfPath(GetTestData(ELF_FILE)));
}

// @CddTest = 6.1/C-0-2
TEST(read_elf, check_symbol_for_plt_section) {
  std::map<std::string, ElfFileSymbol> symbols;
  ElfStatus status;
  auto elf = ElfFile::Open(GetTestData(ELF_FILE), &status);
  ASSERT_EQ(ElfStatus::NO_ERROR, status);
  ASSERT_EQ(ElfStatus::NO_ERROR,
            elf->ParseSymbols(std::bind(ParseSymbol, std::placeholders::_1, &symbols)));
  ASSERT_NE(symbols.find("@plt"), symbols.end());
}

// @CddTest = 6.1/C-0-2
TEST(read_elf, read_elf_with_broken_section_table) {
  std::string elf_path = GetTestData("libsgmainso-6.4.36.so");
  std::map<std::string, ElfFileSymbol> symbols;
  ElfStatus status;
  auto elf = ElfFile::Open(elf_path, &status);
  ASSERT_EQ(ElfStatus::NO_ERROR, status);
  ASSERT_EQ(ElfStatus::NO_SYMBOL_TABLE,
            elf->ParseSymbols(std::bind(ParseSymbol, std::placeholders::_1, &symbols)));

  BuildId build_id;
  ASSERT_EQ(ElfStatus::NO_BUILD_ID, elf->GetBuildId(&build_id));

  uint64_t file_offset_of_min_vaddr;
  uint64_t min_vaddr = elf->ReadMinExecutableVaddr(&file_offset_of_min_vaddr);
  ASSERT_EQ(min_vaddr, 0u);
  ASSERT_EQ(file_offset_of_min_vaddr, 0u);
}

// @CddTest = 6.1/C-0-2
TEST(read_elf, ReadMinExecutableVaddr) {
  ElfStatus status;
  auto elf = ElfFile::Open(GetTestData("libc.so"), &status);
  ASSERT_EQ(status, ElfStatus::NO_ERROR);
  uint64_t file_offset_of_min_vaddr;
  uint64_t min_vaddr = elf->ReadMinExecutableVaddr(&file_offset_of_min_vaddr);
  ASSERT_EQ(min_vaddr, 0x29000u);
  ASSERT_EQ(file_offset_of_min_vaddr, 0x29000u);
}

// @CddTest = 6.1/C-0-2
TEST(read_elf, NoUndefinedSymbol) {
  // Check if we read undefined symbols (like dlerror) from libc.so.
  bool has_dlerror = false;
  auto parse_symbol = [&](const ElfFileSymbol& symbol) {
    if (symbol.name == "dlerror") {
      has_dlerror = true;
    }
  };

  ElfStatus status;
  auto elf = ElfFile::Open(GetTestData("libc.so"), &status);
  ASSERT_EQ(status, ElfStatus::NO_ERROR);
  ASSERT_EQ(ElfStatus::NO_ERROR, elf->ParseSymbols(parse_symbol));
  ASSERT_FALSE(has_dlerror);
}

// @CddTest = 6.1/C-0-2
TEST(read_elf, VaddrToOff) {
  auto elf = ElfFile::Open(GetTestData(ELF_FILE));
  ASSERT_TRUE(elf != nullptr);
  uint64_t off;
  ASSERT_TRUE(elf->VaddrToOff(0x400200, &off));
  ASSERT_EQ(off, 0x200);
  ASSERT_FALSE(elf->VaddrToOff(0x300200, &off));
  ASSERT_FALSE(elf->VaddrToOff(0x420000, &off));
}

// @CddTest = 6.1/C-0-2
TEST(read_elf, GetSectionHeader) {
  auto elf = ElfFile::Open(GetTestData(ELF_FILE));
  ASSERT_TRUE(elf != nullptr);
  std::vector<ElfSection> sections = elf->GetSectionHeader();
  ASSERT_EQ(sections.size(), 30);
  ASSERT_EQ(sections[13].name, ".text");
  ASSERT_EQ(sections[13].vaddr, 0x400400);
  ASSERT_EQ(sections[13].file_offset, 0x400);
  ASSERT_EQ(sections[13].size, 0x1b2);
}
