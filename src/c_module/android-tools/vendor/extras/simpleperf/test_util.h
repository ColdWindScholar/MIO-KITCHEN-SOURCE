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

#include <map>
#include <memory>
#include <optional>
#include <string>
#include <vector>

#include <android-base/file.h>
#include <android-base/strings.h>

#include "environment.h"
#include "read_elf.h"
#include "utils.h"
#include "workload.h"

using namespace simpleperf;

static const std::string SLEEP_SEC = "0.001";

void RunWorkloadFunction();
void CreateProcesses(size_t count, std::vector<std::unique_ptr<Workload>>* workloads);

void ParseSymbol(const ElfFileSymbol& symbol, std::map<std::string, ElfFileSymbol>* symbols);
void CheckElfFileSymbols(const std::map<std::string, ElfFileSymbol>& symbols);

#define TEST_IN_ROOT(TestStatement)                                                            \
  do {                                                                                         \
    if (IsRoot()) {                                                                            \
      TestStatement;                                                                           \
    } else {                                                                                   \
      GTEST_LOG_(INFO) << "Didn't test \"" << #TestStatement << "\" requires root privileges"; \
    }                                                                                          \
  } while (0)

#define TEST_REQUIRE_ROOT()                                              \
  do {                                                                   \
    if (!IsRoot()) {                                                     \
      GTEST_LOG_(INFO) << "Skip this test as it needs root privileges."; \
      return;                                                            \
    }                                                                    \
  } while (0)

#define TEST_REQUIRE_NON_ROOT()                                            \
  do {                                                                     \
    if (IsRoot()) {                                                        \
      GTEST_LOG_(INFO) << "Skip this test as it tests non-root behavior."; \
      return;                                                              \
    }                                                                      \
  } while (0)

#if defined(__ANDROID__)
#define TEST_REQUIRE_HOST_ROOT()
#else
#define TEST_REQUIRE_HOST_ROOT() TEST_REQUIRE_ROOT()
#endif

std::optional<bool> IsInNativeAbi();
// Used to skip tests not supposed to run on non-native ABIs.
#define OMIT_TEST_ON_NON_NATIVE_ABIS()                                      \
  do {                                                                      \
    std::optional<bool> in_native_abi = IsInNativeAbi();                    \
    ASSERT_TRUE(in_native_abi.has_value());                                 \
    if (!in_native_abi.value()) {                                           \
      GTEST_LOG_(INFO) << "Skip this test as it only runs on native ABIs."; \
      return;                                                               \
    }                                                                       \
  } while (0)

bool HasHardwareCounter();
#define TEST_REQUIRE_HW_COUNTER()                                                              \
  do {                                                                                         \
    if (!HasHardwareCounter()) {                                                               \
      GTEST_LOG_(INFO) << "Skip this test as the machine doesn't have hardware PMU counters."; \
      return;                                                                                  \
    }                                                                                          \
  } while (0)

bool HasPmuCounter();
#define TEST_REQUIRE_PMU_COUNTER()                                                              \
  do {                                                                                          \
    if (!HasPmuCounter()) {                                                                     \
      GTEST_LOG_(INFO) << "Skip this test as the machine doesn't have low-level PMU counters."; \
      return;                                                                                   \
    }                                                                                           \
  } while (0)

bool HasTracepointEvents();
#define TEST_REQUIRE_TRACEPOINT_EVENTS()                                                      \
  do {                                                                                        \
    if (!HasTracepointEvents()) {                                                             \
      GTEST_LOG_(INFO) << "Skip this test as the machine doesn't support tracepoint events."; \
      return;                                                                                 \
    }                                                                                         \
  } while (0)

#if defined(IN_CTS_TEST)
#define TEST_REQUIRE_APPS()
#else
#define TEST_REQUIRE_APPS()                                              \
  do {                                                                   \
    GTEST_LOG_(INFO) << "Skip this test as test apps aren't available."; \
    return;                                                              \
  } while (0)
#endif

class CaptureStdout {
 public:
  CaptureStdout() : started_(false) {}

  ~CaptureStdout() {
    if (started_) {
      Finish();
    }
  }

  bool Start() {
    fflush(stdout);
    old_stdout_ = dup(STDOUT_FILENO);
    if (old_stdout_ == -1) {
      return false;
    }
    started_ = true;
    tmpfile_.reset(new TemporaryFile);
    if (dup2(tmpfile_->fd, STDOUT_FILENO) == -1) {
      return false;
    }
    return true;
  }

  std::string Finish() {
    fflush(stdout);
    started_ = false;
    dup2(old_stdout_, STDOUT_FILENO);
    close(old_stdout_);
    std::string s;
    if (!android::base::ReadFileToString(tmpfile_->path, &s)) {
      return "";
    }
    return s;
  }

 private:
  bool started_;
  int old_stdout_;
  std::unique_ptr<TemporaryFile> tmpfile_;
};

class AppHelper {
 public:
  ~AppHelper() {
    for (auto& package : installed_packages_) {
      Workload::RunCmd({"pm", "uninstall", package});
    }
  }

  bool InstallApk(const std::string& apk_path, const std::string& package_name) {
    if (Workload::RunCmd({"pm", "install", "-t", "--abi", GetABI(), apk_path})) {
      installed_packages_.emplace_back(package_name);
      return true;
    }
    return false;
  }

  bool StartApp(const std::string& start_cmd) {
    app_start_proc_ = Workload::CreateWorkload(android::base::Split(start_cmd, " "));
    return app_start_proc_ && app_start_proc_->Start();
  }

 private:
  const char* GetABI() {
#if defined(__i386__)
    return "x86";
#elif defined(__x86_64__)
    return "x86_64";
#elif defined(__aarch64__)
    return "arm64-v8a";
#elif defined(__arm__)
    return "armeabi-v7a";
#elif defined(__riscv)
    return "riscv64";
#else
#error "unrecognized ABI"
#endif
  }

  std::vector<std::string> installed_packages_;
  std::unique_ptr<Workload> app_start_proc_;
};

bool IsInEmulator();
