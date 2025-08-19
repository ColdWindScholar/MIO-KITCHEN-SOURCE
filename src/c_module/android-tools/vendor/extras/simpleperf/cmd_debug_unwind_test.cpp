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

#include <unistd.h>

#include <memory>
#include <string>
#include <vector>

#include <android-base/file.h>

#include "command.h"
#include "get_test_data.h"
#include "record_file.h"
#include "test_util.h"

using namespace simpleperf;

static std::unique_ptr<Command> DebugUnwindCmd() {
  return CreateCommandInstance("debug-unwind");
}

// @CddTest = 6.1/C-0-2
TEST(cmd_debug_unwind, unwind_sample_option) {
  std::string input_data = GetTestData(PERF_DATA_NO_UNWIND);
  CaptureStdout capture;

  ASSERT_TRUE(capture.Start());
  ASSERT_TRUE(DebugUnwindCmd()->Run({"-i", input_data, "--unwind-sample"}));
  ASSERT_NE(capture.Finish().find("sample_time: 1516379654300997"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_debug_unwind, sample_time_option) {
  std::string input_data = GetTestData(PERF_DATA_NO_UNWIND);
  CaptureStdout capture;

  ASSERT_TRUE(capture.Start());
  ASSERT_TRUE(DebugUnwindCmd()->Run({"-i", input_data, "--unwind-sample", "--sample-time",
                                     "1516379654300997", "--sample-time",
                                     "1516379654363914,1516379655959122"}));
  std::string output = capture.Finish();
  ASSERT_NE(output.find("sample_time: 1516379654300997"), std::string::npos);
  ASSERT_NE(output.find("sample_time: 1516379654363914"), std::string::npos);
  ASSERT_NE(output.find("sample_time: 1516379655959122"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_debug_unwind, output_option) {
  std::string input_data = GetTestData(PERF_DATA_NO_UNWIND);
  TemporaryFile tmpfile;
  close(tmpfile.release());
  ASSERT_TRUE(DebugUnwindCmd()->Run({"-i", input_data, "--unwind-sample", "--sample-time",
                                     "1516379654300997", "-o", tmpfile.path}));
  std::string output;
  ASSERT_TRUE(android::base::ReadFileToString(tmpfile.path, &output));
  ASSERT_NE(output.find("sample_time: 1516379654300997"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_debug_unwind, symfs_option) {
  std::string input_data = GetTestData(NATIVELIB_IN_APK_PERF_DATA);
  CaptureStdout capture;
  ASSERT_TRUE(capture.Start());
  ASSERT_TRUE(DebugUnwindCmd()->Run({"-i", input_data, "--symfs", GetTestDataDir(),
                                     "--unwind-sample", "--sample-time", "500329355223"}));
  ASSERT_NE(capture.Finish().find(
                "dso_4: /data/app/com.example.hellojni-1/base.apk!/lib/arm64-v8a/libhello-jni.so"),
            std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_debug_unwind, unwind_with_ip_zero_in_callchain) {
  CaptureStdout capture;
  ASSERT_TRUE(capture.Start());
  ASSERT_TRUE(DebugUnwindCmd()->Run({"-i", GetTestData(PERF_DATA_WITH_IP_ZERO_IN_CALLCHAIN),
                                     "--unwind-sample", "--sample-time", "152526249937103"}));
  ASSERT_NE(capture.Finish().find("sample_time: 152526249937103"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_debug_unwind, unwind_embedded_lib_in_apk) {
  // Check if we can unwind through a native library embedded in an apk. In the profiling data
  // file, there is a sample with ip address pointing to
  // /data/app/simpleperf.demo.cpp_api/base.apk!/lib/arm64-v8a/libnative-lib.so.
  // If unwound successfully, it can reach a function in libc.so.
  CaptureStdout capture;
  ASSERT_TRUE(capture.Start());
  ASSERT_TRUE(DebugUnwindCmd()->Run({"-i", GetTestData("perf_unwind_embedded_lib_in_apk.data"),
                                     "--symfs", GetTestDataDir(), "--unwind-sample",
                                     "--sample-time", "20345907755421"}));
  std::string output = capture.Finish();
  ASSERT_NE(
      output.find(
          "dso_1: /data/app/simpleperf.demo.cpp_api/base.apk!/lib/arm64-v8a/libnative-lib.so"),
      std::string::npos)
      << output;
  ASSERT_NE(output.find("dso_2: /bionic/lib64/libc.so"), std::string::npos) << output;
}

// @CddTest = 6.1/C-0-2
TEST(cmd_debug_unwind, unwind_sample_in_unwinding_debug_info_file) {
  CaptureStdout capture;
  ASSERT_TRUE(capture.Start());
  ASSERT_TRUE(DebugUnwindCmd()->Run(
      {"-i", GetTestData("perf_with_failed_unwinding_debug_info.data"), "--unwind-sample"}));
  std::string output = capture.Finish();
  ASSERT_NE(output.find("symbol_5: android.os.Handler.post"), std::string::npos) << output;
}

// @CddTest = 6.1/C-0-2
TEST(cmd_debug_unwind, skip_sample_print_option) {
  std::string input_data = GetTestData(PERF_DATA_NO_UNWIND);
  CaptureStdout capture;

  ASSERT_TRUE(capture.Start());
  ASSERT_TRUE(DebugUnwindCmd()->Run({"-i", input_data, "--unwind-sample", "--skip-sample-print"}));

  std::string output = capture.Finish();
  ASSERT_EQ(output.find("sample_time:"), std::string::npos);
  ASSERT_NE(output.find("unwinding_sample_count: 8"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_debug_unwind, generate_test_file) {
  TemporaryFile tmpfile;
  close(tmpfile.release());
  ASSERT_TRUE(DebugUnwindCmd()->Run(
      {"-i", GetTestData("perf_with_failed_unwinding_debug_info.data"), "--generate-test-file",
       "--sample-time", "626968783364202", "-o", tmpfile.path, "--keep-binaries-in-test-file",
       "perf.data_jit_app_cache:255984-259968,perf.data_jit_app_cache:280144-283632"}));

  CaptureStdout capture;
  ASSERT_TRUE(capture.Start());
  ASSERT_TRUE(DebugUnwindCmd()->Run({"-i", tmpfile.path, "--unwind-sample"}));
  std::string output = capture.Finish();
  ASSERT_NE(output.find("symbol_2: android.os.Handler.enqueueMessage"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_debug_unwind, generate_test_file_with_build_id) {
  TemporaryFile tmpfile;
  close(tmpfile.release());
  ASSERT_TRUE(DebugUnwindCmd()->Run({"-i", GetTestData("perf_display_bitmaps.data"),
                                     "--generate-test-file", "--sample-time", "684943450156904",
                                     "-o", tmpfile.path, "--keep-binaries-in-test-file",
                                     "/apex/com.android.runtime/lib64/bionic/libc.so"}));
  auto reader = RecordFileReader::CreateInstance(tmpfile.path);
  ASSERT_TRUE(reader);
  auto build_ids = reader->ReadBuildIdFeature();
  ASSERT_EQ(build_ids.size(), 1);
  ASSERT_STREQ(build_ids[0].filename, "/apex/com.android.runtime/lib64/bionic/libc.so");
}

// @CddTest = 6.1/C-0-2
TEST(cmd_debug_unwind, generate_report) {
  TemporaryFile tmpfile;
  close(tmpfile.release());
  ASSERT_TRUE(
      DebugUnwindCmd()->Run({"-i", GetTestData("perf_with_failed_unwinding_debug_info.data"),
                             "--generate-report", "-o", tmpfile.path}));
  std::string output;
  ASSERT_TRUE(android::base::ReadFileToString(tmpfile.path, &output));
  ASSERT_NE(output.find("unwinding_error_code: 4"), std::string::npos);
  ASSERT_NE(output.find("symbol_2: android.os.Handler.enqueueMessage"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_debug_unwind, unwind_sample_for_small_map_range) {
  CaptureStdout capture;
  ASSERT_TRUE(capture.Start());
  ASSERT_TRUE(DebugUnwindCmd()->Run(
      {"-i", GetTestData("debug_unwind_small_map_range.data"), "--unwind-sample"}));
  std::string output = capture.Finish();
  ASSERT_NE(output.find("dso_3: /apex/com.android.art/lib64/libart.so"), std::string::npos)
      << output;
}
