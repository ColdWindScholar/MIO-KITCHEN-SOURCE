//
// Copyright (C) 2020 The Android Open Source Project
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//
//

#include <stdio.h>

#include <optional>

#include <android-base/logging.h>
#include <android-base/properties.h>

#include "command.h"
#include "event_attr.h"
#include "event_fd.h"
#include "event_type.h"
#include "record_file.h"
#include "test_util.h"

#if defined(__linux__)

static std::optional<bool> CanSampleRegsFor32BitABI() {
  std::vector<std::unique_ptr<Workload>> workloads;
  CreateProcesses(1, &workloads);
  std::string pid = std::to_string(workloads[0]->GetPid());
  std::unique_ptr<Command> cmd = CreateCommandInstance("record");
  TemporaryFile tmpfile;
  if (!cmd->Run({"-p", pid, "--call-graph", "dwarf,8", "--no-unwind", "-e", "cpu-clock:u",
                 "--duration", "3", "-o", tmpfile.path})) {
    return std::nullopt;
  }
  auto reader = RecordFileReader::CreateInstance(tmpfile.path);
  if (!reader) {
    return std::nullopt;
  }
  for (const std::unique_ptr<Record>& record : reader->DataSection()) {
    if (record->type() == PERF_RECORD_SAMPLE) {
      auto sample = static_cast<const SampleRecord*>(record.get());
      if (sample->regs_user_data.abi == PERF_SAMPLE_REGS_ABI_32) {
        return true;
      }
    }
  }
  return false;
}

std::optional<bool> IsInNativeAbi() {
  static int in_native_abi = -1;
  if (in_native_abi == -1) {
    FILE* fp = popen("uname -m", "re");
    char buf[40];
    memset(buf, '\0', sizeof(buf));
    CHECK_EQ(fgets(buf, sizeof(buf), fp), buf);
    pclose(fp);
    std::string s = buf;
    in_native_abi = 1;
    if (GetTargetArch() == ARCH_X86_32 || GetTargetArch() == ARCH_X86_64) {
      if (s.find("86") == std::string::npos) {
        in_native_abi = 0;
      }
    } else if (GetTargetArch() == ARCH_ARM || GetTargetArch() == ARCH_ARM64) {
      if (s.find("arm") == std::string::npos && s.find("aarch64") == std::string::npos) {
        in_native_abi = 0;
      }
      if (GetTargetArch() == ARCH_ARM) {
        // If we can't get ARM registers in samples, probably we are running with a 32-bit
        // translator on 64-bit only CPUs. Then we should make in_native_abi = 0.
        if (auto result = CanSampleRegsFor32BitABI(); result.has_value()) {
          in_native_abi = result.value() ? 1 : 0;
        } else {
          in_native_abi = 2;
        }
      }
    } else if (GetTargetArch() == ARCH_RISCV64) {
      if (s.find("riscv") == std::string::npos) {
        in_native_abi = 0;
      }
    }
  }
  if (in_native_abi == 2) {
    return std::nullopt;
  }
  return in_native_abi == 1;
}

// Check if we can get a non-zero instruction event count by monitoring current thread.
static bool HasNonZeroInstructionEventCount() {
  const simpleperf::EventType* type = simpleperf::FindEventTypeByName("instructions", false);
  if (type == nullptr) {
    return false;
  }
  perf_event_attr attr = CreateDefaultPerfEventAttr(*type);
  std::unique_ptr<EventFd> event_fd =
      EventFd::OpenEventFile(attr, gettid(), -1, nullptr, type->name, false);
  if (!event_fd) {
    return false;
  }
  // do some cpu work.
  for (volatile int i = 0; i < 100000; ++i) {
  }
  PerfCounter counter;
  if (event_fd->ReadCounter(&counter)) {
    return counter.value != 0;
  }
  return false;
}

bool IsInEmulator() {
  std::string fingerprint = android::base::GetProperty("ro.system.build.fingerprint", "");
  return android::base::StartsWith(fingerprint, "google/sdk_gphone") ||
         android::base::StartsWith(fingerprint, "google/sdk_gpc") ||
         android::base::StartsWith(fingerprint, "generic/cf") ||
         android::base::StartsWith(fingerprint, "generic/aosp_cf");
}

bool HasHardwareCounter() {
  static int has_hw_counter = -1;
  if (has_hw_counter == -1) {
    has_hw_counter = 1;
    auto arch = GetTargetArch();

    bool in_native_abi = IsInNativeAbi() == std::optional(true);

    if (arch == ARCH_X86_64 || arch == ARCH_X86_32 || !in_native_abi || IsInEmulator()) {
      // On x86 and x86_64, or when we are not in native abi, it's likely to run on an emulator or
      // vm without hardware perf counters. It's hard to enumerate them all. So check the support
      // at runtime.
      const simpleperf::EventType* type = simpleperf::FindEventTypeByName("cpu-cycles", false);
      CHECK(type != nullptr);
      perf_event_attr attr = CreateDefaultPerfEventAttr(*type);
      has_hw_counter = IsEventAttrSupported(attr, "cpu-cycles") ? 1 : 0;
    } else if (arch == ARCH_ARM) {
      // For arm32 devices, external non-invasive debug signal controls PMU counters. Once it is
      // disabled for security reason, we always get zero values for PMU counters. And we want to
      // skip hardware counter tests once we detect it.
      has_hw_counter &= HasNonZeroInstructionEventCount() ? 1 : 0;
    }
  }
  return has_hw_counter == 1;
}

#else   // !defined(__linux__)
bool HasHardwareCounter() {
  return false;
}
#endif  // !defined(__linux__)

bool HasPmuCounter() {
  static int has_pmu_counter = -1;
  if (has_pmu_counter == -1) {
    has_pmu_counter = 0;
    auto callback = [&](const simpleperf::EventType& event_type) {
      if (event_type.IsPmuEvent()) {
        has_pmu_counter = 1;
        return false;
      }
      return true;
    };
    simpleperf::EventTypeManager::Instance().ForEachType(callback);
  }
  return has_pmu_counter == 1;
}

bool HasTracepointEvents() {
  static int has_tracepoint_events = -1;
  if (has_tracepoint_events == -1) {
    has_tracepoint_events = 0;
    if (const char* dir = GetTraceFsDir(); dir != nullptr) {
      if (IsDir(std::string(dir) + "/events/sched/sched_switch")) {
        has_tracepoint_events = 1;
      }
    }
  }
  return has_tracepoint_events == 1;
}
