/*
 * Copyright (C) 2022 The Android Open Source Project
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

#include "RegEx.h"

#include <gtest/gtest.h>

using namespace simpleperf;

// @CddTest = 6.1/C-0-2
TEST(RegEx, smoke) {
  auto re = RegEx::Create("b+");
  ASSERT_EQ(re->GetPattern(), "b+");
  ASSERT_FALSE(re->Search("aaa"));
  ASSERT_TRUE(re->Search("aba"));
  ASSERT_FALSE(re->Match("aba"));
  ASSERT_TRUE(re->Match("bbb"));

  auto match = re->SearchAll("aaa");
  ASSERT_FALSE(match->IsValid());
  match = re->SearchAll("ababb");
  ASSERT_TRUE(match->IsValid());
  ASSERT_EQ(match->GetField(0), "b");
  match->MoveToNextMatch();
  ASSERT_TRUE(match->IsValid());
  ASSERT_EQ(match->GetField(0), "bb");
  match->MoveToNextMatch();
  ASSERT_FALSE(match->IsValid());

  ASSERT_EQ(re->Replace("ababb", "c").value(), "acac");
}

// @CddTest = 6.1/C-0-2
TEST(RegEx, invalid_pattern) {
  ASSERT_TRUE(RegEx::Create("?hello") == nullptr);
}
