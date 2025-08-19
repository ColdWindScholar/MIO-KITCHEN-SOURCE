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

#include "OfflineUnwinder.h"

#include <inttypes.h>
#include <sys/mman.h>

#include <unordered_map>

#include <android-base/logging.h>
#include <android-base/parseint.h>
#include <unwindstack/MachineArm.h>
#include <unwindstack/MachineArm64.h>
#include <unwindstack/MachineX86.h>
#include <unwindstack/MachineX86_64.h>
#include <unwindstack/MachineRiscv64.h>
#include <unwindstack/Maps.h>
#include <unwindstack/RegsArm.h>
#include <unwindstack/RegsArm64.h>
#include <unwindstack/RegsX86.h>
#include <unwindstack/RegsX86_64.h>
#include <unwindstack/RegsRiscv64.h>
#include <unwindstack/Unwinder.h>
#include <unwindstack/UserArm.h>
#include <unwindstack/UserArm64.h>
#include <unwindstack/UserX86.h>
#include <unwindstack/UserX86_64.h>
#include <unwindstack/UserRiscv64.h>

#include "JITDebugReader.h"
#include "OfflineUnwinder_impl.h"
#include "environment.h"
#include "perf_regs.h"
#include "read_apk.h"
#include "thread_tree.h"

namespace simpleperf {

// unwindstack only builds on linux. So simpleperf redefines flags in unwindstack, to use them on
// darwin/windows. Use static_assert to make sure they are on the same page.
static_assert(map_flags::PROT_JIT_SYMFILE_MAP == unwindstack::MAPS_FLAGS_JIT_SYMFILE_MAP);

#define CHECK_ERROR_CODE(error_code_name)                \
  static_assert(UnwindStackErrorCode::error_code_name == \
                (UnwindStackErrorCode)unwindstack::ErrorCode::error_code_name)

CHECK_ERROR_CODE(ERROR_NONE);
CHECK_ERROR_CODE(ERROR_MEMORY_INVALID);
CHECK_ERROR_CODE(ERROR_UNWIND_INFO);
CHECK_ERROR_CODE(ERROR_UNSUPPORTED);
CHECK_ERROR_CODE(ERROR_INVALID_MAP);
CHECK_ERROR_CODE(ERROR_MAX_FRAMES_EXCEEDED);
CHECK_ERROR_CODE(ERROR_REPEATED_FRAME);
CHECK_ERROR_CODE(ERROR_INVALID_ELF);
CHECK_ERROR_CODE(ERROR_THREAD_DOES_NOT_EXIST);
CHECK_ERROR_CODE(ERROR_THREAD_TIMEOUT);
CHECK_ERROR_CODE(ERROR_SYSTEM_CALL);
CHECK_ERROR_CODE(ERROR_BAD_ARCH);
CHECK_ERROR_CODE(ERROR_MAPS_PARSE);
CHECK_ERROR_CODE(ERROR_INVALID_PARAMETER);
CHECK_ERROR_CODE(ERROR_MAX);

// Max frames seen so far is 463, in http://b/110923759.
static constexpr size_t MAX_UNWINDING_FRAMES = 512;

unwindstack::Regs* OfflineUnwinderImpl::GetBacktraceRegs(const RegSet& regs) {
  switch (regs.arch) {
    case ARCH_ARM: {
      unwindstack::arm_user_regs arm_user_regs;
      memset(&arm_user_regs, 0, sizeof(arm_user_regs));
      static_assert(static_cast<int>(unwindstack::ARM_REG_R0) == static_cast<int>(PERF_REG_ARM_R0),
                    "");
      static_assert(
          static_cast<int>(unwindstack::ARM_REG_LAST) == static_cast<int>(PERF_REG_ARM_MAX), "");
      for (size_t i = unwindstack::ARM_REG_R0; i < unwindstack::ARM_REG_LAST; ++i) {
        arm_user_regs.regs[i] = static_cast<uint32_t>(regs.data[i]);
      }
      return unwindstack::RegsArm::Read(&arm_user_regs);
    }
    case ARCH_ARM64: {
      unwindstack::arm64_user_regs arm64_user_regs;
      memset(&arm64_user_regs, 0, sizeof(arm64_user_regs));
      static_assert(
          static_cast<int>(unwindstack::ARM64_REG_R0) == static_cast<int>(PERF_REG_ARM64_X0), "");
      static_assert(
          static_cast<int>(unwindstack::ARM64_REG_R30) == static_cast<int>(PERF_REG_ARM64_LR), "");
      memcpy(&arm64_user_regs.regs[unwindstack::ARM64_REG_R0], &regs.data[PERF_REG_ARM64_X0],
             sizeof(uint64_t) * (PERF_REG_ARM64_LR - PERF_REG_ARM64_X0 + 1));
      arm64_user_regs.sp = regs.data[PERF_REG_ARM64_SP];
      arm64_user_regs.pc = regs.data[PERF_REG_ARM64_PC];
      auto regs =
          static_cast<unwindstack::RegsArm64*>(unwindstack::RegsArm64::Read(&arm64_user_regs));
      regs->SetPACMask(arm64_pac_mask_);
      return regs;
    }
    case ARCH_X86_32: {
      unwindstack::x86_user_regs x86_user_regs;
      memset(&x86_user_regs, 0, sizeof(x86_user_regs));
      x86_user_regs.eax = static_cast<uint32_t>(regs.data[PERF_REG_X86_AX]);
      x86_user_regs.ebx = static_cast<uint32_t>(regs.data[PERF_REG_X86_BX]);
      x86_user_regs.ecx = static_cast<uint32_t>(regs.data[PERF_REG_X86_CX]);
      x86_user_regs.edx = static_cast<uint32_t>(regs.data[PERF_REG_X86_DX]);
      x86_user_regs.ebp = static_cast<uint32_t>(regs.data[PERF_REG_X86_BP]);
      x86_user_regs.edi = static_cast<uint32_t>(regs.data[PERF_REG_X86_DI]);
      x86_user_regs.esi = static_cast<uint32_t>(regs.data[PERF_REG_X86_SI]);
      x86_user_regs.esp = static_cast<uint32_t>(regs.data[PERF_REG_X86_SP]);
      x86_user_regs.eip = static_cast<uint32_t>(regs.data[PERF_REG_X86_IP]);
      return unwindstack::RegsX86::Read(&x86_user_regs);
    }
    case ARCH_X86_64: {
      unwindstack::x86_64_user_regs x86_64_user_regs;
      memset(&x86_64_user_regs, 0, sizeof(x86_64_user_regs));
      x86_64_user_regs.rax = regs.data[PERF_REG_X86_AX];
      x86_64_user_regs.rbx = regs.data[PERF_REG_X86_BX];
      x86_64_user_regs.rcx = regs.data[PERF_REG_X86_CX];
      x86_64_user_regs.rdx = regs.data[PERF_REG_X86_DX];
      x86_64_user_regs.r8 = regs.data[PERF_REG_X86_R8];
      x86_64_user_regs.r9 = regs.data[PERF_REG_X86_R9];
      x86_64_user_regs.r10 = regs.data[PERF_REG_X86_R10];
      x86_64_user_regs.r11 = regs.data[PERF_REG_X86_R11];
      x86_64_user_regs.r12 = regs.data[PERF_REG_X86_R12];
      x86_64_user_regs.r13 = regs.data[PERF_REG_X86_R13];
      x86_64_user_regs.r14 = regs.data[PERF_REG_X86_R14];
      x86_64_user_regs.r15 = regs.data[PERF_REG_X86_R15];
      x86_64_user_regs.rdi = regs.data[PERF_REG_X86_DI];
      x86_64_user_regs.rsi = regs.data[PERF_REG_X86_SI];
      x86_64_user_regs.rbp = regs.data[PERF_REG_X86_BP];
      x86_64_user_regs.rsp = regs.data[PERF_REG_X86_SP];
      x86_64_user_regs.rip = regs.data[PERF_REG_X86_IP];
      return unwindstack::RegsX86_64::Read(&x86_64_user_regs);
    }
    case ARCH_RISCV64: {
      unwindstack::riscv64_user_regs riscv64_user_regs;
      memset(&riscv64_user_regs, 0, sizeof(riscv64_user_regs));
      riscv64_user_regs.regs[PERF_REG_RISCV_PC] = regs.data[PERF_REG_RISCV_PC];
      riscv64_user_regs.regs[PERF_REG_RISCV_RA] = regs.data[PERF_REG_RISCV_RA];
      riscv64_user_regs.regs[PERF_REG_RISCV_SP] = regs.data[PERF_REG_RISCV_SP];
      riscv64_user_regs.regs[PERF_REG_RISCV_GP] = regs.data[PERF_REG_RISCV_GP];
      riscv64_user_regs.regs[PERF_REG_RISCV_TP] = regs.data[PERF_REG_RISCV_TP];
      riscv64_user_regs.regs[PERF_REG_RISCV_T0] = regs.data[PERF_REG_RISCV_T0];
      riscv64_user_regs.regs[PERF_REG_RISCV_T1] = regs.data[PERF_REG_RISCV_T1];
      riscv64_user_regs.regs[PERF_REG_RISCV_T2] = regs.data[PERF_REG_RISCV_T2];
      riscv64_user_regs.regs[PERF_REG_RISCV_S0] = regs.data[PERF_REG_RISCV_S0];
      riscv64_user_regs.regs[PERF_REG_RISCV_S1] = regs.data[PERF_REG_RISCV_S1];
      riscv64_user_regs.regs[PERF_REG_RISCV_A0] = regs.data[PERF_REG_RISCV_A0];
      riscv64_user_regs.regs[PERF_REG_RISCV_A1] = regs.data[PERF_REG_RISCV_A1];
      riscv64_user_regs.regs[PERF_REG_RISCV_A2] = regs.data[PERF_REG_RISCV_A2];
      riscv64_user_regs.regs[PERF_REG_RISCV_A3] = regs.data[PERF_REG_RISCV_A3];
      riscv64_user_regs.regs[PERF_REG_RISCV_A4] = regs.data[PERF_REG_RISCV_A4];
      riscv64_user_regs.regs[PERF_REG_RISCV_A5] = regs.data[PERF_REG_RISCV_A5];
      riscv64_user_regs.regs[PERF_REG_RISCV_A6] = regs.data[PERF_REG_RISCV_A6];
      riscv64_user_regs.regs[PERF_REG_RISCV_A7] = regs.data[PERF_REG_RISCV_A7];
      riscv64_user_regs.regs[PERF_REG_RISCV_S2] = regs.data[PERF_REG_RISCV_S2];
      riscv64_user_regs.regs[PERF_REG_RISCV_S3] = regs.data[PERF_REG_RISCV_S3];
      riscv64_user_regs.regs[PERF_REG_RISCV_S4] = regs.data[PERF_REG_RISCV_S4];
      riscv64_user_regs.regs[PERF_REG_RISCV_S5] = regs.data[PERF_REG_RISCV_S5];
      riscv64_user_regs.regs[PERF_REG_RISCV_S6] = regs.data[PERF_REG_RISCV_S6];
      riscv64_user_regs.regs[PERF_REG_RISCV_S7] = regs.data[PERF_REG_RISCV_S7];
      riscv64_user_regs.regs[PERF_REG_RISCV_S8] = regs.data[PERF_REG_RISCV_S8];
      riscv64_user_regs.regs[PERF_REG_RISCV_S9] = regs.data[PERF_REG_RISCV_S9];
      riscv64_user_regs.regs[PERF_REG_RISCV_S10] = regs.data[PERF_REG_RISCV_S10];
      riscv64_user_regs.regs[PERF_REG_RISCV_S11] = regs.data[PERF_REG_RISCV_S11];
      riscv64_user_regs.regs[PERF_REG_RISCV_T3] = regs.data[PERF_REG_RISCV_T3];
      riscv64_user_regs.regs[PERF_REG_RISCV_T4] = regs.data[PERF_REG_RISCV_T4];
      riscv64_user_regs.regs[PERF_REG_RISCV_T5] = regs.data[PERF_REG_RISCV_T5];
      riscv64_user_regs.regs[PERF_REG_RISCV_T6] = regs.data[PERF_REG_RISCV_T6];
      return unwindstack::RegsRiscv64::Read(&riscv64_user_regs);
    }
    default:
      return nullptr;
  }
}

static std::shared_ptr<unwindstack::MapInfo> CreateMapInfo(const MapEntry* entry) {
  std::string name_holder;
  const char* name = entry->dso->GetDebugFilePath().data();
  uint64_t pgoff = entry->pgoff;
  auto tuple = SplitUrlInApk(entry->dso->GetDebugFilePath());
  if (std::get<0>(tuple)) {
    // The unwinder does not understand the ! format, so change back to
    // the previous format (apk, offset).
    EmbeddedElf* elf = ApkInspector::FindElfInApkByName(std::get<1>(tuple), std::get<2>(tuple));
    if (elf != nullptr) {
      name = elf->filepath().data();
      pgoff += elf->entry_offset();
    }
  } else if (entry->flags & map_flags::PROT_JIT_SYMFILE_MAP) {
    // Remove location_in_file suffix, which isn't recognized by libunwindstack.
    const std::string& path = entry->dso->GetDebugFilePath();
    if (JITDebugReader::IsPathInJITSymFile(path)) {
      size_t colon_pos = path.rfind(':');
      CHECK_NE(colon_pos, std::string::npos);
      name_holder = path.substr(0, colon_pos);
      name = name_holder.data();
    }
  }
  return unwindstack::MapInfo::Create(entry->start_addr, entry->get_end_addr(), pgoff,
                                      PROT_READ | entry->flags, name);
}

void UnwindMaps::UpdateMaps(const MapSet& map_set) {
  if (version_ == map_set.version) {
    return;
  }
  version_ = map_set.version;
  size_t i = 0;
  size_t old_size = entries_.size();
  bool has_removed_entry = false;
  for (auto it = map_set.maps.begin(); it != map_set.maps.end();) {
    const MapEntry* entry = it->second;
    if (i < old_size && entry == entries_[i]) {
      i++;
      ++it;
    } else if (i == old_size || entry->start_addr <= entries_[i]->start_addr) {
      // Add an entry.
      entries_.push_back(entry);
      maps_.emplace_back(CreateMapInfo(entry));
      ++it;
    } else {
      // Remove an entry.
      has_removed_entry = true;
      entries_[i] = nullptr;
      maps_[i++] = nullptr;
    }
  }
  while (i < old_size) {
    has_removed_entry = true;
    entries_[i] = nullptr;
    maps_[i++] = nullptr;
  }

  if (has_removed_entry) {
    entries_.resize(std::remove(entries_.begin(), entries_.end(), nullptr) - entries_.begin());
    maps_.resize(std::remove(maps_.begin(), maps_.end(), std::shared_ptr<unwindstack::MapInfo>()) -
                 maps_.begin());
  }

  std::sort(entries_.begin(), entries_.end(),
            [](const auto& e1, const auto& e2) { return e1->start_addr < e2->start_addr; });
  // Use Sort() to sort maps_ and create prev_real_map links.
  // prev_real_map is needed by libunwindstack to find the start of an embedded lib in an apk.
  // See http://b/120981155.
  Sort();
}

void OfflineUnwinder::CollectMetaInfo(std::unordered_map<std::string, std::string>* info_map
                                      __attribute__((unused))) {
#if defined(__aarch64__)
  // Find pac_mask for ARMv8.3-A Pointer Authentication by below steps:
  // 1. Create a 64 bit value with every bit set, but clear bit 55. Because linux user space uses
  //    TTBR0.
  // 2. Use XPACLRI to clear auth code bits.
  // 3. Flip every bit to get pac_mask, excluding bit 55.
  // We can also use ptrace(PTRACE_GETREGSET, pid, NT_ARM_PAC_MASK). But it needs a tracee.
  register uint64_t x30 __asm("x30") = ~(1ULL << 55);
  // This is XPACLRI on ARMv8.3-A, and nop on prev ARMv8.3-A.
  asm("hint 0x7" : "+r"(x30));
  uint64_t pac_mask = ~x30 & ~(1ULL << 55);
  if (pac_mask != 0) {
    (*info_map)[META_KEY_ARM64_PAC_MASK] = android::base::StringPrintf("0x%" PRIx64, pac_mask);
  }
#endif
}

void OfflineUnwinderImpl::LoadMetaInfo(
    const std::unordered_map<std::string, std::string>& info_map) {
  if (auto it = info_map.find(META_KEY_ARM64_PAC_MASK); it != info_map.end()) {
    CHECK(android::base::ParseUint(it->second, &arm64_pac_mask_));
  }
}

bool OfflineUnwinderImpl::UnwindCallChain(const ThreadEntry& thread, const RegSet& regs,
                                          const char* stack, size_t stack_size,
                                          std::vector<uint64_t>* ips, std::vector<uint64_t>* sps) {
  uint64_t start_time;
  if (collect_stat_) {
    start_time = GetSystemClock();
  }
  is_callchain_broken_for_incomplete_jit_debug_info_ = false;
  ips->clear();
  sps->clear();
  std::vector<uint64_t> result;
  uint64_t sp_reg_value;
  if (!regs.GetSpRegValue(&sp_reg_value)) {
    LOG(ERROR) << "can't get sp reg value";
    return false;
  }
  uint64_t stack_addr = sp_reg_value;

  UnwindMaps& cached_map = cached_maps_[thread.pid];
  cached_map.UpdateMaps(*thread.maps);
  std::unique_ptr<unwindstack::Regs> unwind_regs(GetBacktraceRegs(regs));
  if (!unwind_regs) {
    return false;
  }
  unwindstack::Unwinder unwinder(
      MAX_UNWINDING_FRAMES, &cached_map, unwind_regs.get(),
      unwindstack::Memory::CreateOfflineMemory(reinterpret_cast<const uint8_t*>(stack), stack_addr,
                                               stack_addr + stack_size));
  unwinder.SetResolveNames(false);
  unwinder.Unwind();
  size_t last_jit_method_frame = UINT_MAX;
  for (auto& frame : unwinder.frames()) {
    // Unwinding in arm architecture can return 0 pc address.

    // If frame.map_info == nullptr, this frame doesn't hit any map, it could be:
    // 1. In an executable map not backed by a file. Note that RecordCommand::ShouldOmitRecord()
    //    may omit maps only exist memory.
    // 2. An incorrectly unwound frame. Likely caused by invalid stack data, as in
    //    SampleRecord::GetValidStackSize(). Or caused by incomplete JIT debug info.
    // We want to remove this frame and callchains following it in either case.
    if (frame.map_info == nullptr) {
      is_callchain_broken_for_incomplete_jit_debug_info_ = true;
      break;
    }
    if (frame.map_info->flags() & unwindstack::MAPS_FLAGS_JIT_SYMFILE_MAP) {
      last_jit_method_frame = ips->size();
    }
    ips->push_back(frame.pc);
    sps->push_back(frame.sp);
  }
  // If the unwound frames stop near to a JITed method, it may be caused by incomplete JIT debug
  // info.
  if (last_jit_method_frame != UINT_MAX && last_jit_method_frame + 3 > ips->size()) {
    is_callchain_broken_for_incomplete_jit_debug_info_ = true;
  }

  uint64_t ip_reg_value;
  if (!regs.GetIpRegValue(&ip_reg_value)) {
    LOG(ERROR) << "can't get ip reg value";
    return false;
  }
  if (ips->empty()) {
    ips->push_back(ip_reg_value);
    sps->push_back(sp_reg_value);
  } else {
    // Check if the unwinder returns ip reg value as the first ip address in callstack.
    CHECK_EQ((*ips)[0], ip_reg_value);
  }
  if (collect_stat_) {
    unwinding_result_.used_time = GetSystemClock() - start_time;
    unwinding_result_.error_code = unwinder.LastErrorCode();
    unwinding_result_.error_addr = unwinder.LastErrorAddress();
    unwinding_result_.stack_start = stack_addr;
    unwinding_result_.stack_end = stack_addr + stack_size;
  }
  return true;
}

std::unique_ptr<OfflineUnwinder> OfflineUnwinder::Create(bool collect_stat) {
  return std::unique_ptr<OfflineUnwinder>(new OfflineUnwinderImpl(collect_stat));
}

}  // namespace simpleperf
