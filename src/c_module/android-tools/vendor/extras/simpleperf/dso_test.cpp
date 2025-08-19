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

#include "dso.h"

#include <gtest/gtest.h>

#include <android-base/file.h>
#include <android-base/stringprintf.h>
#include <android-base/test_utils.h>

#include "get_test_data.h"
#include "read_apk.h"
#include "thread_tree.h"
#include "utils.h"

using namespace simpleperf;
using namespace simpleperf_dso_impl;

// @CddTest = 6.1/C-0-2
TEST(DebugElfFileFinder, use_build_id_list) {
  // Create a temp symdir with build_id_list.
  TemporaryDir tmpdir;
  TemporaryFile tmpfile(tmpdir.path);
  std::string data;
  ASSERT_TRUE(android::base::ReadFileToString(GetTestData(ELF_FILE), &data));
  ASSERT_TRUE(android::base::WriteStringToFile(data, tmpfile.path));
  BuildId build_id(ELF_FILE_BUILD_ID);
  std::string build_id_list = android::base::StringPrintf(
      "%s=%s\n", build_id.ToString().c_str(), android::base::Basename(tmpfile.path).c_str());
  std::string build_id_list_file = std::string(tmpdir.path) + "/build_id_list";
  ASSERT_TRUE(android::base::WriteStringToFile(build_id_list, build_id_list_file));

  DebugElfFileFinder finder;
  ASSERT_TRUE(finder.SetSymFsDir(tmpdir.path));
  ASSERT_EQ(finder.FindDebugFile("elf", false, build_id), std::string(tmpfile.path));
  unlink(build_id_list_file.c_str());
}

static std::string ConvertPathSeparator(const std::string& path) {
  std::string result = path;
  if (OS_PATH_SEPARATOR != '/') {
    std::replace(result.begin(), result.end(), '/', OS_PATH_SEPARATOR);
  }
  return result;
}

// @CddTest = 6.1/C-0-2
TEST(DebugElfFileFinder, concatenating_symfs_dir) {
  DebugElfFileFinder finder;
  ASSERT_TRUE(finder.SetSymFsDir(GetTestDataDir()));
  ASSERT_EQ(finder.GetPathInSymFsDir("/system/libc.so"),
            GetTestDataDir() + "system" + OS_PATH_SEPARATOR + "libc.so");
  ASSERT_EQ(finder.GetPathInSymFsDir("/data/base.apk!/lib/base.so"),
            GetTestDataDir() + "data" + OS_PATH_SEPARATOR + "base.apk!/lib/base.so");

  BuildId build_id(ELF_FILE_BUILD_ID);
  ASSERT_EQ(finder.FindDebugFile(ELF_FILE, false, build_id), GetTestDataDir() + ELF_FILE);
  std::string native_lib_in_apk = APK_FILE + "!/" + NATIVELIB_IN_APK;
  std::string apk_path = ConvertPathSeparator(APK_FILE);
  ASSERT_EQ(finder.FindDebugFile(native_lib_in_apk, false, native_lib_build_id),
            GetTestDataDir() + apk_path + "!/" + NATIVELIB_IN_APK);
}

// @CddTest = 6.1/C-0-2
TEST(DebugElfFileFinder, use_vdso) {
  DebugElfFileFinder finder;
  std::string fake_vdso32 = "fake_vdso32";
  std::string fake_vdso64 = "fake_vdso64";
  finder.SetVdsoFile(fake_vdso32, false);
  finder.SetVdsoFile(fake_vdso64, true);
  BuildId build_id;
  ASSERT_EQ(finder.FindDebugFile("[vdso]", false, build_id), fake_vdso32);
  ASSERT_EQ(finder.FindDebugFile("[vdso]", true, build_id), fake_vdso64);
}

// @CddTest = 6.1/C-0-2
TEST(DebugElfFileFinder, add_symbol_dir) {
  DebugElfFileFinder finder;
  ASSERT_FALSE(finder.AddSymbolDir(GetTestDataDir() + "dir_not_exist"));
  ASSERT_EQ(finder.FindDebugFile("elf", false, CHECK_ELF_FILE_BUILD_ID), "elf");
  std::string symfs_dir = ConvertPathSeparator(GetTestDataDir() + CORRECT_SYMFS_FOR_BUILD_ID_CHECK);
  ASSERT_TRUE(finder.AddSymbolDir(symfs_dir));
  ASSERT_EQ(finder.FindDebugFile("elf", false, CHECK_ELF_FILE_BUILD_ID),
            symfs_dir + OS_PATH_SEPARATOR + "elf_for_build_id_check");
}

