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

#include <gtest/gtest.h>

#include "command.h"
#include "get_test_data.h"
#include "test_util.h"

using namespace simpleperf;

static std::unique_ptr<Command> DumpCmd() {
  return CreateCommandInstance("dump");
}

// @CddTest = 6.1/C-0-2
TEST(cmd_dump, record_file_option) {
  ASSERT_TRUE(DumpCmd()->Run({GetTestData("perf.data")}));
}

// @CddTest = 6.1/C-0-2
TEST(cmd_dump, input_option) {
  ASSERT_TRUE(DumpCmd()->Run({"-i", GetTestData("perf.data")}));
}

// @CddTest = 6.1/C-0-2
TEST(cmd_dump, dump_data_generated_by_linux_perf) {
  ASSERT_TRUE(DumpCmd()->Run({GetTestData(PERF_DATA_GENERATED_BY_LINUX_PERF)}));
}

// @CddTest = 6.1/C-0-2
TEST(cmd_dump, dump_callchain_records) {
  ASSERT_TRUE(DumpCmd()->Run({GetTestData(PERF_DATA_WITH_CALLCHAIN_RECORD)}));
}

// @CddTest = 6.1/C-0-2
TEST(cmd_dump, dump_callchain_of_sample_records) {
  CaptureStdout capture;
  ASSERT_TRUE(capture.Start());
  ASSERT_TRUE(DumpCmd()->Run({GetTestData(PERF_DATA_WITH_INTERPRETER_FRAMES)}));
  std::string data = capture.Finish();
  ASSERT_NE(data.find("[kernel.kallsyms][+ffffffc000086b4a]"), std::string::npos);
  ASSERT_NE(data.find("__ioctl (/system/lib64/libc.so[+70b6c])"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_dump, dump_tracepoint_fields_of_sample_records) {
  CaptureStdout capture;
  ASSERT_TRUE(capture.Start());
  ASSERT_TRUE(DumpCmd()->Run({GetTestData("perf_with_tracepoint_event.data")}));
  std::string data = capture.Finish();
  ASSERT_NE(data.find("prev_comm: sleep"), std::string::npos);

  // dump dynamic field of tracepoint events.
  ASSERT_TRUE(capture.Start());
  ASSERT_TRUE(DumpCmd()->Run({GetTestData("perf_with_tracepoint_event_dynamic_field.data")}));
  data = capture.Finish();
  ASSERT_NE(data.find("name: /sys/kernel/debug/tracing/events/kprobes/myopen/format"),
            std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_dump, etm_data) {
  CaptureStdout capture;
  ASSERT_TRUE(capture.Start());
  ASSERT_TRUE(DumpCmd()->Run({"--dump-etm", "raw,packet,element", "--symdir",
                              GetTestDataDir() + "etm", GetTestData(PERF_DATA_ETM_TEST_LOOP)}));
  std::string data = capture.Finish();
  ASSERT_NE(data.find("record aux:"), std::string::npos);
  ASSERT_NE(data.find("feature section for auxtrace:"), std::string::npos);
  // Check if we can decode etm data into instruction range elements.
  ASSERT_NE(data.find("OCSD_GEN_TRC_ELEM_INSTR_RANGE"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_dump, dump_arm_regs_recorded_in_arm64) {
  ASSERT_TRUE(DumpCmd()->Run({GetTestData("perf_with_arm_regs.data")}));
}
