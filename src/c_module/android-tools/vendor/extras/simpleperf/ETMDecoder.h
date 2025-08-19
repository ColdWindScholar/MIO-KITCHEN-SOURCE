/*
 * Copyright (C) 2019 The Android Open Source Project
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

#include <functional>
#include <memory>
#include <string>

#include <android-base/expected.h>

#include "record.h"
#include "thread_tree.h"

namespace simpleperf {

struct ETMDumpOption {
  bool dump_raw_data = false;
  bool dump_packets = false;
  bool dump_elements = false;
};

bool ParseEtmDumpOption(const std::string& s, ETMDumpOption* option);

struct ETMInstrRange {
  // the binary containing the instruction range
  Dso* dso = nullptr;
  // the address of the first instruction in the binary
  uint64_t start_addr = 0;
  // the address of the last instruction in the binary
  uint64_t end_addr = 0;
  // If the last instruction is a branch instruction, and it branches
  // to a fixed location in the same binary, then branch_to_addr points
  // to the branched to instruction.
  uint64_t branch_to_addr = 0;
  // times the branch is taken
  uint64_t branch_taken_count = 0;
  // times the branch isn't taken
  uint64_t branch_not_taken_count = 0;
};

struct ETMBranchList {
  // the binary containing the branch list
  Dso* dso = nullptr;
  // the instruction address before the first branch. Bit 0 is set for thumb instructions.
  uint64_t addr = 0;
  // the branch list (one bit for each branch, true for branch taken, false for not taken)
  std::vector<bool> branch;
};

// ThreadTree interface used by ETMDecoder
class ETMThreadTree {
 public:
  virtual ~ETMThreadTree() {}
  virtual void DisableThreadExitRecords() = 0;
  virtual const ThreadEntry* FindThread(int tid) = 0;
  virtual const MapSet& GetKernelMaps() = 0;
};

class ETMDecoder {
 public:
  static std::unique_ptr<ETMDecoder> Create(const AuxTraceInfoRecord& auxtrace_info,
                                            ETMThreadTree& thread_tree);
  virtual ~ETMDecoder() {}
  virtual void EnableDump(const ETMDumpOption& option) = 0;

  using InstrRangeCallbackFn = std::function<void(const ETMInstrRange&)>;
  virtual void RegisterCallback(const InstrRangeCallbackFn& callback) = 0;

  using BranchListCallbackFn = std::function<void(const ETMBranchList&)>;
  virtual void RegisterCallback(const BranchListCallbackFn& callback) = 0;

  virtual bool ProcessData(const uint8_t* data, size_t size, bool formatted, uint32_t cpu) = 0;
  virtual bool FinishData() = 0;
};

// Map from addrs to a map of (branch_list, count).
// Use maps instead of unordered_maps. Because it helps locality by decoding instructions for sorted
// addresses.
using ETMBranchMap = std::map<uint64_t, std::map<std::vector<bool>, uint64_t>>;

android::base::expected<void, std::string> ConvertETMBranchMapToInstrRanges(
    Dso* dso, const ETMBranchMap& branch_map, const ETMDecoder::InstrRangeCallbackFn& callback);

}  // namespace simpleperf