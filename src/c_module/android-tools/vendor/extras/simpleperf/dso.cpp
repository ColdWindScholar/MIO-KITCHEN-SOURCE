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

#include "dso.h"

#include <stdlib.h>
#include <string.h>

#include <algorithm>
#include <limits>
#include <memory>
#include <optional>
#include <string_view>
#include <vector>

#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/strings.h>

#include "JITDebugReader.h"
#include "environment.h"
#include "kallsyms.h"
#include "read_apk.h"
#include "read_dex_file.h"
#include "read_elf.h"
#include "utils.h"

namespace simpleperf {

using android::base::EndsWith;
using android::base::StartsWith;

namespace simpleperf_dso_impl {

std::string RemovePathSeparatorSuffix(const std::string& path) {
  // Don't remove path separator suffix for '/'.
  if (EndsWith(path, OS_PATH_SEPARATOR) && path.size() > 1u) {
    return path.substr(0, path.size() - 1);
  }
  return path;
}

void DebugElfFileFinder::Reset() {
  vdso_64bit_.clear();
  vdso_32bit_.clear();
  symfs_dir_.clear();
  build_id_to_file_map_.clear();
}

bool DebugElfFileFinder::SetSymFsDir(const std::string& symfs_dir) {
  symfs_dir_ = RemovePathSeparatorSuffix(symfs_dir);
  if (!IsDir(symfs_dir_)) {
    LOG(ERROR) << "Invalid symfs_dir '" << symfs_dir_ << "'";
    return false;
  }
  std::string build_id_list_file = symfs_dir_ + OS_PATH_SEPARATOR + "build_id_list";
  std::string build_id_list;
  if (android::base::ReadFileToString(build_id_list_file, &build_id_list)) {
    for (auto& line : android::base::Split(build_id_list, "\n")) {
      std::vector<std::string> items = android::base::Split(line, "=");
      if (items.size() == 2u) {
        build_id_to_file_map_[items[0]] = symfs_dir_ + OS_PATH_SEPARATOR + items[1];
      }
    }
  }
  return true;
}

bool DebugElfFileFinder::AddSymbolDir(const std::string& symbol_dir) {
  if (!IsDir(symbol_dir)) {
    LOG(ERROR) << "Invalid symbol dir " << symbol_dir;
    return false;
  }
  std::string dir = RemovePathSeparatorSuffix(symbol_dir);
  CollectBuildIdInDir(dir);
  return true;
}

void DebugElfFileFinder::CollectBuildIdInDir(const std::string& dir) {
  for (const std::string& entry : GetEntriesInDir(dir)) {
    std::string path = dir + OS_PATH_SEPARATOR + entry;
    if (IsDir(path)) {
      CollectBuildIdInDir(path);
    } else {
      BuildId build_id;
      ElfStatus status;
      auto elf = ElfFile::Open(path, &status);
      if (status == ElfStatus::NO_ERROR && elf->GetBuildId(&build_id) == ElfStatus::NO_ERROR) {
        build_id_to_file_map_[build_id.ToString()] = path;
      }
    }
  }
}

void DebugElfFileFinder::SetVdsoFile(const std::string& vdso_file, bool is_64bit) {
  if (is_64bit) {
    vdso_64bit_ = vdso_file;
  } else {
    vdso_32bit_ = vdso_file;
  }
}

static bool CheckDebugFilePath(const std::string& path, BuildId& build_id,
                               bool report_build_id_mismatch) {
  ElfStatus status;
  auto elf = ElfFile::Open(path, &status);
  if (!elf) {
    return false;
  }
  BuildId debug_build_id;
  status = elf->GetBuildId(&debug_build_id);
  if (status != ElfStatus::NO_ERROR && status != ElfStatus::NO_BUILD_ID) {
    return false;
  }

  // Native libraries in apks and kernel modules may not have build ids.
  // So build_id and debug_build_id can either be empty, or have the same value.
  bool match = build_id == debug_build_id;
  if (!match && report_build_id_mismatch) {
    LOG(WARNING) << path << " isn't used because of build id mismatch: expected " << build_id
                 << ", real " << debug_build_id;
  }
  return match;
}

std::string DebugElfFileFinder::FindDebugFile(const std::string& dso_path, bool force_64bit,
                                              BuildId& build_id) {
  if (dso_path == "[vdso]") {
    if (force_64bit && !vdso_64bit_.empty()) {
      return vdso_64bit_;
    } else if (!force_64bit && !vdso_32bit_.empty()) {
      return vdso_32bit_;
    }
  }
  if (build_id.IsEmpty()) {
    // Try reading build id from file if we don't already have one.
    GetBuildIdFromDsoPath(dso_path, &build_id);
  }

  // 1. Try build_id_to_file_map.
  if (!build_id_to_file_map_.empty()) {
    if (!build_id.IsEmpty() || GetBuildIdFromDsoPath(dso_path, &build_id)) {
      auto it = build_id_to_file_map_.find(build_id.ToString());
      if (it != build_id_to_file_map_.end() && CheckDebugFilePath(it->second, build_id, false)) {
        return it->second;
      }
    }
  }
  if (!symfs_dir_.empty()) {
    // 2. Try concatenating symfs_dir and dso_path.
    std::string path = GetPathInSymFsDir(dso_path);
    if (CheckDebugFilePath(path, build_id, true)) {
      return path;
    }
    if (EndsWith(dso_path, ".apk") && IsRegularFile(path)) {
      return path;
    }
    // 3. Try concatenating symfs_dir and basename of dso_path.
    path = symfs_dir_ + OS_PATH_SEPARATOR + android::base::Basename(dso_path);
    if (CheckDebugFilePath(path, build_id, false)) {
      return path;
    }
  }
  // 4. Try concatenating /usr/lib/debug and dso_path.
  // Linux host can store debug shared libraries in /usr/lib/debug.
  if (CheckDebugFilePath("/usr/lib/debug" + dso_path, build_id, false)) {
    return "/usr/lib/debug" + dso_path;
  }
  return dso_path;
}

std::string DebugElfFileFinder::GetPathInSymFsDir(const std::string& path) {
  auto add_symfs_prefix = [&](const std::string& path) {
    if (StartsWith(path, OS_PATH_SEPARATOR)) {
      return symfs_dir_ + path;
    }
    return symfs_dir_ + OS_PATH_SEPARATOR + path;
  };
  if (OS_PATH_SEPARATOR == '/') {
    return add_symfs_prefix(path);
  }
  // Paths in recorded perf.data uses '/' as path separator. When reporting on Windows, it needs
  // to be converted to '\\'.
  auto tuple = SplitUrlInApk(path);
  if (std::get<0>(tuple)) {
    std::string apk_path = std::get<1>(tuple);
    std::string entry_path = std::get<2>(tuple);
    std::replace(apk_path.begin(), apk_path.end(), '/', OS_PATH_SEPARATOR);
    return GetUrlInApk(add_symfs_prefix(apk_path), entry_path);
  }
  std::string elf_path = path;
  std::replace(elf_path.begin(), elf_path.end(), '/', OS_PATH_SEPARATOR);
  return add_symfs_prefix(elf_path);
}
}  // namespace simpleperf_dso_impl

static OneTimeFreeAllocator symbol_name_allocator;

Symbol::Symbol(std::string_view name, uint64_t addr, uint64_t len)
    : addr(addr),
      len(len),
      name_(symbol_name_allocator.AllocateString(name)),
      demangled_name_(nullptr),
      dump_id_(UINT_MAX) {}

const char* Symbol::DemangledName() const {
  if (demangled_name_ == nullptr) {
    const std::string s = Dso::Demangle(name_);
    SetDemangledName(s);
  }
  return demangled_name_;
}

void Symbol::SetDemangledName(std::string_view name) const {
  if (name == name_) {
    demangled_name_ = name_;
  } else {
    demangled_name_ = symbol_name_allocator.AllocateString(name);
  }
}

std::string_view Symbol::FunctionName() const {
  // Name with signature is like "void ctep.v(cteo, ctgc, ctbn)".
  std::string_view name = DemangledName();
  auto brace_pos = name.find('(');
  if (brace_pos != name.npos) {
    name = name.substr(0, brace_pos);
    auto space_pos = name.rfind(' ');
    if (space_pos != name.npos) {
      name = name.substr(space_pos + 1);
    }
  }
  return name;
}

static bool CompareSymbolToAddr(const Symbol& s, uint64_t addr) {
  return s.addr < addr;
}

static bool CompareAddrToSymbol(uint64_t addr, const Symbol& s) {
  return addr < s.addr;
}

bool Dso::demangle_ = true;
std::string Dso::vmlinux_;
std::string Dso::kallsyms_;
std::unordered_map<std::string, BuildId> Dso::build_id_map_;
size_t Dso::dso_count_;
uint32_t Dso::g_dump_id_;
simpleperf_dso_impl::DebugElfFileFinder Dso::debug_elf_file_finder_;

void Dso::SetDemangle(bool demangle) {
  demangle_ = demangle;
}

extern "C" char* __cxa_demangle(const char* mangled_name, char* buf, size_t* n, int* status);
#if defined(__linux__) || defined(__darwin__)
extern "C" char* rustc_demangle(const char* mangled, char* out, size_t* len, int* status);
#endif

std::string Dso::Demangle(const std::string& name) {
  if (!demangle_) {
    return name;
  }
  int status;
  bool is_linker_symbol = (name.find(linker_prefix) == 0);
  const char* mangled_str = name.c_str();
  if (is_linker_symbol) {
    mangled_str += linker_prefix.size();
  }

  if (mangled_str[0] == '_') {
    char* demangled_name = nullptr;
    int status = -2;  // -2 means name didn't demangle.
    if (mangled_str[1] == 'Z') {
      demangled_name = __cxa_demangle(mangled_str, nullptr, nullptr, &status);
#if defined(__linux__) || defined(__darwin__)
    } else if (mangled_str[1] == 'R') {
      demangled_name = rustc_demangle(mangled_str, nullptr, nullptr, &status);
#endif
    }
    if (status == 0) {
      // demangled successfully
      std::string result;
      if (is_linker_symbol) {
        result = std::string("[linker]") + demangled_name;
      } else {
        result = demangled_name;
      }
      free(demangled_name);
      return result;
    }
  }

  // failed to demangle
  if (is_linker_symbol) {
    return std::string("[linker]") + mangled_str;
  }
  return name;
}

bool Dso::SetSymFsDir(const std::string& symfs_dir) {
  return debug_elf_file_finder_.SetSymFsDir(symfs_dir);
}

bool Dso::AddSymbolDir(const std::string& symbol_dir) {
  return debug_elf_file_finder_.AddSymbolDir(symbol_dir);
}

void Dso::SetVmlinux(const std::string& vmlinux) {
  vmlinux_ = vmlinux;
}

void Dso::SetBuildIds(const std::vector<std::pair<std::string, BuildId>>& build_ids) {
  std::unordered_map<std::string, BuildId> map;
  for (auto& pair : build_ids) {
    LOG(DEBUG) << "build_id_map: " << pair.first << ", " << pair.second.ToString();
    map.insert(pair);
  }
  build_id_map_ = std::move(map);
}

void Dso::SetVdsoFile(const std::string& vdso_file, bool is_64bit) {
  debug_elf_file_finder_.SetVdsoFile(vdso_file, is_64bit);
}

BuildId Dso::FindExpectedBuildIdForPath(const std::string& path) {
  auto it = build_id_map_.find(path);
  if (it != build_id_map_.end()) {
    return it->second;
  }
  return BuildId();
}

BuildId Dso::GetExpectedBuildId() const {
  return FindExpectedBuildIdForPath(path_);
}

Dso::Dso(DsoType type, const std::string& path)
    : type_(type),
      path_(path),
      is_loaded_(false),
      dump_id_(UINT_MAX),
      symbol_dump_id_(0),
      symbol_warning_loglevel_(android::base::WARNING) {
  size_t pos = path.find_last_of("/\\");
  if (pos != std::string::npos) {
    file_name_ = path.substr(pos + 1);
  } else {
    file_name_ = path;
  }
  dso_count_++;
}

Dso::~Dso() {
  if (--dso_count_ == 0) {
    // Clean up global variables when no longer used.
    symbol_name_allocator.Clear();
    demangle_ = true;
    vmlinux_.clear();
    kallsyms_.clear();
    build_id_map_.clear();
    g_dump_id_ = 0;
    debug_elf_file_finder_.Reset();
  }
}

uint32_t Dso::CreateDumpId() {
  CHECK(!HasDumpId());
  return dump_id_ = g_dump_id_++;
}

uint32_t Dso::CreateSymbolDumpId(const Symbol* symbol) {
  CHECK(!symbol->HasDumpId());
  symbol->dump_id_ = symbol_dump_id_++;
  return symbol->dump_id_;
}

std::optional<uint64_t> Dso::IpToFileOffset(uint64_t ip, uint64_t map_start, uint64_t map_pgoff) {
  return ip - map_start + map_pgoff;
}

const Symbol* Dso::FindSymbol(uint64_t vaddr_in_dso) {
  if (!is_loaded_) {
    LoadSymbols();
  }
  auto it = std::upper_bound(symbols_.begin(), symbols_.end(), vaddr_in_dso, CompareAddrToSymbol);
  if (it != symbols_.begin()) {
    --it;
    if (it->addr <= vaddr_in_dso && (it->addr + it->len > vaddr_in_dso)) {
      return &*it;
    }
  }
  if (!unknown_symbols_.empty()) {
    auto it = unknown_symbols_.find(vaddr_in_dso);
    if (it != unknown_symbols_.end()) {
      return &it->second;
    }
  }
  return nullptr;
}

void Dso::SetSymbols(std::vector<Symbol>* symbols) {
  symbols_ = std::move(*symbols);
  symbols->clear();
}

void Dso::AddUnknownSymbol(uint64_t vaddr_in_dso, const std::string& name) {
  unknown_symbols_.insert(std::make_pair(vaddr_in_dso, Symbol(name, vaddr_in_dso, 1)));
}

bool Dso::IsForJavaMethod() const {
  if (type_ == DSO_DEX_FILE) {
    return true;
  }
  if (type_ == DSO_ELF_FILE) {
    if (JITDebugReader::IsPathInJITSymFile(path_)) {
      return true;
    }
    // JITDebugReader in old versions generates symfiles in 'TemporaryFile-XXXXXX'.
    size_t pos = path_.rfind('/');
    pos = (pos == std::string::npos) ? 0 : pos + 1;
    return StartsWith(std::string_view(&path_[pos], path_.size() - pos), "TemporaryFile");
  }
  return false;
}

void Dso::LoadSymbols() {
  if (!is_loaded_) {
    is_loaded_ = true;
    std::vector<Symbol> symbols = LoadSymbolsImpl();
    if (symbols_.empty()) {
      symbols_ = std::move(symbols);
    } else {
      std::vector<Symbol> merged_symbols;
      std::set_union(symbols_.begin(), symbols_.end(), symbols.begin(), symbols.end(),
                     std::back_inserter(merged_symbols), Symbol::CompareValueByAddr);
      symbols_ = std::move(merged_symbols);
    }
  }
}

static void ReportReadElfSymbolResult(
    ElfStatus result, const std::string& path, const std::string& debug_file_path,
    android::base::LogSeverity warning_loglevel = android::base::WARNING) {
  if (result == ElfStatus::NO_ERROR) {
    LOG(VERBOSE) << "Read symbols from " << debug_file_path << " successfully";
  } else if (result == ElfStatus::NO_SYMBOL_TABLE) {
    if (path == "[vdso]") {
      // Vdso only contains dynamic symbol table, and we can't change that.
      return;
    }
    // Lacking symbol table isn't considered as an error but worth reporting.
    LOG(warning_loglevel) << debug_file_path << " doesn't contain symbol table";
  } else {
    LOG(warning_loglevel) << "failed to read symbols from " << debug_file_path << ": " << result;
  }
}

static void SortAndFixSymbols(std::vector<Symbol>& symbols) {
  std::sort(symbols.begin(), symbols.end(), Symbol::CompareValueByAddr);
  Symbol* prev_symbol = nullptr;
  for (auto& symbol : symbols) {
    if (prev_symbol != nullptr && prev_symbol->len == 0) {
      prev_symbol->len = symbol.addr - prev_symbol->addr;
    }
    prev_symbol = &symbol;
  }
}

class DexFileDso : public Dso {
 public:
  DexFileDso(const std::string& path) : Dso(DSO_DEX_FILE, path) {}

