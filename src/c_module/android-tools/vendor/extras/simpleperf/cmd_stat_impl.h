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

#pragma once

#include <math.h>
#include <sys/types.h>

#include <algorithm>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

#include <android-base/stringprintf.h>

#include "SampleComparator.h"
#include "command.h"
#include "event_selection_set.h"

namespace simpleperf {

struct CounterSum {
  uint64_t value = 0;
  uint64_t time_enabled = 0;
  uint64_t time_running = 0;

  void FromCounter(const PerfCounter& counter) {
    value = counter.value;
    time_enabled = counter.time_enabled;
    time_running = counter.time_running;
  }

  void ToCounter(PerfCounter& counter) const {
    counter.value = value;
    counter.time_enabled = time_enabled;
    counter.time_running = time_running;
  }

  CounterSum operator+(const CounterSum& other) const {
    CounterSum res;
    res.value = value + other.value;
    res.time_enabled = time_enabled + other.time_enabled;
    res.time_running = time_running + other.time_running;
    return res;
  }

  CounterSum operator-(const CounterSum& other) const {
    CounterSum res;
    res.value = value - other.value;
    res.time_enabled = time_enabled - other.time_enabled;
    res.time_running = time_running - other.time_running;
    return res;
  }
};

struct ThreadInfo {
  pid_t tid;
  pid_t pid;
  std::string name;
};

struct CounterSummary {
  std::string type_name;
  std::string modifier;
  uint32_t group_id;
  const ThreadInfo* thread;
  int cpu;  // -1 represents all cpus
  uint64_t count;
  uint64_t runtime_in_ns;
  double scale;
  std::string readable_count;
  std::string comment;
  bool auto_generated;

  // used to sort summaries by count_per_thread
  uint64_t count_per_thread = 0;

  CounterSummary(const std::string& type_name, const std::string& modifier, uint32_t group_id,
                 const ThreadInfo* thread, int cpu, uint64_t count, uint64_t runtime_in_ns,
                 double scale, bool auto_generated, bool csv)
      : type_name(type_name),
        modifier(modifier),
        group_id(group_id),
        thread(thread),
        cpu(cpu),
        count(count),
        runtime_in_ns(runtime_in_ns),
        scale(scale),
        auto_generated(auto_generated) {
    readable_count = ReadableCountValue(csv);
  }

  bool IsMonitoredAtTheSameTime(const CounterSummary& other) const {
    // Two summaries are monitored at the same time if they are in the same
    // group or are monitored all the time.
    if (group_id == other.group_id) {
      return true;
    }
    return IsMonitoredAllTheTime() && other.IsMonitoredAllTheTime();
  }

  std::string Name() const {
    if (modifier.empty()) {
      return type_name;
    }
    return type_name + ":" + modifier;
  }

  bool IsMonitoredAllTheTime() const {
    // If an event runs all the time it is enabled (by not sharing hardware
    // counters with other events), the scale of its summary is usually within
    // [1, 1 + 1e-5]. By setting SCALE_ERROR_LIMIT to 1e-5, We can identify
    // events monitored all the time in most cases while keeping the report
    // error rate <= 1e-5.
    constexpr double SCALE_ERROR_LIMIT = 1e-5;
    return (fabs(scale - 1.0) < SCALE_ERROR_LIMIT);
  }

