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

#include <set>
#include <unordered_map>

#include <android-base/file.h>
#include <android-base/parseint.h>
#include <android-base/strings.h>
#include <android-base/test_utils.h>

#include "RegEx.h"
#include "command.h"
#include "get_test_data.h"
#include "perf_regs.h"
#include "read_apk.h"
#include "test_util.h"

using namespace simpleperf;

static std::unique_ptr<Command> ReportCmd() {
  return CreateCommandInstance("report");
}

// @CddTest = 6.1/C-0-2
class ReportCommandTest : public ::testing::Test {
 protected:
  void Report(const std::string& perf_data,
              const std::vector<std::string>& add_args = std::vector<std::string>(),
              bool with_symfs = true) {
    ReportRaw(GetTestData(perf_data), add_args, with_symfs);
  }

  void ReportRaw(const std::string& perf_data,
                 const std::vector<std::string>& add_args = std::vector<std::string>(),
                 bool with_symfs = true) {
    success = false;
    TemporaryFile tmp_file;
    std::vector<std::string> args = {"-i", perf_data, "-o", tmp_file.path};

    if (with_symfs) {
      args.emplace_back("--symfs");
      args.emplace_back(GetTestDataDir());
    }

    args.insert(args.end(), add_args.begin(), add_args.end());
    ASSERT_TRUE(ReportCmd()->Run(args));
    ASSERT_TRUE(android::base::ReadFileToString(tmp_file.path, &content));
    ASSERT_TRUE(!content.empty());
    std::vector<std::string> raw_lines = android::base::Split(content, "\n");
    lines.clear();
    for (const auto& line : raw_lines) {
      std::string s = android::base::Trim(line);
      if (!s.empty()) {
        lines.push_back(s);
      }
    }
    ASSERT_GE(lines.size(), 2u);
    success = true;
  }

  size_t GetSampleCount() {
    auto regex = RegEx::Create(R"(Samples: (\d+))");
    auto match = regex->SearchAll(content);
    if (match->IsValid()) {
      size_t count;
      if (android::base::ParseUint(match->GetField(1), &count)) {
        return count;
      }
    }
    return 0;
  }

