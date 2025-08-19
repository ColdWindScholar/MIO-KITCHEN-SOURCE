/*
 * Copyright (C) 2023 The Android Open Source Project
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

#include <gtest/gtest.h>

#include "BranchListFile.h"

using namespace simpleperf;

// @CddTest = 6.1/C-0-2
TEST(BranchListFile, etm_branch_to_proto_string) {
  std::vector<bool> branch;
  for (size_t i = 0; i < 100; i++) {
    branch.push_back(i % 2 == 0);
    std::string s = ETMBranchToProtoString(branch);
    for (size_t j = 0; j <= i; j++) {
      bool b = s[j >> 3] & (1 << (j & 7));
      ASSERT_EQ(b, branch[j]);
    }
    std::vector<bool> branch2 = ProtoStringToETMBranch(s, branch.size());
    ASSERT_EQ(branch, branch2);
  }
}