  void AddDexFileOffset(uint64_t dex_file_offset) override {
    auto it = std::lower_bound(dex_file_offsets_.begin(), dex_file_offsets_.end(), dex_file_offset);
    if (it != dex_file_offsets_.end() && *it == dex_file_offset) {
      return;
    }
    dex_file_offsets_.insert(it, dex_file_offset);
  }

  const std::vector<uint64_t>* DexFileOffsets() override { return &dex_file_offsets_; }

  uint64_t IpToVaddrInFile(uint64_t ip, uint64_t map_start, uint64_t map_pgoff) override {
    return ip - map_start + map_pgoff;
  }

  std::vector<Symbol> LoadSymbolsImpl() override {
    std::vector<Symbol> symbols;
    if (StartsWith(path_, kDexFileInMemoryPrefix)) {
      // For dex file in memory, the symbols should already be set via SetSymbols().
      return symbols;
    }

    const std::string& debug_file_path = GetDebugFilePath();
    auto tuple = SplitUrlInApk(debug_file_path);
    // Symbols of dex files are collected on device. If the dex file doesn't exist, probably
    // we are reporting on host, and there is no need to report warning of missing dex files.
    if (!IsRegularFile(std::get<0>(tuple) ? std::get<1>(tuple) : debug_file_path)) {
      LOG(DEBUG) << "skip reading symbols from non-exist dex_file " << debug_file_path;
      return symbols;
    }
    bool status = false;
    auto symbol_callback = [&](DexFileSymbol* symbol) {
      symbols.emplace_back(symbol->name, symbol->addr, symbol->size);
    };
    if (std::get<0>(tuple)) {
      std::unique_ptr<ArchiveHelper> ahelper = ArchiveHelper::CreateInstance(std::get<1>(tuple));
      ZipEntry entry;
      std::vector<uint8_t> data;
      if (ahelper && ahelper->FindEntry(std::get<2>(tuple), &entry) &&
          ahelper->GetEntryData(entry, &data)) {
        status = ReadSymbolsFromDexFileInMemory(data.data(), data.size(), debug_file_path,
                                                dex_file_offsets_, symbol_callback);
      }
    } else {
      status = ReadSymbolsFromDexFile(debug_file_path, dex_file_offsets_, symbol_callback);
    }
    if (!status) {
      android::base::LogSeverity level =
          symbols_.empty() ? android::base::WARNING : android::base::DEBUG;
      LOG(level) << "Failed to read symbols from dex_file " << debug_file_path;
      return symbols;
    }
    LOG(VERBOSE) << "Read symbols from dex_file " << debug_file_path << " successfully";
    SortAndFixSymbols(symbols);
    return symbols;
  }