  std::string content;
  std::vector<std::string> lines;
  bool success;
};

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, no_option) {
  Report(PERF_DATA);
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("GlobalFunc"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, report_symbol_from_elf_file_with_mini_debug_info) {
  Report(PERF_DATA_WITH_MINI_DEBUG_INFO);
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("GlobalFunc"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, sort_option_pid) {
  Report(PERF_DATA, {"--sort", "pid"});
  ASSERT_TRUE(success);
  size_t line_index = 0;
  while (line_index < lines.size() && lines[line_index].find("Pid") == std::string::npos) {
    line_index++;
  }
  ASSERT_LT(line_index + 2, lines.size());
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, sort_option_more_than_one) {
  Report(PERF_DATA, {"--sort", "comm,pid,dso,symbol"});
  ASSERT_TRUE(success);
  size_t line_index = 0;
  while (line_index < lines.size() && lines[line_index].find("Overhead") == std::string::npos) {
    line_index++;
  }
  ASSERT_LT(line_index + 1, lines.size());
  ASSERT_NE(lines[line_index].find("Command"), std::string::npos);
  ASSERT_NE(lines[line_index].find("Pid"), std::string::npos);
  ASSERT_NE(lines[line_index].find("Shared Object"), std::string::npos);
  ASSERT_NE(lines[line_index].find("Symbol"), std::string::npos);
  ASSERT_EQ(lines[line_index].find("Tid"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, children_option) {
  Report(CALLGRAPH_FP_PERF_DATA, {"--children", "--sort", "symbol"});
  ASSERT_TRUE(success);
  std::unordered_map<std::string, std::pair<double, double>> map;
  for (size_t i = 0; i < lines.size(); ++i) {
    char name[1024];
    std::pair<double, double> pair;
    if (sscanf(lines[i].c_str(), "%lf%%%lf%%%s", &pair.first, &pair.second, name) == 3) {
      map.insert(std::make_pair(name, pair));
    }
  }
  ASSERT_NE(map.find("GlobalFunc"), map.end());
  ASSERT_NE(map.find("main"), map.end());
  auto func_pair = map["GlobalFunc"];
  auto main_pair = map["main"];
  ASSERT_GE(main_pair.first, func_pair.first);
  ASSERT_GE(func_pair.first, func_pair.second);
  ASSERT_GE(func_pair.second, main_pair.second);
}

static bool CheckCalleeMode(std::vector<std::string>& lines) {
  bool found = false;
  for (size_t i = 0; i + 1 < lines.size(); ++i) {
    if (lines[i].find("GlobalFunc") != std::string::npos &&
        lines[i + 1].find("main") != std::string::npos) {
      found = true;
      break;
    }
  }
  return found;
}

static bool CheckCallerMode(std::vector<std::string>& lines) {
  bool found = false;
  for (size_t i = 0; i + 1 < lines.size(); ++i) {
    if (lines[i].find("main") != std::string::npos &&
        lines[i + 1].find("GlobalFunc") != std::string::npos) {
      found = true;
      break;
    }
  }
  return found;
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, callgraph_option) {
  Report(CALLGRAPH_FP_PERF_DATA, {"-g"});
  ASSERT_TRUE(success);
  ASSERT_TRUE(CheckCallerMode(lines));
  Report(CALLGRAPH_FP_PERF_DATA, {"-g", "callee"});
  ASSERT_TRUE(success);
  ASSERT_TRUE(CheckCalleeMode(lines));
  Report(CALLGRAPH_FP_PERF_DATA, {"-g", "caller"});
  ASSERT_TRUE(success);
  ASSERT_TRUE(CheckCallerMode(lines));
}

static bool AllItemsWithString(std::vector<std::string>& lines,
                               const std::vector<std::string>& strs) {
  size_t line_index = 0;
  while (line_index < lines.size() && lines[line_index].find("Overhead") == std::string::npos) {
    line_index++;
  }
  if (line_index == lines.size() || line_index + 1 == lines.size()) {
    return false;
  }
  line_index++;
  for (; line_index < lines.size(); ++line_index) {
    bool exist = false;
    for (auto& s : strs) {
      if (lines[line_index].find(s) != std::string::npos) {
        exist = true;
        break;
      }
    }
    if (!exist) {
      return false;
    }
  }
  return true;
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, pid_filter_option) {
  Report(PERF_DATA_WITH_MULTIPLE_PIDS_AND_TIDS, {"--sort", "pid"});
  ASSERT_TRUE(success);
  ASSERT_FALSE(AllItemsWithString(lines, {"17441"}));
  ASSERT_FALSE(AllItemsWithString(lines, {"17441", "17443"}));
  Report(PERF_DATA_WITH_MULTIPLE_PIDS_AND_TIDS, {"--sort", "pid", "--pids", "17441"});
  ASSERT_TRUE(success);
  ASSERT_TRUE(AllItemsWithString(lines, {"17441"}));
  Report(PERF_DATA_WITH_MULTIPLE_PIDS_AND_TIDS, {"--sort", "pid", "--pids", "17441,17443"});
  ASSERT_TRUE(success);
  ASSERT_TRUE(AllItemsWithString(lines, {"17441", "17443"}));

  // Test that --pids option is not the same as --tids option.
  // Thread 17445 and 17441 are in process 17441.
  Report(PERF_DATA_WITH_MULTIPLE_PIDS_AND_TIDS, {"--sort", "tid", "--pids", "17441"});
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("17441"), std::string::npos);
  ASSERT_NE(content.find("17445"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, wrong_pid_filter_option) {
  ASSERT_EXIT(
      {
        Report(PERF_DATA_WITH_MULTIPLE_PIDS_AND_TIDS, {"--pids", "2,bogus"});
        exit(success ? 0 : 1);
      },
      testing::ExitedWithCode(1), "invalid pid: bogus");
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, tid_filter_option) {
  Report(PERF_DATA_WITH_MULTIPLE_PIDS_AND_TIDS, {"--sort", "tid"});
  ASSERT_TRUE(success);
  ASSERT_FALSE(AllItemsWithString(lines, {"17441"}));
  ASSERT_FALSE(AllItemsWithString(lines, {"17441", "17445"}));
  Report(PERF_DATA_WITH_MULTIPLE_PIDS_AND_TIDS, {"--sort", "tid", "--tids", "17441"});
  ASSERT_TRUE(success);
  ASSERT_TRUE(AllItemsWithString(lines, {"17441"}));
  Report(PERF_DATA_WITH_MULTIPLE_PIDS_AND_TIDS, {"--sort", "tid", "--tids", "17441,17445"});
  ASSERT_TRUE(success);
  ASSERT_TRUE(AllItemsWithString(lines, {"17441", "17445"}));
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, wrong_tid_filter_option) {
  ASSERT_EXIT(
      {
        Report(PERF_DATA_WITH_MULTIPLE_PIDS_AND_TIDS, {"--tids", "2,bogus"});
        exit(success ? 0 : 1);
      },
      testing::ExitedWithCode(1), "Invalid tid 'bogus'");
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, comm_filter_option) {
  Report(PERF_DATA, {"--sort", "comm"});
  ASSERT_TRUE(success);
  ASSERT_FALSE(AllItemsWithString(lines, {"t1"}));
  ASSERT_FALSE(AllItemsWithString(lines, {"t1", "t2"}));
  Report(PERF_DATA, {"--sort", "comm", "--comms", "t1"});
  ASSERT_TRUE(success);
  ASSERT_TRUE(AllItemsWithString(lines, {"t1"}));
  Report(PERF_DATA, {"--sort", "comm", "--comms", "t1,t2"});
  ASSERT_TRUE(success);
  ASSERT_TRUE(AllItemsWithString(lines, {"t1", "t2"}));
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, dso_filter_option) {
  Report(PERF_DATA, {"--sort", "dso"});
  ASSERT_TRUE(success);
  ASSERT_FALSE(AllItemsWithString(lines, {"/t1"}));
  ASSERT_FALSE(AllItemsWithString(lines, {"/t1", "/t2"}));
  Report(PERF_DATA, {"--sort", "dso", "--dsos", "/t1"});
  ASSERT_TRUE(success);
  ASSERT_TRUE(AllItemsWithString(lines, {"/t1"}));
  Report(PERF_DATA, {"--sort", "dso", "--dsos", "/t1,/t2"});
  ASSERT_TRUE(success);
  ASSERT_TRUE(AllItemsWithString(lines, {"/t1", "/t2"}));
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, symbol_filter_option) {
  Report(PERF_DATA_WITH_SYMBOLS, {"--sort", "symbol"});
  ASSERT_TRUE(success);
  ASSERT_FALSE(AllItemsWithString(lines, {"func2(int, int)"}));
  ASSERT_FALSE(AllItemsWithString(lines, {"main", "func2(int, int)"}));
  Report(PERF_DATA_WITH_SYMBOLS, {"--sort", "symbol", "--symbols", "func2(int, int)"});
  ASSERT_TRUE(success);
  ASSERT_TRUE(AllItemsWithString(lines, {"func2(int, int)"}));
  Report(PERF_DATA_WITH_SYMBOLS, {"--sort", "symbol", "--symbols", "main;func2(int, int)"});
  ASSERT_TRUE(success);
  ASSERT_TRUE(AllItemsWithString(lines, {"main", "func2(int, int)"}));
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, dso_symbol_filter_with_children_option) {
  // dso and symbol filter should filter different layers of the callchain separately.
  Report("perf_display_bitmaps.data", {"--dsos", "/apex/com.android.runtime/lib64/libart.so",
                                       "--children", "--raw-period", "--sort", "dso"});
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("63500000  43250000  /apex/com.android.runtime/lib64/libart.so"),
            std::string::npos);

  Report("perf_display_bitmaps.data",
         {"--symbols", "MterpInvokeVirtual", "--children", "--raw-period", "--sort", "symbol"});
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("51500000  2500000  MterpInvokeVirtual"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, use_branch_address) {
  Report(BRANCH_PERF_DATA, {"-b", "--sort", "symbol_from,symbol_to"});
  std::set<std::pair<std::string, std::string>> hit_set;
  bool after_overhead = false;
  for (const auto& line : lines) {
    if (!after_overhead && line.find("Overhead") != std::string::npos) {
      after_overhead = true;
    } else if (after_overhead) {
      char from[80];
      char to[80];
      if (sscanf(line.c_str(), "%*f%%%s%s", from, to) == 2) {
        hit_set.insert(std::make_pair<std::string, std::string>(from, to));
      }
    }
  }
  ASSERT_NE(hit_set.find(std::make_pair<std::string, std::string>("GlobalFunc", "CalledFunc")),
            hit_set.end());
  ASSERT_NE(hit_set.find(std::make_pair<std::string, std::string>("CalledFunc", "GlobalFunc")),
            hit_set.end());
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, report_symbols_of_nativelib_in_apk) {
  Report(NATIVELIB_IN_APK_PERF_DATA);
  ASSERT_TRUE(success);
  ASSERT_NE(content.find(GetUrlInApk(APK_FILE, NATIVELIB_IN_APK)), std::string::npos);
  ASSERT_NE(content.find("Func2"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, report_more_than_one_event_types) {
  Report(PERF_DATA_WITH_TWO_EVENT_TYPES);
  ASSERT_TRUE(success);
  size_t pos = 0;
  ASSERT_NE(pos = content.find("cpu-cycles", pos), std::string::npos);
  ASSERT_NE(pos = content.find("Samples:", pos), std::string::npos);
  ASSERT_NE(pos = content.find("cpu-clock", pos), std::string::npos);
  ASSERT_NE(pos = content.find("Samples:", pos), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, report_kernel_symbol) {
  Report(PERF_DATA_WITH_KERNEL_SYMBOL);
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("perf_event_aux"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, report_dumped_symbols) {
  Report(PERF_DATA_WITH_SYMBOLS);
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("main"), std::string::npos);
  Report(PERF_DATA_WITH_SYMBOLS_FOR_NONZERO_MINVADDR_DSO);
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("memcpy"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, report_dumped_symbols_with_symfs_dir) {
  // Check if we can report symbols when they appear both in perf.data and symfs dir.
  Report(PERF_DATA_WITH_SYMBOLS, {"--symfs", GetTestDataDir()});
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("main"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, report_dumped_symbols_with_symdir) {
  // Check if we can report symbols by specifying symdir.
  Report(PERF_DATA, {"--symdir", GetTestDataDir()}, false);
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("GlobalFunc"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, report_without_symfs_dir) {
  TemporaryFile tmpfile;
  ASSERT_TRUE(ReportCmd()->Run({"-i", GetTestData(PERF_DATA), "-o", tmpfile.path}));
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, report_sort_vaddr_in_file) {
  Report(PERF_DATA, {"--sort", "vaddr_in_file"});
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("VaddrInFile"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, check_build_id) {
  Report(PERF_DATA_FOR_BUILD_ID_CHECK, {"--symfs", GetTestData(CORRECT_SYMFS_FOR_BUILD_ID_CHECK)});
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("main"), std::string::npos);
  ASSERT_EXIT(
      {
        Report(PERF_DATA_FOR_BUILD_ID_CHECK,
               {"--symfs", GetTestData(WRONG_SYMFS_FOR_BUILD_ID_CHECK)});
        if (!success) {
          exit(1);
        }
        if (content.find("main") != std::string::npos) {
          exit(2);
        }
        exit(0);
      },
      testing::ExitedWithCode(0), "failed to read symbols from /elf_for_build_id_check");
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, no_show_ip_option) {
  Report(PERF_DATA);
  ASSERT_TRUE(success);
  ASSERT_EQ(content.find("unknown"), std::string::npos);
  Report(PERF_DATA, {"--no-show-ip"});
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("unknown"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, read_elf_file_warning) {
  ASSERT_EXIT(
      {
        Report(PERF_DATA, {"--symfs", GetTestData(SYMFS_FOR_READ_ELF_FILE_WARNING)});
        if (!success) {
          exit(1);
        }
        if (content.find("GlobalFunc") != std::string::npos) {
          exit(2);
        }
        exit(0);
      },
      testing::ExitedWithCode(0), "failed to read symbols from /elf: File not found");
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, report_data_generated_by_linux_perf) {
  Report(PERF_DATA_GENERATED_BY_LINUX_PERF);
  ASSERT_TRUE(success);
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, max_stack_and_percent_limit_option) {
  Report(PERF_DATA_MAX_STACK_AND_PERCENT_LIMIT, {"-g"});
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("89.03"), std::string::npos);

  Report(PERF_DATA_MAX_STACK_AND_PERCENT_LIMIT, {"-g", "--max-stack", "0"});
  ASSERT_TRUE(success);
  ASSERT_EQ(content.find("89.03"), std::string::npos);
  Report(PERF_DATA_MAX_STACK_AND_PERCENT_LIMIT, {"-g", "--max-stack", "2"});
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("89.03"), std::string::npos);

  Report(PERF_DATA_MAX_STACK_AND_PERCENT_LIMIT, {"-g", "--percent-limit", "90"});
  ASSERT_TRUE(success);
  ASSERT_EQ(content.find("89.03"), std::string::npos);
  Report(PERF_DATA_MAX_STACK_AND_PERCENT_LIMIT, {"-g", "--percent-limit", "70"});
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("89.03"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, percent_limit_option) {
  Report(PERF_DATA);
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("7.70%"), std::string::npos);
  ASSERT_NE(content.find("3.23%"), std::string::npos);
  Report(PERF_DATA, {"--percent-limit", "3.24"});
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("7.70%"), std::string::npos);
  ASSERT_EQ(content.find("3.23%"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, kallsyms_option) {
  Report(PERF_DATA, {"--kallsyms", GetTestData("kallsyms")});
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("FakeKernelSymbol"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, invalid_perf_data) {
  ASSERT_FALSE(ReportCmd()->Run({"-i", GetTestData(INVALID_PERF_DATA)}));
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, raw_period_option) {
  Report(PERF_DATA, {"--raw-period"});
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("GlobalFunc"), std::string::npos);
  ASSERT_EQ(content.find('%'), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, full_callgraph_option) {
  Report(CALLGRAPH_FP_PERF_DATA, {"-g"});
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("skipped in brief callgraph mode"), std::string::npos);
  Report(CALLGRAPH_FP_PERF_DATA, {"-g", "--full-callgraph"});
  ASSERT_TRUE(success);
  ASSERT_EQ(content.find("skipped in brief callgraph mode"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, report_offcpu_time) {
  Report(PERF_DATA_WITH_TRACE_OFFCPU, {"--children"});
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("Time in ns"), std::string::npos);
  bool found = false;
  for (auto& line : lines) {
    if (line.find("SleepFunction") != std::string::npos) {
      ASSERT_NE(line.find("38.76%"), std::string::npos);
      found = true;
      break;
    }
  }
  ASSERT_TRUE(found);
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, report_big_trace_data) {
  Report(PERF_DATA_WITH_BIG_TRACE_DATA);
  ASSERT_TRUE(success);
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, csv_option) {
  Report(PERF_DATA, {"--csv"});
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("EventCount,EventName"), std::string::npos);

  Report(CALLGRAPH_FP_PERF_DATA, {"--children", "--csv"});
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("AccEventCount,SelfEventCount,EventName"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, csv_separator_option) {
  Report(PERF_DATA, {"--csv", "--csv-separator", ";"});
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("EventCount;EventName"), std::string::npos);
  ASSERT_NE(content.find(";cpu-cycles"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, dso_path_for_jit_cache) {
  Report("perf_with_jit_symbol.data", {"--sort", "dso"});
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("[JIT app cache]"), std::string::npos);

  // Check if we can filter dso by "[JIT app cache]".
  Report("perf_with_jit_symbol.data", {"--dsos", "[JIT app cache]"});
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("[JIT app cache]"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, generic_jit_symbols) {
  Report("perf_with_generic_git_symbols.data", {"--sort", "symbol"});
  ASSERT_TRUE(success);
  ASSERT_NE(std::string::npos, content.find("generic_jit_symbol_one"));
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, cpu_option) {
  Report("perf.data");
  ASSERT_TRUE(success);
  ASSERT_EQ(2409, GetSampleCount());
  Report("perf.data", {"--cpu", "2"});
  ASSERT_TRUE(success);
  ASSERT_EQ(603, GetSampleCount());
  Report("perf.data", {"--cpu", "2-6,16"});
  ASSERT_TRUE(success);
  ASSERT_EQ(1806, GetSampleCount());
  Report("perf.data", {"--cpu", "2-6", "--cpu", "16"});
  ASSERT_TRUE(success);
  ASSERT_EQ(1806, GetSampleCount());
  ASSERT_FALSE(ReportCmd()->Run({"-i", GetTestData("perf.data"), "--cpu", "-2"}));
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, print_event_count_option) {
  // Report record file not recorded with --add-counter.
  Report("perf.data", {"--print-event-count"});
  ASSERT_TRUE(success);
  ASSERT_NE(content.find("EventCount"), std::string::npos);
  ASSERT_TRUE(
      RegEx::Create(R"(325005586\s+elf\s+26083\s+26083\s+/elf\s+GlobalFunc)")->Search(content));

  // Report record file recorded with --add-counter.
  const std::string record_file = "perf_with_add_counter.data";
  Report(record_file, {"--print-event-count"});
  ASSERT_TRUE(success);
  ASSERT_TRUE(RegEx::Create(R"(EventCount_cpu-cycles\s+EventCount_instructions)")->Search(content));
  ASSERT_TRUE(
      RegEx::Create(R"(175099\s+140443\s+sleep\s+689664\s+689664.+_dl_addr)")->Search(content));

  // Report accumulated event counts.
  Report(record_file, {"--print-event-count", "--children"});
  ASSERT_TRUE(success);
  ASSERT_TRUE(
      RegEx::Create(
          R"(AccEventCount_cpu-cycles\s+SelfEventCount_cpu-cycles\s+AccEventCount_instructions\s+)"
          R"(SelfEventCount_instructions)")
          ->Search(content));
  ASSERT_TRUE(
      RegEx::Create(R"(175099\s+175099\s+140443\s+140443\s+sleep\s+689664\s+689664.+_dl_addr)")
          ->Search(content));
  ASSERT_TRUE(
      RegEx::Create(R"(366116\s+0\s+297474\s+0\s+sleep\s+689664\s+689664.+__libc_start_main)")
          ->Search(content));
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, exclude_include_pid_options) {
  Report(PERF_DATA_WITH_MULTIPLE_PIDS_AND_TIDS, {"--sort", "pid", "--exclude-pid", "17441"});
  ASSERT_TRUE(success);
  ASSERT_TRUE(AllItemsWithString(lines, {"17443", "17444"}));
  Report(PERF_DATA_WITH_MULTIPLE_PIDS_AND_TIDS, {"--sort", "pid", "--include-pid", "17441"});
  ASSERT_TRUE(success);
  ASSERT_TRUE(AllItemsWithString(lines, {"17441"}));
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, exclude_include_tid_options) {
  Report(PERF_DATA_WITH_MULTIPLE_PIDS_AND_TIDS,
         {"--sort", "tid", "--exclude-tid", "17441,17443,17444"});
  ASSERT_TRUE(success);
  ASSERT_TRUE(AllItemsWithString(lines, {"17445", "17446", "17447"}));
  Report(PERF_DATA_WITH_MULTIPLE_PIDS_AND_TIDS,
         {"--sort", "tid", "--include-tid", "17441,17443,17444"});
  ASSERT_TRUE(success);
  ASSERT_TRUE(AllItemsWithString(lines, {"17441", "17443", "17444"}));
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, exclude_include_process_name_options) {
  Report(PERF_DATA_WITH_MULTIPLE_PIDS_AND_TIDS, {"--sort", "comm", "--exclude-process-name", "t1"});
  ASSERT_TRUE(success);
  ASSERT_TRUE(AllItemsWithString(lines, {"simpleperf"}));
  Report(PERF_DATA_WITH_MULTIPLE_PIDS_AND_TIDS, {"--sort", "comm", "--include-process-name", "t1"});
  ASSERT_TRUE(success);
  ASSERT_TRUE(AllItemsWithString(lines, {"t1"}));
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, exclude_include_thread_name_options) {
  Report(PERF_DATA_WITH_MULTIPLE_PIDS_AND_TIDS, {"--sort", "comm", "--exclude-thread-name", "t1"});
  ASSERT_TRUE(success);
  ASSERT_TRUE(AllItemsWithString(lines, {"simpleperf"}));
  Report(PERF_DATA_WITH_MULTIPLE_PIDS_AND_TIDS, {"--sort", "comm", "--include-thread-name", "t1"});
  ASSERT_TRUE(success);
  ASSERT_TRUE(AllItemsWithString(lines, {"t1"}));
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, filter_file_option) {
  std::string filter_data =
      "GLOBAL_BEGIN 684943449406175\n"
      "GLOBAL_END 684943449406176";
  TemporaryFile tmpfile;
  ASSERT_TRUE(android::base::WriteStringToFd(filter_data, tmpfile.fd));
  Report("perf_display_bitmaps.data", {"--filter-file", tmpfile.path});
  ASSERT_TRUE(success);
  ASSERT_EQ(GetSampleCount(), 1);

  // PERF_DATA uses clock perf, which doesn't match the default clock in filter data.
  CapturedStderr capture;
  ASSERT_FALSE(ReportCmd()->Run({"-i", GetTestData(PERF_DATA), "--filter-file", tmpfile.path}));
  capture.Stop();
  ASSERT_NE(capture.str().find("doesn't match clock used in time filter"), std::string::npos);
}

#if defined(__linux__)
#include "event_selection_set.h"

static std::unique_ptr<Command> RecordCmd() {
  return CreateCommandInstance("record");
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, dwarf_callgraph) {
  TEST_REQUIRE_HW_COUNTER();
  OMIT_TEST_ON_NON_NATIVE_ABIS();
  ASSERT_TRUE(IsDwarfCallChainSamplingSupported());
  std::vector<std::unique_ptr<Workload>> workloads;
  CreateProcesses(1, &workloads);
  std::string pid = std::to_string(workloads[0]->GetPid());
  TemporaryFile tmp_file;
  ASSERT_TRUE(RecordCmd()->Run({"-p", pid, "-g", "-o", tmp_file.path, "sleep", SLEEP_SEC}));
  ReportRaw(tmp_file.path, {"-g"});
  ASSERT_TRUE(success);
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, report_dwarf_callgraph_of_nativelib_in_apk) {
  Report(NATIVELIB_IN_APK_PERF_DATA, {"-g"});
  ASSERT_NE(content.find(GetUrlInApk(APK_FILE, NATIVELIB_IN_APK)), std::string::npos);
  ASSERT_NE(content.find("Func2"), std::string::npos);
  ASSERT_NE(content.find("Func1"), std::string::npos);
  ASSERT_NE(content.find("GlobalFunc"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST_F(ReportCommandTest, exclude_kernel_callchain) {
  TEST_REQUIRE_HW_COUNTER();
  TEST_REQUIRE_HOST_ROOT();
  OMIT_TEST_ON_NON_NATIVE_ABIS();
  std::vector<std::unique_ptr<Workload>> workloads;
  CreateProcesses(1, &workloads);
  std::string pid = std::to_string(workloads[0]->GetPid());
  TemporaryFile tmpfile;
  ASSERT_TRUE(RecordCmd()->Run({"--trace-offcpu", "-e", "cpu-clock:u", "-p", pid, "--duration", "2",
                                "-o", tmpfile.path, "-g"}));
  ReportRaw(tmpfile.path, {"-g"});
  ASSERT_TRUE(success);
  ASSERT_EQ(content.find("[kernel.kallsyms]"), std::string::npos);
}

#endif
