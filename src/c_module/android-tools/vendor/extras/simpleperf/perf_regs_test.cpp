/*
 * Copyright (C) 2021 The Android Open Source Project
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

#include <gtest/gtest.h>

using namespace simpleperf;

// @CddTest = 6.1/C-0-2
TEST(RegSet, arch) {
  ArchType arch_pairs[3][2] = {
      {ARCH_X86_32, ARCH_X86_64},
      {ARCH_ARM, ARCH_ARM64},
      {ARCH_RISCV64, ARCH_RISCV64},
  };
  for (ArchType* arch_pair : arch_pairs) {
    for (size_t i = 0; i < 2; i++) {
      ScopedCurrentArch scoped_arch(arch_pair[i]);
      RegSet reg32(PERF_SAMPLE_REGS_ABI_32, 0, nullptr);
      ASSERT_EQ(reg32.arch, arch_pair[0]) << i;
      RegSet reg64(PERF_SAMPLE_REGS_ABI_64, 0, nullptr);
      ASSERT_EQ(reg64.arch, arch_pair[1]) << i;
    }
  }
}
