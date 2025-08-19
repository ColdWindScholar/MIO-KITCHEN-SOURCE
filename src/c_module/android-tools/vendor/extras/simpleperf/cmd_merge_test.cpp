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

#include <optional>

#include <android-base/file.h>

#include "command.h"
#include "get_test_data.h"
#include "record.h"
#include "record_file.h"
#include "test_util.h"
#include "utils.h"

using namespace simpleperf;

static std::unique_ptr<Command> MergeCmd() {
  return CreateCommandInstance("merge");
}

static std::string GetReport(const std::string& record_file) {
  TemporaryFile tmpfile;
  close(tmpfile.release());
  if (!CreateCommandInstance("report")->Run({"-i", record_file, "-g", "-o", tmpfile.path})) {
    return "";
  }
  std::string data;
  if (!android::base::ReadFileToString(tmpfile.path, &data)) {
    return "";
  }
  return data;
}

// @CddTest = 6.1/C-0-2
TEST(merge_cmd, input_output_options) {
  // missing arguments
  ASSERT_FALSE(MergeCmd()->Run({}));
  // missing input files
  std::string input_file = GetTestData("perf.data");
  ASSERT_FALSE(MergeCmd()->Run({"-i", input_file}));
  // missing output file
  TemporaryFile tmpfile;
  close(tmpfile.release());
  ASSERT_FALSE(MergeCmd()->Run({"-o", tmpfile.path}));
  ASSERT_TRUE(MergeCmd()->Run({"-i", input_file, "-o", tmpfile.path}));
  // input files separated by comma
  ASSERT_TRUE(MergeCmd()->Run({"-i", input_file + "," + input_file, "-o", tmpfile.path}));
  // input files in different -i options
  ASSERT_TRUE(MergeCmd()->Run({"-i", input_file, "-i", input_file, "-o", tmpfile.path}));
}

// @CddTest = 6.1/C-0-2
TEST(merge_cmd, merge_two_files) {
  std::string input_file1 = GetTestData("perf_merge1.data");
  std::string input_file2 = GetTestData("perf_merge2.data");

  std::string report = GetReport(input_file1);
  ASSERT_NE(report.find("Samples: 27"), std::string::npos);
  ASSERT_NE(report.find("malloc"), std::string::npos);
  ASSERT_EQ(report.find("sleep_main"), std::string::npos);
  ASSERT_NE(report.find("toybox_main"), std::string::npos);

  report = GetReport(input_file2);
  ASSERT_NE(report.find("Samples: 31"), std::string::npos);
  ASSERT_EQ(report.find("malloc"), std::string::npos);
  ASSERT_NE(report.find("sleep_main"), std::string::npos);
  ASSERT_NE(report.find("toybox_main"), std::string::npos);

  TemporaryFile tmpfile;
  close(tmpfile.release());
  ASSERT_TRUE(MergeCmd()->Run({"-i", input_file1 + "," + input_file2, "-o", tmpfile.path}));
  report = GetReport(tmpfile.path);
  // sum of sample counts in input files
  ASSERT_NE(report.find("Samples: 58"), std::string::npos);
  // union of symbols in input files
  ASSERT_NE(report.find("malloc"), std::string::npos);
  ASSERT_NE(report.find("sleep_main"), std::string::npos);
  ASSERT_NE(report.find("toybox_main"), std::string::npos);
}
