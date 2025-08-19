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

#include "RegEx.h"
#include "command.h"
#include "get_test_data.h"

using namespace simpleperf;

static std::unique_ptr<Command> ReportSampleCmd() {
  return CreateCommandInstance("report-sample");
}

// @CddTest = 6.1/C-0-2
TEST(cmd_report_sample, text) {
  ASSERT_TRUE(ReportSampleCmd()->Run({"-i", GetTestData(PERF_DATA_WITH_SYMBOLS)}));
}

// @CddTest = 6.1/C-0-2
TEST(cmd_report_sample, output_option) {
  TemporaryFile tmpfile;
  ASSERT_TRUE(
      ReportSampleCmd()->Run({"-i", GetTestData(PERF_DATA_WITH_SYMBOLS), "-o", tmpfile.path}));
}

// @CddTest = 6.1/C-0-2
TEST(cmd_report_sample, show_callchain_option) {
  TemporaryFile tmpfile;
  ASSERT_TRUE(ReportSampleCmd()->Run(
      {"-i", GetTestData(CALLGRAPH_FP_PERF_DATA), "-o", tmpfile.path, "--show-callchain"}));
}

static void GetProtobufReport(const std::string& test_data_file, std::string* protobuf_report,
                              const std::vector<std::string>& extra_args = {}) {
  TemporaryFile tmpfile;
  TemporaryFile tmpfile2;
  std::vector<std::string> args = {"-i", GetTestData(test_data_file), "-o", tmpfile.path,
                                   "--protobuf"};
  args.insert(args.end(), extra_args.begin(), extra_args.end());
  ASSERT_TRUE(ReportSampleCmd()->Run(args));
  ASSERT_TRUE(
      ReportSampleCmd()->Run({"--dump-protobuf-report", tmpfile.path, "-o", tmpfile2.path}));
  ASSERT_TRUE(android::base::ReadFileToString(tmpfile2.path, protobuf_report));
}