 private:
  std::vector<uint64_t> dex_file_offsets_;
};

class ElfDso : public Dso {
 public:
  ElfDso(const std::string& path, bool force_64bit)
      : Dso(DSO_ELF_FILE, path), force_64bit_(force_64bit) {}

  std::string_view GetReportPath() const override {
    if (JITDebugReader::IsPathInJITSymFile(path_)) {
      if (path_.find(kJITAppCacheFile) != path_.npos) {
        return "[JIT app cache]";
      }
      return "[JIT zygote cache]";
    }
    return path_;
  }

  void SetMinExecutableVaddr(uint64_t min_vaddr, uint64_t file_offset) override {
    min_vaddr_ = min_vaddr;
    file_offset_of_min_vaddr_ = file_offset;
  }

  void GetMinExecutableVaddr(uint64_t* min_vaddr, uint64_t* file_offset) override {
    if (type_ == DSO_DEX_FILE) {
      return dex_file_dso_->GetMinExecutableVaddr(min_vaddr, file_offset);
    }
    if (min_vaddr_ == uninitialized_value) {
      min_vaddr_ = 0;
      BuildId build_id = GetExpectedBuildId();

      ElfStatus status;
      auto elf = ElfFile::Open(GetDebugFilePath(), &build_id, &status);
      if (elf) {
        min_vaddr_ = elf->ReadMinExecutableVaddr(&file_offset_of_min_vaddr_);
      } else {
        // This is likely to be a file wrongly thought of as an ELF file, due to stack unwinding.
        // No need to report it by default.
        LOG(DEBUG) << "failed to read min virtual address of " << GetDebugFilePath() << ": "
                   << status;
      }
    }
    *min_vaddr = min_vaddr_;
    *file_offset = file_offset_of_min_vaddr_;
  }

