/*
 * Copyright (C) 2023 The Android Open Source Project
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

#include "event_selection_set.h"

using namespace simpleperf;

// @CddTest = 6.1/C-0-2
TEST(EventSelectionSet, set_sample_rate_for_new_events) {
  EventSelectionSet event_selection_set(false);
  ASSERT_TRUE(event_selection_set.AddEventType("cpu-clock:u"));
  event_selection_set.SetSampleRateForNewEvents(SampleRate(100, 0));
  ASSERT_TRUE(event_selection_set.AddEventType("page-faults:u"));
  event_selection_set.SetSampleRateForNewEvents(SampleRate(200, 0));
  ASSERT_TRUE(event_selection_set.AddEventGroup({"context-switches:u", "task-clock:u"}));
  EventAttrIds attrs = event_selection_set.GetEventAttrWithId();
  ASSERT_EQ(attrs.size(), 4);
  ASSERT_EQ(GetEventNameByAttr(attrs[0].attr), "cpu-clock:u");
  ASSERT_EQ(attrs[0].attr.freq, 1);
  ASSERT_EQ(attrs[0].attr.sample_freq, 100);
  ASSERT_EQ(GetEventNameByAttr(attrs[1].attr), "page-faults:u");
  ASSERT_EQ(attrs[1].attr.freq, 1);
  ASSERT_EQ(attrs[1].attr.sample_freq, 100);
  ASSERT_EQ(GetEventNameByAttr(attrs[2].attr), "context-switches:u");
  ASSERT_EQ(attrs[2].attr.freq, 1);
  ASSERT_EQ(attrs[2].attr.sample_freq, 200);
  ASSERT_EQ(GetEventNameByAttr(attrs[3].attr), "task-clock:u");
  ASSERT_EQ(attrs[3].attr.freq, 1);
  ASSERT_EQ(attrs[3].attr.sample_freq, 200);
}

// @CddTest = 6.1/C-0-2
TEST(EventSelectionSet, add_event_with_sample_rate) {
  EventSelectionSet event_selection_set(false);
  ASSERT_TRUE(event_selection_set.AddEventType("cpu-clock:u"));
  ASSERT_TRUE(event_selection_set.AddEventType("context-switches", SampleRate(0, 1)));
  EventAttrIds attrs = event_selection_set.GetEventAttrWithId();
  ASSERT_EQ(attrs.size(), 2);
  ASSERT_EQ(GetEventNameByAttr(attrs[0].attr), "cpu-clock:u");
  ASSERT_EQ(attrs[0].attr.freq, 1);
  ASSERT_EQ(attrs[0].attr.sample_freq, 4000);
  ASSERT_EQ(GetEventNameByAttr(attrs[1].attr), "context-switches");
  ASSERT_EQ(attrs[1].attr.freq, 0);
  ASSERT_EQ(attrs[1].attr.sample_period, 1);
}

// @CddTest = 6.1/C-0-2
TEST(EventSelectionSet, set_cpus_for_new_events) {
  EventSelectionSet event_selection_set(false);
  std::vector<int> online_cpus = GetOnlineCpus();
  ASSERT_FALSE(online_cpus.empty());
  ASSERT_TRUE(event_selection_set.AddEventType("cpu-clock:u"));
  event_selection_set.SetCpusForNewEvents({online_cpus[0]});
  ASSERT_TRUE(event_selection_set.AddEventType("page-faults:u"));
  event_selection_set.SetCpusForNewEvents({online_cpus.back()});
  ASSERT_TRUE(event_selection_set.AddEventGroup({"context-switches:u", "task-clock:u"}));
  event_selection_set.AddMonitoredThreads({gettid()});
  ASSERT_TRUE(event_selection_set.OpenEventFiles());

  std::unordered_map<uint64_t, int> id_to_cpu = event_selection_set.GetCpusById();
  auto get_cpu = [&](int id) {
    if (auto it = id_to_cpu.find(id); it != id_to_cpu.end()) {
      return it->second;
    }
    return -2;
  };

  EventAttrIds attrs = event_selection_set.GetEventAttrWithId();
  ASSERT_EQ(attrs.size(), 4);
  ASSERT_EQ(GetEventNameByAttr(attrs[0].attr), "cpu-clock:u");
  ASSERT_EQ(attrs[0].ids.size(), 1);
  ASSERT_EQ(get_cpu(attrs[0].ids[0]), online_cpus[0]);
  ASSERT_EQ(GetEventNameByAttr(attrs[1].attr), "page-faults:u");
  ASSERT_EQ(attrs[1].ids.size(), 1);
  ASSERT_EQ(get_cpu(attrs[1].ids[0]), online_cpus[0]);
  ASSERT_EQ(GetEventNameByAttr(attrs[2].attr), "context-switches:u");
  ASSERT_EQ(attrs[2].ids.size(), 1);
  ASSERT_EQ(get_cpu(attrs[2].ids[0]), online_cpus.back());
  ASSERT_EQ(GetEventNameByAttr(attrs[3].attr), "task-clock:u");
  ASSERT_EQ(attrs[3].ids.size(), 1);
  ASSERT_EQ(get_cpu(attrs[3].ids[0]), online_cpus.back());
}
