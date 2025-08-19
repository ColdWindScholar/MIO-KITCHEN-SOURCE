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

#ifndef SIMPLE_PERF_DSO_H_
#define SIMPLE_PERF_DSO_H_

#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

#include <android-base/file.h>
#include <android-base/logging.h>

#include "build_id.h"
#include "kallsyms.h"
#include "read_elf.h"

namespace simpleperf {
namespace simpleperf_dso_impl {

// Find elf files with symbol table and debug information.
class DebugElfFileFinder {
 public:
  void Reset();
  bool SetSymFsDir(const std::string& symfs_dir);
  bool AddSymbolDir(const std::string& symbol_dir);
  void SetVdsoFile(const std::string& vdso_file, bool is_64bit);
  std::string FindDebugFile(const std::string& dso_path, bool force_64bit, BuildId& build_id);
  // Only for testing
  std::string GetPathInSymFsDir(const std::string& path);

 private:
  void CollectBuildIdInDir(const std::string& dir);

  std::string vdso_64bit_;
  std::string vdso_32bit_;
  std::string symfs_dir_;
  std::unordered_map<std::string, std::string> build_id_to_file_map_;
};

}  // namespace simpleperf_dso_impl

struct Symbol {
  uint64_t addr;
  // TODO: make len uint32_t.
  uint64_t len;

  Symbol(std::string_view name, uint64_t addr, uint64_t len);
  const char* Name() const { return name_; }

  const char* DemangledName() const;
  void SetDemangledName(std::string_view name) const;
  // Return function name without signature.
  std::string_view FunctionName() const;

  bool HasDumpId() const { return dump_id_ != UINT_MAX; }

  bool GetDumpId(uint32_t* pdump_id) const {
    if (!HasDumpId()) {
      return false;
    }
    *pdump_id = dump_id_;
    return true;
  }

  static bool CompareByDumpId(const Symbol* s1, const Symbol* s2) {
    uint32_t id1 = UINT_MAX;
    s1->GetDumpId(&id1);
    uint32_t id2 = UINT_MAX;
    s2->GetDumpId(&id2);
    return id1 < id2;
  }

  static bool CompareByAddr(const Symbol* s1, const Symbol* s2) { return s1->addr < s2->addr; }

  static bool CompareValueByAddr(const Symbol& s1, const Symbol& s2) { return s1.addr < s2.addr; }

 private:
  const char* name_;
  mutable const char* demangled_name_;
  mutable uint32_t dump_id_;

  friend class Dso;
};

enum DsoType {
  DSO_KERNEL,
  DSO_KERNEL_MODULE,
  DSO_ELF_FILE,
  DSO_DEX_FILE,  // For files containing dex files, like .vdex files.
  DSO_SYMBOL_MAP_FILE,
  DSO_UNKNOWN_FILE,
  // DSO_UNKNOWN_FILE is written to the file feature section in recording files. Changing its value
  // may cause compatibility issue. So put new DsoTypes below.
};

class Dso {
 public:
  static void SetDemangle(bool demangle);
  static std::string Demangle(const std::string& name);
  // SymFsDir is used to provide an alternative root directory looking for files with symbols.
  // For example, if we are searching symbols for /system/lib/libc.so and SymFsDir is /data/symbols,
  // then we will also search file /data/symbols/system/lib/libc.so.
  static bool SetSymFsDir(const std::string& symfs_dir);
  // SymbolDir is used to add a directory containing files with symbols. Each file under it will
  // be searched recursively to build a build_id_map.
  static bool AddSymbolDir(const std::string& symbol_dir);
  static void SetVmlinux(const std::string& vmlinux);
  static void SetKallsyms(std::string kallsyms) {
    if (!kallsyms.empty()) {
      kallsyms_ = std::move(kallsyms);
    }
  }
  static void SetBuildIds(const std::vector<std::pair<std::string, BuildId>>& build_ids);
  static BuildId FindExpectedBuildIdForPath(const std::string& path);
  static void SetVdsoFile(const std::string& vdso_file, bool is_64bit);

