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

#ifndef SIMPLE_PERF_JIT_DEBUG_READER_H_
#define SIMPLE_PERF_JIT_DEBUG_READER_H_

#include <unistd.h>

#include <functional>
#include <memory>
#include <queue>
#include <stack>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include <android-base/file.h>
#include <android-base/logging.h>

#include "IOEventLoop.h"
#include "environment.h"
#include "record.h"

namespace simpleperf {

inline constexpr const char* kJITAppCacheFile = "jit_app_cache";
inline constexpr const char* kJITZygoteCacheFile = "jit_zygote_cache";
inline constexpr const char* kDexFileInMemoryPrefix = "dexfile_in_memory";

namespace JITDebugReader_impl {

enum class DescriptorType {
  kDEX,
  kJIT,
};

// An arch-independent representation of JIT/dex debug descriptor.
struct Descriptor {
  DescriptorType type;
  int version = 0;
  uint32_t action_seqlock = 0;    // incremented before and after any modification
  uint64_t action_timestamp = 0;  // CLOCK_MONOTONIC time of last action
  uint64_t first_entry_addr = 0;
};

// An arch-independent representation of JIT/dex code entry.
struct CodeEntry {
  uint64_t addr;
  uint64_t symfile_addr;
  uint64_t symfile_size;
  uint64_t timestamp;  // CLOCK_MONOTONIC time of last action
};

struct Process {
  pid_t pid = -1;
  bool initialized = false;
  bool died = false;
  bool is_64bit = false;
  // remote addr of jit descriptor
  uint64_t jit_descriptor_addr = 0;
  // remote addr of dex descriptor
  uint64_t dex_descriptor_addr = 0;

  // The state we know about the remote jit debug descriptor.
  Descriptor last_jit_descriptor;
  // The state we know about the remote dex debug descriptor.
  Descriptor last_dex_descriptor;

  // memory space for /memfd:jit-zygote-cache
  std::vector<std::pair<uint64_t, uint64_t>> jit_zygote_cache_ranges_;
};

}  // namespace JITDebugReader_impl

// JITDebugInfo represents the debug info of a JITed Java method or a dex file.
struct JITDebugInfo {
  enum {
    JIT_DEBUG_JIT_CODE,
    JIT_DEBUG_DEX_FILE,
  } type;
  pid_t pid;           // Process of the debug info
  uint64_t timestamp;  // Monotonic timestamp for the creation of the debug info

  union {
    struct {
      uint64_t jit_code_addr;  // The start addr of the JITed code
      uint64_t jit_code_len;   // The end addr of the JITed code
    };
    uint64_t dex_file_offset;  // The offset of the dex file in the file containing it
  };
  // For JITed code, it is the path of a temporary ELF file storing its debug info.
  // For dex file, it is the path of the file containing the dex file.
  std::string file_path;
  uint64_t file_offset;

  // dex_file_map may be a dex file extracted in memory. On Android >= Q, ART may extract dex files
  // in apk files directly into memory, and name it using prctl(). The kernel doesn't generate a
  // new mmap record for it. So we need to dump it manually.
  // Or dex_file_map may be a dex file created in memory. In that case, symbols are read from the
  // dex file.
  std::shared_ptr<ThreadMmap> dex_file_map;
  std::vector<Symbol> symbols;

  JITDebugInfo(pid_t pid, uint64_t timestamp, uint64_t jit_code_addr, uint64_t jit_code_len,
               const std::string& file_path, uint64_t file_offset)
      : type(JIT_DEBUG_JIT_CODE),
        pid(pid),
        timestamp(timestamp),
        jit_code_addr(jit_code_addr),
        jit_code_len(jit_code_len),
        file_path(file_path),
        file_offset(file_offset) {}

  JITDebugInfo(pid_t pid, uint64_t timestamp, uint64_t dex_file_offset,
               const std::string& file_path, const std::shared_ptr<ThreadMmap>& dex_file_map,
               std::vector<Symbol> symbols)
      : type(JIT_DEBUG_DEX_FILE),
        pid(pid),
        timestamp(timestamp),
        dex_file_offset(dex_file_offset),
        file_path(file_path),
        file_offset(0),
        dex_file_map(dex_file_map),
        symbols(std::move(symbols)) {}

  bool operator>(const JITDebugInfo& other) const { return timestamp > other.timestamp; }
};

class TempSymFile;

// JITDebugReader reads debug info of JIT code and dex files of processes using ART. The
// corresponding debug interface in ART is at art/runtime/jit/debugger_interface.cc.
class JITDebugReader {
 public:
  using Descriptor = JITDebugReader_impl::Descriptor;
  using CodeEntry = JITDebugReader_impl::CodeEntry;
  using Process = JITDebugReader_impl::Process;

  enum class SymFileOption {
    kDropSymFiles,  // JIT symfiles are dropped after recording.
    kKeepSymFiles,  // JIT symfiles are kept after recording, usually for debug unwinding.
  };

