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

#include "perf_regs.h"

#include <string.h>

#include <android-base/logging.h>
#include <android-base/stringprintf.h>
#include <android-base/strings.h>
#include <unordered_map>

#include "perf_event.h"

namespace simpleperf {

ArchType ScopedCurrentArch::current_arch = ARCH_UNSUPPORTED;

ArchType GetArchType(const std::string& arch) {
  if (arch == "x86" || arch == "i686") {
    return ARCH_X86_32;
  } else if (arch == "x86_64") {
    return ARCH_X86_64;
  } else if (arch == "riscv64") {
    return ARCH_RISCV64;
  } else if (arch == "aarch64") {
    return ARCH_ARM64;
  } else if (android::base::StartsWith(arch, "arm")) {
    // If arch is "armv8l", it is likely that we are using a 32-bit simpleperf
    // binary on a aarch64 device. In this case, the profiling environment is
    // ARCH_ARM64, because the kernel is aarch64.
    if (arch[3] == 'v') {
      int version = atoi(&arch[4]);
      if (version >= 8) {
        return ARCH_ARM64;
      }
    }
    return ARCH_ARM;
  }
  LOG(ERROR) << "unsupported arch: " << arch;
  return ARCH_UNSUPPORTED;
}

ArchType GetArchForAbi(ArchType machine_arch, int abi) {
  if (abi == PERF_SAMPLE_REGS_ABI_32) {
    if (machine_arch == ARCH_X86_64) {
      return ARCH_X86_32;
    }
    if (machine_arch == ARCH_ARM64) {
      return ARCH_ARM;
    }
  } else if (abi == PERF_SAMPLE_REGS_ABI_64) {
    if (machine_arch == ARCH_X86_32) {
      return ARCH_X86_64;
    }
    if (machine_arch == ARCH_ARM) {
      return ARCH_ARM64;
    }
  }
  return machine_arch;
}

std::string GetArchString(ArchType arch) {
  switch (arch) {
    case ARCH_X86_32:
      return "x86";
    case ARCH_X86_64:
      return "x86_64";
    case ARCH_ARM64:
      return "arm64";
    case ARCH_ARM:
      return "arm";
    case ARCH_RISCV64:
      return "riscv64";
    default:
      break;
  }
  return "unknown";
}

uint64_t GetSupportedRegMask(ArchType arch) {
  switch (arch) {
    case ARCH_X86_32:
      return ((1ULL << PERF_REG_X86_32_MAX) - 1) & ~(1ULL << PERF_REG_X86_DS) &
             ~(1ULL << PERF_REG_X86_ES) & ~(1ULL << PERF_REG_X86_FS) & ~(1ULL << PERF_REG_X86_GS);
    case ARCH_X86_64:
      return (((1ULL << PERF_REG_X86_64_MAX) - 1) & ~(1ULL << PERF_REG_X86_DS) &
              ~(1ULL << PERF_REG_X86_ES) & ~(1ULL << PERF_REG_X86_FS) & ~(1ULL << PERF_REG_X86_GS));
    case ARCH_ARM:
      return ((1ULL << PERF_REG_ARM_MAX) - 1);
    case ARCH_ARM64:
      return ((1ULL << PERF_REG_ARM64_MAX) - 1);
    case ARCH_RISCV64:
      return ((1ULL << PERF_REG_RISCV_MAX) - 1);
    default:
      return 0;
  }
  return 0;
}

static std::unordered_map<size_t, std::string> x86_reg_map = {
    {PERF_REG_X86_AX, "ax"},       {PERF_REG_X86_BX, "bx"}, {PERF_REG_X86_CX, "cx"},
    {PERF_REG_X86_DX, "dx"},       {PERF_REG_X86_SI, "si"}, {PERF_REG_X86_DI, "di"},
    {PERF_REG_X86_BP, "bp"},       {PERF_REG_X86_SP, "sp"}, {PERF_REG_X86_IP, "ip"},
    {PERF_REG_X86_FLAGS, "flags"}, {PERF_REG_X86_CS, "cs"}, {PERF_REG_X86_SS, "ss"},
    {PERF_REG_X86_DS, "ds"},       {PERF_REG_X86_ES, "es"}, {PERF_REG_X86_FS, "fs"},
    {PERF_REG_X86_GS, "gs"},
};

static std::unordered_map<size_t, std::string> arm_reg_map = {
    {PERF_REG_ARM_FP, "fp"}, {PERF_REG_ARM_IP, "ip"}, {PERF_REG_ARM_SP, "sp"},
    {PERF_REG_ARM_LR, "lr"}, {PERF_REG_ARM_PC, "pc"},
};

static std::unordered_map<size_t, std::string> arm64_reg_map = {
    {PERF_REG_ARM64_LR, "lr"},
    {PERF_REG_ARM64_SP, "sp"},
    {PERF_REG_ARM64_PC, "pc"},
};

static std::unordered_map<size_t, std::string> riscv64_reg_map = {
    {PERF_REG_RISCV_PC, "pc"},
    {PERF_REG_RISCV_RA, "ra"},
    {PERF_REG_RISCV_SP, "sp"},
    {PERF_REG_RISCV_GP, "gp"},
    {PERF_REG_RISCV_TP, "tp"},
    {PERF_REG_RISCV_T0, "t0"},
    {PERF_REG_RISCV_T1, "t1"},
    {PERF_REG_RISCV_T2, "t2"},
    {PERF_REG_RISCV_S0, "s0"},
    {PERF_REG_RISCV_S1, "s1"},
    {PERF_REG_RISCV_A0, "a0"},
    {PERF_REG_RISCV_A1, "a1"},
    {PERF_REG_RISCV_A2, "a2"},
    {PERF_REG_RISCV_A3, "a3"},
    {PERF_REG_RISCV_A4, "a4"},
    {PERF_REG_RISCV_A5, "a5"},
    {PERF_REG_RISCV_A6, "a6"},
    {PERF_REG_RISCV_A7, "a7"},
    {PERF_REG_RISCV_S2, "s2"},
    {PERF_REG_RISCV_S3, "s3"},
    {PERF_REG_RISCV_S4, "s4"},
    {PERF_REG_RISCV_S5, "s5"},
    {PERF_REG_RISCV_S6, "s6"},
    {PERF_REG_RISCV_S7, "s7"},
    {PERF_REG_RISCV_S8, "s8"},
    {PERF_REG_RISCV_S9, "s9"},
    {PERF_REG_RISCV_S10, "s10"},
    {PERF_REG_RISCV_S11, "s11"},
    {PERF_REG_RISCV_T3, "t3"},
    {PERF_REG_RISCV_T4, "t4"},
    {PERF_REG_RISCV_T5, "t5"},
    {PERF_REG_RISCV_T6, "t6"},
};

std::string GetRegName(size_t regno, ArchType arch) {
  // Cast regno to int type to avoid -Werror=type-limits.
  int reg = static_cast<int>(regno);
  switch (arch) {
    case ARCH_X86_64: {
      if (reg >= PERF_REG_X86_R8 && reg <= PERF_REG_X86_R15) {
        return android::base::StringPrintf("r%d", reg - PERF_REG_X86_R8 + 8);
      }
      FALLTHROUGH_INTENDED;
    }
    case ARCH_X86_32: {
      auto it = x86_reg_map.find(reg);
      CHECK(it != x86_reg_map.end()) << "unknown reg " << reg;
      return it->second;
    }
    case ARCH_ARM: {
      if (reg >= PERF_REG_ARM_R0 && reg <= PERF_REG_ARM_R10) {
        return android::base::StringPrintf("r%d", reg - PERF_REG_ARM_R0);
      }
      if (auto it = arm_reg_map.find(reg); it != arm_reg_map.end()) {
        return it->second;
      }
      FALLTHROUGH_INTENDED;
    }
    case ARCH_ARM64: {
      if (reg >= PERF_REG_ARM64_X0 && reg <= PERF_REG_ARM64_X29) {
        return android::base::StringPrintf("r%d", reg - PERF_REG_ARM64_X0);
      }
      auto it = arm64_reg_map.find(reg);
      CHECK(it != arm64_reg_map.end()) << "unknown reg " << reg;
      return it->second;
    }
    case ARCH_RISCV64: {
      auto it = riscv64_reg_map.find(reg);
      CHECK(it != riscv64_reg_map.end()) << "unknown reg " << reg;
      return it->second;
    }
    default:
      return "unknown";
  }
}

RegSet::RegSet(int abi, uint64_t valid_mask, const uint64_t* valid_regs) : valid_mask(valid_mask) {
  arch = GetArchForAbi(ScopedCurrentArch::GetCurrentArch(), abi);
  memset(data, 0, sizeof(data));
  for (int i = 0, j = 0; i < 64; ++i) {
    if ((valid_mask >> i) & 1) {
      data[i] = valid_regs[j++];
    }
  }
  if (ScopedCurrentArch::GetCurrentArch() == ARCH_ARM64 && abi == PERF_SAMPLE_REGS_ABI_32) {
    // The kernel dumps arm64 regs, but we need arm regs. So map arm64 regs into arm regs.
    data[PERF_REG_ARM_PC] = data[PERF_REG_ARM64_PC];
  }
}

bool RegSet::GetRegValue(size_t regno, uint64_t* value) const {
  CHECK_LT(regno, 64U);
  if ((valid_mask >> regno) & 1) {
    *value = data[regno];
    return true;
  }
  return false;
}

bool RegSet::GetSpRegValue(uint64_t* value) const {
  size_t regno;
  switch (arch) {
    case ARCH_X86_32:
      regno = PERF_REG_X86_SP;
      break;
    case ARCH_X86_64:
      regno = PERF_REG_X86_SP;
      break;
    case ARCH_ARM:
      regno = PERF_REG_ARM_SP;
      break;
    case ARCH_ARM64:
      regno = PERF_REG_ARM64_SP;
      break;
    case ARCH_RISCV64:
      regno = PERF_REG_RISCV_SP;
      break;
    default:
      return false;
  }
  return GetRegValue(regno, value);
}

bool RegSet::GetIpRegValue(uint64_t* value) const {
  size_t regno;
  switch (arch) {
    case ARCH_X86_64:
    case ARCH_X86_32:
      regno = PERF_REG_X86_IP;
      break;
    case ARCH_ARM:
      regno = PERF_REG_ARM_PC;
      break;
    case ARCH_ARM64:
      regno = PERF_REG_ARM64_PC;
      break;
    case ARCH_RISCV64:
      regno = PERF_REG_RISCV_PC;
      break;
    default:
      return false;
  }
  return GetRegValue(regno, value);
}

}  // namespace simpleperf
