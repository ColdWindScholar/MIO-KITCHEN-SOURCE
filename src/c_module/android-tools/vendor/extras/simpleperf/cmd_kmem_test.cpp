/*
 * Copyright (C) 2016 The Android Open Source Project
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

#include <android-base/file.h>
#include <android-base/strings.h>

#include <memory>

#include "command.h"
#include "get_test_data.h"
#include "record.h"
#include "record_file.h"
#include "test_util.h"

using namespace simpleperf;

static std::unique_ptr<Command> KmemCmd() {
  return CreateCommandInstance("kmem");
}

struct ReportResult {
  bool success;
  std::string content;
  std::vector<std::string> lines;
};

static void KmemReportRawFile(const std::string& perf_data,
                              const std::vector<std::string>& additional_args,
                              ReportResult* result) {
  result->success = false;
  TemporaryFile tmp_file;
  close(tmp_file.release());
  std::vector<std::string> args = {"report", "-i", perf_data, "-o", tmp_file.path};
  args.insert(args.end(), additional_args.begin(), additional_args.end());
  ASSERT_TRUE(KmemCmd()->Run(args));
  ASSERT_TRUE(android::base::ReadFileToString(tmp_file.path, &result->content));
  ASSERT_TRUE(!result->content.empty());
  std::vector<std::string> raw_lines = android::base::Split(result->content, "\n");
  result->lines.clear();
  for (const auto& line : raw_lines) {
    std::string s = android::base::Trim(line);
    if (!s.empty()) {
      result->lines.push_back(s);
    }
  }
  ASSERT_GE(result->lines.size(), 2u);
  result->success = true;
}

static void KmemReportFile(const std::string& perf_data,
                           const std::vector<std::string>& additional_args, ReportResult* result) {
  KmemReportRawFile(GetTestData(perf_data), additional_args, result);
}

#if defined(__linux__)
#include "environment.h"

static bool RunKmemRecordCmd(std::vector<std::string> v, const char* output_file = nullptr) {
  std::unique_ptr<TemporaryFile> tmpfile;
  std::string out_file;
  if (output_file != nullptr) {
    out_file = output_file;
  } else {
    tmpfile.reset(new TemporaryFile);
    close(tmpfile->release());
    out_file = tmpfile->path;
  }
  v.insert(v.begin(), "record");
  v.insert(v.end(), {"-o", out_file, "sleep", SLEEP_SEC});
  return KmemCmd()->Run(v);
}

// @CddTest = 6.1/C-0-2
TEST(kmem_cmd, record_slab) {
  TEST_IN_ROOT(ASSERT_TRUE(RunKmemRecordCmd({"--slab"})));
}

// @CddTest = 6.1/C-0-2
TEST(kmem_cmd, record_fp_callchain_sampling) {
  TEST_IN_ROOT(ASSERT_TRUE(RunKmemRecordCmd({"--slab", "-g"})));
  TEST_IN_ROOT(ASSERT_TRUE(RunKmemRecordCmd({"--slab", "--call-graph", "fp"})));
}

// @CddTest = 6.1/C-0-2
TEST(kmem_cmd, record_and_report) {
  TemporaryFile tmp_file;
  TEST_IN_ROOT({
    ASSERT_TRUE(RunKmemRecordCmd({"--slab"}, tmp_file.path));
    ReportResult result;
    KmemReportRawFile(tmp_file.path, {}, &result);
    ASSERT_TRUE(result.success);
  });
}

// @CddTest = 6.1/C-0-2
TEST(kmem_cmd, record_and_report_callgraph) {
  TemporaryFile tmp_file;
  TEST_IN_ROOT({
    ASSERT_TRUE(RunKmemRecordCmd({"--slab", "-g"}, tmp_file.path));
    ReportResult result;
    KmemReportRawFile(tmp_file.path, {"-g"}, &result);
    ASSERT_TRUE(result.success);
  });
}

#endif

// @CddTest = 6.1/C-0-2
TEST(kmem_cmd, report) {
  ReportResult result;
  KmemReportFile(PERF_DATA_WITH_KMEM_SLAB_CALLGRAPH_RECORD, {}, &result);
  ASSERT_TRUE(result.success);
  ASSERT_NE(result.content.find("kmem:kmalloc"), std::string::npos);
  ASSERT_NE(result.content.find("__alloc_skb"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(kmem_cmd, report_all_sort_options) {
  ReportResult result;
  KmemReportFile(
      PERF_DATA_WITH_KMEM_SLAB_CALLGRAPH_RECORD,
      {"--slab-sort", "hit,caller,ptr,bytes_req,bytes_alloc,fragment,gfp_flags,pingpong"}, &result);
  ASSERT_TRUE(result.success);
  ASSERT_NE(result.content.find("Ptr"), std::string::npos);
  ASSERT_NE(result.content.find("GfpFlags"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(kmem_cmd, report_callgraph) {
  ReportResult result;
  KmemReportFile(PERF_DATA_WITH_KMEM_SLAB_CALLGRAPH_RECORD, {"-g"}, &result);
  ASSERT_TRUE(result.success);
  ASSERT_NE(result.content.find("kmem:kmalloc"), std::string::npos);
  ASSERT_NE(result.content.find("__alloc_skb"), std::string::npos);
  ASSERT_NE(result.content.find("system_call_fastpath"), std::string::npos);
}