  static std::unique_ptr<Dso> CreateDso(DsoType dso_type, const std::string& dso_path,
                                        bool force_64bit = false);
  static std::unique_ptr<Dso> CreateDsoWithBuildId(DsoType dso_type, const std::string& dso_path,
                                                   BuildId& build_id);
  static std::unique_ptr<Dso> CreateKernelModuleDso(const std::string& dso_path,
                                                    uint64_t memory_start, uint64_t memory_end,
                                                    Dso* kernel_dso);
  virtual ~Dso();

  DsoType type() const { return type_; }

  // Return the path recorded in perf.data.
  const std::string& Path() const { return path_; }
  // Return the path containing symbol table and debug information.
  const std::string& GetDebugFilePath() const {
    if (!debug_file_path_.has_value()) {
      debug_file_path_ = FindDebugFilePath();
    }
    return debug_file_path_.value();
  }

  // Return the path beautified for reporting.
  virtual std::string_view GetReportPath() const { return Path(); }
  // Return the file name without directory info.
  const std::string& FileName() const { return file_name_; }

  bool HasDumpId() { return dump_id_ != UINT_MAX; }

  bool GetDumpId(uint32_t* pdump_id) {
    if (!HasDumpId()) {
      return false;
    }
    *pdump_id = dump_id_;
    return true;
  }

  uint32_t CreateDumpId();
  uint32_t CreateSymbolDumpId(const Symbol* symbol);

  virtual void SetMinExecutableVaddr(uint64_t, uint64_t) {}
  virtual void GetMinExecutableVaddr(uint64_t* min_vaddr, uint64_t* file_offset) {
    *min_vaddr = 0;
    *file_offset = 0;
  }
  virtual void AddDexFileOffset(uint64_t) {}
  virtual const std::vector<uint64_t>* DexFileOffsets() { return nullptr; }

  virtual uint64_t IpToVaddrInFile(uint64_t ip, uint64_t map_start, uint64_t map_pgoff) = 0;
  virtual std::optional<uint64_t> IpToFileOffset(uint64_t ip, uint64_t map_start,
                                                 uint64_t map_pgoff);

  const Symbol* FindSymbol(uint64_t vaddr_in_dso);
  void LoadSymbols();
  const std::vector<Symbol>& GetSymbols() const { return symbols_; }
  void SetSymbols(std::vector<Symbol>* symbols);

  // Create a symbol for a virtual address which can't find a corresponding
  // symbol in symbol table.
  void AddUnknownSymbol(uint64_t vaddr_in_dso, const std::string& name);
  bool IsForJavaMethod() const;

 protected:
  static bool demangle_;
  static std::string vmlinux_;
  static std::string kallsyms_;
  static std::unordered_map<std::string, BuildId> build_id_map_;
  static size_t dso_count_;
  static uint32_t g_dump_id_;
  static simpleperf_dso_impl::DebugElfFileFinder debug_elf_file_finder_;

  Dso(DsoType type, const std::string& path);
  BuildId GetExpectedBuildId() const;

  virtual std::string FindDebugFilePath() const { return path_; }
  virtual std::vector<Symbol> LoadSymbolsImpl() = 0;

  DsoType type_;
  // path of the shared library used by the profiled program
  const std::string path_;
  // path of the shared library having symbol table and debug information
  // It is the same as path_, or has the same build id as path_.
  mutable std::optional<std::string> debug_file_path_;
  // File name of the shared library, got by removing directories in path_.
  std::string file_name_;
  std::vector<Symbol> symbols_;
  // unknown symbols are like [libc.so+0x1234].
  std::unordered_map<uint64_t, Symbol> unknown_symbols_;
  bool is_loaded_;
  // Used to identify current dso if it needs to be dumped.
  uint32_t dump_id_;
  // Used to assign dump_id for symbols in current dso.
  uint32_t symbol_dump_id_;
  android::base::LogSeverity symbol_warning_loglevel_;
};

const char* DsoTypeToString(DsoType dso_type);
bool GetBuildIdFromDsoPath(const std::string& dso_path, BuildId* build_id);
bool GetBuildId(const Dso& dso, BuildId& build_id);

}  // namespace simpleperf

#endif  // SIMPLE_PERF_DSO_H_
