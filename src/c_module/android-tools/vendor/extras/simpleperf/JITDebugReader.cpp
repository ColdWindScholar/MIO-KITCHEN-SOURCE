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

#include "JITDebugReader.h"

#include <inttypes.h>
#include <stdio.h>
#include <sys/mman.h>
#include <sys/uio.h>
#include <sys/user.h>
#include <unistd.h>

#include <algorithm>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/stringprintf.h>
#include <android-base/strings.h>

#include "JITDebugReader_impl.h"
#include "dso.h"
#include "environment.h"
#include "read_apk.h"
#include "read_dex_file.h"
#include "read_elf.h"
#include "utils.h"

namespace simpleperf {

using namespace JITDebugReader_impl;
using android::base::StartsWith;
using android::base::StringPrintf;

// If the size of a symfile is larger than EXPECTED_MAX_SYMFILE_SIZE, we don't want to read it
// remotely.
static constexpr size_t MAX_JIT_SYMFILE_SIZE = 1 * kMegabyte;

// It takes about 30us-130us on Pixel (depending on the cpu frequency) to check if the descriptors
// have been updated (most time spent in process_vm_preadv). We want to know if the JIT debug info
// changed as soon as possible, while not wasting too much time checking for updates. So use a
// period of 100 ms.
// In system wide profiling, we may need to check JIT debug info changes for many processes, to
// avoid spending all time checking, wait 100 ms between any two checks.
static constexpr size_t kUpdateJITDebugInfoIntervalInMs = 100;

// map name used for jit zygote cache
static const char* kJITZygoteCacheMmapPrefix = "/memfd:jit-zygote-cache";

// Match the format of JITDescriptor in art/runtime/jit/debugger_interface.cc.
template <typename ADDRT>
struct JITDescriptor {
  uint32_t version;
  uint32_t action_flag;
  ADDRT relevant_entry_addr;
  ADDRT first_entry_addr;
  uint8_t magic[8];
  uint32_t flags;
  uint32_t sizeof_descriptor;
  uint32_t sizeof_entry;
  uint32_t action_seqlock;    // incremented before and after any modification
  uint64_t action_timestamp;  // CLOCK_MONOTONIC time of last action

  bool Valid() const;

  int AndroidVersion() const { return magic[7] - '0'; }
};

// Match the format of JITCodeEntry in art/runtime/jit/debugger_interface.cc
// with JITDescriptor.magic == "Android1".
template <typename ADDRT>
struct JITCodeEntry {
  ADDRT next_addr;
  ADDRT prev_addr;
  ADDRT symfile_addr;
  uint64_t symfile_size;
  uint64_t register_timestamp;  // CLOCK_MONOTONIC time of entry registration

  bool Valid() const { return symfile_addr > 0u && symfile_size > 0u; }
};

// Match the format of JITCodeEntry in art/runtime/jit/debugger_interface.cc
// with JITDescriptor.magic == "Android1".
template <typename ADDRT>
struct __attribute__((packed)) PackedJITCodeEntry {
  ADDRT next_addr;
  ADDRT prev_addr;
  ADDRT symfile_addr;
  uint64_t symfile_size;
  uint64_t register_timestamp;

  bool Valid() const { return symfile_addr > 0u && symfile_size > 0u; }
};

// Match the format of JITCodeEntry in art/runtime/jit/debugger_interface.cc
// with JITDescriptor.magic == "Android2".
template <typename ADDRT>
struct JITCodeEntryV2 {
  ADDRT next_addr;
  ADDRT prev_addr;
  ADDRT symfile_addr;
  uint64_t symfile_size;
  uint64_t register_timestamp;  // CLOCK_MONOTONIC time of entry registration
  uint32_t seqlock;             // even value if valid

  bool Valid() const { return (seqlock & 1) == 0; }
};

// Match the format of JITCodeEntry in art/runtime/jit/debugger_interface.cc
// with JITDescriptor.magic == "Android2".
template <typename ADDRT>
struct __attribute__((packed)) PackedJITCodeEntryV2 {
  ADDRT next_addr;
  ADDRT prev_addr;
  ADDRT symfile_addr;
  uint64_t symfile_size;
  uint64_t register_timestamp;
  uint32_t seqlock;

