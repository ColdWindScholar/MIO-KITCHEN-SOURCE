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

#include <libgen.h>

#include <memory>

#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/strings.h>

#if defined(__ANDROID__)
#include <android-base/properties.h>
#endif

#include "command.h"
#include "environment.h"
#include "get_test_data.h"
#include "read_elf.h"
#include "test_util.h"
#include "utils.h"
#include "workload.h"

using namespace simpleperf;

static std::string testdata_dir;

#if defined(__ANDROID__)

class ScopedEnablingPerf {
 public:
  ScopedEnablingPerf() {
    prop_value_ = android::base::GetProperty("security.perf_harden", "");
    SetProp("0");
  }

  ~ScopedEnablingPerf() {
    if (!prop_value_.empty()) {
      SetProp(prop_value_);
    }
  }

 private:
  void SetProp(const std::string& value) {
    android::base::SetProperty("security.perf_harden", value);

    // Sleep one second to wait for security.perf_harden changing
    // perf_event_allow_path.
    sleep(1);
  }

  std::string prop_value_;
};

#endif  // defined(__ANDROID__)

// Detect test environment before running tests to utilize cached results for delay-sensitive
// tests.
void DetectTestEnvironment() {
#if defined(__linux__)
  IsInNativeAbi();
  HasHardwareCounter();
#endif  // defined(__linux__)
  HasPmuCounter();
  HasTracepointEvents();
}

int main(int argc, char** argv) {
  RegisterAllCommands();
  // To test profiling apps, simpleperf_unit_test needs to copy itself to the app's directory,
  // and run the binary as simpleperf executable.
  if (android::base::Basename(argv[0]) == "simpleperf") {
    return RunSimpleperfCmd(argc, argv) ? 0 : 1;
  }

  testing::InitGoogleTest(&argc, argv);
  android::base::InitLogging(argv, android::base::StderrLogger);
  android::base::LogSeverity log_severity = android::base::WARNING;
  testdata_dir = std::string(dirname(argv[0])) + "/testdata";
  for (int i = 1; i < argc; ++i) {
    if (strcmp(argv[i], "-t") == 0 && i + 1 < argc) {
      testdata_dir = argv[i + 1];
      i++;
    } else if (strcmp(argv[i], "--log") == 0) {
      if (i + 1 < argc) {
        ++i;
        if (!GetLogSeverity(argv[i], &log_severity)) {
          LOG(ERROR) << "Unknown log severity: " << argv[i];
          return 1;
        }
      } else {
        LOG(ERROR) << "Missing argument for --log option.\n";
        return 1;
      }
    }
  }
  android::base::ScopedLogSeverity severity(log_severity);

#if defined(__ANDROID__)
  // A cts test is testing if perf_event_allow_path is 3, so restore perf_harden
  // value after current test to not break that test.
  ScopedEnablingPerf scoped_enabling_perf;
#endif

  if (!::testing::GTEST_FLAG(list_tests)) {
    if (!IsDir(testdata_dir)) {
      LOG(ERROR) << "testdata wasn't found. Use \"" << argv[0] << " -t <testdata_dir>\"";
      return 1;
    }
  }
  if (!android::base::EndsWith(testdata_dir, OS_PATH_SEPARATOR)) {
    testdata_dir += OS_PATH_SEPARATOR;
  }
  LOG(INFO) << "testdata is in " << testdata_dir;
  DetectTestEnvironment();
  return RUN_ALL_TESTS();
}

std::string GetTestData(const std::string& filename) {
  return testdata_dir + filename;
}

const std::string& GetTestDataDir() {
  return testdata_dir;
}