 private:
  std::string ReadableCountValue(bool csv);
};

BUILD_COMPARE_VALUE_FUNCTION_REVERSE(CompareSummaryCount, count);
BUILD_COMPARE_VALUE_FUNCTION_REVERSE(CompareSummaryCountPerThread, count_per_thread);
BUILD_COMPARE_VALUE_FUNCTION(CompareSummaryCpu, cpu);
BUILD_COMPARE_VALUE_FUNCTION(CompareSummaryPid, thread->pid);
BUILD_COMPARE_VALUE_FUNCTION(CompareSummaryTid, thread->tid);
BUILD_COMPARE_VALUE_FUNCTION(CompareSummaryComm, thread->name);

using SummaryComparator = SampleComparator<CounterSummary>;

inline std::optional<SummaryComparator> BuildSummaryComparator(const std::vector<std::string>& keys,
                                                               bool report_per_thread,
                                                               bool report_per_core) {
  SummaryComparator comparator;
  for (auto& key : keys) {
    if (key == "count") {
      comparator.AddCompareFunction(CompareSummaryCount);
    } else if (key == "count_per_thread") {
      if (report_per_thread) {
        comparator.AddCompareFunction(CompareSummaryCountPerThread);
      }
    } else if (key == "cpu") {
      if (report_per_core) {
        comparator.AddCompareFunction(CompareSummaryCpu);
      }
    } else if (key == "pid") {
      if (report_per_thread) {
        comparator.AddCompareFunction(CompareSummaryPid);
      }
    } else if (key == "tid") {
      if (report_per_thread) {
        comparator.AddCompareFunction(CompareSummaryTid);
      }
    } else if (key == "comm") {
      if (report_per_thread) {
        comparator.AddCompareFunction(CompareSummaryComm);
      }
    } else {
      LOG(ERROR) << "Unknown sort key: " << key;
      return {};
    }
  }
  return comparator;
}

// Build a vector of CounterSummary.
class CounterSummaryBuilder {
 public:
  CounterSummaryBuilder(bool report_per_thread, bool report_per_core, bool csv,
                        const std::unordered_map<pid_t, ThreadInfo>& thread_map,
                        const std::optional<SummaryComparator>& comparator)
      : report_per_thread_(report_per_thread),
        report_per_core_(report_per_core),
        csv_(csv),
        thread_map_(thread_map),
        summary_comparator_(comparator) {}

  void AddCountersForOneEventType(const CountersInfo& info) {
    std::unordered_map<uint64_t, CounterSum> sum_map;
    for (const auto& counter : info.counters) {
      uint64_t key = 0;
      if (report_per_thread_) {
        key |= counter.tid;
      }
      if (report_per_core_) {
        key |= static_cast<uint64_t>(counter.cpu) << 32;
      }
      CounterSum& sum = sum_map[key];
      CounterSum add;
      add.FromCounter(counter.counter);
      sum = sum + add;
    }
    size_t pre_sum_count = summaries_.size();
    for (const auto& pair : sum_map) {
      pid_t tid = report_per_thread_ ? static_cast<pid_t>(pair.first & UINT32_MAX) : 0;
      int cpu = report_per_core_ ? static_cast<int>(pair.first >> 32) : -1;
      const CounterSum& sum = pair.second;
      AddSummary(info, tid, cpu, sum);
    }
    if (report_per_thread_ || report_per_core_) {
      SortSummaries(summaries_.begin() + pre_sum_count, summaries_.end());
    }
  }

  std::vector<CounterSummary> Build() {
    std::vector<CounterSummary> res = std::move(summaries_);
    summaries_.clear();
    return res;
  }

 private:
  void AddSummary(const CountersInfo& info, pid_t tid, int cpu, const CounterSum& sum) {
    double scale = 1.0;
    if (sum.time_running < sum.time_enabled && sum.time_running != 0) {
      scale = static_cast<double>(sum.time_enabled) / sum.time_running;
    }
    if ((report_per_thread_ || report_per_core_) && sum.time_running == 0) {
      // No need to report threads or cpus not running.
      return;
    }
    const ThreadInfo* thread = nullptr;
    if (report_per_thread_) {
      auto it = thread_map_.find(tid);
      CHECK(it != thread_map_.end());
      thread = &it->second;
    }
    summaries_.emplace_back(info.event_name, info.event_modifier, info.group_id, thread, cpu,
                            sum.value, sum.time_running, scale, false, csv_);
  }

  void SortSummaries(std::vector<CounterSummary>::iterator begin,
                     std::vector<CounterSummary>::iterator end) {
    // Generate count_per_thread value for sorting.
    if (report_per_thread_) {
      if (report_per_core_) {
        std::unordered_map<pid_t, uint64_t> count_per_thread;
        for (auto it = begin; it != end; ++it) {
          count_per_thread[it->thread->tid] += it->count;
        }
        for (auto it = begin; it != end; ++it) {
          it->count_per_thread = count_per_thread[it->thread->tid];
        }
      } else {
        for (auto it = begin; it != end; ++it) {
          it->count_per_thread = it->count;
        }
      }
    }

    std::sort(begin, end, summary_comparator_.value());
  };

