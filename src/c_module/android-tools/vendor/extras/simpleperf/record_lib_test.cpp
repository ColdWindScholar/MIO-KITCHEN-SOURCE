/*
 * Copyright (C) 2017 The Android Open Source Project
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

#include "simpleperf.h"

#include <gtest/gtest.h>

#include <memory>

using namespace simpleperf;

// @CddTest = 6.1/C-0-2
TEST(get_all_events, smoke) {
  std::vector<std::string> events = GetAllEvents();
  ASSERT_GT(events.size(), 0u);
  ASSERT_NE(std::find(events.begin(), events.end(), "cpu-cycles"), events.end());
  ASSERT_TRUE(IsEventSupported("cpu-cycles"));
  ASSERT_TRUE(IsEventSupported("cpu-cycles:u"));
  ASSERT_TRUE(IsEventSupported("cpu-cycles:k"));
}

static void DoSomeWork() {
  for (volatile int i = 0; i < 100000000; ++i) {
  }
}

// @CddTest = 6.1/C-0-2
TEST(counter, add_event) {
  std::unique_ptr<PerfEventSet> perf(
      PerfEventSet::CreateInstance(PerfEventSet::Type::kPerfForCounting));
  ASSERT_TRUE(perf);
  ASSERT_TRUE(perf->AddEvent("cpu-cycles"));
  ASSERT_TRUE(perf->AddEvent("cpu-cycles:u"));
  ASSERT_TRUE(perf->AddEvent("cpu-cycles:k"));
  ASSERT_TRUE(perf->MonitorCurrentProcess());
  ASSERT_TRUE(perf->StartCounters());
  DoSomeWork();
  ASSERT_TRUE(perf->StopCounters());
  std::vector<Counter> counters;
  ASSERT_TRUE(perf->ReadCounters(&counters));
  ASSERT_EQ(counters.size(), 3u);
  ASSERT_EQ(counters[0].event, "cpu-cycles");
  ASSERT_EQ(counters[1].event, "cpu-cycles:u");
  ASSERT_EQ(counters[2].event, "cpu-cycles:k");
  for (auto& counter : counters) {
    ASSERT_GE(counter.value, 0u);
    ASSERT_GE(counter.time_enabled_in_ns, 0u);
    ASSERT_GE(counter.time_running_in_ns, 0u);
    ASSERT_LE(counter.time_running_in_ns, counter.time_enabled_in_ns);
  }
}

// @CddTest = 6.1/C-0-2
TEST(counter, different_targets) {
  auto test_function = [](std::function<void(PerfEventSet*)> set_target_func) {
    std::unique_ptr<PerfEventSet> perf(
        PerfEventSet::CreateInstance(PerfEventSet::Type::kPerfForCounting));
    ASSERT_TRUE(perf);
    ASSERT_TRUE(perf->AddEvent("cpu-cycles"));
    set_target_func(perf.get());
    ASSERT_TRUE(perf->MonitorCurrentProcess());
    ASSERT_TRUE(perf->StartCounters());
    DoSomeWork();
    ASSERT_TRUE(perf->StopCounters());
    std::vector<Counter> counters;
    ASSERT_TRUE(perf->ReadCounters(&counters));
    ASSERT_EQ(counters.size(), 1u);
    ASSERT_EQ(counters[0].event, "cpu-cycles");
    ASSERT_GT(counters[0].value, 0u);
    ASSERT_GT(counters[0].time_enabled_in_ns, 0u);
    ASSERT_GT(counters[0].time_running_in_ns, 0u);
    ASSERT_LE(counters[0].time_running_in_ns, counters[0].time_enabled_in_ns);
  };
  test_function([](PerfEventSet* perf) { ASSERT_TRUE(perf->MonitorCurrentProcess()); });
  test_function([](PerfEventSet* perf) { ASSERT_TRUE(perf->MonitorCurrentThread()); });
  test_function(
      [](PerfEventSet* perf) { ASSERT_TRUE(perf->MonitorThreadsInCurrentProcess({getpid()})); });
}

// @CddTest = 6.1/C-0-2
TEST(counter, start_stop_multiple_times) {
  const size_t TEST_COUNT = 10;
  std::unique_ptr<PerfEventSet> perf(
      PerfEventSet::CreateInstance(PerfEventSet::Type::kPerfForCounting));
  ASSERT_TRUE(perf);
  ASSERT_TRUE(perf->AddEvent("cpu-cycles"));
  ASSERT_TRUE(perf->MonitorCurrentProcess());
  Counter prev_counter;
  for (size_t i = 0; i < TEST_COUNT; ++i) {
    ASSERT_TRUE(perf->StartCounters());
    DoSomeWork();
    ASSERT_TRUE(perf->StopCounters());
    std::vector<Counter> counters;
    ASSERT_TRUE(perf->ReadCounters(&counters));
    ASSERT_EQ(counters.size(), 1u);
    ASSERT_EQ(counters[0].event, "cpu-cycles");
    ASSERT_GT(counters[0].value, 0u);
    ASSERT_GT(counters[0].time_enabled_in_ns, 0u);
    ASSERT_GT(counters[0].time_running_in_ns, 0u);
    ASSERT_LE(counters[0].time_running_in_ns, counters[0].time_enabled_in_ns);
    if (i > 0u) {
      ASSERT_GT(counters[0].value, prev_counter.value);
      ASSERT_GT(counters[0].time_enabled_in_ns, prev_counter.time_enabled_in_ns);
      ASSERT_GT(counters[0].time_running_in_ns, prev_counter.time_running_in_ns);
    }
    prev_counter = counters[0];
  }
}

// @CddTest = 6.1/C-0-2
TEST(counter, no_change_after_stop) {
  std::unique_ptr<PerfEventSet> perf(
      PerfEventSet::CreateInstance(PerfEventSet::Type::kPerfForCounting));
  ASSERT_TRUE(perf);
  ASSERT_TRUE(perf->AddEvent("cpu-cycles"));
  ASSERT_TRUE(perf->MonitorCurrentProcess());
  ASSERT_TRUE(perf->StartCounters());
  DoSomeWork();
  ASSERT_TRUE(perf->StopCounters());
  std::vector<Counter> counters;
  ASSERT_TRUE(perf->ReadCounters(&counters));
  ASSERT_EQ(counters.size(), 1u);
  ASSERT_EQ(counters[0].event, "cpu-cycles");
  ASSERT_GT(counters[0].value, 0u);
  ASSERT_GT(counters[0].time_enabled_in_ns, 0u);
  ASSERT_GT(counters[0].time_running_in_ns, 0u);
  ASSERT_LE(counters[0].time_running_in_ns, counters[0].time_enabled_in_ns);
  Counter prev_counter = counters[0];
  DoSomeWork();
  ASSERT_TRUE(perf->ReadCounters(&counters));
  ASSERT_EQ(counters.size(), 1u);
  ASSERT_EQ(counters[0].value, prev_counter.value);
  ASSERT_EQ(counters[0].time_enabled_in_ns, prev_counter.time_enabled_in_ns);
  ASSERT_EQ(counters[0].time_running_in_ns, prev_counter.time_running_in_ns);
}