  bool Valid() const { return (seqlock & 1) == 0; }
};

// Match the format of JITCodeEntry in art/runtime/jit/debugger_interface.cc
// with JITDescriptor.magic == "Android2".
template <typename ADDRT>
struct __attribute__((packed)) PaddedJITCodeEntryV2 {
  ADDRT next_addr;
  ADDRT prev_addr;
  ADDRT symfile_addr;
  uint64_t symfile_size;
  uint64_t register_timestamp;
  uint32_t seqlock;
  uint32_t pad;

  bool Valid() const { return (seqlock & 1) == 0; }
};

using JITDescriptor32 = JITDescriptor<uint32_t>;
using JITDescriptor64 = JITDescriptor<uint64_t>;

#if defined(__x86_64__)
// Make sure simpleperf built for i386 and x86_64 see the correct JITCodeEntry layout of i386.
using JITCodeEntry32 = PackedJITCodeEntry<uint32_t>;
using JITCodeEntry32V2 = PackedJITCodeEntryV2<uint32_t>;
#else
using JITCodeEntry32 = JITCodeEntry<uint32_t>;
using JITCodeEntry32V2 = JITCodeEntryV2<uint32_t>;
#endif

using JITCodeEntry64 = JITCodeEntry<uint64_t>;
#if defined(__i386__)
// Make sure simpleperf built for i386 and x86_64 see the correct JITCodeEntry layout of x86_64.
using JITCodeEntry64V2 = PaddedJITCodeEntryV2<uint64_t>;
#else
using JITCodeEntry64V2 = JITCodeEntryV2<uint64_t>;
#endif

template <typename ADDRT>
bool JITDescriptor<ADDRT>::Valid() const {
  const char* magic_str = reinterpret_cast<const char*>(magic);
  if (version != 1 ||
      !(strncmp(magic_str, "Android1", 8) == 0 || strncmp(magic_str, "Android2", 8) == 0)) {
    return false;
  }
  if (sizeof(*this) != sizeof_descriptor) {
    return false;
  }
  if (sizeof(ADDRT) == 4) {
    return sizeof_entry == (AndroidVersion() == 1) ? sizeof(JITCodeEntry32)
                                                   : sizeof(JITCodeEntry32V2);
  }
  return sizeof_entry == (AndroidVersion() == 1) ? sizeof(JITCodeEntry64)
                                                 : sizeof(JITCodeEntry64V2);
}

// We want to support both 64-bit and 32-bit simpleperf when profiling either 64-bit or 32-bit
// apps. So using static_asserts to make sure that simpleperf on arm and aarch64 having the same
// view of structures, and simpleperf on i386 and x86_64 having the same view of structures.
static_assert(sizeof(JITDescriptor32) == 48, "");
static_assert(sizeof(JITDescriptor64) == 56, "");

#if defined(__i386__) or defined(__x86_64__)
static_assert(sizeof(JITCodeEntry32) == 28, "");
static_assert(sizeof(JITCodeEntry32V2) == 32, "");
static_assert(sizeof(JITCodeEntry64) == 40, "");
static_assert(sizeof(JITCodeEntry64V2) == 48, "");
#else
static_assert(sizeof(JITCodeEntry32) == 32, "");
static_assert(sizeof(JITCodeEntry32V2) == 40, "");
static_assert(sizeof(JITCodeEntry64) == 40, "");
static_assert(sizeof(JITCodeEntry64V2) == 48, "");
#endif

JITDebugReader::JITDebugReader(const std::string& symfile_prefix, SymFileOption symfile_option,
                               SyncOption sync_option)
    : symfile_prefix_(symfile_prefix), symfile_option_(symfile_option), sync_option_(sync_option) {}

JITDebugReader::~JITDebugReader() {}

bool JITDebugReader::RegisterDebugInfoCallback(IOEventLoop* loop,
                                               const debug_info_callback_t& callback) {
  debug_info_callback_ = callback;
  read_event_ = loop->AddPeriodicEvent(SecondToTimeval(kUpdateJITDebugInfoIntervalInMs / 1000.0),
                                       [this]() { return ReadAllProcesses(); });
  return (read_event_ != nullptr && IOEventLoop::DisableEvent(read_event_));
}

bool JITDebugReader::MonitorProcess(pid_t pid) {
  if (processes_.find(pid) == processes_.end()) {
    processes_[pid].pid = pid;
    LOG(DEBUG) << "Start monitoring process " << pid;
    if (processes_.size() == 1u) {
      if (!IOEventLoop::EnableEvent(read_event_)) {
        return false;
      }
    }
  }
  return true;
}

static bool IsArtLib(const std::string& filename) {
  return android::base::EndsWith(filename, "libart.so") ||
         android::base::EndsWith(filename, "libartd.so");
}

bool JITDebugReader::UpdateRecord(const Record* record) {
  if (record->type() == PERF_RECORD_MMAP) {
    auto r = static_cast<const MmapRecord*>(record);
    if (IsArtLib(r->filename)) {
      pids_with_art_lib_.emplace(r->data->pid, false);
    }
  } else if (record->type() == PERF_RECORD_MMAP2) {
    auto r = static_cast<const Mmap2Record*>(record);
    if (IsArtLib(r->filename)) {
      pids_with_art_lib_.emplace(r->data->pid, false);
    }
  } else if (record->type() == PERF_RECORD_FORK) {
    auto r = static_cast<const ForkRecord*>(record);
    if (r->data->pid != r->data->ppid &&
        pids_with_art_lib_.find(r->data->ppid) != pids_with_art_lib_.end()) {
      pids_with_art_lib_.emplace(r->data->pid, false);
    }
  } else if (record->type() == PERF_RECORD_SAMPLE) {
    auto r = static_cast<const SampleRecord*>(record);
    auto it = pids_with_art_lib_.find(r->tid_data.pid);
    if (it != pids_with_art_lib_.end() && !it->second) {
      it->second = true;
      if (!MonitorProcess(r->tid_data.pid)) {
        return false;
      }
      return ReadProcess(r->tid_data.pid);
    }
  }
  return FlushDebugInfo(record->Timestamp());
}

bool JITDebugReader::FlushDebugInfo(uint64_t timestamp) {
  if (sync_option_ == SyncOption::kSyncWithRecords) {
    if (!debug_info_q_.empty() && debug_info_q_.top().timestamp < timestamp) {
      std::vector<JITDebugInfo> debug_info;
      while (!debug_info_q_.empty() && debug_info_q_.top().timestamp < timestamp) {
        debug_info.emplace_back(debug_info_q_.top());
        debug_info_q_.pop();
      }
      return debug_info_callback_(debug_info, false);
    }
  }
  return true;
}

bool JITDebugReader::ReadAllProcesses() {
  if (!IOEventLoop::DisableEvent(read_event_)) {
    return false;
  }
  std::vector<JITDebugInfo> debug_info;
  for (auto it = processes_.begin(); it != processes_.end();) {
    Process& process = it->second;
    if (!ReadProcess(process, &debug_info)) {
      return false;
    }
    if (process.died) {
      LOG(DEBUG) << "Stop monitoring process " << process.pid;
      it = processes_.erase(it);
    } else {
      ++it;
    }
  }
  if (!AddDebugInfo(std::move(debug_info), true)) {
    return false;
  }
  if (!processes_.empty()) {
    return IOEventLoop::EnableEvent(read_event_);
  }
  return true;
}

bool JITDebugReader::ReadProcess(pid_t pid) {
  auto it = processes_.find(pid);
  if (it != processes_.end()) {
    std::vector<JITDebugInfo> debug_info;
    return ReadProcess(it->second, &debug_info) && AddDebugInfo(std::move(debug_info), false);
  }
  return true;
}

bool JITDebugReader::ReadProcess(Process& process, std::vector<JITDebugInfo>* debug_info) {
  if (process.died || (!process.initialized && !InitializeProcess(process))) {
    return true;
  }
  // 1. Read descriptors.
  Descriptor jit_descriptor;
  Descriptor dex_descriptor;
  if (!ReadDescriptors(process, &jit_descriptor, &dex_descriptor)) {
    return true;
  }
  // 2. Return if descriptors are not changed.
  if (jit_descriptor.action_seqlock == process.last_jit_descriptor.action_seqlock &&
      dex_descriptor.action_seqlock == process.last_dex_descriptor.action_seqlock) {
    return true;
  }

  // 3. Read new symfiles.
  return ReadDebugInfo(process, jit_descriptor, debug_info) &&
         ReadDebugInfo(process, dex_descriptor, debug_info);
}

bool JITDebugReader::ReadDebugInfo(Process& process, Descriptor& new_descriptor,
                                   std::vector<JITDebugInfo>* debug_info) {
  DescriptorType type = new_descriptor.type;
  Descriptor* old_descriptor =
      (type == DescriptorType::kJIT) ? &process.last_jit_descriptor : &process.last_dex_descriptor;

  bool has_update = new_descriptor.action_seqlock != old_descriptor->action_seqlock &&
                    (new_descriptor.action_seqlock & 1) == 0;
  LOG(DEBUG) << (type == DescriptorType::kJIT ? "JIT" : "Dex") << " symfiles of pid " << process.pid
             << ": old seqlock " << old_descriptor->action_seqlock << ", new seqlock "
             << new_descriptor.action_seqlock;
  if (!has_update) {
    return true;
  }
  std::vector<CodeEntry> new_entries;
  // Adding or removing one code entry will make two increments of action_seqlock. So we should
  // not read more than (seqlock_diff / 2) new entries.
  uint32_t read_entry_limit = (new_descriptor.action_seqlock - old_descriptor->action_seqlock) / 2;
  if (!ReadNewCodeEntries(process, new_descriptor, old_descriptor->action_timestamp,
                          read_entry_limit, &new_entries)) {
    return true;
  }
  // If the descriptor was changed while we were reading new entries, skip reading debug info this
  // time.
  if (IsDescriptorChanged(process, new_descriptor)) {
    return true;
  }
  LOG(DEBUG) << (type == DescriptorType::kJIT ? "JIT" : "Dex") << " symfiles of pid " << process.pid
             << ": read " << new_entries.size() << " new entries";

  if (!new_entries.empty()) {
    if (type == DescriptorType::kJIT) {
      if (!ReadJITCodeDebugInfo(process, new_entries, debug_info)) {
        return false;
      }
    } else {
      ReadDexFileDebugInfo(process, new_entries, debug_info);
    }
  }
  *old_descriptor = new_descriptor;
  return true;
}

bool JITDebugReader::IsDescriptorChanged(Process& process, Descriptor& prev_descriptor) {
  Descriptor tmp_jit_descriptor;
  Descriptor tmp_dex_descriptor;
  if (!ReadDescriptors(process, &tmp_jit_descriptor, &tmp_dex_descriptor)) {
    return true;
  }
  if (prev_descriptor.type == DescriptorType::kJIT) {
    return prev_descriptor.action_seqlock != tmp_jit_descriptor.action_seqlock;
  }
  return prev_descriptor.action_seqlock != tmp_dex_descriptor.action_seqlock;
}

bool JITDebugReader::InitializeProcess(Process& process) {
  // 1. Read map file to find the location of libart.so.
  std::vector<ThreadMmap> thread_mmaps;
  if (!GetThreadMmapsInProcess(process.pid, &thread_mmaps)) {
    process.died = true;
    return false;
  }
  std::string art_lib_path;
  uint64_t min_vaddr_in_memory;
  for (auto& map : thread_mmaps) {
    if ((map.prot & PROT_EXEC) && IsArtLib(map.name)) {
      art_lib_path = map.name;
      min_vaddr_in_memory = map.start_addr;
      break;
    }
  }
  if (art_lib_path.empty()) {
    return false;
  }

  // 2. Read libart.so to find the addresses of __jit_debug_descriptor and __dex_debug_descriptor.
  const DescriptorsLocation* location = GetDescriptorsLocation(art_lib_path);
  if (location == nullptr) {
    return false;
  }
  process.is_64bit = location->is_64bit;
  process.jit_descriptor_addr = location->jit_descriptor_addr + min_vaddr_in_memory;
  process.dex_descriptor_addr = location->dex_descriptor_addr + min_vaddr_in_memory;

  for (auto& map : thread_mmaps) {
    if (StartsWith(map.name, kJITZygoteCacheMmapPrefix)) {
      process.jit_zygote_cache_ranges_.emplace_back(map.start_addr, map.start_addr + map.len);
    }
  }

  process.initialized = true;
  return true;
}

const JITDebugReader::DescriptorsLocation* JITDebugReader::GetDescriptorsLocation(
    const std::string& art_lib_path) {
  auto it = descriptors_location_cache_.find(art_lib_path);
  if (it != descriptors_location_cache_.end()) {
    return it->second.jit_descriptor_addr == 0u ? nullptr : &it->second;
  }
  DescriptorsLocation& location = descriptors_location_cache_[art_lib_path];

  // Read libart.so to find the addresses of __jit_debug_descriptor and __dex_debug_descriptor.
  ElfStatus status;
  auto elf = ElfFile::Open(art_lib_path, &status);
  if (!elf) {
    LOG(ERROR) << "failed to read min_exec_vaddr from " << art_lib_path << ": " << status;
    return nullptr;
  }

  const size_t kPageSize = getpagesize();
  const size_t kPageMask = ~(kPageSize - 1);
  uint64_t file_offset;
  uint64_t min_vaddr_in_file = elf->ReadMinExecutableVaddr(&file_offset);
  // min_vaddr_in_file is the min vaddr of executable segments. It may not be page aligned.
  // And dynamic linker will create map mapping to (segment.p_vaddr & kPageMask).
  uint64_t aligned_segment_vaddr = min_vaddr_in_file & kPageMask;
  const char* jit_str = "__jit_debug_descriptor";
  const char* dex_str = "__dex_debug_descriptor";
  uint64_t jit_addr = 0u;
  uint64_t dex_addr = 0u;

  auto callback = [&](const ElfFileSymbol& symbol) {
    if (symbol.name == jit_str) {
      jit_addr = symbol.vaddr - aligned_segment_vaddr;
    } else if (symbol.name == dex_str) {
      dex_addr = symbol.vaddr - aligned_segment_vaddr;
    }
  };
  elf->ParseDynamicSymbols(callback);
  if (jit_addr == 0u || dex_addr == 0u) {
    return nullptr;
  }
  location.is_64bit = elf->Is64Bit();
  location.jit_descriptor_addr = jit_addr;
  location.dex_descriptor_addr = dex_addr;
  return &location;
}

bool JITDebugReader::ReadRemoteMem(Process& process, uint64_t remote_addr, uint64_t size,
                                   void* data) {
  iovec local_iov;
  local_iov.iov_base = data;
  local_iov.iov_len = size;
  iovec remote_iov;
  remote_iov.iov_base = reinterpret_cast<void*>(static_cast<uintptr_t>(remote_addr));
  remote_iov.iov_len = size;
  ssize_t result = process_vm_readv(process.pid, &local_iov, 1, &remote_iov, 1, 0);
  if (static_cast<size_t>(result) != size) {
    PLOG(DEBUG) << "ReadRemoteMem("
                << " pid " << process.pid << ", addr " << std::hex << remote_addr << ", size "
                << size << ") failed";
    process.died = true;
    return false;
  }
  return true;
}

bool JITDebugReader::ReadDescriptors(Process& process, Descriptor* jit_descriptor,
                                     Descriptor* dex_descriptor) {
  if (process.is_64bit) {
    return ReadDescriptorsImpl<JITDescriptor64>(process, jit_descriptor, dex_descriptor);
  }
  return ReadDescriptorsImpl<JITDescriptor32>(process, jit_descriptor, dex_descriptor);
}

template <typename DescriptorT>
bool JITDebugReader::ReadDescriptorsImpl(Process& process, Descriptor* jit_descriptor,
                                         Descriptor* dex_descriptor) {
  DescriptorT raw_jit_descriptor;
  DescriptorT raw_dex_descriptor;
  iovec local_iovs[2];
  local_iovs[0].iov_base = &raw_jit_descriptor;
  local_iovs[0].iov_len = sizeof(DescriptorT);
  local_iovs[1].iov_base = &raw_dex_descriptor;
  local_iovs[1].iov_len = sizeof(DescriptorT);
  iovec remote_iovs[2];
  remote_iovs[0].iov_base =
      reinterpret_cast<void*>(static_cast<uintptr_t>(process.jit_descriptor_addr));
  remote_iovs[0].iov_len = sizeof(DescriptorT);
  remote_iovs[1].iov_base =
      reinterpret_cast<void*>(static_cast<uintptr_t>(process.dex_descriptor_addr));
  remote_iovs[1].iov_len = sizeof(DescriptorT);
  ssize_t result = process_vm_readv(process.pid, local_iovs, 2, remote_iovs, 2, 0);
  if (static_cast<size_t>(result) != sizeof(DescriptorT) * 2) {
    PLOG(DEBUG) << "ReadDescriptor(pid " << process.pid << ", jit_addr " << std::hex
                << process.jit_descriptor_addr << ", dex_addr " << process.dex_descriptor_addr
                << ") failed";
    process.died = true;
    return false;
  }

  if (!ParseDescriptor(raw_jit_descriptor, jit_descriptor) ||
      !ParseDescriptor(raw_dex_descriptor, dex_descriptor)) {
    return false;
  }
  jit_descriptor->type = DescriptorType::kJIT;
  dex_descriptor->type = DescriptorType::kDEX;
  return true;
}

template <typename DescriptorT>
bool JITDebugReader::ParseDescriptor(const DescriptorT& raw_descriptor, Descriptor* descriptor) {
  if (!raw_descriptor.Valid()) {
    return false;
  }
  descriptor->action_seqlock = raw_descriptor.action_seqlock;
  descriptor->action_timestamp = raw_descriptor.action_timestamp;
  descriptor->first_entry_addr = raw_descriptor.first_entry_addr;
  descriptor->version = raw_descriptor.AndroidVersion();
  return true;
}

// Read new code entries with timestamp > last_action_timestamp.
// Since we don't stop the app process while reading code entries, it is possible we are reading
// broken data. So return false once we detect that the data is broken.
bool JITDebugReader::ReadNewCodeEntries(Process& process, const Descriptor& descriptor,
                                        uint64_t last_action_timestamp, uint32_t read_entry_limit,
                                        std::vector<CodeEntry>* new_code_entries) {
  if (descriptor.version == 1) {
    if (process.is_64bit) {
      return ReadNewCodeEntriesImpl<JITCodeEntry64>(process, descriptor, last_action_timestamp,
                                                    read_entry_limit, new_code_entries);
    }
    return ReadNewCodeEntriesImpl<JITCodeEntry32>(process, descriptor, last_action_timestamp,
                                                  read_entry_limit, new_code_entries);
  }
  if (descriptor.version == 2) {
    if (process.is_64bit) {
      return ReadNewCodeEntriesImpl<JITCodeEntry64V2>(process, descriptor, last_action_timestamp,
                                                      read_entry_limit, new_code_entries);
    }
    return ReadNewCodeEntriesImpl<JITCodeEntry32V2>(process, descriptor, last_action_timestamp,
                                                    read_entry_limit, new_code_entries);
  }
  return false;
}

template <typename CodeEntryT>
bool JITDebugReader::ReadNewCodeEntriesImpl(Process& process, const Descriptor& descriptor,
                                            uint64_t last_action_timestamp,
                                            uint32_t read_entry_limit,
                                            std::vector<CodeEntry>* new_code_entries) {
  uint64_t current_entry_addr = descriptor.first_entry_addr;
  uint64_t prev_entry_addr = 0u;
  std::unordered_set<uint64_t> entry_addr_set;
  for (size_t i = 0u; i < read_entry_limit && current_entry_addr != 0u; ++i) {
    if (entry_addr_set.find(current_entry_addr) != entry_addr_set.end()) {
      // We enter a loop, which means a broken linked list.
      return false;
    }
    CodeEntryT entry;
    if (!ReadRemoteMem(process, current_entry_addr, sizeof(entry), &entry)) {
      return false;
    }
    if (entry.prev_addr != prev_entry_addr || !entry.Valid()) {
      // A broken linked list
      return false;
    }
    if (entry.register_timestamp <= last_action_timestamp) {
      // The linked list has entries with timestamp in decreasing order. So stop searching
      // once we hit an entry with timestamp <= last_action_timestmap.
      break;
    }
    if (entry.symfile_size > 0) {
      CodeEntry code_entry;
      code_entry.addr = current_entry_addr;
      code_entry.symfile_addr = entry.symfile_addr;
      code_entry.symfile_size = entry.symfile_size;
      code_entry.timestamp = entry.register_timestamp;
      new_code_entries->push_back(code_entry);
    }
    entry_addr_set.insert(current_entry_addr);
    prev_entry_addr = current_entry_addr;
    current_entry_addr = entry.next_addr;
  }
  return true;
}

bool JITDebugReader::ReadJITCodeDebugInfo(Process& process,
                                          const std::vector<CodeEntry>& jit_entries,
                                          std::vector<JITDebugInfo>* debug_info) {
  std::vector<char> data;

  for (auto& jit_entry : jit_entries) {
    if (jit_entry.symfile_size > MAX_JIT_SYMFILE_SIZE) {
      continue;
    }
    if (data.size() < jit_entry.symfile_size) {
      data.resize(jit_entry.symfile_size);
    }
    if (!ReadRemoteMem(process, jit_entry.symfile_addr, jit_entry.symfile_size, data.data())) {
      continue;
    }
    if (!IsValidElfFileMagic(data.data(), jit_entry.symfile_size)) {
      continue;
    }
    TempSymFile* symfile = GetTempSymFile(process, jit_entry);
    if (symfile == nullptr) {
      return false;
    }
    uint64_t file_offset = symfile->GetOffset();
    if (!symfile->WriteEntry(data.data(), jit_entry.symfile_size)) {
      return false;
    }

    auto callback = [&](const ElfFileSymbol& symbol) {
      if (symbol.len == 0) {  // Some arm labels can have zero length.
        return;
      }
      // Pass out the location of the symfile for unwinding and symbolization.
      std::string location_in_file =
          StringPrintf(":%" PRIu64 "-%" PRIu64, file_offset, file_offset + jit_entry.symfile_size);
      debug_info->emplace_back(process.pid, jit_entry.timestamp, symbol.vaddr, symbol.len,
                               symfile->GetPath() + location_in_file, file_offset);

      LOG(VERBOSE) << "JITSymbol " << symbol.name << " at [" << std::hex << symbol.vaddr << " - "
                   << (symbol.vaddr + symbol.len) << " with size " << symbol.len << " in "
                   << symfile->GetPath() << location_in_file;
    };
    ElfStatus status;
    auto elf = ElfFile::Open(data.data(), jit_entry.symfile_size, &status);
    if (elf) {
      elf->ParseSymbols(callback);
    }
  }

  if (app_symfile_) {
    app_symfile_->Flush();
  }
  if (zygote_symfile_) {
    zygote_symfile_->Flush();
  }
  return true;
}

TempSymFile* JITDebugReader::GetTempSymFile(Process& process, const CodeEntry& jit_entry) {
  bool is_zygote = false;
  for (const auto& range : process.jit_zygote_cache_ranges_) {
    if (jit_entry.symfile_addr >= range.first && jit_entry.symfile_addr < range.second) {
      is_zygote = true;
      break;
    }
  }
  if (is_zygote) {
    if (!zygote_symfile_) {
      std::string path = symfile_prefix_ + "_" + kJITZygoteCacheFile;
      zygote_symfile_ =
          TempSymFile::Create(std::move(path), symfile_option_ == SymFileOption::kDropSymFiles);
    }
    return zygote_symfile_.get();
  }
  if (!app_symfile_) {
    std::string path = symfile_prefix_ + "_" + kJITAppCacheFile;
    app_symfile_ =
        TempSymFile::Create(std::move(path), symfile_option_ == SymFileOption::kDropSymFiles);
  }
  return app_symfile_.get();
}

void JITDebugReader::ReadDexFileDebugInfo(Process& process,
                                          const std::vector<CodeEntry>& dex_entries,
                                          std::vector<JITDebugInfo>* debug_info) {
  std::vector<ThreadMmap> thread_mmaps;
  if (!GetThreadMmapsInProcess(process.pid, &thread_mmaps)) {
    process.died = true;
    return;
  }
  auto comp = [](const ThreadMmap& map, uint64_t addr) { return map.start_addr <= addr; };
  for (auto& dex_entry : dex_entries) {
    auto it =
        std::lower_bound(thread_mmaps.begin(), thread_mmaps.end(), dex_entry.symfile_addr, comp);
    if (it == thread_mmaps.begin()) {
      continue;
    }
    --it;
    if (it->start_addr + it->len < dex_entry.symfile_addr + dex_entry.symfile_size) {
      continue;
    }
    std::string file_path;
    std::string zip_path;
    std::string entry_path;
    std::shared_ptr<ThreadMmap> dex_file_map;
    std::vector<Symbol> symbols;
    // Offset of dex file in .vdex file or .apk file.
    uint64_t dex_file_offset = dex_entry.symfile_addr - it->start_addr + it->pgoff;
    if (ParseExtractedInMemoryPath(it->name, &zip_path, &entry_path)) {
      file_path = GetUrlInApk(zip_path, entry_path);
      dex_file_map = std::make_shared<ThreadMmap>(*it);
    } else if (IsRegularFile(it->name)) {
      file_path = it->name;
    } else {
      // Read a dex file only existing in memory.
      file_path = StringPrintf("%s_pid_%d_addr_0x%" PRIx64 "-0x%" PRIx64 "", kDexFileInMemoryPrefix,
                               process.pid, dex_entry.symfile_addr,
                               dex_entry.symfile_addr + dex_entry.symfile_size);
      dex_file_map.reset(new ThreadMmap(dex_entry.symfile_addr, dex_entry.symfile_size, 0,
                                        file_path.c_str(), PROT_READ));
      symbols = ReadDexFileSymbolsInMemory(process, dex_entry.symfile_addr, dex_entry.symfile_size);
      dex_file_offset = 0;
    }

    debug_info->emplace_back(process.pid, dex_entry.timestamp, dex_file_offset, file_path,
                             dex_file_map, std::move(symbols));
    LOG(VERBOSE) << "DexFile " << file_path << "+" << std::hex << dex_file_offset << " in map ["
                 << it->start_addr << " - " << (it->start_addr + it->len) << "] with size "
                 << dex_entry.symfile_size;
  }
}

std::vector<Symbol> JITDebugReader::ReadDexFileSymbolsInMemory(Process& process, uint64_t addr,
                                                               uint64_t size) {
  std::vector<Symbol> symbols;
  std::vector<uint8_t> data(size, 0);
  if (!ReadRemoteMem(process, addr, size, data.data())) {
    LOG(DEBUG) << "failed to read dex file in memory for process " << process.pid << ", addr "
               << std::hex << addr << "-" << (addr + size);
    return symbols;
  }

  auto process_symbol = [&](DexFileSymbol* symbol) {
    symbols.emplace_back(symbol->name, symbol->addr, symbol->size);
  };
  if (!ReadSymbolsFromDexFileInMemory(data.data(), data.size(), "dex_file_in_memory", {0},
                                      process_symbol)) {
    LOG(DEBUG) << "failed to parse dex file in memory for process " << process.pid << ", addr "
               << std::hex << addr << "-" << (addr + size);
    return symbols;
  }
  std::sort(symbols.begin(), symbols.end(), Symbol::CompareValueByAddr);
  return symbols;
}

bool JITDebugReader::AddDebugInfo(std::vector<JITDebugInfo> debug_info, bool sync_kernel_records) {
  if (!debug_info.empty()) {
    if (sync_option_ == SyncOption::kSyncWithRecords) {
      for (auto& info : debug_info) {
        debug_info_q_.push(std::move(info));
      }
    } else {
      return debug_info_callback_(std::move(debug_info), sync_kernel_records);
    }
  }
  return true;
}

}  // namespace simpleperf
