/*
 * Copyright (C) 2020 The Android Open Source Project
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

#include "MapRecordReader.h"

#include <stdint.h>
#include <sys/mman.h>
#include <sys/stat.h>

#include <vector>

#include <android-base/strings.h>

#include "environment.h"
#include "thread_tree.h"

namespace simpleperf {

bool MapRecordReader::ReadKernelMaps() {
  KernelMmap kernel_mmap;
  std::vector<KernelMmap> module_mmaps;
  GetKernelAndModuleMmaps(&kernel_mmap, &module_mmaps);

  // Inject an mmap record covering all of kernel's address space. This is used to set up a map for
  // dynamically allocated BPF JIT regions outside [kernel.kallsyms]. Needs to be added first.
  MmapRecord bpf_record(attr_, true, UINT_MAX, 0, 0, std::numeric_limits<uint64_t>::max(), 0,
                        DEFAULT_KERNEL_BPF_MMAP_NAME, event_id_);
  if (!callback_(&bpf_record)) {
    return false;
  }
  MmapRecord mmap_record(attr_, true, UINT_MAX, 0, kernel_mmap.start_addr, kernel_mmap.len, 0,
                         kernel_mmap.filepath, event_id_);
  if (!callback_(&mmap_record)) {
    return false;
  }
  for (const auto& module_mmap : module_mmaps) {
    MmapRecord mmap_record(attr_, true, UINT_MAX, 0, module_mmap.start_addr, module_mmap.len, 0,
                           module_mmap.filepath, event_id_);
    if (!callback_(&mmap_record)) {
      return false;
    }
  }
  return true;
}

bool MapRecordReader::ReadProcessMaps(pid_t pid, uint64_t timestamp) {
  std::vector<pid_t> tids = GetThreadsInProcess(pid);
  return ReadProcessMaps(pid, std::unordered_set<pid_t>(tids.begin(), tids.end()), timestamp);
}

bool MapRecordReader::ReadProcessMaps(pid_t pid, const std::unordered_set<pid_t>& tids,
                                      uint64_t timestamp) {
  // Dump mmap records.
  std::vector<ThreadMmap> thread_mmaps;
  if (!GetThreadMmapsInProcess(pid, &thread_mmaps)) {
    // The process may exit before we get its info.
    return true;
  }
  for (const auto& map : thread_mmaps) {
    if (!(map.prot & PROT_EXEC) && !keep_non_executable_maps_) {
      continue;
    }
    Mmap2Record record(attr_, false, pid, pid, map.start_addr, map.len, map.pgoff, map.prot,
                       map.name, event_id_, timestamp);
    if (!callback_(&record)) {
      return false;
    }
  }
  // Dump process name.
  std::string process_name = GetCompleteProcessName(pid);
  if (!process_name.empty()) {
    CommRecord record(attr_, pid, pid, process_name, event_id_, timestamp);
    if (!callback_(&record)) {
      return false;
    }
  }
  // Dump thread info.
  for (const auto& tid : tids) {
    std::string name;
    if (tid != pid && GetThreadName(tid, &name)) {
      // If a thread name matches the suffix of its process name, probably the thread name
      // is stripped by TASK_COMM_LEN.
      if (android::base::EndsWith(process_name, name)) {
        name = process_name;
      }
      CommRecord comm_record(attr_, pid, tid, name, event_id_, timestamp);
      if (!callback_(&comm_record)) {
        return false;
      }
    }
  }
  return true;
}

MapRecordThread::MapRecordThread(const MapRecordReader& map_record_reader)
    : map_record_reader_(map_record_reader), fp_(nullptr, fclose) {
  map_record_reader_.SetCallback([this](Record* r) { return WriteRecordToFile(r); });
  tmpfile_ = ScopedTempFiles::CreateTempFile();
  fp_.reset(fdopen(tmpfile_->release(), "r+"));
  thread_ = std::thread([this]() { thread_result_ = RunThread(); });
}

MapRecordThread::~MapRecordThread() {
  if (thread_.joinable()) {
    early_stop_ = true;
    thread_.join();
  }
}

bool MapRecordThread::RunThread() {
  if (!fp_) {
    return false;
  }
  if (!map_record_reader_.ReadKernelMaps()) {
    return false;
  }
  for (auto pid : GetAllProcesses()) {
    if (early_stop_) {
      return false;
    }
    if (!map_record_reader_.ReadProcessMaps(pid, 0)) {
      return false;
    }
  }
  return true;
}

bool MapRecordThread::WriteRecordToFile(Record* record) {
  if (fwrite(record->Binary(), record->size(), 1, fp_.get()) != 1) {
    PLOG(ERROR) << "failed to write map records to file";
    return false;
  }
  return true;
}

bool MapRecordThread::Join() {
  thread_.join();
  if (!thread_result_) {
    LOG(ERROR) << "map record thread failed";
  }
  return thread_result_;
}

bool MapRecordThread::ReadMapRecordData(const std::function<bool(const char*, size_t)>& callback) {
  off_t offset = ftello(fp_.get());
  if (offset == -1) {
    PLOG(ERROR) << "ftello() failed";
    return false;
  }
  uint64_t file_size = static_cast<uint64_t>(offset);
  if (fseek(fp_.get(), 0, SEEK_SET) != 0) {
    PLOG(ERROR) << "fseek() failed";
    return false;
  }
  std::vector<char> buffer(1024 * 1024);
  uint64_t left_bytes = file_size;
  while (left_bytes > 0) {
    size_t to_read = left_bytes > buffer.size() ? buffer.size() : left_bytes;
    if (fread(buffer.data(), to_read, 1, fp_.get()) != 1) {
      PLOG(ERROR) << "fread() failed";
      return false;
    }
    if (!callback(buffer.data(), to_read)) {
      return false;
    }
    left_bytes -= to_read;
  }
  return true;
}

}  // namespace simpleperf