  const bool report_per_thread_;
  const bool report_per_core_;
  const bool csv_;
  const std::unordered_map<pid_t, ThreadInfo>& thread_map_;
  const std::optional<SummaryComparator>& summary_comparator_;
  std::vector<CounterSummary> summaries_;
};

class CounterSummaries {
 public:
  explicit CounterSummaries(std::vector<CounterSummary>&& summaries, bool csv)
      : summaries_(std::move(summaries)), csv_(csv) {}
  const std::vector<CounterSummary>& Summaries() { return summaries_; }

  const CounterSummary* FindSummary(const std::string& type_name, const std::string& modifier,
                                    const ThreadInfo* thread, int cpu);

  // If we have two summaries monitoring the same event type at the same time,
  // that one is for user space only, and the other is for kernel space only;
  // then we can automatically generate a summary combining the two results.
  // For example, a summary of branch-misses:u and a summary for branch-misses:k
  // can generate a summary of branch-misses.
  void AutoGenerateSummaries();
  void GenerateComments(double duration_in_sec);
  void Show(FILE* fp);

 private:
  std::string GetCommentForSummary(const CounterSummary& s, double duration_in_sec);
  std::string GetRateComment(const CounterSummary& s, char sep);
  bool FindRunningTimeForSummary(const CounterSummary& summary, double* running_time_in_sec);
  void ShowCSV(FILE* fp, bool show_thread, bool show_core);
  void ShowText(FILE* fp, bool show_thread, bool show_core);

 private:
  std::vector<CounterSummary> summaries_;
  bool csv_;
};

inline const OptionFormatMap& GetStatCmdOptionFormats() {
  static const OptionFormatMap option_formats = {
      {"-a", {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::NOT_ALLOWED}},
      {"--app", {OptionValueType::STRING, OptionType::SINGLE, AppRunnerType::NOT_ALLOWED}},
      {"--cpu", {OptionValueType::STRING, OptionType::ORDERED, AppRunnerType::ALLOWED}},
      {"--csv", {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
      {"--duration", {OptionValueType::DOUBLE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
      {"--interval", {OptionValueType::DOUBLE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
      {"--interval-only-values",
       {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
      {"-e", {OptionValueType::STRING, OptionType::ORDERED, AppRunnerType::ALLOWED}},
      {"--group", {OptionValueType::STRING, OptionType::ORDERED, AppRunnerType::ALLOWED}},
      {"--in-app", {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
      {"--kprobe", {OptionValueType::STRING, OptionType::MULTIPLE, AppRunnerType::NOT_ALLOWED}},
      {"--no-inherit", {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
      {"-o", {OptionValueType::STRING, OptionType::SINGLE, AppRunnerType::NOT_ALLOWED}},
      {"--out-fd", {OptionValueType::UINT, OptionType::SINGLE, AppRunnerType::CHECK_FD}},
      {"-p", {OptionValueType::STRING, OptionType::MULTIPLE, AppRunnerType::ALLOWED}},
      {"--per-core", {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
      {"--per-thread", {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
      {"--print-hw-counter", {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
      {"--sort", {OptionValueType::STRING, OptionType::SINGLE, AppRunnerType::ALLOWED}},
      {"--stop-signal-fd", {OptionValueType::UINT, OptionType::SINGLE, AppRunnerType::CHECK_FD}},
      {"-t", {OptionValueType::STRING, OptionType::MULTIPLE, AppRunnerType::ALLOWED}},
      {"--tp-filter", {OptionValueType::STRING, OptionType::ORDERED, AppRunnerType::ALLOWED}},
      {"--tracepoint-events",
       {OptionValueType::STRING, OptionType::SINGLE, AppRunnerType::CHECK_PATH}},
      {"--use-devfreq-counters",
       {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::NOT_ALLOWED}},
      {"--verbose", {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
  };
  return option_formats;
}

}  // namespace simpleperf