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

#ifndef SIMPLE_PERF_OFFLINE_UNWINDER_H_
#define SIMPLE_PERF_OFFLINE_UNWINDER_H_

#include <memory>
#include <vector>

#include "perf_regs.h"
#include "thread_tree.h"

namespace simpleperf {
struct ThreadEntry;

enum UnwindStackErrorCode : uint8_t {
  ERROR_NONE,                   // No error.
  ERROR_MEMORY_INVALID,         // Memory read failed.
  ERROR_UNWIND_INFO,            // Unable to use unwind information to unwind.
  ERROR_UNSUPPORTED,            // Encountered unsupported feature.
  ERROR_INVALID_MAP,            // Unwind in an invalid map.
  ERROR_MAX_FRAMES_EXCEEDED,    // The number of frames exceed the total allowed.
  ERROR_REPEATED_FRAME,         // The last frame has the same pc/sp as the next.
  ERROR_INVALID_ELF,            // Unwind in an invalid elf.
  ERROR_THREAD_DOES_NOT_EXIST,  // Attempt to unwind a local thread that does
                                // not exist.
  ERROR_THREAD_TIMEOUT,         // Timeout trying to unwind a local thread.
  ERROR_SYSTEM_CALL,            // System call failed while unwinding.
  ERROR_BAD_ARCH,               // Arch invalid (none, or mismatched).
  ERROR_MAPS_PARSE,             // Failed to parse maps data.
  ERROR_INVALID_PARAMETER,      // Invalid parameter passed to function.
  ERROR_MAX = ERROR_INVALID_PARAMETER,
};

struct UnwindingResult {
  // time used for unwinding, in ns.
  uint64_t used_time;
  // unwindstack::LastErrorCode()
  uint64_t error_code;
  // unwindstack::LastErrorAddress()
  uint64_t error_addr;
  uint64_t stack_start;
  uint64_t stack_end;
};

class OfflineUnwinder {
 public:
  static constexpr const char* META_KEY_ARM64_PAC_MASK = "arm64_pac_mask";

  static std::unique_ptr<OfflineUnwinder> Create(bool collect_stat);
  virtual ~OfflineUnwinder() {}

  virtual bool UnwindCallChain(const ThreadEntry& thread, const RegSet& regs, const char* stack,
                               size_t stack_size, std::vector<uint64_t>* ips,
                               std::vector<uint64_t>* sps) = 0;

  const UnwindingResult& GetUnwindingResult() const { return unwinding_result_; }

  bool IsCallChainBrokenForIncompleteJITDebugInfo() {
    return is_callchain_broken_for_incomplete_jit_debug_info_;
  }

  static void CollectMetaInfo(std::unordered_map<std::string, std::string>* info_map);
  virtual void LoadMetaInfo(const std::unordered_map<std::string, std::string>&) {}

 protected:
  OfflineUnwinder() {}

  UnwindingResult unwinding_result_;
  bool is_callchain_broken_for_incomplete_jit_debug_info_ = false;
};

}  // namespace simpleperf

#endif  // SIMPLE_PERF_OFFLINE_UNWINDER_H_
