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

#include <gtest/gtest.h>

#include <android-base/properties.h>

#include "command.h"
#include "test_util.h"
#include "workload.h"

using namespace simpleperf;

static std::unique_ptr<Command> BootRecordCmd() {
  return CreateCommandInstance("boot-record");
}

// @CddTest = 6.1/C-0-2
TEST(cmd_boot_record, smoke) {
  TEST_REQUIRE_ROOT();
  ASSERT_TRUE(BootRecordCmd()->Run({"--enable", "-a -g --duration 1"}));
  ASSERT_EQ(android::base::GetProperty("persist.simpleperf.boot_record", ""), "-a -g --duration 1");
  // After reboot, init script will run boot-record cmd with --record. But since we can't reboot
  // the device to test the option, run it directly here.
  ASSERT_TRUE(BootRecordCmd()->Run({"--record", "-a --duration 0.001"}));
  ASSERT_TRUE(BootRecordCmd()->Run({"--disable"}));
  ASSERT_EQ(android::base::GetProperty("persist.simpleperf.boot_record", ""), "");
  ASSERT_TRUE(Workload::RunCmd({"rm", "-rf", "/data/simpleperf_boot_data"}));
}
