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

#include <sys/stat.h>
#include <unistd.h>
#if defined(__BIONIC__)
#include <android-base/properties.h>
#endif

#include <atomic>
#include <chrono>
#include <thread>
#include <unordered_map>

#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/stringprintf.h>

#include "environment.h"
#include "event_attr.h"
#include "event_fd.h"
#include "event_type.h"
#include "utils.h"

using namespace simpleperf;

static auto test_duration_for_long_tests = std::chrono::seconds(120);
static auto cpu_hotplug_interval = std::chrono::microseconds(1000);
static bool verbose_mode = false;

#if defined(__BIONIC__)
class ScopedMpdecisionKiller {
 public:
  ScopedMpdecisionKiller() {
    have_mpdecision_ = IsMpdecisionRunning();
    if (have_mpdecision_) {
      DisableMpdecision();
    }
  }

  ~ScopedMpdecisionKiller() {
    if (have_mpdecision_) {
      EnableMpdecision();
    }
  }

 private:
  bool IsMpdecisionRunning() {
    std::string value = android::base::GetProperty("init.svc.mpdecision", "");
    if (value.empty() || value.find("stopped") != std::string::npos) {
      return false;
    }
    return true;
  }

  void DisableMpdecision() {
    CHECK(android::base::SetProperty("ctl.stop", "mpdecision"));
    // Need to wait until mpdecision is actually stopped.
    std::this_thread::sleep_for(std::chrono::milliseconds(500));
    CHECK(!IsMpdecisionRunning());
  }

  void EnableMpdecision() {
    CHECK(android::base::SetProperty("ctl.start", "mpdecision"));
    std::this_thread::sleep_for(std::chrono::milliseconds(500));
    CHECK(IsMpdecisionRunning());
  }

  bool have_mpdecision_;
};
#else
class ScopedMpdecisionKiller {
 public:
  ScopedMpdecisionKiller() {}
};
#endif

static bool IsCpuOnline(int cpu, bool* has_error) {
  std::string filename = android::base::StringPrintf("/sys/devices/system/cpu/cpu%d/online", cpu);
  std::string content;
  bool ret = android::base::ReadFileToString(filename, &content);
  if (!ret) {
    PLOG(ERROR) << "failed to read file " << filename;
    *has_error = true;
    return false;
  }
  *has_error = false;
  return (content.find('1') != std::string::npos);
}

