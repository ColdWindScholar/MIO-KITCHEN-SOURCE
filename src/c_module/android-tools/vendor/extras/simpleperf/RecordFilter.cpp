/*
 * Copyright (C) 2021 The Android Open Source Project
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

#include "RecordFilter.h"

#include "environment.h"
#include "utils.h"

using android::base::Split;
using android::base::Trim;

namespace simpleperf {

namespace {

class CpuFilter : public RecordFilterCondition {
 public:
  void AddCpus(const std::set<int>& cpus) { cpus_.insert(cpus.begin(), cpus.end()); }

  bool Check(const SampleRecord& sample) override {
    int cpu = static_cast<int>(sample.cpu_data.cpu);
    return cpus_.empty() || cpus_.count(cpu) == 1;
  }

 private:
  std::set<int> cpus_;
};

class PidFilter : public RecordFilterCondition {
 public:
  void AddPids(const std::set<pid_t>& pids, bool exclude) {
    auto& dest = exclude ? exclude_pids_ : include_pids_;
    dest.insert(pids.begin(), pids.end());
  }

  bool Check(const SampleRecord& sample) override {
    uint32_t pid = sample.tid_data.pid;
    if (!include_pids_.empty() && include_pids_.count(pid) == 0) {
      return false;
    }
    return exclude_pids_.count(pid) == 0;
  }

 private:
  std::set<pid_t> include_pids_;
  std::set<pid_t> exclude_pids_;
};

class TidFilter : public RecordFilterCondition {
 public:
  void AddTids(const std::set<pid_t>& tids, bool exclude) {
    auto& dest = exclude ? exclude_tids_ : include_tids_;
    dest.insert(tids.begin(), tids.end());
  }

  bool Check(const SampleRecord& sample) override {
    uint32_t tid = sample.tid_data.tid;
    if (!include_tids_.empty() && include_tids_.count(tid) == 0) {
      return false;
    }
    return exclude_tids_.count(tid) == 0;
  }

 private:
  std::set<pid_t> include_tids_;
  std::set<pid_t> exclude_tids_;
};

class ProcessNameFilter : public RecordFilterCondition {
 public:
  ProcessNameFilter(const ThreadTree& thread_tree) : thread_tree_(thread_tree) {}

  bool AddProcessNameRegex(const std::string& process_name, bool exclude) {
    if (auto regex = RegEx::Create(process_name); regex != nullptr) {
      auto& dest = exclude ? exclude_names_ : include_names_;
      dest.emplace_back(std::move(regex));
      return true;
    }
    return false;
  }

  bool Check(const SampleRecord& sample) override {
    ThreadEntry* process = thread_tree_.FindThread(sample.tid_data.pid);
    if (process == nullptr) {
      return false;
    }
    std::string_view process_name = process->comm;
    if (!include_names_.empty() && !SearchInRegs(process_name, include_names_)) {
      return false;
    }
    return !SearchInRegs(process_name, exclude_names_);
  }

 private:
  const ThreadTree& thread_tree_;
  std::vector<std::unique_ptr<RegEx>> include_names_;
  std::vector<std::unique_ptr<RegEx>> exclude_names_;
};

class ThreadNameFilter : public RecordFilterCondition {
 public:
  ThreadNameFilter(const ThreadTree& thread_tree) : thread_tree_(thread_tree) {}

  bool AddThreadNameRegex(const std::string& thread_name, bool exclude) {
    if (auto regex = RegEx::Create(thread_name); regex != nullptr) {
      auto& dest = exclude ? exclude_names_ : include_names_;
      dest.emplace_back(std::move(regex));
      return true;
    }
    return false;
  }

  bool Check(const SampleRecord& sample) override {
    ThreadEntry* thread = thread_tree_.FindThread(sample.tid_data.tid);
    if (thread == nullptr) {
      return false;
    }
    std::string_view thread_name = thread->comm;
    if (!include_names_.empty() && !SearchInRegs(thread_name, include_names_)) {
      return false;
    }
    return !SearchInRegs(thread_name, exclude_names_);
  }

 private:
  const ThreadTree& thread_tree_;
  std::vector<std::unique_ptr<RegEx>> include_names_;
  std::vector<std::unique_ptr<RegEx>> exclude_names_;
};

class UidFilter : public RecordFilterCondition {
 public:
  void AddUids(const std::set<uint32_t>& uids, bool exclude) {
    auto& dest = exclude ? exclude_uids_ : include_uids_;
    dest.insert(uids.begin(), uids.end());
  }

  bool Check(const SampleRecord& sample) override {
    uint32_t pid = sample.tid_data.pid;
    std::optional<uint32_t> uid;
    if (auto it = pid_to_uid_map_.find(pid); it != pid_to_uid_map_.end()) {
      uid = it->second;
    } else {
      uid = GetProcessUid(pid);
      pid_to_uid_map_[pid] = uid;
    }
    if (!uid) {
      return false;
    }
    if (!include_uids_.empty() && include_uids_.count(uid.value()) == 0) {
      return false;
    }
    return exclude_uids_.count(uid.value()) == 0;
  }

 private:
  std::set<uint32_t> include_uids_;
  std::set<uint32_t> exclude_uids_;
  std::unordered_map<uint32_t, std::optional<uint32_t>> pid_to_uid_map_;
};

using TimeRange = std::pair<uint64_t, uint64_t>;

class TimeRanges {
 public:
  void Begin(uint64_t timestamp) {
    if (!begin_time_.has_value()) {
      begin_time_ = timestamp;
    }
  }

  bool End(uint64_t timestamp) {
    if (begin_time_.has_value()) {
      if (begin_time_ >= timestamp) {
        LOG(ERROR) << "Invalid time range in filter data: begin time " << begin_time_.value()
                   << " >= end time " << timestamp;
        return false;
      }
      ranges_.emplace_back(begin_time_.value(), timestamp);
      begin_time_.reset();
    }
    return true;
  }

  void NoMoreTimestamp() {
    if (begin_time_.has_value()) {
      ranges_.emplace_back(begin_time_.value(), UINT64_MAX);
    }
    std::sort(ranges_.begin(), ranges_.end());
  }

  bool Empty() const { return ranges_.empty(); }

  bool InRange(uint64_t timestamp) const {
    auto it = std::upper_bound(ranges_.begin(), ranges_.end(),
                               std::pair<uint64_t, uint64_t>(timestamp, 0));
    if (it != ranges_.end() && it->first == timestamp) {
      return true;
    }
    if (it != ranges_.begin()) {
      --it;
      if (it->second > timestamp) {
        return true;
      }
    }
    return false;
  }

 private:
  std::optional<uint64_t> begin_time_;
  std::vector<TimeRange> ranges_;
};

}  // namespace

class TimeFilter : public RecordFilterCondition {
 public:
  const std::string& GetClock() const { return clock_; }
  void SetClock(const std::string& clock) { clock_ = clock; }

  void GlobalBegin(uint64_t timestamp) { global_ranges_.Begin(timestamp); }

  bool GlobalEnd(uint64_t timestamp) { return global_ranges_.End(timestamp); }

  void ProcessBegin(pid_t pid, uint64_t timestamp) { process_ranges_[pid].Begin(timestamp); }

  bool ProcessEnd(pid_t pid, uint64_t timestamp) { return process_ranges_[pid].End(timestamp); }

  void ThreadBegin(pid_t tid, uint64_t timestamp) { thread_ranges_[tid].Begin(timestamp); }

  bool ThreadEnd(pid_t tid, uint64_t timestamp) { return thread_ranges_[tid].End(timestamp); }

  void NoMoreTimestamp() {
    global_ranges_.NoMoreTimestamp();
    for (auto& p : process_ranges_) {
      p.second.NoMoreTimestamp();
    }
    for (auto& p : thread_ranges_) {
      p.second.NoMoreTimestamp();
    }
  }

  bool Empty() const {
    return global_ranges_.Empty() && process_ranges_.empty() && thread_ranges_.empty();
  }

  bool Check(const SampleRecord& sample) override {
    uint64_t timestamp = sample.Timestamp();
    if (!global_ranges_.Empty() && !global_ranges_.InRange(timestamp)) {
      return false;
    }
    if (!process_ranges_.empty()) {
      auto it = process_ranges_.find(sample.tid_data.pid);
      if (it == process_ranges_.end() || !it->second.InRange(timestamp)) {
        return false;
      }
    }
    if (!thread_ranges_.empty()) {
      auto it = thread_ranges_.find(sample.tid_data.tid);
      if (it == thread_ranges_.end() || !it->second.InRange(timestamp)) {
        return false;
      }
    }
    return true;
  }

 private:
  std::string clock_ = "monotonic";
  TimeRanges global_ranges_;
  std::unordered_map<pid_t, TimeRanges> process_ranges_;
  std::unordered_map<pid_t, TimeRanges> thread_ranges_;
};

// Read filter file. The format is in doc/sample_filter.md.
class FilterFileReader {
 public:
  FilterFileReader(const std::string& filename) : filename_(filename) {}

  bool Read() {
    std::string data;
    if (!android::base::ReadFileToString(filename_, &data)) {
      PLOG(ERROR) << "failed to read " << filename_;
      return false;
    }
    line_number_ = 0;
    time_filter_.reset(new TimeFilter);
    std::string arg_str;
    std::vector<std::string> args;
    uint64_t timestamp;
    pid_t pid;
    for (const auto& line : Split(data, "\n")) {
      line_number_++;
      if (SearchCmd(line, "CLOCK", &arg_str)) {
        if (!SplitArgs(arg_str, 1, &args)) {
          return false;
        }
        time_filter_->SetClock(args[0]);
      } else if (SearchCmd(line, "GLOBAL_BEGIN", &arg_str)) {
        if (!SplitArgs(arg_str, 1, &args) || !ParseTimestamp(args[0], &timestamp)) {
          return false;
        }
        time_filter_->GlobalBegin(timestamp);
      } else if (SearchCmd(line, "GLOBAL_END", &arg_str)) {
        if (!SplitArgs(arg_str, 1, &args) || !ParseTimestamp(args[0], &timestamp) ||
            !time_filter_->GlobalEnd(timestamp)) {
          return false;
        }
      } else if (SearchCmd(line, "PROCESS_BEGIN", &arg_str)) {
        if (!SplitArgs(arg_str, 2, &args) || !ParsePid(args[0], &pid) ||
            !ParseTimestamp(args[1], &timestamp)) {
          return false;
        }
        time_filter_->ProcessBegin(pid, timestamp);
      } else if (SearchCmd(line, "PROCESS_END", &arg_str)) {
        if (!SplitArgs(arg_str, 2, &args) || !ParsePid(args[0], &pid) ||
            !ParseTimestamp(args[1], &timestamp) || !time_filter_->ProcessEnd(pid, timestamp)) {
          return false;
        }
      } else if (SearchCmd(line, "THREAD_BEGIN", &arg_str)) {
        if (!SplitArgs(arg_str, 2, &args) || !ParsePid(args[0], &pid) ||
            !ParseTimestamp(args[1], &timestamp)) {
          return false;
        }
        time_filter_->ThreadBegin(pid, timestamp);
      } else if (SearchCmd(line, "THREAD_END", &arg_str)) {
        if (!SplitArgs(arg_str, 2, &args) || !ParsePid(args[0], &pid) ||
            !ParseTimestamp(args[1], &timestamp) || !time_filter_->ThreadEnd(pid, timestamp)) {
          return false;
        }
      }
    }
    return true;
  }

  std::unique_ptr<TimeFilter>& GetTimeFilter() { return time_filter_; }

 private:
  bool SearchCmd(const std::string& s, const char* cmd, std::string* arg_str) {
    auto pos = s.find(cmd);
    if (pos == s.npos) {
      return false;
    }
    *arg_str = s.substr(pos + strlen(cmd));
    return true;
  }

  bool SplitArgs(const std::string& s, size_t nargs, std::vector<std::string>* args) {
    *args = Split(Trim(s), " ");
    if (args->size() != nargs) {
      LOG(ERROR) << "Invalid args in " << filename_ << ":" << line_number_ << ": " << s;
      return false;
    }
    return true;
  }

  bool ParsePid(const std::string& s, pid_t* pid) {
    if (!android::base::ParseInt(s.c_str(), pid, static_cast<pid_t>(0))) {
      LOG(ERROR) << "Invalid pid in " << filename_ << ":" << line_number_ << ": " << s;
      return false;
    }
    return true;
  }

  bool ParseTimestamp(const std::string& s, uint64_t* timestamp) {
    if (!android::base::ParseUint(s.c_str(), timestamp)) {
      LOG(ERROR) << "Invalid timestamp in " << filename_ << ":" << line_number_ << ": " << s;
      return false;
    }
    return true;
  }

  const std::string filename_;
  size_t line_number_ = 0;
  std::unique_ptr<TimeFilter> time_filter_;
};

RecordFilter::RecordFilter(const ThreadTree& thread_tree) : thread_tree_(thread_tree) {}

RecordFilter::~RecordFilter() {}

bool RecordFilter::ParseOptions(OptionValueMap& options) {
  for (bool exclude : {true, false}) {
    std::string prefix = exclude ? "--exclude-" : "--include-";
    if (auto strs = options.PullStringValues(prefix + "pid"); !strs.empty()) {
      if (auto pids = GetPidsFromStrings(strs, false, false); pids) {
        AddPids(pids.value(), exclude);
      } else {
        return false;
      }
    }
    for (const OptionValue& value : options.PullValues(prefix + "tid")) {
      if (auto tids = GetTidsFromString(value.str_value, false); tids) {
        AddTids(tids.value(), exclude);
      } else {
        return false;
      }
    }
    for (const OptionValue& value : options.PullValues(prefix + "process-name")) {
      if (!AddProcessNameRegex(value.str_value, exclude)) {
        return false;
      }
    }
    for (const OptionValue& value : options.PullValues(prefix + "thread-name")) {
      if (!AddThreadNameRegex(value.str_value, exclude)) {
        return false;
      }
    }
    for (const OptionValue& value : options.PullValues(prefix + "uid")) {
      if (auto uids = ParseUintVector<uint32_t>(value.str_value); uids) {
        AddUids(uids.value(), exclude);
      } else {
        return false;
      }
    }
  }
  for (const OptionValue& value : options.PullValues("--cpu")) {
    if (auto cpus = GetCpusFromString(value.str_value); cpus) {
      AddCpus(cpus.value());
    } else {
      return false;
    }
  }
  if (auto value = options.PullValue("--filter-file"); value) {
    if (!SetFilterFile(value->str_value)) {
      return false;
    }
  }
  return true;
}

void RecordFilter::AddCpus(const std::set<int>& cpus) {
  std::unique_ptr<RecordFilterCondition>& cpu_filter = conditions_["cpu"];
  if (!cpu_filter) {
    cpu_filter.reset(new CpuFilter);
  }
  static_cast<CpuFilter&>(*cpu_filter).AddCpus(cpus);
}

void RecordFilter::AddPids(const std::set<pid_t>& pids, bool exclude) {
  std::unique_ptr<RecordFilterCondition>& pid_filter = conditions_["pid"];
  if (!pid_filter) {
    pid_filter.reset(new PidFilter);
  }
  static_cast<PidFilter&>(*pid_filter).AddPids(pids, exclude);
}

void RecordFilter::AddTids(const std::set<pid_t>& tids, bool exclude) {
  std::unique_ptr<RecordFilterCondition>& tid_filter = conditions_["tid"];
  if (!tid_filter) {
    tid_filter.reset(new TidFilter);
  }
  static_cast<TidFilter&>(*tid_filter).AddTids(tids, exclude);
}

bool RecordFilter::AddProcessNameRegex(const std::string& process_name, bool exclude) {
  std::unique_ptr<RecordFilterCondition>& process_name_filter = conditions_["process_name"];
  if (!process_name_filter) {
    process_name_filter.reset(new ProcessNameFilter(thread_tree_));
  }
  return static_cast<ProcessNameFilter&>(*process_name_filter)
      .AddProcessNameRegex(process_name, exclude);
}

bool RecordFilter::AddThreadNameRegex(const std::string& thread_name, bool exclude) {
  std::unique_ptr<RecordFilterCondition>& thread_name_filter = conditions_["thread_name"];
  if (!thread_name_filter) {
    thread_name_filter.reset(new ThreadNameFilter(thread_tree_));
  }
  return static_cast<ThreadNameFilter&>(*thread_name_filter)
      .AddThreadNameRegex(thread_name, exclude);
}

void RecordFilter::AddUids(const std::set<uint32_t>& uids, bool exclude) {
  std::unique_ptr<RecordFilterCondition>& uid_filter = conditions_["uid"];
  if (!uid_filter) {
    uid_filter.reset(new UidFilter);
  }
  return static_cast<UidFilter&>(*uid_filter).AddUids(uids, exclude);
}

bool RecordFilter::SetFilterFile(const std::string& filename) {
  FilterFileReader reader(filename);
  if (!reader.Read()) {
    return false;
  }
  conditions_["time"] = std::move(reader.GetTimeFilter());
  return true;
}

bool RecordFilter::Check(const SampleRecord& r) {
  for (auto& p : conditions_) {
    if (!p.second->Check(r)) {
      return false;
    }
  }
  return true;
}

bool RecordFilter::CheckClock(const std::string& clock) {
  if (auto it = conditions_.find("time"); it != conditions_.end()) {
    TimeFilter& time_filter = static_cast<TimeFilter&>(*it->second);
    if (time_filter.GetClock() != clock) {
      LOG(ERROR) << "clock generating sample timestamps is " << clock
                 << ", which doesn't match clock used in time filter " << time_filter.GetClock();
      return false;
    }
  }
  return true;
}

void RecordFilter::Clear() {
  conditions_.clear();
}

}  // namespace simpleperf
