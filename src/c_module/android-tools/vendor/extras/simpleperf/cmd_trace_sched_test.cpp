/*
 * Copyright (C) 2018 The Android Open Source Project
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

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#include <android-base/file.h>
#include <android-base/stringprintf.h>

#include <map>
#include <memory>
#include <thread>

#include "command.h"
#include "environment.h"
#include "event_selection_set.h"
#include "get_test_data.h"
#include "record.h"
#include "record_file.h"
#include "test_util.h"
#include "thread_tree.h"

using namespace simpleperf;
using namespace PerfFileFormat;

static std::unique_ptr<Command> TraceSchedCmd() {
  return CreateCommandInstance("trace-sched");
}

// @CddTest = 6.1/C-0-2
TEST(trace_sched_cmd, smoke) {
  TEST_IN_ROOT({ ASSERT_TRUE(TraceSchedCmd()->Run({"--duration", "1"})); });
}

// @CddTest = 6.1/C-0-2
TEST(trace_sched_cmd, report_smoke) {
  CaptureStdout capture;
  ASSERT_TRUE(capture.Start());
  ASSERT_TRUE(TraceSchedCmd()->Run(
      {"--record-file", GetTestData(PERF_DATA_SCHED_STAT_RUNTIME), "--show-threads"}));
  std::string data = capture.Finish();
  ASSERT_NE(data.find("Process  3845.961 ms  94.90%      8603  examplepurejava"),
            std::string::npos);
  ASSERT_NE(data.find("Thread   3845.961 ms  94.90%      8615  BusyThread"), std::string::npos);
  ASSERT_NE(data.find("Detect 3 spin loops in process examplepurejava (8603) thread "
                      "BusyThread (8615),\nmax rate at [326962.439095 s - 326963.442418 s], "
                      "taken 997.813 ms / 1003.323 ms (99.45%)."),
            std::string::npos);
}