static bool SetCpuOnline(int cpu, bool online) {
  bool has_error;
  bool ret = IsCpuOnline(cpu, &has_error);
  if (has_error) {
    return false;
  }
  if (ret == online) {
    return true;
  }
  std::string filename = android::base::StringPrintf("/sys/devices/system/cpu/cpu%d/online", cpu);
  std::string content = online ? "1" : "0";
  ret = android::base::WriteStringToFile(content, filename);
  if (!ret) {
    ret = IsCpuOnline(cpu, &has_error);
    if (has_error) {
      return false;
    }
    if (online == ret) {
      return true;
    }
    PLOG(ERROR) << "failed to write " << content << " to " << filename;
    return false;
  }
  // Kernel needs time to offline/online cpus, so use a loop to wait here.
  size_t retry_count = 0;
  while (true) {
    ret = IsCpuOnline(cpu, &has_error);
    if (has_error) {
      return false;
    }
    if (ret == online) {
      break;
    }
    LOG(ERROR) << "reading cpu retry count = " << retry_count << ", requested = " << online
               << ", real = " << ret;
    if (++retry_count == 10000) {
      LOG(ERROR) << "setting cpu " << cpu << (online ? " online" : " offline")
                 << " seems not to take effect";
      return false;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
  }
  return true;
}

static int GetCpuCount() {
  return static_cast<int>(sysconf(_SC_NPROCESSORS_CONF));
}

class CpuOnlineRestorer {
 public:
  CpuOnlineRestorer() {
    for (int cpu = 1; cpu < GetCpuCount(); ++cpu) {
      bool has_error;
      bool ret = IsCpuOnline(cpu, &has_error);
      if (has_error) {
        continue;
      }
      online_map_[cpu] = ret;
    }
  }

  ~CpuOnlineRestorer() {
    for (const auto& pair : online_map_) {
      SetCpuOnline(pair.first, pair.second);
    }
  }

 private:
  std::unordered_map<int, bool> online_map_;
};

bool FindAHotpluggableCpu(int* hotpluggable_cpu) {
  if (!IsRoot()) {
    GTEST_LOG_(INFO) << "This test needs root privilege to hotplug cpu.";
    return false;
  }
  for (int cpu = 1; cpu < GetCpuCount(); ++cpu) {
    bool has_error;
    bool online = IsCpuOnline(cpu, &has_error);
    if (has_error) {
      continue;
    }
    if (SetCpuOnline(cpu, !online)) {
      *hotpluggable_cpu = cpu;
      return true;
    }
  }
  GTEST_LOG_(INFO) << "There is no hotpluggable cpu.";
  return false;
}

struct CpuToggleThreadArg {
  int toggle_cpu;
  std::atomic<bool> end_flag;
  std::atomic<bool> cpu_hotplug_failed;

  CpuToggleThreadArg(int cpu) : toggle_cpu(cpu), end_flag(false), cpu_hotplug_failed(false) {}
};

static void CpuToggleThread(CpuToggleThreadArg* arg) {
  while (!arg->end_flag) {
    if (!SetCpuOnline(arg->toggle_cpu, true)) {
      arg->cpu_hotplug_failed = true;
      break;
    }
    std::this_thread::sleep_for(cpu_hotplug_interval);
    if (!SetCpuOnline(arg->toggle_cpu, false)) {
      arg->cpu_hotplug_failed = true;
      break;
    }
    std::this_thread::sleep_for(cpu_hotplug_interval);
  }
}

// http://b/25193162.
TEST(cpu_offline, offline_while_recording) {
  ScopedMpdecisionKiller scoped_mpdecision_killer;
  CpuOnlineRestorer cpuonline_restorer;
  if (GetCpuCount() == 1) {
    GTEST_LOG_(INFO) << "This test does nothing, because there is only one cpu in the system.";
    return;
  }
  // Start cpu hotpluger.
  int test_cpu;
  if (!FindAHotpluggableCpu(&test_cpu)) {
    return;
  }
  CpuToggleThreadArg cpu_toggle_arg(test_cpu);
  std::thread cpu_toggle_thread(CpuToggleThread, &cpu_toggle_arg);

  std::unique_ptr<EventTypeAndModifier> event_type_modifier = ParseEventType("cpu-cycles");
  ASSERT_TRUE(event_type_modifier != nullptr);
  perf_event_attr attr = CreateDefaultPerfEventAttr(event_type_modifier->event_type);
  attr.disabled = 0;
  attr.enable_on_exec = 0;

  auto start_time = std::chrono::steady_clock::now();
  auto cur_time = start_time;
  auto end_time = std::chrono::steady_clock::now() + test_duration_for_long_tests;
  auto report_step = std::chrono::seconds(15);
  size_t iterations = 0;

  while (cur_time < end_time && !cpu_toggle_arg.cpu_hotplug_failed) {
    if (cur_time + report_step < std::chrono::steady_clock::now()) {
      // Report test time.
      auto diff = std::chrono::duration_cast<std::chrono::seconds>(
          std::chrono::steady_clock::now() - start_time);
      if (verbose_mode) {
        GTEST_LOG_(INFO) << "Have Tested " << (diff.count() / 60.0) << " minutes.";
      }
      cur_time = std::chrono::steady_clock::now();
    }

    std::unique_ptr<EventFd> event_fd =
        EventFd::OpenEventFile(attr, -1, test_cpu, nullptr, event_type_modifier->name, false);
    if (event_fd == nullptr) {
      // Failed to open because the test_cpu is offline.
      continue;
    }
    iterations++;
    if (verbose_mode) {
      GTEST_LOG_(INFO) << "Test offline while recording for " << iterations << " times.";
    }
  }
  if (cpu_toggle_arg.cpu_hotplug_failed) {
    GTEST_LOG_(INFO) << "Test ends because of cpu hotplug failure.";
  }
  cpu_toggle_arg.end_flag = true;
  cpu_toggle_thread.join();
}

// http://b/25193162.
TEST(cpu_offline, offline_while_ioctl_enable) {
  ScopedMpdecisionKiller scoped_mpdecision_killer;
  CpuOnlineRestorer cpuonline_restorer;
  if (GetCpuCount() == 1) {
    GTEST_LOG_(INFO) << "This test does nothing, because there is only one cpu in the system.";
    return;
  }
  // Start cpu hotpluger.
  int test_cpu;
  if (!FindAHotpluggableCpu(&test_cpu)) {
    return;
  }
  CpuToggleThreadArg cpu_toggle_arg(test_cpu);
  std::thread cpu_toggle_thread(CpuToggleThread, &cpu_toggle_arg);

  std::unique_ptr<EventTypeAndModifier> event_type_modifier = ParseEventType("cpu-cycles");
  ASSERT_TRUE(event_type_modifier != nullptr);
  perf_event_attr attr = CreateDefaultPerfEventAttr(event_type_modifier->event_type);
  attr.disabled = 1;
  attr.enable_on_exec = 0;

  auto start_time = std::chrono::steady_clock::now();
  auto cur_time = start_time;
  auto end_time = std::chrono::steady_clock::now() + test_duration_for_long_tests;
  auto report_step = std::chrono::seconds(15);
  size_t iterations = 0;

  while (cur_time < end_time && !cpu_toggle_arg.cpu_hotplug_failed) {
    if (cur_time + report_step < std::chrono::steady_clock::now()) {
      // Report test time.
      auto diff = std::chrono::duration_cast<std::chrono::seconds>(
          std::chrono::steady_clock::now() - start_time);
      if (verbose_mode) {
        GTEST_LOG_(INFO) << "Have Tested " << (diff.count() / 60.0) << " minutes.";
      }
      cur_time = std::chrono::steady_clock::now();
    }
    std::unique_ptr<EventFd> event_fd =
        EventFd::OpenEventFile(attr, -1, test_cpu, nullptr, event_type_modifier->name, false);
    if (event_fd == nullptr) {
      // Failed to open because the test_cpu is offline.
      continue;
    }
    // Wait a little for the event to be installed on test_cpu's perf context.
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
    ASSERT_TRUE(event_fd->SetEnableEvent(true));
    iterations++;
    if (verbose_mode) {
      GTEST_LOG_(INFO) << "Test offline while ioctl(PERF_EVENT_IOC_ENABLE) for " << iterations
                       << " times.";
    }
  }
  if (cpu_toggle_arg.cpu_hotplug_failed) {
    GTEST_LOG_(INFO) << "Test ends because of cpu hotplug failure.";
  }
  cpu_toggle_arg.end_flag = true;
  cpu_toggle_thread.join();
}

struct CpuSpinThreadArg {
  int spin_cpu;
  std::atomic<pid_t> tid;
  std::atomic<bool> end_flag;
};

static void CpuSpinThread(CpuSpinThreadArg* arg) {
  arg->tid = gettid();
  while (!arg->end_flag) {
    cpu_set_t mask;
    CPU_ZERO(&mask);
    CPU_SET(arg->spin_cpu, &mask);
    // If toggle_cpu is offline, setaffinity fails. So call it in a loop to
    // make sure current thread mostly runs on toggle_cpu.
    sched_setaffinity(arg->tid, sizeof(mask), &mask);
  }
}

// http://b/28086229.
TEST(cpu_offline, offline_while_user_process_profiling) {
  ScopedMpdecisionKiller scoped_mpdecision_killer;
  CpuOnlineRestorer cpuonline_restorer;
  // Start cpu hotpluger.
  int test_cpu;
  if (!FindAHotpluggableCpu(&test_cpu)) {
    return;
  }
  CpuToggleThreadArg cpu_toggle_arg(test_cpu);
  std::thread cpu_toggle_thread(CpuToggleThread, &cpu_toggle_arg);

  // Start cpu spinner.
  CpuSpinThreadArg cpu_spin_arg;
  cpu_spin_arg.spin_cpu = test_cpu;
  cpu_spin_arg.tid = 0;
  cpu_spin_arg.end_flag = false;
  std::thread cpu_spin_thread(CpuSpinThread, &cpu_spin_arg);
  while (cpu_spin_arg.tid == 0) {
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
  }

  std::unique_ptr<EventTypeAndModifier> event_type_modifier = ParseEventType("cpu-cycles");
  ASSERT_TRUE(event_type_modifier != nullptr);
  perf_event_attr attr = CreateDefaultPerfEventAttr(event_type_modifier->event_type);
  // Enable profiling in perf_event_open system call.
  attr.disabled = 0;
  attr.enable_on_exec = 0;

  auto start_time = std::chrono::steady_clock::now();
  auto cur_time = start_time;
  auto end_time = start_time + test_duration_for_long_tests;
  auto report_step = std::chrono::seconds(15);
  size_t iterations = 0;

  while (cur_time < end_time && !cpu_toggle_arg.cpu_hotplug_failed) {
    if (cur_time + report_step < std::chrono::steady_clock::now()) {
      auto diff = std::chrono::duration_cast<std::chrono::seconds>(
          std::chrono::steady_clock::now() - start_time);
      if (verbose_mode) {
        GTEST_LOG_(INFO) << "Have Tested " << (diff.count() / 60.0) << " minutes.";
      }
      cur_time = std::chrono::steady_clock::now();
    }
    // Test if the cpu pmu is still usable.
    ASSERT_TRUE(EventFd::OpenEventFile(attr, 0, -1, nullptr, event_type_modifier->name, true) !=
                nullptr);

    std::unique_ptr<EventFd> event_fd = EventFd::OpenEventFile(
        attr, cpu_spin_arg.tid, test_cpu, nullptr, event_type_modifier->name, false);
    if (event_fd == nullptr) {
      // Failed to open because the test_cpu is offline.
      continue;
    }
    // profile for a while.
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
    iterations++;
    if (verbose_mode) {
      GTEST_LOG_(INFO) << "Test offline while user process profiling for " << iterations
                       << " times.";
    }
  }
  if (cpu_toggle_arg.cpu_hotplug_failed) {
    GTEST_LOG_(INFO) << "Test ends because of cpu hotplug failure.";
  }
  cpu_toggle_arg.end_flag = true;
  cpu_toggle_thread.join();
  cpu_spin_arg.end_flag = true;
  cpu_spin_thread.join();
  // Check if the cpu-cycle event is still available on test_cpu.
  if (SetCpuOnline(test_cpu, true)) {
    ASSERT_TRUE(EventFd::OpenEventFile(attr, -1, test_cpu, nullptr, event_type_modifier->name,
                                       true) != nullptr);
  }
}

// http://b/19863147.
TEST(cpu_offline, offline_while_recording_on_another_cpu) {
  ScopedMpdecisionKiller scoped_mpdecision_killer;
  CpuOnlineRestorer cpuonline_restorer;

  if (GetCpuCount() == 1) {
    GTEST_LOG_(INFO) << "This test does nothing, because there is only one cpu in the system.";
    return;
  }
  int test_cpu;
  if (!FindAHotpluggableCpu(&test_cpu)) {
    return;
  }
  std::unique_ptr<EventTypeAndModifier> event_type_modifier = ParseEventType("cpu-cycles");
  perf_event_attr attr = CreateDefaultPerfEventAttr(event_type_modifier->event_type);
  attr.disabled = 0;
  attr.enable_on_exec = 0;

  const size_t TEST_ITERATION_COUNT = 10u;
  for (size_t i = 0; i < TEST_ITERATION_COUNT; ++i) {
    int record_cpu = 0;
    if (!SetCpuOnline(test_cpu, true)) {
      break;
    }
    std::unique_ptr<EventFd> event_fd =
        EventFd::OpenEventFile(attr, getpid(), record_cpu, nullptr, event_type_modifier->name);
    ASSERT_TRUE(event_fd != nullptr);
    if (!SetCpuOnline(test_cpu, false)) {
      break;
    }
    event_fd = nullptr;
    event_fd =
        EventFd::OpenEventFile(attr, getpid(), record_cpu, nullptr, event_type_modifier->name);
    ASSERT_TRUE(event_fd != nullptr);
  }
}

int main(int argc, char** argv) {
  for (int i = 1; i < argc; ++i) {
    if (strcmp(argv[i], "--help") == 0) {
      printf("--long_test_duration <second> Set test duration for long tests. Default is 120s.\n");
      printf(
          "--cpu_hotplug_interval <microseconds> Set cpu hotplug interval. Default is 1000us.\n");
      printf("--verbose  Show verbose log.\n");
    } else if (strcmp(argv[i], "--long_test_duration") == 0) {
      if (i + 1 < argc) {
        int second_count = atoi(argv[i + 1]);
        if (second_count <= 0) {
          fprintf(stderr, "Invalid arg for --long_test_duration.\n");
          return 1;
        }
        test_duration_for_long_tests = std::chrono::seconds(second_count);
        i++;
      }
    } else if (strcmp(argv[i], "--cpu_hotplug_interval") == 0) {
      if (i + 1 < argc) {
        int microsecond_count = atoi(argv[i + 1]);
        if (microsecond_count <= 0) {
          fprintf(stderr, "Invalid arg for --cpu_hotplug_interval\n");
          return 1;
        }
        cpu_hotplug_interval = std::chrono::microseconds(microsecond_count);
        i++;
      }
    } else if (strcmp(argv[i], "--verbose") == 0) {
      verbose_mode = true;
    }
  }
  testing::InitGoogleTest(&argc, argv);
  android::base::InitLogging(argv, android::base::StderrLogger);
  return RUN_ALL_TESTS();
}
