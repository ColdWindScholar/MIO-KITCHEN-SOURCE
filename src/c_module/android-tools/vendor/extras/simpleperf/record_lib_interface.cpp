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

#define SIMPLEPERF_EXPORT __attribute__((visibility("default")))
#include "include/simpleperf.h"

#include <memory>
#include <set>
#include <string>
#include <vector>

#include <android-base/logging.h>

#include "environment.h"
#include "event_attr.h"
#include "event_fd.h"
#include "event_selection_set.h"
#include "event_type.h"

namespace simpleperf {

std::vector<std::string> GetAllEvents() {
  std::vector<std::string> result;
  if (!CheckPerfEventLimit()) {
    return result;
  }
  auto callback = [&](const EventType& type) {
    perf_event_attr attr = CreateDefaultPerfEventAttr(type);
    if (IsEventAttrSupported(attr, type.name)) {
      result.push_back(type.name);
    }
    return true;
  };
  EventTypeManager::Instance().ForEachType(callback);
  return result;
}

bool IsEventSupported(const std::string& name) {
  if (!CheckPerfEventLimit()) {
    return false;
  }
  std::unique_ptr<EventTypeAndModifier> type = ParseEventType(name);
  if (type == nullptr) {
    return false;
  }
  perf_event_attr attr = CreateDefaultPerfEventAttr(type->event_type);
  return IsEventAttrSupported(attr, type->name);
}

class PerfEventSetImpl : public PerfEventSet {
 public:
  virtual ~PerfEventSetImpl() {}

  bool AddEvent(const std::string& name) override {
    if (!IsEventSupported(name)) {
      return false;
    }
    event_names_.push_back(name);
    return true;
  }

  bool MonitorCurrentProcess() override {
    whole_process_ = true;
    return true;
  }

  bool MonitorCurrentThread() override {
    whole_process_ = false;
    threads_.insert(gettid());
    return true;
  }

  bool MonitorThreadsInCurrentProcess(const std::vector<pid_t>& threads) override {
    whole_process_ = false;
    std::vector<pid_t> tids = GetThreadsInProcess(getpid());
    for (auto& tid : threads) {
      if (std::find(tids.begin(), tids.end(), tid) == tids.end()) {
        LOG(ERROR) << "Thread " << tid << " doesn't exist in current process.";
        return false;
      }
    }
    threads_.insert(threads.begin(), threads.end());
    return true;
  }

 protected:
  PerfEventSetImpl() : whole_process_(false) {}

  std::vector<std::string> event_names_;
  bool whole_process_;
  std::set<pid_t> threads_;
};

class PerfEventSetForCounting : public PerfEventSetImpl {
 public:
  PerfEventSetForCounting() : in_counting_state_(false) {}
  virtual ~PerfEventSetForCounting() {}

  bool StartCounters() override;
  bool StopCounters() override;
  bool ReadCounters(std::vector<Counter>* counters) override;

 private:
  bool CreateEventSelectionSet();
  void InitAccumulatedCounters();
  bool ReadRawCounters(std::vector<Counter>* counters);
  // Add counter b to a.
  void AddCounter(Counter& a, const Counter& b);
  // Sub counter b from a.
  void SubCounter(Counter& a, const Counter& b);