  uint64_t IpToVaddrInFile(uint64_t ip, uint64_t map_start, uint64_t map_pgoff) override {
    if (type_ == DSO_DEX_FILE) {
      return dex_file_dso_->IpToVaddrInFile(ip, map_start, map_pgoff);
    }
    uint64_t min_vaddr;
    uint64_t file_offset_of_min_vaddr;
    GetMinExecutableVaddr(&min_vaddr, &file_offset_of_min_vaddr);
    if (file_offset_of_min_vaddr == uninitialized_value) {
      return ip - map_start + min_vaddr;
    }
    // Apps may make part of the executable segment of a shared library writeable, which can
    // generate multiple executable segments at runtime. So use map_pgoff to calculate
    // vaddr_in_file.
    return ip - map_start + map_pgoff - file_offset_of_min_vaddr + min_vaddr;
  }

  void AddDexFileOffset(uint64_t dex_file_offset) override {
    if (type_ == DSO_ELF_FILE) {
      // When simpleperf does unwinding while recording, it processes mmap records before reading
      // dex file linked list (via JITDebugReader). To process mmap records, it creates Dso
      // objects of type ELF_FILE. Then after reading dex file linked list, it realizes some
      // ELF_FILE Dso objects should actually be DEX_FILE, because they have dex file offsets.
      // So here converts ELF_FILE Dso into DEX_FILE Dso.
      type_ = DSO_DEX_FILE;
      dex_file_dso_.reset(new DexFileDso(path_));
    }
    dex_file_dso_->AddDexFileOffset(dex_file_offset);
  }

