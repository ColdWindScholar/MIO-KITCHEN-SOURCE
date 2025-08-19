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

#pragma once

#include <inttypes.h>
#include <stdio.h>

#include <atomic>
#include <functional>
#include <memory>
#include <thread>
#include <unordered_set>
#include <vector>

#include "event_attr.h"
#include "record.h"

namespace simpleperf {

class MapRecordReader {
 public:
  MapRecordReader(const perf_event_attr& attr, uint64_t event_id, bool keep_non_executable_maps)
      : attr_(attr), event_id_(event_id), keep_non_executable_maps_(keep_non_executable_maps) {}

  const perf_event_attr& Attr() { return attr_; }
  void SetCallback(const std::function<bool(Record*)>& callback) { callback_ = callback; }
  bool ReadKernelMaps();
  // Read process maps and all thread names in a process.
  bool ReadProcessMaps(pid_t pid, uint64_t timestamp);
  // Read process maps and selected thread names in a process.
  bool ReadProcessMaps(pid_t pid, const std::unordered_set<pid_t>& tids, uint64_t timestamp);

 private:
  const perf_event_attr& attr_;
  const uint64_t event_id_;
  const bool keep_non_executable_maps_;
  std::function<bool(Record*)> callback_;
};

// Create a thread for reading maps while recording. The maps are stored in a temporary file, and
// read back after recording.
class MapRecordThread {
 public:
  MapRecordThread(const MapRecordReader& map_record_reader);
  ~MapRecordThread();

  bool Join();
  bool ReadMapRecordData(const std::function<bool(const char*, size_t)>& callback);

 private:
  // functions running in the map record thread
  bool RunThread();
  bool WriteRecordToFile(Record* record);

  MapRecordReader map_record_reader_;
  std::unique_ptr<TemporaryFile> tmpfile_;
  std::unique_ptr<FILE, decltype(&fclose)> fp_;
  std::thread thread_;
  std::atomic<bool> early_stop_ = false;
  std::atomic<bool> thread_result_ = false;
};

}  // namespace simpleperf
