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

#include "thread_tree.h"

#include <inttypes.h>

#include <limits>

#include <android-base/logging.h>
#include <android-base/stringprintf.h>
#include <android-base/strings.h>

#include "perf_event.h"
#include "record.h"
#include "record_file.h"
#include "utils.h"

namespace simpleperf {
namespace {

// Real map file path depends on where the process can create files.
// For example, app can create files only in its data directory.
// Use normalized name inherited from pid instead.
std::string GetSymbolMapDsoName(int pid) {
  return android::base::StringPrintf("perf-%d.map", pid);
}

}  // namespace

void ThreadTree::SetThreadName(int pid, int tid, const std::string& comm) {
  ThreadEntry* thread = FindThreadOrNew(pid, tid);
  if (comm != thread->comm) {
    thread_comm_storage_.push_back(std::unique_ptr<std::string>(new std::string(comm)));
    thread->comm = thread_comm_storage_.back()->c_str();
  }
}

bool ThreadTree::ForkThread(int pid, int tid, int ppid, int ptid) {
  // Check thread ID.
  if (tid == ptid) {
    return false;
  }
  // Check thread group ID (pid here) as in https://linux.die.net/man/2/clone2.
  if (pid != tid && pid != ppid) {
    return false;
  }
  ThreadEntry* parent = FindThreadOrNew(ppid, ptid);
  ThreadEntry* child = FindThreadOrNew(pid, tid);
  child->comm = parent->comm;
  if (pid != ppid) {
    // Copy maps from parent process.
    if (child->maps->maps.empty()) {
      *child->maps = *parent->maps;
    } else {
      CHECK_NE(child->maps, parent->maps);
      for (auto& pair : parent->maps->maps) {
        InsertMap(*child->maps, *pair.second);
      }
    }
  }
  return true;
}

ThreadEntry* ThreadTree::FindThread(int tid) const {
  if (auto it = thread_tree_.find(tid); it != thread_tree_.end()) {
    return it->second.get();
  }
  return nullptr;
}

ThreadEntry* ThreadTree::FindThreadOrNew(int pid, int tid) {
  auto it = thread_tree_.find(tid);
  if (it != thread_tree_.end() && pid == it->second.get()->pid) {
    return it->second.get();
  }
  if (it != thread_tree_.end()) {
    ExitThread(it->second.get()->pid, tid);
  }
  return CreateThread(pid, tid);
}

ThreadEntry* ThreadTree::CreateThread(int pid, int tid) {
  const char* comm;
  std::shared_ptr<MapSet> maps;
  if (pid == tid) {
    comm = "unknown";
    maps.reset(new MapSet);
  } else {
    // Share maps among threads in the same thread group.
    ThreadEntry* process = FindThreadOrNew(pid, pid);
    comm = process->comm;
    maps = process->maps;
  }
  ThreadEntry* thread = new ThreadEntry{
      pid,
      tid,
      comm,
      maps,
  };
  auto pair = thread_tree_.insert(std::make_pair(tid, std::unique_ptr<ThreadEntry>(thread)));
  CHECK(pair.second);
  if (pid == tid) {
    // If there is a symbol map dso for the process, add maps for the symbols.
    auto name = GetSymbolMapDsoName(pid);
    auto it = user_dso_tree_.find(name);
    if (it != user_dso_tree_.end()) {
      AddThreadMapsForDsoSymbols(thread, it->second.get());
    }
  }
  return thread;
}

void ThreadTree::ExitThread(int pid, int tid) {
  auto it = thread_tree_.find(tid);
  if (it != thread_tree_.end() && pid == it->second.get()->pid) {
    thread_tree_.erase(it);
  }
}

void ThreadTree::AddKernelMap(uint64_t start_addr, uint64_t len, uint64_t pgoff,
                              const std::string& filename) {
  // kernel map len can be 0 when record command is not run in supervisor mode.
  if (len == 0) {
    return;
  }
  Dso* dso;
  if (android::base::StartsWith(filename, DEFAULT_KERNEL_MMAP_NAME) ||
      android::base::StartsWith(filename, DEFAULT_KERNEL_BPF_MMAP_NAME)) {
    dso = FindKernelDsoOrNew();
  } else {
    dso = FindKernelModuleDsoOrNew(filename, start_addr, start_addr + len);
  }
  InsertMap(kernel_maps_, MapEntry(start_addr, len, pgoff, dso, true));
}

Dso* ThreadTree::FindKernelDsoOrNew() {
  if (!kernel_dso_) {
    kernel_dso_ = Dso::CreateDso(DSO_KERNEL, DEFAULT_KERNEL_MMAP_NAME);
  }
  return kernel_dso_.get();
}

Dso* ThreadTree::FindKernelModuleDsoOrNew(const std::string& filename, uint64_t memory_start,
                                          uint64_t memory_end) {
  auto it = module_dso_tree_.find(filename);
  if (it == module_dso_tree_.end()) {
    module_dso_tree_[filename] =
        Dso::CreateKernelModuleDso(filename, memory_start, memory_end, FindKernelDsoOrNew());
    it = module_dso_tree_.find(filename);
  }
  return it->second.get();
}

void ThreadTree::AddThreadMap(int pid, int tid, uint64_t start_addr, uint64_t len, uint64_t pgoff,
                              const std::string& filename, uint32_t flags) {
  ThreadEntry* thread = FindThreadOrNew(pid, tid);
  Dso* dso = FindUserDsoOrNew(filename, start_addr);
  CHECK(dso != nullptr);
  InsertMap(*thread->maps, MapEntry(start_addr, len, pgoff, dso, false, flags));
}

void ThreadTree::AddThreadMapsForDsoSymbols(ThreadEntry* thread, Dso* dso) {
  const uint64_t page_size = GetPageSize();

  auto maps = thread->maps;

  uint64_t map_start = 0;
  uint64_t map_end = 0;

  // Dso symbols are sorted by address. Walk and calculate containing pages.
  for (const auto& sym : dso->GetSymbols()) {
    uint64_t sym_map_start = AlignDown(sym.addr, page_size);
    uint64_t sym_map_end = Align(sym.addr + sym.len, page_size);

    if (map_end < sym_map_start) {
      if (map_start < map_end) {
        InsertMap(*maps, MapEntry(map_start, map_end - map_start, map_start, dso, false, 0));
      }
      map_start = sym_map_start;
    }
    if (map_end < sym_map_end) {
      map_end = sym_map_end;
    }
  }

  if (map_start < map_end) {
    InsertMap(*maps, MapEntry(map_start, map_end - map_start, map_start, dso, false, 0));
  }
}

Dso* ThreadTree::FindUserDsoOrNew(const std::string& filename, uint64_t start_addr,
                                  DsoType dso_type) {
  auto it = user_dso_tree_.find(filename);
  if (it == user_dso_tree_.end()) {
    bool force_64bit = start_addr > UINT_MAX;
    std::unique_ptr<Dso> dso = Dso::CreateDso(dso_type, filename, force_64bit);
    if (!dso) {
      return nullptr;
    }
    auto pair = user_dso_tree_.insert(std::make_pair(filename, std::move(dso)));
    CHECK(pair.second);
    it = pair.first;
  }
  return it->second.get();
}

void ThreadTree::AddSymbolsForProcess(int pid, std::vector<Symbol>* symbols) {
  auto name = GetSymbolMapDsoName(pid);

  auto dso = FindUserDsoOrNew(name, 0, DSO_SYMBOL_MAP_FILE);
  dso->SetSymbols(symbols);

  auto thread = FindThreadOrNew(pid, pid);
  AddThreadMapsForDsoSymbols(thread, dso);
}

const MapEntry* ThreadTree::AllocateMap(const MapEntry& entry) {
  map_storage_.emplace_back(new MapEntry(entry));
  return map_storage_.back().get();
}

static MapEntry RemoveFirstPartOfMapEntry(const MapEntry* entry, uint64_t new_start_addr) {
  MapEntry result = *entry;
  result.start_addr = new_start_addr;
  result.len -= result.start_addr - entry->start_addr;
  result.pgoff += result.start_addr - entry->start_addr;
  return result;
}

static MapEntry RemoveSecondPartOfMapEntry(const MapEntry* entry, uint64_t new_len) {
  MapEntry result = *entry;
  result.len = new_len;
  return result;
}

// Insert a new map entry in a MapSet. If some existing map entries overlap the new map entry,
// then remove the overlapped parts.
void ThreadTree::InsertMap(MapSet& maps, const MapEntry& entry) {
  std::map<uint64_t, const MapEntry*>& map = maps.maps;
  auto it = map.lower_bound(entry.start_addr);
  // Remove overlapped entry with start_addr < entry.start_addr.
  if (it != map.begin()) {
    auto it2 = it;
    --it2;
    if (it2->second->get_end_addr() > entry.get_end_addr()) {
      map.emplace(entry.get_end_addr(),
                  AllocateMap(RemoveFirstPartOfMapEntry(it2->second, entry.get_end_addr())));
    }
    if (it2->second->get_end_addr() > entry.start_addr) {
      it2->second =
          AllocateMap(RemoveSecondPartOfMapEntry(it2->second, entry.start_addr - it2->first));
    }
  }
  // Remove overlapped entries with start_addr >= entry.start_addr.
  while (it != map.end() && it->second->get_end_addr() <= entry.get_end_addr()) {
    it = map.erase(it);
  }
  if (it != map.end() && it->second->start_addr < entry.get_end_addr()) {
    map.emplace(entry.get_end_addr(),
                AllocateMap(RemoveFirstPartOfMapEntry(it->second, entry.get_end_addr())));
    map.erase(it);
  }
  // Insert the new entry.
  map.emplace(entry.start_addr, AllocateMap(entry));
  maps.version++;
}

const MapEntry* MapSet::FindMapByAddr(uint64_t addr) const {
  auto it = maps.upper_bound(addr);
  if (it != maps.begin()) {
    --it;
    if (it->second->get_end_addr() > addr) {
      return it->second;
    }
  }
  return nullptr;
}

const MapEntry* ThreadTree::FindMap(const ThreadEntry* thread, uint64_t ip, bool in_kernel) {
  const MapEntry* result = nullptr;
  if (!in_kernel) {
    result = thread->maps->FindMapByAddr(ip);
  } else {
    result = kernel_maps_.FindMapByAddr(ip);
  }
  return result != nullptr ? result : &unknown_map_;
}

const MapEntry* ThreadTree::FindMap(const ThreadEntry* thread, uint64_t ip) {
  const MapEntry* result = thread->maps->FindMapByAddr(ip);
  if (result != nullptr) {
    return result;
  }
  result = kernel_maps_.FindMapByAddr(ip);
  return result != nullptr ? result : &unknown_map_;
}

const Symbol* ThreadTree::FindSymbol(const MapEntry* map, uint64_t ip, uint64_t* pvaddr_in_file,
                                     Dso** pdso) {
  uint64_t vaddr_in_file = 0;
  const Symbol* symbol = nullptr;
  Dso* dso = map->dso;
  if (map->flags & map_flags::PROT_JIT_SYMFILE_MAP) {
    vaddr_in_file = ip;
  } else {
    vaddr_in_file = dso->IpToVaddrInFile(ip, map->start_addr, map->pgoff);
  }
  symbol = dso->FindSymbol(vaddr_in_file);
  if (symbol == nullptr && dso->type() == DSO_KERNEL_MODULE) {
    // If the ip address hits the vmlinux, or hits a kernel module, but we can't find its symbol
    // in the kernel module file, then find its symbol in /proc/kallsyms or vmlinux.
    vaddr_in_file = ip;
    dso = FindKernelDsoOrNew();
    symbol = dso->FindSymbol(vaddr_in_file);
  }

  if (symbol == nullptr) {
    if (show_ip_for_unknown_symbol_) {
      std::string name = android::base::StringPrintf("%s%s[+%" PRIx64 "]",
                                                     (show_mark_for_unknown_symbol_ ? "*" : ""),
                                                     dso->FileName().c_str(), vaddr_in_file);
      dso->AddUnknownSymbol(vaddr_in_file, name);
      symbol = dso->FindSymbol(vaddr_in_file);
      CHECK(symbol != nullptr);
    } else {
      symbol = &unknown_symbol_;
    }
  }
  if (pvaddr_in_file != nullptr) {
    *pvaddr_in_file = vaddr_in_file;
  }
  if (pdso != nullptr) {
    *pdso = dso;
  }
  return symbol;
}

const Symbol* ThreadTree::FindKernelSymbol(uint64_t ip) {
  const MapEntry* map = FindMap(nullptr, ip, true);
  return FindSymbol(map, ip, nullptr);
}

void ThreadTree::ClearThreadAndMap() {
  thread_tree_.clear();
  thread_comm_storage_.clear();
  kernel_maps_.maps.clear();
  map_storage_.clear();
}

bool ThreadTree::AddDsoInfo(FileFeature& file) {
  DsoType dso_type = file.type;
  Dso* dso = nullptr;
  if (dso_type == DSO_KERNEL) {
    dso = FindKernelDsoOrNew();
  } else if (dso_type == DSO_KERNEL_MODULE) {
    dso = FindKernelModuleDsoOrNew(file.path, 0, 0);
  } else {
    dso = FindUserDsoOrNew(file.path, 0, dso_type);
  }
  if (!dso) {
    return false;
  }
  dso->SetMinExecutableVaddr(file.min_vaddr, file.file_offset_of_min_vaddr);
  dso->SetSymbols(&file.symbols);
  for (uint64_t offset : file.dex_file_offsets) {
    dso->AddDexFileOffset(offset);
  }
  return true;
}

void ThreadTree::AddDexFileOffset(const std::string& file_path, uint64_t dex_file_offset) {
  Dso* dso = FindUserDsoOrNew(file_path, 0, DSO_DEX_FILE);
  dso->AddDexFileOffset(dex_file_offset);
}

void ThreadTree::Update(const Record& record) {
  if (record.type() == PERF_RECORD_MMAP) {
    const MmapRecord& r = *static_cast<const MmapRecord*>(&record);
    if (r.InKernel()) {
      AddKernelMap(r.data->addr, r.data->len, r.data->pgoff, r.filename);
    } else {
      AddThreadMap(r.data->pid, r.data->tid, r.data->addr, r.data->len, r.data->pgoff, r.filename);
    }
  } else if (record.type() == PERF_RECORD_MMAP2) {
    const Mmap2Record& r = *static_cast<const Mmap2Record*>(&record);
    if (r.InKernel()) {
      AddKernelMap(r.data->addr, r.data->len, r.data->pgoff, r.filename);
    } else {
      std::string filename =
          (r.filename == DEFAULT_EXECNAME_FOR_THREAD_MMAP) ? "[unknown]" : r.filename;
      AddThreadMap(r.data->pid, r.data->tid, r.data->addr, r.data->len, r.data->pgoff, filename,
                   r.data->prot);
    }
  } else if (record.type() == PERF_RECORD_COMM) {
    const CommRecord& r = *static_cast<const CommRecord*>(&record);
    SetThreadName(r.data->pid, r.data->tid, r.comm);
  } else if (record.type() == PERF_RECORD_FORK) {
    const ForkRecord& r = *static_cast<const ForkRecord*>(&record);
    ForkThread(r.data->pid, r.data->tid, r.data->ppid, r.data->ptid);
  } else if (record.type() == PERF_RECORD_EXIT) {
    if (!disable_thread_exit_records_) {
      const ExitRecord& r = *static_cast<const ExitRecord*>(&record);
      ExitThread(r.data->pid, r.data->tid);
    }
  } else if (record.type() == SIMPLE_PERF_RECORD_KERNEL_SYMBOL) {
    const auto& r = *static_cast<const KernelSymbolRecord*>(&record);
    Dso::SetKallsyms(std::string(r.kallsyms, r.kallsyms_size));
  }
}

std::vector<Dso*> ThreadTree::GetAllDsos() const {
  std::vector<Dso*> result;
  if (kernel_dso_) {
    result.push_back(kernel_dso_.get());
  }
  for (auto& p : module_dso_tree_) {
    result.push_back(p.second.get());
  }
  for (auto& p : user_dso_tree_) {
    result.push_back(p.second.get());
  }
  result.push_back(unknown_dso_.get());
  return result;
}

}  // namespace simpleperf