  const std::vector<uint64_t>* DexFileOffsets() override {
    return dex_file_dso_ ? dex_file_dso_->DexFileOffsets() : nullptr;
  }

 protected:
  std::string FindDebugFilePath() const override {
    BuildId build_id = GetExpectedBuildId();
    return debug_elf_file_finder_.FindDebugFile(path_, force_64bit_, build_id);
  }

  std::vector<Symbol> LoadSymbolsImpl() override {
    if (dex_file_dso_) {
      return dex_file_dso_->LoadSymbolsImpl();
    }
    std::vector<Symbol> symbols;
    BuildId build_id = GetExpectedBuildId();
    auto symbol_callback = [&](const ElfFileSymbol& symbol) {
      if (symbol.is_func || (symbol.is_label && symbol.is_in_text_section)) {
        symbols.emplace_back(symbol.name, symbol.vaddr, symbol.len);
      }
    };
    ElfStatus status;
    auto elf = ElfFile::Open(GetDebugFilePath(), &build_id, &status);
    if (elf) {
      status = elf->ParseSymbols(symbol_callback);
    }
    android::base::LogSeverity log_level = android::base::WARNING;
    if (!symbols_.empty() || !symbols.empty()) {
      // We already have some symbols when recording.
      log_level = android::base::DEBUG;
    }
    if ((status == ElfStatus::FILE_NOT_FOUND || status == ElfStatus::FILE_MALFORMED) &&
        build_id.IsEmpty()) {
      // This is likely to be a file wrongly thought of as an ELF file, due to stack unwinding.
      log_level = android::base::DEBUG;
    }
    ReportReadElfSymbolResult(status, path_, GetDebugFilePath(), log_level);
    SortAndFixSymbols(symbols);
    return symbols;
  }

 private:
  static constexpr uint64_t uninitialized_value = std::numeric_limits<uint64_t>::max();

  bool force_64bit_;
  uint64_t min_vaddr_ = uninitialized_value;
  uint64_t file_offset_of_min_vaddr_ = uninitialized_value;
  std::unique_ptr<DexFileDso> dex_file_dso_;
};

class KernelDso : public Dso {
 public:
  KernelDso(const std::string& path) : Dso(DSO_KERNEL, path) {}