// @CddTest = 6.1/C-0-2
TEST(cmd_report_sample, protobuf_option) {
  std::string data;
  GetProtobufReport(PERF_DATA_WITH_SYMBOLS, &data);
  ASSERT_NE(data.find("magic: SIMPLEPERF"), std::string::npos);
  ASSERT_NE(data.find("version: 1"), std::string::npos);
  ASSERT_NE(data.find("file:"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_report_sample, no_skipped_file_id) {
  std::string data;
  GetProtobufReport(PERF_DATA_WITH_WRONG_IP_IN_CALLCHAIN, &data);
  // If wrong ips in callchain are omitted, "unknown" file path will not be generated.
  ASSERT_EQ(data.find("unknown"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_report_sample, sample_has_event_count) {
  std::string data;
  GetProtobufReport(PERF_DATA_WITH_SYMBOLS, &data);
  ASSERT_NE(data.find("event_count:"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_report_sample, has_thread_record) {
  std::string data;
  GetProtobufReport(PERF_DATA_WITH_SYMBOLS, &data);
  ASSERT_NE(data.find("thread:"), std::string::npos);
  ASSERT_NE(data.find("thread_name: t2"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_report_sample, trace_offcpu) {
  std::string data;
  GetProtobufReport("perf_with_trace_offcpu_v2.data", &data);
  ASSERT_NE(data.find("event_type: sched:sched_switch"), std::string::npos);
  ASSERT_NE(data.find("trace_offcpu: true"), std::string::npos);
  std::vector<std::vector<std::string>> cases = {
      {"context_switch:", "switch_on: true", "time: 676374949239318", "thread_id: 6525"},
      {"context_switch:", "switch_on: false", "time: 676374953363850", "thread_id: 6525"},
  };
  for (auto& test_case : cases) {
    auto regex = RegEx::Create(android::base::Join(test_case, R"((\s|\n|\r)+)"));
    ASSERT_TRUE(regex->Search(data));
  }
}

// @CddTest = 6.1/C-0-2
TEST(cmd_report_sample, have_clear_callchain_end_in_protobuf_output) {
  std::string data;
  GetProtobufReport("perf_with_trace_offcpu_v2.data", &data, {"--show-callchain"});
  ASSERT_NE(data.find("__libc_init"), std::string::npos);
  ASSERT_EQ(data.find("_start_main"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_report_sample, app_device_info_in_meta_info) {
  std::string data;
  GetProtobufReport("perf_with_meta_info.data", &data);
  ASSERT_NE(data.find("app_package_name: com.google.sample.tunnel"), std::string::npos);
  ASSERT_NE(data.find("app_type: debuggable"), std::string::npos);
  ASSERT_NE(data.find("android_sdk_version: 30"), std::string::npos);
  ASSERT_NE(data.find("android_build_type: userdebug"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_report_sample, remove_unknown_kernel_symbols) {
  std::string data;
  // Test --remove-unknown-kernel-symbols on perf.data with kernel_symbols_available=false.
  GetProtobufReport(PERF_DATA_WITH_KERNEL_SYMBOLS_AVAILABLE_FALSE, &data, {"--show-callchain"});
  ASSERT_NE(data.find("time: 1368182962424044"), std::string::npos);
  ASSERT_NE(data.find("path: [kernel.kallsyms]"), std::string::npos);
  ASSERT_NE(data.find("path: /system/lib64/libc.so"), std::string::npos);
  GetProtobufReport(PERF_DATA_WITH_KERNEL_SYMBOLS_AVAILABLE_FALSE, &data,
                    {"--show-callchain", "--remove-unknown-kernel-symbols"});
  // The sample dumped at time 1368182962424044 shouldn't be removed. Because it has user space
  // callchains.
  ASSERT_NE(data.find("time: 1368182962424044"), std::string::npos);
  // Kernel callchains shouldn't be removed.
  ASSERT_EQ(data.find("path: [kernel.kallsyms]"), std::string::npos);
  // User space callchains still exist.
  ASSERT_NE(data.find("path: /system/lib64/libc.so"), std::string::npos);

  // Test --remove-unknown-kernel-symbols on perf.data with kernel_symbols_available=true.
  GetProtobufReport(PERF_DATA_WITH_KERNEL_SYMBOLS_AVAILABLE_TRUE, &data, {"--show-callchain"});
  ASSERT_NE(data.find("time: 1368297633794862"), std::string::npos);
  ASSERT_NE(data.find("path: [kernel.kallsyms]"), std::string::npos);
  ASSERT_NE(data.find("symbol: binder_ioctl_write_read"), std::string::npos);
  ASSERT_NE(data.find("path: /system/lib64/libc.so"), std::string::npos);
  GetProtobufReport(PERF_DATA_WITH_KERNEL_SYMBOLS_AVAILABLE_TRUE, &data,
                    {"--show-callchain", "--remove-unknown-kernel-symbols"});
  ASSERT_NE(data.find("time: 1368297633794862"), std::string::npos);
  ASSERT_NE(data.find("path: [kernel.kallsyms]"), std::string::npos);
  ASSERT_NE(data.find("symbol: binder_ioctl_write_read"), std::string::npos);
  ASSERT_NE(data.find("path: /system/lib64/libc.so"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_report_sample, show_art_frames_option) {
  std::string data;
  GetProtobufReport(PERF_DATA_WITH_INTERPRETER_FRAMES, &data, {"--show-callchain"});
  ASSERT_EQ(data.find("artMterpAsmInstructionStart"), std::string::npos);
  GetProtobufReport(PERF_DATA_WITH_INTERPRETER_FRAMES, &data,
                    {"--show-callchain", "--show-art-frames"});
  ASSERT_NE(data.find("artMterpAsmInstructionStart"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_report_sample, show_execution_type_option) {
  std::string data;
  GetProtobufReport("perf_display_bitmaps.data", &data,
                    {"--show-callchain", "--show-execution-type"});
  ASSERT_NE(data.find("execution_type: interpreted_jvm_method"), std::string::npos);
  // We convert JIT frames to map to dex files. So there is no file named jit_app_cache in the
  // report. But the execution type of a JIT frame isn't changed.
  ASSERT_EQ(data.find("jit_app_cache"), std::string::npos);
  ASSERT_NE(data.find("execution_type: jit_jvm_method"), std::string::npos);
  // art_method is shown only when --show-art-frames is used.
  ASSERT_EQ(data.find("execution_type: art_method"), std::string::npos);

  GetProtobufReport("perf_display_bitmaps.data", &data,
                    {"--show-callchain", "--show-execution-type", "--show-art-frames"});
  ASSERT_NE(data.find("execution_type: art_method"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_report_sample, show_symbols_before_and_after_demangle) {
  std::string data;
  GetProtobufReport(PERF_DATA_WITH_INTERPRETER_FRAMES, &data, {"--show-callchain"});
  ASSERT_NE(data.find("symbol: android::hardware::IPCThreadState::talkWithDriver(bool)"),
            std::string::npos);
  ASSERT_NE(data.find("mangled_symbol: _ZN7android8hardware14IPCThreadState14talkWithDriverEb"),
            std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_report_sample, symdir_option) {
  std::string data;
  GetProtobufReport(PERF_DATA_FOR_BUILD_ID_CHECK, &data);
  ASSERT_EQ(data.find("symbol: main"), std::string::npos);
  GetProtobufReport(PERF_DATA_FOR_BUILD_ID_CHECK, &data,
                    {"--symdir", GetTestDataDir() + CORRECT_SYMFS_FOR_BUILD_ID_CHECK});
  ASSERT_NE(data.find("symbol: main"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_report_sample, show_art_jni_methods) {
  std::string data;
  GetProtobufReport("perf_display_bitmaps.data", &data, {"--show-callchain"});
  ASSERT_NE(data.find("art::Method_invoke"), std::string::npos);
  // Don't show art_jni_trampoline.
  ASSERT_EQ(data.find("art_jni_trampoline"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_report_sample, show_unwinding_result) {
  std::string data;
  GetProtobufReport("perf_with_failed_unwinding_debug_info.data", &data,
                    {"--show-callchain", "--remove-gaps", "0"});
  ASSERT_NE(data.find("error_code: ERROR_INVALID_MAP"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_report_sample, proguard_mapping_file_option) {
  std::string data;
  // Symbols aren't de-obfuscated without proguard mapping file.
  GetProtobufReport("perf_need_proguard_mapping.data", &data,
                    {"--show-callchain", "--remove-gaps", "0"});
  ASSERT_EQ(data.find("androidx.fragment.app.FragmentActivity.startActivityForResult"),
            std::string::npos);
  ASSERT_EQ(data.find("com.example.android.displayingbitmaps.ui.ImageGridFragment.onItemClick"),
            std::string::npos);
  // Symbols are de-obfuscated with proguard mapping file.
  GetProtobufReport("perf_need_proguard_mapping.data", &data,
                    {"--show-callchain", "--proguard-mapping-file",
                     GetTestData("proguard_mapping.txt"), "--remove-gaps", "0"});
  ASSERT_NE(data.find("androidx.fragment.app.FragmentActivity.startActivityForResult"),
            std::string::npos);
  ASSERT_NE(data.find("com.example.android.displayingbitmaps.ui.ImageGridFragment.onItemClick"),
            std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_report_sample, exclude_include_pid_options) {
  std::string data;
  GetProtobufReport("perf_display_bitmaps.data", &data, {"--exclude-pid", "31850"});
  ASSERT_EQ(data.find("thread_id: 31850"), std::string::npos);

  GetProtobufReport("perf_display_bitmaps.data", &data, {"--include-pid", "31850"});
  ASSERT_NE(data.find("thread_id: 31850"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_report_sample, exclude_include_tid_options) {
  std::string data;
  GetProtobufReport("perf_display_bitmaps.data", &data, {"--exclude-tid", "31881"});
  ASSERT_EQ(data.find("thread_id: 31881"), std::string::npos);

  GetProtobufReport("perf_display_bitmaps.data", &data, {"--include-tid", "31881"});
  ASSERT_NE(data.find("thread_id: 31881"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_report_sample, exclude_include_process_name_options) {
  std::string data;
  GetProtobufReport("perf_display_bitmaps.data", &data,
                    {"--exclude-process-name", "com.example.android.displayingbitmaps"});
  ASSERT_EQ(data.find("thread_id: 31881"), std::string::npos);

  GetProtobufReport("perf_display_bitmaps.data", &data,
                    {"--include-process-name", "com.example.android.displayingbitmaps"});
  ASSERT_NE(data.find("thread_id: 31881"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_report_sample, exclude_include_thread_name_options) {
  std::string data;
  GetProtobufReport("perf_display_bitmaps.data", &data,
                    {"--exclude-thread-name", "com.example.android.displayingbitmaps"});
  ASSERT_EQ(data.find("thread_id: 31850"), std::string::npos);

  GetProtobufReport("perf_display_bitmaps.data", &data,
                    {"--include-thread-name", "com.example.android.displayingbitmaps"});
  ASSERT_NE(data.find("thread_id: 31850"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_report_sample, filter_file_option) {
  std::string filter_data =
      "GLOBAL_BEGIN 684943449406175\n"
      "GLOBAL_END 684943449406176";
  TemporaryFile tmpfile;
  ASSERT_TRUE(android::base::WriteStringToFd(filter_data, tmpfile.fd));
  std::string data;
  GetProtobufReport("perf_display_bitmaps.data", &data, {"--filter-file", tmpfile.path});
  ASSERT_NE(data.find("thread_id: 31881"), std::string::npos);
  ASSERT_EQ(data.find("thread_id: 31850"), std::string::npos);
}

// @CddTest = 6.1/C-0-2
TEST(cmd_report_sample, remove_gaps_option) {
  auto get_sample_count = [](const std::string& s) {
    size_t count = 0;
    ssize_t pos = 0;
    while ((pos = s.find("\nsample ", pos)) != s.npos) {
      ++count;
      pos += strlen("\nsample ");
    }
    return count;
  };

  std::string data;
  // By default, `--remove-gaps 3` is used.
  GetProtobufReport("perf_display_bitmaps.data", &data, {"--show-callchain"});
  ASSERT_EQ(get_sample_count(data), 517);
  ASSERT_NE(data.find("sample_count: 517"), std::string::npos) << data;
  // We can disable removing gaps by using `--remove-gaps 0`.
  GetProtobufReport("perf_display_bitmaps.data", &data, {"--show-callchain", "--remove-gaps", "0"});
  ASSERT_EQ(get_sample_count(data), 525);
  ASSERT_NE(data.find("sample_count: 525"), std::string::npos);
}