// @CddTest = 6.1/C-0-2
TEST(DebugElfFileFinder, build_id_list) {
  DebugElfFileFinder finder;
  // Find file in symfs dir with correct build_id_list.
  std::string symfs_dir = ConvertPathSeparator(GetTestDataDir() + "data/symfs_with_build_id_list");
  ASSERT_TRUE(finder.SetSymFsDir(symfs_dir));
  ASSERT_EQ(finder.FindDebugFile("elf", false, CHECK_ELF_FILE_BUILD_ID),
            symfs_dir + OS_PATH_SEPARATOR + "elf_for_build_id_check");

  // Find file in symfs_dir with wrong build_id_list.
  symfs_dir = ConvertPathSeparator(GetTestDataDir() + "data/symfs_with_wrong_build_id_list");
  finder.Reset();
  ASSERT_TRUE(finder.SetSymFsDir(symfs_dir));
  ASSERT_EQ(finder.FindDebugFile("elf", false, CHECK_ELF_FILE_BUILD_ID), "elf");
}

// @CddTest = 6.1/C-0-2
TEST(DebugElfFileFinder, no_build_id) {
  DebugElfFileFinder finder;
  // If not given a build id, we should match an elf in symfs without build id.
  std::string symfs_dir = ConvertPathSeparator(GetTestDataDir() + "data/symfs_without_build_id");
  ASSERT_TRUE(finder.SetSymFsDir(symfs_dir));
  BuildId build_id;
  ASSERT_EQ(finder.FindDebugFile("elf", false, build_id), symfs_dir + OS_PATH_SEPARATOR + "elf");
}

// @CddTest = 6.1/C-0-2
TEST(DebugElfFileFinder, find_basename_in_symfs_dir) {
  DebugElfFileFinder finder;
  // Find normal elf file.
  finder.SetSymFsDir(GetTestDataDir());
  BuildId build_id(ELF_FILE_BUILD_ID);
  ASSERT_EQ(finder.FindDebugFile("random_dir/elf", false, build_id), GetTestData("elf"));

  // Find embedded native library.
  ASSERT_EQ(finder.FindDebugFile("base.apk!/lib/x86_64/elf", false, build_id), GetTestData("elf"));

  // Find elf file without build id.
  std::string symfs_dir = ConvertPathSeparator(GetTestDataDir() + "data/symfs_without_build_id");
  finder.SetSymFsDir(symfs_dir);
  build_id = BuildId();
  ASSERT_EQ(finder.FindDebugFile("random_dir/elf", false, build_id),
            symfs_dir + OS_PATH_SEPARATOR + "elf");
}