  // IpToVaddrInFile() and LoadSymbols() must be consistent in fixing addresses changed by kernel
  // address space layout randomization.
  uint64_t IpToVaddrInFile(uint64_t ip, uint64_t map_start, uint64_t) override {
    if (map_start != 0 && GetKernelStartAddr() != 0) {
      // Fix kernel addresses changed by kernel address randomization.
      fix_kernel_address_randomization_ = true;
      return ip - map_start + GetKernelStartAddr();
    }
    return ip;
  }

  std::optional<uint64_t> IpToFileOffset(uint64_t ip, uint64_t map_start, uint64_t) override {
    if (map_start != 0 && GetKernelStartOffset() != 0) {
      return ip - map_start + GetKernelStartOffset();
    }
    return std::nullopt;
  }

 protected:
  std::string FindDebugFilePath() const override {
    BuildId build_id = GetExpectedBuildId();
    if (!vmlinux_.empty()) {
      // Use vmlinux as the kernel debug file.
      ElfStatus status;
      if (ElfFile::Open(vmlinux_, &build_id, &status)) {
        return vmlinux_;
      }
    }
    return debug_elf_file_finder_.FindDebugFile(path_, false, build_id);
  }

  std::vector<Symbol> LoadSymbolsImpl() override {
    std::vector<Symbol> symbols;
    ReadSymbolsFromDebugFile(&symbols);

    if (symbols.empty() && !kallsyms_.empty()) {
      ReadSymbolsFromKallsyms(kallsyms_, &symbols);
    }
#if defined(__linux__)
    if (symbols.empty()) {
      ReadSymbolsFromProc(&symbols);
    }
#endif  // defined(__linux__)
    SortAndFixSymbols(symbols);
    if (!symbols.empty() && symbols.back().len == 0) {
      symbols.back().len = std::numeric_limits<uint64_t>::max() - symbols.back().addr;
    }
    return symbols;
  }

 private:
  void ReadSymbolsFromDebugFile(std::vector<Symbol>* symbols) {
    ElfStatus status;
    auto elf = ElfFile::Open(GetDebugFilePath(), &status);
    if (!elf) {
      return;
    }

    if (!fix_kernel_address_randomization_) {
      LOG(WARNING) << "Don't know how to fix addresses changed by kernel address randomization. So "
                      "symbols in "
                   << GetDebugFilePath() << " are not used";
      return;
    }
    // symbols_ are kernel symbols got from /proc/kallsyms while recording. Those symbols are
    // not fixed for kernel address randomization. So clear them to avoid mixing them with
    // symbols in debug_file_path.
    symbols_.clear();

    auto symbol_callback = [&](const ElfFileSymbol& symbol) {
      if (symbol.is_func) {
        symbols->emplace_back(symbol.name, symbol.vaddr, symbol.len);
      }
    };
    status = elf->ParseSymbols(symbol_callback);
    ReportReadElfSymbolResult(status, path_, GetDebugFilePath());
  }

  void ReadSymbolsFromKallsyms(std::string& kallsyms, std::vector<Symbol>* symbols) {
    auto symbol_callback = [&](const KernelSymbol& symbol) {
      if (strchr("TtWw", symbol.type) && symbol.addr != 0u) {
        if (symbol.module == nullptr) {
          symbols->emplace_back(symbol.name, symbol.addr, 0);
        } else {
          std::string name = std::string(symbol.name) + " [" + symbol.module + "]";
          symbols->emplace_back(name, symbol.addr, 0);
        }
      }
      return false;
    };
    ProcessKernelSymbols(kallsyms, symbol_callback);
    if (symbols->empty()) {
      LOG(WARNING) << "Symbol addresses in /proc/kallsyms on device are all zero. "
                      "`echo 0 >/proc/sys/kernel/kptr_restrict` if possible.";
    }
  }

#if defined(__linux__)
  void ReadSymbolsFromProc(std::vector<Symbol>* symbols) {
    BuildId build_id = GetExpectedBuildId();
    if (!build_id.IsEmpty()) {
      // Try /proc/kallsyms only when asked to do so, or when build id matches.
      // Otherwise, it is likely to use /proc/kallsyms on host for perf.data recorded on device.
      bool can_read_kallsyms = true;
      if (!build_id.IsEmpty()) {
        BuildId real_build_id;
        if (!GetKernelBuildId(&real_build_id) || build_id != real_build_id) {
          LOG(DEBUG) << "failed to read symbols from /proc/kallsyms: Build id mismatch";
          can_read_kallsyms = false;
        }
      }
      if (can_read_kallsyms) {
        std::string kallsyms;
        if (LoadKernelSymbols(&kallsyms)) {
          ReadSymbolsFromKallsyms(kallsyms, symbols);
        }
      }
    }
  }
#endif  // defined(__linux__)

  uint64_t GetKernelStartAddr() {
    if (!kernel_start_addr_) {
      ParseKernelStartAddr();
    }
    return kernel_start_addr_.value();
  }

  uint64_t GetKernelStartOffset() {
    if (!kernel_start_file_offset_) {
      ParseKernelStartAddr();
    }
    return kernel_start_file_offset_.value();
  }