  bool in_counting_state_;
  std::unique_ptr<EventSelectionSet> event_selection_set_;
  // The counters at the last time calling StartCounting().
  std::vector<Counter> last_start_counters_;
  // The accumulated counters of counting periods, excluding
  // the last one.
  std::vector<Counter> accumulated_counters_;
};

bool PerfEventSetForCounting::CreateEventSelectionSet() {
  std::unique_ptr<EventSelectionSet> set(new EventSelectionSet(true));
  if (event_names_.empty()) {
    LOG(ERROR) << "No events.";
    return false;
  }
  for (const auto& name : event_names_) {
    if (!set->AddEventType(name)) {
      return false;
    }
  }
  if (whole_process_) {
    set->AddMonitoredProcesses({getpid()});
  } else {
    if (threads_.empty()) {
      LOG(ERROR) << "No monitored threads.";
      return false;
    }
    set->AddMonitoredThreads(threads_);
  }
  if (!set->OpenEventFiles()) {
    return false;
  }
  event_selection_set_ = std::move(set);
  return true;
}

void PerfEventSetForCounting::InitAccumulatedCounters() {
  for (const auto& name : event_names_) {
    Counter counter;
    counter.event = name;
    counter.value = 0;
    counter.time_enabled_in_ns = 0;
    counter.time_running_in_ns = 0;
    accumulated_counters_.push_back(counter);
  }
}

bool PerfEventSetForCounting::ReadRawCounters(std::vector<Counter>* counters) {
  CHECK(event_selection_set_);
  std::vector<CountersInfo> s;
  if (!event_selection_set_->ReadCounters(&s)) {
    return false;
  }
  CHECK_EQ(s.size(), event_names_.size());
  counters->resize(s.size());
  for (size_t i = 0; i < s.size(); ++i) {
    CountersInfo& info = s[i];
    std::string name =
        info.event_modifier.empty() ? info.event_name : info.event_name + ":" + info.event_modifier;
    CHECK_EQ(name, event_names_[i]);
    Counter& sum = (*counters)[i];
    sum.event = name;
    sum.value = 0;
    sum.time_enabled_in_ns = 0;
    sum.time_running_in_ns = 0;
    for (CounterInfo& c : info.counters) {
      sum.value += c.counter.value;
      sum.time_enabled_in_ns += c.counter.time_enabled;
      sum.time_running_in_ns += c.counter.time_running;
    }
  }
  return true;
}

void PerfEventSetForCounting::AddCounter(Counter& a, const Counter& b) {
  a.value += b.value;
  a.time_enabled_in_ns += b.time_enabled_in_ns;
  a.time_running_in_ns += b.time_enabled_in_ns;
}

void PerfEventSetForCounting::SubCounter(Counter& a, const Counter& b) {
  a.value -= b.value;
  a.time_enabled_in_ns -= b.time_enabled_in_ns;
  a.time_running_in_ns -= b.time_running_in_ns;
}

bool PerfEventSetForCounting::StartCounters() {
  if (in_counting_state_) {
    return true;
  }
  if (event_selection_set_ == nullptr) {
    if (!CreateEventSelectionSet()) {
      return false;
    }
    InitAccumulatedCounters();
  }
  if (!ReadRawCounters(&last_start_counters_)) {
    return false;
  }
  in_counting_state_ = true;
  return true;
}

bool PerfEventSetForCounting::StopCounters() {
  if (!in_counting_state_) {
    return true;
  }
  std::vector<Counter> cur;
  if (!ReadRawCounters(&cur)) {
    return false;
  }
  for (size_t i = 0; i < event_names_.size(); ++i) {
    SubCounter(cur[i], last_start_counters_[i]);
    AddCounter(accumulated_counters_[i], cur[i]);
  }
  in_counting_state_ = false;
  return true;
}

bool PerfEventSetForCounting::ReadCounters(std::vector<Counter>* counters) {
  if (!in_counting_state_) {
    *counters = accumulated_counters_;
    return true;
  }
  if (!ReadRawCounters(counters)) {
    return false;
  }
  for (size_t i = 0; i < event_names_.size(); ++i) {
    SubCounter((*counters)[i], last_start_counters_[i]);
    AddCounter((*counters)[i], accumulated_counters_[i]);
  }
  return true;
}

PerfEventSet* PerfEventSet::CreateInstance(PerfEventSet::Type type) {
  if (!CheckPerfEventLimit()) {
    return nullptr;
  }
  if (type == Type::kPerfForCounting) {
    return new PerfEventSetForCounting;
  }
  return nullptr;
}

bool PerfEventSet::AddEvent(const std::string&) {
  return false;
}

bool PerfEventSet::MonitorCurrentProcess() {
  return false;
}

bool PerfEventSet::MonitorCurrentThread() {
  return false;
}

bool PerfEventSet::MonitorThreadsInCurrentProcess(const std::vector<pid_t>&) {
  return false;
}

bool PerfEventSet::StartCounters() {
  return false;
}

bool PerfEventSet::StopCounters() {
  return false;
}

bool PerfEventSet::ReadCounters(std::vector<Counter>*) {
  return false;
}

}  // namespace simpleperf