// @CddTest = 6.1/C-0-2
TEST(DebugElfFileFinder, build_id_mismatch) {
  DebugElfFileFinder finder;
  finder.SetSymFsDir(GetTestDataDir());
  CapturedStderr capture;
  BuildId mismatch_build_id("0c12a384a9f4a3f3659b7171ca615dbec3a81f71");
  std::string debug_file = finder.FindDebugFile(ELF_FILE, false, mismatch_build_id);
  capture.Stop();
  std::string stderr_output = capture.str();
  ASSERT_EQ(debug_file, ELF_FILE);
  ASSERT_NE(stderr_output.find("build id mismatch"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(dso, dex_file_dso) {
#if defined(__linux__)
  for (DsoType dso_type : {DSO_DEX_FILE, DSO_ELF_FILE}) {
    std::unique_ptr<Dso> dso = Dso::CreateDso(dso_type, GetTestData("base.vdex"));
    ASSERT_TRUE(dso);
    dso->AddDexFileOffset(0x28);
    ASSERT_EQ(DSO_DEX_FILE, dso->type());
    const Symbol* symbol = dso->FindSymbol(0x6c77e);
    ASSERT_NE(symbol, nullptr);
    ASSERT_EQ(symbol->addr, static_cast<uint64_t>(0x6c77e));
    ASSERT_EQ(symbol->len, static_cast<uint64_t>(0x16));
    ASSERT_STREQ(symbol->DemangledName(),
                 "com.example.simpleperf.simpleperfexamplewithnative.MixActivity$1.run");
    uint64_t min_vaddr;
    uint64_t file_offset_of_min_vaddr;
    dso->GetMinExecutableVaddr(&min_vaddr, &file_offset_of_min_vaddr);
    ASSERT_EQ(min_vaddr, 0);
    ASSERT_EQ(file_offset_of_min_vaddr, 0);

    // Don't crash on not exist zip entry.
    dso = Dso::CreateDso(dso_type, GetTestData("base.zip!/not_exist_entry"));
    ASSERT_TRUE(dso);
    ASSERT_EQ(nullptr, dso->FindSymbol(0));
  }
#else
  GTEST_LOG_(INFO) << "This test only runs on linux because of libdexfile";
#endif  // defined(__linux__)
}

// @CddTest = 6.1/C-0-2
TEST(dso, dex_file_offsets) {
  std::unique_ptr<Dso> dso = Dso::CreateDso(DSO_DEX_FILE, "");
  ASSERT_TRUE(dso);
  for (uint64_t offset : {0x3, 0x1, 0x5, 0x4, 0x2, 0x4, 0x3}) {
    dso->AddDexFileOffset(offset);
  }
  ASSERT_EQ(*dso->DexFileOffsets(), std::vector<uint64_t>({0x1, 0x2, 0x3, 0x4, 0x5}));
}

// @CddTest = 6.1/C-0-2
TEST(dso, embedded_elf) {
  const std::string file_path = GetUrlInApk(GetTestData(APK_FILE), NATIVELIB_IN_APK);
  std::unique_ptr<Dso> dso = Dso::CreateDso(DSO_ELF_FILE, file_path);
  ASSERT_TRUE(dso);
  ASSERT_EQ(dso->Path(), file_path);
  ASSERT_EQ(dso->GetDebugFilePath(), file_path);
  uint64_t min_vaddr;
  uint64_t file_offset_of_min_vaddr;
  dso->GetMinExecutableVaddr(&min_vaddr, &file_offset_of_min_vaddr);
  ASSERT_EQ(min_vaddr, 0);
  ASSERT_EQ(file_offset_of_min_vaddr, 0);
  const Symbol* symbol = dso->FindSymbol(0x9a4);
  ASSERT_TRUE(symbol != nullptr);
  ASSERT_STREQ(symbol->Name(), "Java_com_example_hellojni_HelloJni_callFunc1");
  BuildId build_id;
  ASSERT_TRUE(GetBuildIdFromDsoPath(file_path, &build_id));
  ASSERT_EQ(build_id, native_lib_build_id);
}

// @CddTest = 6.1/C-0-2
TEST(dso, IpToVaddrInFile) {
  std::unique_ptr<Dso> dso = Dso::CreateDso(DSO_ELF_FILE, GetTestData("libc.so"));
  ASSERT_TRUE(dso);
  ASSERT_EQ(0xa5140, dso->IpToVaddrInFile(0xe9201140, 0xe9201000, 0xa5000));
}

// @CddTest = 6.1/C-0-2
TEST(dso, kernel_address_randomization) {
  // Use ELF_FILE as a fake kernel vmlinux.
  const std::string vmlinux_path = GetTestData(ELF_FILE);
  Dso::SetVmlinux(vmlinux_path);
  std::unique_ptr<Dso> dso = Dso::CreateDso(DSO_KERNEL, DEFAULT_KERNEL_MMAP_NAME);
  ASSERT_TRUE(dso);
  ASSERT_EQ(dso->GetDebugFilePath(), vmlinux_path);
  // When map_start = 0, can't fix kernel address randomization. So vmlinux isn't used.
  ASSERT_EQ(dso->IpToVaddrInFile(0x800500, 0, 0), 0x800500);
  ASSERT_FALSE(dso->IpToFileOffset(0x800500, 0, 0));
  ASSERT_TRUE(dso->FindSymbol(0x400510) == nullptr);

  dso = Dso::CreateDso(DSO_KERNEL, DEFAULT_KERNEL_MMAP_NAME);
  ASSERT_TRUE(dso);
  ASSERT_EQ(dso->GetDebugFilePath(), vmlinux_path);
  // When map_start != 0, can fix kernel address randomization. So vmlinux is used.
  ASSERT_EQ(dso->IpToVaddrInFile(0x800500, 0x800400, 0), 0x400500);
  ASSERT_EQ(dso->IpToFileOffset(0x800500, 0x800400, 0).value(), 0x500);
  const Symbol* symbol = dso->FindSymbol(0x400510);
  ASSERT_TRUE(symbol != nullptr);
  ASSERT_STREQ(symbol->Name(), "GlobalFunc");
}

// @CddTest = 6.1/C-0-2
TEST(dso, find_vmlinux_in_symdirs) {
  // Create a symdir.
  TemporaryDir tmpdir;
  std::string vmlinux_path = std::string(tmpdir.path) + OS_PATH_SEPARATOR + "elf";
  std::string data;
  ASSERT_TRUE(android::base::ReadFileToString(GetTestData(ELF_FILE), &data));
  ASSERT_TRUE(android::base::WriteStringToFile(data, vmlinux_path));

  // Find vmlinux in symbol dirs.
  Dso::SetVmlinux("");
  Dso::AddSymbolDir(tmpdir.path);
  Dso::SetBuildIds({std::make_pair(DEFAULT_KERNEL_MMAP_NAME, BuildId(ELF_FILE_BUILD_ID))});
  std::unique_ptr<Dso> dso = Dso::CreateDso(DSO_KERNEL, DEFAULT_KERNEL_MMAP_NAME);
  ASSERT_TRUE(dso);
  ASSERT_EQ(dso->GetDebugFilePath(), vmlinux_path);
  ASSERT_EQ(0x400927, dso->IpToVaddrInFile(0x800527, 0x800000, 0));

  // Find vmlinux by CreateDsoWithBuildId.
  Dso::SetBuildIds({});
  BuildId build_id(ELF_FILE_BUILD_ID);
  dso = Dso::CreateDsoWithBuildId(DSO_KERNEL, DEFAULT_KERNEL_MMAP_NAME, build_id);
  ASSERT_TRUE(dso);
  ASSERT_EQ(dso->GetDebugFilePath(), vmlinux_path);
  ASSERT_EQ(0x400927, dso->IpToVaddrInFile(0x800527, 0x800000, 0));
}

// @CddTest = 6.1/C-0-2
TEST(dso, kernel_module) {
  // Test finding debug files for kernel modules.
  Dso::SetSymFsDir(GetTestDataDir());
  std::vector<std::pair<std::string, BuildId>> build_ids;
  build_ids.emplace_back(ELF_FILE, BuildId(ELF_FILE_BUILD_ID));
  Dso::SetBuildIds(build_ids);
  std::unique_ptr<Dso> kernel_dso = Dso::CreateDso(DSO_KERNEL, DEFAULT_KERNEL_MMAP_NAME);
  ASSERT_TRUE(kernel_dso);
  std::unique_ptr<Dso> dso = Dso::CreateKernelModuleDso(ELF_FILE, 0, 0, kernel_dso.get());
  ASSERT_EQ(dso->GetDebugFilePath(), GetTestData(ELF_FILE));
}

// @CddTest = 6.1/C-0-2
TEST(dso, kernel_module_CalculateMinVaddr) {
  // Create fake Dso objects.
  auto kernel_dso = Dso::CreateDso(DSO_KERNEL, DEFAULT_KERNEL_MMAP_NAME);
  ASSERT_TRUE(kernel_dso);
  const uint64_t module_memory_start = 0xffffffa9bc790000ULL;
  const uint64_t module_memory_size = 0x8d7000ULL;
  TemporaryFile tmpfile;
  auto module_dso =
      Dso::CreateKernelModuleDso(tmpfile.path, module_memory_start,
                                 module_memory_start + module_memory_size, kernel_dso.get());
  ASSERT_TRUE(module_dso);

  // Provide symbol info for calculating min vaddr.
  std::vector<Symbol> kernel_symbols;
  kernel_symbols.emplace_back("fake_module_function [fake_module]", 0xffffffa9bc7a64e8ULL, 0x60c);
  kernel_dso->SetSymbols(&kernel_symbols);
  std::vector<Symbol> module_symbols;
  module_symbols.emplace_back("fake_module_function", 0x144e8, 0x60c);
  module_dso->SetSymbols(&module_symbols);

  // Calculate min vaddr.
  uint64_t min_vaddr;
  uint64_t memory_offset;
  module_dso->GetMinExecutableVaddr(&min_vaddr, &memory_offset);
  ASSERT_EQ(min_vaddr, 0x144e8);
  ASSERT_EQ(memory_offset, 0x164e8);

  // Use min vaddr in IpToVaddrInFile().
  ASSERT_EQ(module_dso->IpToVaddrInFile(0xffffffa9bc7a64e8ULL, module_memory_start, 0), 0x144e8);
}

// @CddTest = 6.1/C-0-2
TEST(dso, symbol_map_file) {
  auto dso = Dso::CreateDso(DSO_SYMBOL_MAP_FILE, "perf-123.map");
  ASSERT_TRUE(dso);
  ASSERT_EQ(DSO_SYMBOL_MAP_FILE, dso->type());
  ASSERT_EQ(0x12345678, dso->IpToVaddrInFile(0x12345678, 0x0, 0x0));
  ASSERT_EQ(0x12345678, dso->IpToVaddrInFile(0x12345678, 0xe9201000, 0xa5000));
}

// @CddTest = 6.1/C-0-2
TEST(dso, FunctionName) {
  Symbol symbol = Symbol("void ctep.v(cteo, ctgc, ctbn)", 0x0, 0x1);
  ASSERT_EQ(symbol.FunctionName(), "ctep.v");
  symbol = Symbol("ctep.v(cteo, ctgc, ctbn)", 0x0, 0x1);
  ASSERT_EQ(symbol.FunctionName(), "ctep.v");
  symbol = Symbol("ctep.v", 0x0, 0x1);
  ASSERT_EQ(symbol.FunctionName(), "ctep.v");
}

// @CddTest = 6.1/C-0-2
TEST(dso, search_debug_file_only_when_needed) {
  Dso::SetBuildIds({std::make_pair("/elf", BuildId("1b12a384a9f4a3f3659b7171ca615dbec3a81f71"))});
  Dso::SetSymFsDir(GetTestDataDir());
  CapturedStderr capture;
  auto dso = Dso::CreateDso(DSO_ELF_FILE, "/elf");
  ASSERT_EQ(capture.str().find("build id mismatch"), std::string::npos);
  ASSERT_EQ(dso->GetDebugFilePath(), "/elf");
  ASSERT_NE(capture.str().find("build id mismatch"), std::string::npos);
  capture.Stop();
}

// @CddTest = 6.1/C-0-2
TEST(dso, read_symbol_warning) {
  {
    // Don't warn when the file may not be an ELF file.
    auto dso = Dso::CreateDso(DSO_ELF_FILE, GetTestData("not_exist_file"));
    CapturedStderr capture;
    dso->LoadSymbols();
    ASSERT_EQ(capture.str().find("failed to read symbols"), std::string::npos);
  }
  {
    // Don't warn when the file may not be an ELF file.
    auto dso = Dso::CreateDso(DSO_ELF_FILE, GetTestData("base.vdex"));
    CapturedStderr capture;
    dso->LoadSymbols();
    ASSERT_EQ(capture.str().find("failed to read symbols"), std::string::npos);
  }
  {
    // Warn when the file is an ELF file (having a build id).
    std::string file_path = GetTestData("not_exist_file");
    Dso::SetBuildIds(
        {std::make_pair(file_path, BuildId("1b12a384a9f4a3f3659b7171ca615dbec3a81f71"))});
    auto dso = Dso::CreateDso(DSO_ELF_FILE, file_path);
    CapturedStderr capture;
    dso->LoadSymbols();
    ASSERT_NE(capture.str().find("failed to read symbols"), std::string::npos);
  }
  {
    // Don't warn when we already have symbols.
    std::string file_path = GetTestData("not_exist_file");
    Dso::SetBuildIds(
        {std::make_pair(file_path, BuildId("1b12a384a9f4a3f3659b7171ca615dbec3a81f71"))});
    auto dso = Dso::CreateDso(DSO_ELF_FILE, file_path);
    std::vector<Symbol> symbols;
    symbols.emplace_back("fake_symbol", 0x1234, 0x60);
    dso->SetSymbols(&symbols);
    CapturedStderr capture;
    dso->LoadSymbols();
    ASSERT_EQ(capture.str().find("failed to read symbols"), std::string::npos);
  }
}

// @CddTest = 6.1/C-0-2
TEST(dso, demangle) {
  ASSERT_EQ(Dso::Demangle("main"), "main");
  ASSERT_EQ(Dso::Demangle("_ZN4main4main17h2a68d4d833d7495aE"), "main::main::h2a68d4d833d7495a");
#if defined(__linux__) || defined(__darwin__)
  // Demangling rust symbol is only supported on linux and darwin.
  ASSERT_EQ(Dso::Demangle("_RNvC6_123foo3bar"), "123foo::bar");
#endif
}
