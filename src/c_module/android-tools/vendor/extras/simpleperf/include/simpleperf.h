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

#ifndef _SIMPLEPERF_H
#define _SIMPLEPERF_H

#include <sys/types.h>

#include <string>
#include <vector>

#ifndef SIMPLEPERF_EXPORT
#define SIMPLEPERF_EXPORT
#endif

namespace simpleperf {

std::vector<std::string> GetAllEvents() SIMPLEPERF_EXPORT;
bool IsEventSupported(const std::string& name) SIMPLEPERF_EXPORT;

struct Counter {
  std::string event;
  uint64_t value;
  // If there is not enough hardware counters, kernel will share counters between events.
  // time_enabled_in_ns is the period when counting is enabled, and time_running_in_ns is
  // the period when counting really happens in hardware.
  uint64_t time_enabled_in_ns;
  uint64_t time_running_in_ns;
};

// PerfEventSet can be used to count perf events or record perf events in perf.data.
// To count perf events, you can do as follows:
//  1. Create PerfEventSet instance.
//  2. Select perf events to count. You can add more than one events.
//  3. Set monitored targets.
//  4. Start/stop/read counters when needed.
// An example is as below:
//    PerfEventSet* perf = PerfEventSet::CreateInstance(PerfEventSetType::kPerfForCounting);
//    perf->AddEvent("cpu-cycles");
//    perf->AddEvent("instructions");
//    perf->MonitorCurrentProcess();
//    perf->StartCounters();
//    perf->StopCounters();
//    perf->ReadCounters(&counters);
//
// PerfEventSet is not thread-safe. To access it from different threads, please protect
// it under locks.
class SIMPLEPERF_EXPORT PerfEventSet {
 public:
  enum Type {
    kPerfForCounting,
    kPerfForRecording,
  };

  static PerfEventSet* CreateInstance(Type type);
  virtual ~PerfEventSet() {}

  // Add event in the set. All valid events are returned by GetAllEvents().
  // To only monitor events happen in user space, add :u suffix, like cpu-cycles:u.
  virtual bool AddEvent(const std::string& name);

  // Set monitored target. You can only monitor threads in current process.
  virtual bool MonitorCurrentProcess();
  virtual bool MonitorCurrentThread();
  virtual bool MonitorThreadsInCurrentProcess(const std::vector<pid_t>& threads);

  // Counting interface:
  // Start counters. When the PerfEventSet instance is created, the counters are stopped.
  virtual bool StartCounters();
  // Stop counters. The values of the counters will not change until the next StartCounters().
  virtual bool StopCounters();
  // Read counter values. There is a value for each event. You don't need to stop counters before
  // reading them. The counter values are the accumulated value from the first StartCounters().
  virtual bool ReadCounters(std::vector<Counter>* counters);

 protected:
  PerfEventSet() {}
};

}  // namespace simpleperf

#undef SIMPLEPERF_EXPORT

#endif  // _SIMPLEPERF_H
