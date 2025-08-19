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

#ifndef SIMPLE_PERF_PERF_REGS_H_
#define SIMPLE_PERF_PERF_REGS_H_

#if defined(USE_BIONIC_UAPI_HEADERS)
#include <uapi/asm-arm/asm/perf_regs.h>
#undef PERF_REG_EXTENDED_MASK
#include <uapi/asm-x86/asm/perf_regs.h>
#undef PERF_REG_EXTENDED_MASK
#include <uapi/asm-riscv/asm/perf_regs.h>
#undef PERF_REG_EXTENDED_MASK
#define perf_event_arm_regs perf_event_arm64_regs
#include <uapi/asm-arm64/asm/perf_regs.h>
#undef PERF_REG_EXTENDED_MASK
#else
#include <asm-arm/asm/perf_regs.h>
#undef PERF_REG_EXTENDED_MASK
#include <asm-x86/asm/perf_regs.h>
#undef PERF_REG_EXTENDED_MASK
#include <asm-riscv/asm/perf_regs.h>
#undef PERF_REG_EXTENDED_MASK
#define perf_event_arm_regs perf_event_arm64_regs
#include <asm-arm64/asm/perf_regs.h>
#undef PERF_REG_EXTENDED_MASK
#endif

#include <stdint.h>
#include <string>
#include <vector>

#include "perf_event.h"

namespace simpleperf {

enum ArchType {
  ARCH_X86_32,
  ARCH_X86_64,
  ARCH_ARM,
  ARCH_ARM64,
  ARCH_RISCV64,
  ARCH_UNSUPPORTED,
};

constexpr ArchType GetTargetArch() {
#if defined(__i386__)
  return ARCH_X86_32;
#elif defined(__x86_64__)
  return ARCH_X86_64;
#elif defined(__aarch64__)
  return ARCH_ARM64;
#elif defined(__arm__)
  return ARCH_ARM;
#elif defined(__riscv)
  return ARCH_RISCV64;
#else
  return ARCH_UNSUPPORTED;
#endif
}

ArchType GetArchType(const std::string& arch);
ArchType GetArchForAbi(ArchType machine_arch, int abi);
std::string GetArchString(ArchType arch);
uint64_t GetSupportedRegMask(ArchType arch);
std::string GetRegName(size_t regno, ArchType arch);

class ScopedCurrentArch {
 public:
  explicit ScopedCurrentArch(ArchType arch) : saved_arch(current_arch) {
    current_arch = arch;
  }
  ~ScopedCurrentArch() {
    current_arch = saved_arch;
  }
  static ArchType GetCurrentArch() { return current_arch; }

 private:
  ArchType saved_arch;
  static ArchType current_arch;
};

struct RegSet {
  ArchType arch;
  // For each setting bit in valid_mask, there is a valid reg value in data[].
  uint64_t valid_mask;
  // Stores reg values. Values for invalid regs are 0.
  uint64_t data[64];

  RegSet(int abi, uint64_t valid_mask, const uint64_t* valid_regs);

  bool GetRegValue(size_t regno, uint64_t* value) const;
  bool GetSpRegValue(uint64_t* value) const;
  bool GetIpRegValue(uint64_t* value) const;
};

}  // namespace simpleperf

#endif  // SIMPLE_PERF_PERF_REGS_H_