  void ParseKernelStartAddr() {
    kernel_start_addr_ = 0;
    kernel_start_file_offset_ = 0;
    ElfStatus status;
    if (auto elf = ElfFile::Open(GetDebugFilePath(), &status); elf) {
      for (const auto& section : elf->GetSectionHeader()) {
        if (section.name == ".text") {
          kernel_start_addr_ = section.vaddr;
          kernel_start_file_offset_ = section.file_offset;
          break;
        }
      }
    }
  }

  bool fix_kernel_address_randomization_ = false;
  std::optional<uint64_t> kernel_start_addr_;
  std::optional<uint64_t> kernel_start_file_offset_;
};

class KernelModuleDso : public Dso {
 public:
  KernelModuleDso(const std::string& path, uint64_t memory_start, uint64_t memory_end,
                  Dso* kernel_dso)
      : Dso(DSO_KERNEL_MODULE, path),
        memory_start_(memory_start),
        memory_end_(memory_end),
        kernel_dso_(kernel_dso) {}

  void SetMinExecutableVaddr(uint64_t min_vaddr, uint64_t memory_offset) override {
    min_vaddr_ = min_vaddr;
    memory_offset_of_min_vaddr_ = memory_offset;
  }

  void GetMinExecutableVaddr(uint64_t* min_vaddr, uint64_t* memory_offset) override {
    if (!min_vaddr_) {
      CalculateMinVaddr();
    }
    *min_vaddr = min_vaddr_.value();
    *memory_offset = memory_offset_of_min_vaddr_.value();
  }

  uint64_t IpToVaddrInFile(uint64_t ip, uint64_t map_start, uint64_t) override {
    uint64_t min_vaddr;
    uint64_t memory_offset;
    GetMinExecutableVaddr(&min_vaddr, &memory_offset);
    return ip - map_start - memory_offset + min_vaddr;
  }

 protected:
  std::string FindDebugFilePath() const override {
    BuildId build_id = GetExpectedBuildId();
    return debug_elf_file_finder_.FindDebugFile(path_, false, build_id);
  }

  std::vector<Symbol> LoadSymbolsImpl() override {
    std::vector<Symbol> symbols;
    BuildId build_id = GetExpectedBuildId();
    auto symbol_callback = [&](const ElfFileSymbol& symbol) {
      // We only know how to map ip addrs to symbols in text section.
      if (symbol.is_in_text_section && (symbol.is_label || symbol.is_func)) {
        symbols.emplace_back(symbol.name, symbol.vaddr, symbol.len);
      }
    };
    ElfStatus status;
    auto elf = ElfFile::Open(GetDebugFilePath(), &build_id, &status);
    if (elf) {
      status = elf->ParseSymbols(symbol_callback);
    }
    // Don't warn when a kernel module is missing. As a backup, we read symbols from /proc/kallsyms.
    ReportReadElfSymbolResult(status, path_, GetDebugFilePath(), android::base::DEBUG);
    SortAndFixSymbols(symbols);
    return symbols;
  }

 private:
  void CalculateMinVaddr() {
    min_vaddr_ = 0;
    memory_offset_of_min_vaddr_ = 0;

    // min_vaddr and memory_offset are used to convert an ip addr of a kernel module to its
    // vaddr_in_file, as shown in IpToVaddrInFile(). When the kernel loads a kernel module, it
    // puts ALLOC sections (like .plt, .text.ftrace_trampoline, .text) in memory in order. The
    // text section may not be at the start of the module memory. To do address conversion, we
    // need to know its relative position in the module memory. There are two ways:
    // 1. Read the kernel module file to calculate the relative position of .text section. It
    // is relatively complex and depends on both PLT entries and the kernel version.
    // 2. Find a module symbol in .text section, get its address in memory from /proc/kallsyms,
    // and its vaddr_in_file from the kernel module file. Then other symbols in .text section can
    // be mapped in the same way. Below we use the second method.

    if (!IsRegularFile(GetDebugFilePath())) {
      return;
    }

    // 1. Select a module symbol in /proc/kallsyms.
    kernel_dso_->LoadSymbols();
    const auto& kernel_symbols = kernel_dso_->GetSymbols();
    auto it = std::lower_bound(kernel_symbols.begin(), kernel_symbols.end(), memory_start_,
                               CompareSymbolToAddr);
    const Symbol* kernel_symbol = nullptr;
    while (it != kernel_symbols.end() && it->addr < memory_end_) {
      if (strlen(it->Name()) > 0 && it->Name()[0] != '$') {
        kernel_symbol = &*it;
        break;
      }
      ++it;
    }
    if (kernel_symbol == nullptr) {
      return;
    }

    // 2. Find the symbol in .ko file.
    std::string symbol_name = kernel_symbol->Name();
    if (auto pos = symbol_name.rfind(' '); pos != std::string::npos) {
      symbol_name.resize(pos);
    }
    LoadSymbols();
    for (const auto& symbol : symbols_) {
      if (symbol_name == symbol.Name()) {
        min_vaddr_ = symbol.addr;
        memory_offset_of_min_vaddr_ = kernel_symbol->addr - memory_start_;
        return;
      }
    }
  }

