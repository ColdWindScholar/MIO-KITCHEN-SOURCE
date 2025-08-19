/*
 * Copyright (C) 2020 The Android Open Source Project
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

#include <android-base/strings.h>
#if defined(__ANDROID__)
#include <android-base/properties.h>
#endif

#include <vector>

#include "command.h"
#include "test_util.h"

using namespace simpleperf;

static std::unique_ptr<Command> MonitorCmd() {
  return CreateCommandInstance("monitor");
}

static const char* GetDefaultEvent() {
  return HasHardwareCounter() ? "cpu-cycles" : "task-clock";
}

static ::testing::AssertionResult RunMonitorCmd(std::vector<std::string> v, std::string& output) {
  bool has_event = false;
  for (auto& arg : v) {
    if (arg == "-e") {
      has_event = true;
      break;
    }
  }
  if (!has_event) {
    v.insert(v.end(), {"-e", GetDefaultEvent()});
  }

  v.insert(v.end(), {"--duration", SLEEP_SEC});

  CaptureStdout capture;
  if (!capture.Start()) {
    return ::testing::AssertionFailure() << "Unable to capture stdout";
  }
  auto result = MonitorCmd()->Run(v);
  output.append(capture.Finish());
  return (result ? ::testing::AssertionSuccess() : ::testing::AssertionFailure());
}

// @CddTest = 6.1/C-0-2
TEST(monitor_cmd, no_options) {
  std::string output;
  ASSERT_FALSE(RunMonitorCmd({}, output));
}

// @CddTest = 6.1/C-0-2
TEST(monitor_cmd, no_event) {
  ASSERT_FALSE(MonitorCmd()->Run({"-a", "--duration", "1"}));
}

// @CddTest = 6.1/C-0-2
TEST(monitor_cmd, global) {
  TEST_REQUIRE_ROOT();
  std::string output;
  ASSERT_TRUE(RunMonitorCmd({"-a"}, output));
  ASSERT_GT(output.size(), 0);
}

// @CddTest = 6.1/C-0-2
TEST(monitor_cmd, no_perf) {
  TEST_REQUIRE_ROOT();
  std::string output;
  ASSERT_TRUE(RunMonitorCmd({"-a", "--exclude-perf"}, output));
  ASSERT_GT(output.size(), 0);
}

// @CddTest = 6.1/C-0-2
TEST(monitor_cmd, with_callchain) {
  TEST_REQUIRE_ROOT();
  std::string output;
  ASSERT_TRUE(RunMonitorCmd({"-a", "-g"}, output));
  ASSERT_GT(output.size(), 0);
}

// @CddTest = 6.1/C-0-2
TEST(monitor_cmd, with_callchain_fp) {
  TEST_REQUIRE_ROOT();
  std::string output;
  ASSERT_TRUE(RunMonitorCmd({"-a", "--call-graph", "fp"}, output));
  ASSERT_GT(output.size(), 0);
}

// @CddTest = 6.1/C-0-2
TEST(monitor_cmd, with_callchain_dwarf) {
  TEST_REQUIRE_ROOT();
  std::string output;
  ASSERT_TRUE(RunMonitorCmd({"-a", "--call-graph", "dwarf,512"}, output));
  ASSERT_GT(output.size(), 0);
}

// @CddTest = 6.1/C-0-2
TEST(monitor_cmd, frequency) {
  TEST_REQUIRE_ROOT();
  std::string output;
  ASSERT_TRUE(RunMonitorCmd({"-a", "-f", "1"}, output));
}

// @CddTest = 6.1/C-0-2
TEST(monitor_cmd, count) {
  TEST_REQUIRE_ROOT();
  std::string output;
  ASSERT_TRUE(RunMonitorCmd({"-a", "-c", "10000000"}, output));
}

// @CddTest = 6.1/C-0-2
TEST(monitor_cmd, cpu_percent) {
  TEST_REQUIRE_ROOT();
  std::string output;
  ASSERT_TRUE(RunMonitorCmd({"-a", "--cpu-percent", "1"}, output));
  ASSERT_GT(output.size(), 0);
  ASSERT_FALSE(RunMonitorCmd({"-a", "--cpu-percent", "-1"}, output));
  ASSERT_FALSE(RunMonitorCmd({"-a", "--cpu-percent", "101"}, output));
}

// @CddTest = 6.1/C-0-2
TEST(monitor_cmd, record_filter_options) {
  TEST_REQUIRE_ROOT();
  std::string output;
  ASSERT_TRUE(
      RunMonitorCmd({"-a", "--exclude-pid", "1,2", "--exclude-tid", "3,4", "--exclude-process-name",
                     "processA", "--exclude-thread-name", "threadA", "--exclude-uid", "5,6"},
                    output));
  ASSERT_TRUE(
      RunMonitorCmd({"-a", "--include-pid", "1,2", "--include-tid", "3,4", "--include-process-name",
                     "processB", "--include-thread-name", "threadB", "--include-uid", "5,6"},
                    output));
}
