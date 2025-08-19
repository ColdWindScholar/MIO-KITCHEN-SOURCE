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

#include <gtest/gtest.h>

#include <sys/system_properties.h>

#include "profile-extras.h"

static int dump_count = 0;
static int reset_count = 0;

extern "C" {
void __gcov_dump() {
  dump_count++;
}

void __gcov_reset() {
  reset_count++;
}
}

TEST(profile_extras, smoke) {
  dump_count = 0;
  reset_count = 0;

  ASSERT_EQ(0, dump_count);
  kill(getpid(), COVERAGE_FLUSH_SIGNAL);
  sleep(2);
  ASSERT_EQ(1, dump_count);
  ASSERT_EQ(1, reset_count);
}