  uint64_t memory_start_;
  uint64_t memory_end_;
  Dso* kernel_dso_;
  std::optional<uint64_t> min_vaddr_;
  std::optional<uint64_t> memory_offset_of_min_vaddr_;
};

class SymbolMapFileDso : public Dso {
 public:
  SymbolMapFileDso(const std::string& path) : Dso(DSO_SYMBOL_MAP_FILE, path) {}

  uint64_t IpToVaddrInFile(uint64_t ip, uint64_t, uint64_t) override { return ip; }

 protected:
  std::vector<Symbol> LoadSymbolsImpl() override { return {}; }
};

class UnknownDso : public Dso {
 public:
  UnknownDso(const std::string& path) : Dso(DSO_UNKNOWN_FILE, path) {}

  uint64_t IpToVaddrInFile(uint64_t ip, uint64_t, uint64_t) override { return ip; }

 protected:
  std::vector<Symbol> LoadSymbolsImpl() override { return std::vector<Symbol>(); }
};

std::unique_ptr<Dso> Dso::CreateDso(DsoType dso_type, const std::string& dso_path,
                                    bool force_64bit) {
  switch (dso_type) {
    case DSO_ELF_FILE:
      return std::unique_ptr<Dso>(new ElfDso(dso_path, force_64bit));
    case DSO_KERNEL:
      return std::unique_ptr<Dso>(new KernelDso(dso_path));
    case DSO_DEX_FILE:
      return std::unique_ptr<Dso>(new DexFileDso(dso_path));
    case DSO_SYMBOL_MAP_FILE:
      return std::unique_ptr<Dso>(new SymbolMapFileDso(dso_path));
    case DSO_UNKNOWN_FILE:
      return std::unique_ptr<Dso>(new UnknownDso(dso_path));
    default:
      LOG(ERROR) << "Unexpected dso_type " << static_cast<int>(dso_type);
      return nullptr;
  }
}

std::unique_ptr<Dso> Dso::CreateDsoWithBuildId(DsoType dso_type, const std::string& dso_path,
                                               BuildId& build_id) {
  std::unique_ptr<Dso> dso;
  switch (dso_type) {
    case DSO_ELF_FILE:
      dso.reset(new ElfDso(dso_path, false));
      break;
    case DSO_KERNEL:
      dso.reset(new KernelDso(dso_path));
      break;
    case DSO_KERNEL_MODULE:
      dso.reset(new KernelModuleDso(dso_path, 0, 0, nullptr));
      break;
    default:
      LOG(ERROR) << "Unexpected dso_type " << static_cast<int>(dso_type);
      return nullptr;
  }
  dso->debug_file_path_ = debug_elf_file_finder_.FindDebugFile(dso_path, false, build_id);
  return dso;
}

std::unique_ptr<Dso> Dso::CreateKernelModuleDso(const std::string& dso_path, uint64_t memory_start,
                                                uint64_t memory_end, Dso* kernel_dso) {
  return std::unique_ptr<Dso>(new KernelModuleDso(dso_path, memory_start, memory_end, kernel_dso));
}

const char* DsoTypeToString(DsoType dso_type) {
  switch (dso_type) {
    case DSO_KERNEL:
      return "dso_kernel";
    case DSO_KERNEL_MODULE:
      return "dso_kernel_module";
    case DSO_ELF_FILE:
      return "dso_elf_file";
    case DSO_DEX_FILE:
      return "dso_dex_file";
    case DSO_SYMBOL_MAP_FILE:
      return "dso_symbol_map_file";
    default:
      return "unknown";
  }
}

bool GetBuildIdFromDsoPath(const std::string& dso_path, BuildId* build_id) {
  ElfStatus status;
  auto elf = ElfFile::Open(dso_path, &status);
  if (status == ElfStatus::NO_ERROR && elf->GetBuildId(build_id) == ElfStatus::NO_ERROR) {
    return true;
  }
  return false;
}

bool GetBuildId(const Dso& dso, BuildId& build_id) {
  if (dso.type() == DSO_KERNEL) {
    if (GetKernelBuildId(&build_id)) {
      return true;
    }
  } else if (dso.type() == DSO_KERNEL_MODULE) {
    bool has_build_id = false;
    if (android::base::EndsWith(dso.Path(), ".ko")) {
      return GetBuildIdFromDsoPath(dso.Path(), &build_id);
    }
    if (const std::string& path = dso.Path();
        path.size() > 2 && path[0] == '[' && path.back() == ']') {
      // For kernel modules that we can't find the corresponding file, read build id from /sysfs.
      return GetModuleBuildId(path.substr(1, path.size() - 2), &build_id);
    }
  } else if (dso.type() == DSO_ELF_FILE) {
    if (dso.Path() == DEFAULT_EXECNAME_FOR_THREAD_MMAP || dso.IsForJavaMethod()) {
      return false;
    }
    if (GetBuildIdFromDsoPath(dso.Path(), &build_id)) {
      return true;
    }
  }
  return false;
}

}  // namespace simpleperf