  enum class SyncOption {
    kNoSync,           // Don't sync debug info with records.
    kSyncWithRecords,  // Sync debug info with records based on monotonic timestamp.
  };

  // symfile_prefix: JITDebugReader creates temporary file to store symfiles for JIT code. Add this
  //                 prefix to avoid conflicts.
  JITDebugReader(const std::string& symfile_prefix, SymFileOption symfile_option,
                 SyncOption sync_option);

  ~JITDebugReader();

  bool SyncWithRecords() const { return sync_option_ == SyncOption::kSyncWithRecords; }

  typedef std::function<bool(std::vector<JITDebugInfo>, bool)> debug_info_callback_t;
  bool RegisterDebugInfoCallback(IOEventLoop* loop, const debug_info_callback_t& callback);

  // There are two ways to select which processes to monitor. One is using MonitorProcess(), the
  // other is finding all processes having libart.so using records.
  bool MonitorProcess(pid_t pid);
  bool UpdateRecord(const Record* record);

  // Read new debug info from all monitored processes.
  bool ReadAllProcesses();
  // Read new debug info from one process.
  bool ReadProcess(pid_t pid);

  // Flush all debug info registered before timestamp.
  bool FlushDebugInfo(uint64_t timestamp);

  static bool IsPathInJITSymFile(const std::string& path) {
    return path.find(std::string("_") + kJITAppCacheFile + ":") != path.npos ||
           path.find(std::string("_") + kJITZygoteCacheFile + ":") != path.npos;
  }

  // exported for testing
  void ReadDexFileDebugInfo(Process& process, const std::vector<CodeEntry>& dex_entries,
                            std::vector<JITDebugInfo>* debug_info);

 private:
  // The location of descriptors in libart.so.
  struct DescriptorsLocation {
    bool is_64bit = false;
    uint64_t jit_descriptor_addr = 0;
    uint64_t dex_descriptor_addr = 0;
  };

  bool ReadProcess(Process& process, std::vector<JITDebugInfo>* debug_info);
  bool ReadDebugInfo(Process& process, Descriptor& new_descriptor,
                     std::vector<JITDebugInfo>* debug_info);
  bool IsDescriptorChanged(Process& process, Descriptor& old_descriptor);
  bool InitializeProcess(Process& process);
  const DescriptorsLocation* GetDescriptorsLocation(const std::string& art_lib_path);
  bool ReadRemoteMem(Process& process, uint64_t remote_addr, uint64_t size, void* data);
  bool ReadDescriptors(Process& process, Descriptor* jit_descriptor, Descriptor* dex_descriptor);
  template <typename DescriptorT>
  bool ReadDescriptorsImpl(Process& process, Descriptor* jit_descriptor,
                           Descriptor* dex_descriptor);
  template <typename DescriptorT>
  bool ParseDescriptor(const DescriptorT& raw_descriptor, Descriptor* descriptor);

  bool ReadNewCodeEntries(Process& process, const Descriptor& descriptor,
                          uint64_t last_action_timestamp, uint32_t read_entry_limit,
                          std::vector<CodeEntry>* new_code_entries);
  template <typename CodeEntryT>
  bool ReadNewCodeEntriesImpl(Process& process, const Descriptor& descriptor,
                              uint64_t last_action_timestamp, uint32_t read_entry_limit,
                              std::vector<CodeEntry>* new_code_entries);

  bool ReadJITCodeDebugInfo(Process& process, const std::vector<CodeEntry>& jit_entries,
                            std::vector<JITDebugInfo>* debug_info);
  TempSymFile* GetTempSymFile(Process& process, const CodeEntry& jit_entry);
  std::vector<Symbol> ReadDexFileSymbolsInMemory(Process& process, uint64_t addr, uint64_t size);
  bool AddDebugInfo(std::vector<JITDebugInfo> debug_info, bool sync_kernel_records);

  const std::string symfile_prefix_;
  SymFileOption symfile_option_;
  SyncOption sync_option_;
  IOEventRef read_event_ = nullptr;
  debug_info_callback_t debug_info_callback_;

  // Keys are pids of processes having libart.so, values show whether a process has been monitored.
  std::unordered_map<pid_t, bool> pids_with_art_lib_;

  // All monitored processes
  std::unordered_map<pid_t, Process> processes_;
  std::unordered_map<std::string, DescriptorsLocation> descriptors_location_cache_;

  std::priority_queue<JITDebugInfo, std::vector<JITDebugInfo>, std::greater<JITDebugInfo>>
      debug_info_q_;

  // temporary files used to store jit symfiles created by the app process and the zygote process.
  std::unique_ptr<TempSymFile> app_symfile_;
  std::unique_ptr<TempSymFile> zygote_symfile_;
};

}  // namespace simpleperf

#endif  // SIMPLE_PERF_JIT_DEBUG_READER_H_
