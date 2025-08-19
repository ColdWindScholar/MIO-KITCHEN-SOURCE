/*
 * Copyright (C) 2018 The Android Open Source Project
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

#include <memory>
#include <queue>
#include <string>
#include <unordered_map>
#include <vector>

#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/stringprintf.h>

#include "SampleDisplayer.h"
#include "command.h"
#include "event_selection_set.h"
#include "record.h"
#include "record_file.h"
#include "tracing.h"
#include "utils.h"

namespace simpleperf {
namespace {

using android::base::StringPrintf;

struct SampleInfo {
  uint64_t timestamp;      // the time when the kernel generates the sample
  uint64_t runtime_in_ns;  // the runtime of the thread in the sample
  SampleInfo(uint64_t timestamp = 0, uint64_t runtime_in_ns = 0)
      : timestamp(timestamp), runtime_in_ns(runtime_in_ns) {}
};

struct SpinInfo {
  uint64_t spinloop_count = 0;
  double max_rate = 0;
  uint64_t max_rate_start_timestamp = 0;
  uint64_t max_rate_end_timestamp = 0;
  std::queue<SampleInfo> samples_in_check_period;
  uint64_t runtime_in_check_period = 0;
};

struct ThreadInfo {
  pid_t process_id = 0;
  pid_t thread_id = 0;
  std::string name;
  uint64_t total_runtime_in_ns = 0;
  SpinInfo spin_info;
};

struct ProcessInfo {
  pid_t process_id = 0;
  std::string name;
  uint64_t total_runtime_in_ns = 0;
  std::vector<const ThreadInfo*> threads;
};

class TraceSchedCommand : public Command {
 public:
  TraceSchedCommand()
      : Command("trace-sched", "Trace system-wide process runtime events.",
                // clang-format off
"Records system-wide sched:sched_stat_runtime events, reports runtime taken\n"
"by each process during recording, and optionally warns about processes which\n"
"may have spinloops.\n"
"Usage: simpleperf trace-sched [options]\n"
"--duration time_in_sec  Monitor for time_in_sec seconds. Here time_in_sec may\n"
"                        be any positive floating point number. Default is 10.\n"
"--check-spinloop check_period_in_sec\n"
"        Give warning for threads which may be spinning. A thread is\n"
"        thought of spinning on the CPU, when it takes more than\n"
"        [spin-rate] * [check_period] cpu time in any [check_period].\n"
"        [spin-rate] can be set by --spin-rate. Default check_period is 1 sec.\n"
"--spin-rate spin-rate   Default is 0.8. Vaild range is (0, 1].\n"
"--show-threads          Show runtime of each thread.\n"
"--record-file file_path   Read records from file_path.\n"
                // clang-format on
                ),
        duration_in_sec_(10.0),
        spinloop_check_period_in_sec_(1.0),
        spinloop_check_rate_(0.8),
        show_threads_(false) {}

  bool Run(const std::vector<std::string>& args);

 private:
  bool ParseOptions(const std::vector<std::string>& args);
  bool RecordSchedEvents(const std::string& record_file_path);
  bool ParseSchedEvents(const std::string& record_file_path);
  bool ProcessRecord(Record& record);
  void ProcessSampleRecord(const SampleRecord& record);
  std::vector<ProcessInfo> BuildProcessInfo();
  void ReportProcessInfo(const std::vector<ProcessInfo>& processes);

  double duration_in_sec_;
  double spinloop_check_period_in_sec_;
  double spinloop_check_rate_;
  bool show_threads_;
  std::string record_file_;

  StringTracingFieldPlace tracing_field_comm_;
  TracingFieldPlace tracing_field_runtime_;
  std::unordered_map<pid_t, ThreadInfo> thread_map_;
};

bool TraceSchedCommand::Run(const std::vector<std::string>& args) {
  if (!ParseOptions(args)) {
    return false;
  }
  TemporaryFile tmp_file;
  if (record_file_.empty()) {
    if (!RecordSchedEvents(tmp_file.path)) {
      return false;
    }
    record_file_ = tmp_file.path;
  }
  if (!ParseSchedEvents(record_file_)) {
    return false;
  }
  std::vector<ProcessInfo> processes = BuildProcessInfo();
  ReportProcessInfo(processes);
  return true;
}

bool TraceSchedCommand::ParseOptions(const std::vector<std::string>& args) {
  size_t i;
  for (i = 0; i < args.size(); ++i) {
    if (args[i] == "--duration") {
      if (!GetDoubleOption(args, &i, &duration_in_sec_, 1e-9)) {
        return false;
      }
    } else if (args[i] == "--check-spinloop") {
      if (!GetDoubleOption(args, &i, &spinloop_check_period_in_sec_, 1e-9)) {
        return false;
      }
    } else if (args[i] == "--spin-rate") {
      if (!GetDoubleOption(args, &i, &spinloop_check_rate_, 1e-9, 1.0)) {
        return false;
      }
    } else if (args[i] == "--show-threads") {
      show_threads_ = true;
    } else if (args[i] == "--record-file") {
      if (!NextArgumentOrError(args, &i)) {
        return false;
      }
      record_file_ = args[i];
    } else {
      ReportUnknownOption(args, i);
      return false;
    }
  }
  return true;
}

bool TraceSchedCommand::RecordSchedEvents(const std::string& record_file_path) {
  if (!IsRoot()) {
    LOG(ERROR) << "Need root privilege to trace system wide events.\n";
    return false;
  }
  std::unique_ptr<Command> record_cmd = CreateCommandInstance("record");
  CHECK(record_cmd);
  std::vector<std::string> record_args = {"-e",
                                          "sched:sched_stat_runtime",
                                          "-a",
                                          "--duration",
                                          std::to_string(duration_in_sec_),
                                          "-o",
                                          record_file_path};
  if (IsSettingClockIdSupported()) {
    record_args.push_back("--clockid");
    record_args.push_back("monotonic");
  }
  return record_cmd->Run(record_args);
}

bool TraceSchedCommand::ParseSchedEvents(const std::string& record_file_path) {
  std::unique_ptr<RecordFileReader> reader = RecordFileReader::CreateInstance(record_file_path);
  if (!reader) {
    return false;
  }
  const EventType* event = FindEventTypeByName("sched:sched_stat_runtime");
  const EventAttrIds& attrs = reader->AttrSection();
  if (attrs.size() != 1u || attrs[0].attr.type != event->type ||
      attrs[0].attr.config != event->config) {
    LOG(ERROR) << "sched:sched_stat_runtime isn't recorded in " << record_file_path;
    return false;
  }

  auto callback = [this](std::unique_ptr<Record> record) { return ProcessRecord(*record); };
  return reader->ReadDataSection(callback);
}

bool TraceSchedCommand::ProcessRecord(Record& record) {
  switch (record.type()) {
    case PERF_RECORD_SAMPLE: {
      ProcessSampleRecord(*static_cast<SampleRecord*>(&record));
      break;
    }
    case PERF_RECORD_COMM: {
      const CommRecord& r = *static_cast<const CommRecord*>(&record);
      auto& thread = thread_map_[r.data->tid];
      thread.process_id = r.data->pid;
      thread.thread_id = r.data->tid;
      thread.name = r.comm;
      break;
    }
    case PERF_RECORD_FORK: {
      const ForkRecord& r = *static_cast<const ForkRecord*>(&record);
      auto& parent_thread = thread_map_[r.data->ptid];
      auto& child_thread = thread_map_[r.data->tid];
      parent_thread.process_id = r.data->ppid;
      parent_thread.thread_id = r.data->ptid;
      child_thread.process_id = r.data->pid;
      child_thread.thread_id = r.data->tid;
      child_thread.name = parent_thread.name;
      break;
    }
    case PERF_RECORD_TRACING_DATA:
    case SIMPLE_PERF_RECORD_TRACING_DATA: {
      const TracingDataRecord& r = *static_cast<const TracingDataRecord*>(&record);
      auto tracing = Tracing::Create(std::vector<char>(r.data, r.data + r.data_size));
      if (!tracing) {
        return false;
      }
      const EventType* event = FindEventTypeByName("sched:sched_stat_runtime");
      CHECK(event != nullptr);
      std::optional<TracingFormat> format = tracing->GetTracingFormatHavingId(event->config);
      if (!format.has_value()) {
        return false;
      }
      format.value().GetField("comm", tracing_field_comm_);
      format.value().GetField("runtime", tracing_field_runtime_);
      break;
    }
  }
  return true;
}

void TraceSchedCommand::ProcessSampleRecord(const SampleRecord& record) {
  std::string thread_name = tracing_field_comm_.ReadFromData(record.raw_data.data);
  uint64_t runtime = tracing_field_runtime_.ReadFromData(record.raw_data.data);
  ThreadInfo& thread = thread_map_[record.tid_data.tid];
  thread.process_id = record.tid_data.pid;
  thread.thread_id = record.tid_data.tid;
  thread.name = thread_name;
  thread.total_runtime_in_ns += runtime;
  SpinInfo& spin_info = thread.spin_info;
  spin_info.runtime_in_check_period += runtime;
  spin_info.samples_in_check_period.push(SampleInfo(record.Timestamp(), runtime));

  // Check spin loop.
  if (thread.spin_info.samples_in_check_period.size() == 1u) {
    return;
  }
  uint64_t start_timestamp = spin_info.samples_in_check_period.front().timestamp;
  uint64_t time_period_in_ns = record.Timestamp() - start_timestamp;
  if (time_period_in_ns < spinloop_check_period_in_sec_ * 1e9) {
    return;
  }
  if (thread.spin_info.runtime_in_check_period > time_period_in_ns * spinloop_check_rate_) {
    // Detect a spin loop.
    thread.spin_info.spinloop_count++;
    double rate = std::min(
        1.0, static_cast<double>(thread.spin_info.runtime_in_check_period) / time_period_in_ns);
    if (rate > thread.spin_info.max_rate) {
      thread.spin_info.max_rate = rate;
      thread.spin_info.max_rate_start_timestamp = start_timestamp;
      thread.spin_info.max_rate_end_timestamp = record.Timestamp();
      // Clear samples to avoid overlapped spin loop periods.
      std::queue<SampleInfo> empty_q;
      std::swap(thread.spin_info.samples_in_check_period, empty_q);
      thread.spin_info.runtime_in_check_period = 0;
    } else {
      thread.spin_info.runtime_in_check_period -=
          spin_info.samples_in_check_period.front().runtime_in_ns;
      thread.spin_info.samples_in_check_period.pop();
    }
  }
}

std::vector<ProcessInfo> TraceSchedCommand::BuildProcessInfo() {
  std::unordered_map<pid_t, ProcessInfo> process_map;
  for (auto& pair : thread_map_) {
    const ThreadInfo& thread = pair.second;
    // No need to report simpleperf.
    if (thread.name == "simpleperf") {
      continue;
    }
    ProcessInfo& process = process_map[thread.process_id];
    process.process_id = thread.process_id;
    if (thread.process_id == thread.thread_id) {
      process.name = thread.name;
    }
    process.total_runtime_in_ns += thread.total_runtime_in_ns;
    process.threads.push_back(&thread);
  }
  std::vector<ProcessInfo> processes;
  for (auto& pair : process_map) {
    processes.push_back(pair.second);
  }
  auto sort_process = [](const ProcessInfo& p1, const ProcessInfo& p2) {
    return p1.total_runtime_in_ns > p2.total_runtime_in_ns;
  };
  auto sort_thread = [](const ThreadInfo* t1, const ThreadInfo* t2) {
    return t1->total_runtime_in_ns > t2->total_runtime_in_ns;
  };
  std::sort(processes.begin(), processes.end(), sort_process);
  for (auto& process : processes) {
    std::sort(process.threads.begin(), process.threads.end(), sort_thread);
  }
  return processes;
}

void TraceSchedCommand::ReportProcessInfo(const std::vector<ProcessInfo>& processes) {
  uint64_t total_runtime_in_ns = 0u;
  for (auto& process : processes) {
    total_runtime_in_ns += process.total_runtime_in_ns;
  }
  printf("Total Runtime: %.3f ms\n", total_runtime_in_ns / 1e6);
  struct ReportEntry {
    bool is_process = false;
    uint64_t runtime_in_ns = 0;
    double percentage = 0;
    pid_t pid = 0;
    std::string name;
  };
  std::vector<ReportEntry> entries;
  for (auto& process : processes) {
    ReportEntry entry;
    entry.is_process = true;
    entry.runtime_in_ns = process.total_runtime_in_ns;
    entry.pid = process.process_id;
    entry.name = process.name;
    entry.percentage = 0.0;
    if (total_runtime_in_ns != 0u) {
      entry.percentage = 100.0 * process.total_runtime_in_ns / total_runtime_in_ns;
    }
    // Omit processes taken too small percentage.
    if (entry.percentage < 0.01) {
      continue;
    }
    entries.push_back(entry);
    if (show_threads_) {
      for (auto& thread : process.threads) {
        ReportEntry entry;
        entry.is_process = false;
        entry.runtime_in_ns = thread->total_runtime_in_ns;
        entry.pid = thread->thread_id;
        entry.name = thread->name;
        entry.percentage = 0.0;
        if (total_runtime_in_ns != 0u) {
          entry.percentage = 100.0 * thread->total_runtime_in_ns / total_runtime_in_ns;
        }
        // Omit threads taken too small percentage.
        if (entry.percentage < 0.01) {
          continue;
        }
        entries.push_back(entry);
      }
    }
  }

  SampleDisplayer<ReportEntry, uint64_t> displayer;
  if (show_threads_) {
    displayer.AddDisplayFunction("Type", [](const ReportEntry* entry) -> std::string {
      return entry->is_process ? "Process" : "Thread";
    });
  }
  displayer.AddDisplayFunction("Runtime", [](const ReportEntry* entry) {
    return StringPrintf("%.3f ms", entry->runtime_in_ns / 1e6);
  });
  displayer.AddDisplayFunction("Percentage", [](const ReportEntry* entry) {
    return StringPrintf("%.2f%%", entry->percentage);
  });
  displayer.AddDisplayFunction(
      "Pid", [](const ReportEntry* entry) { return StringPrintf("%d", entry->pid); });
  displayer.AddDisplayFunction("Name", [](const ReportEntry* entry) { return entry->name; });
  for (auto& entry : entries) {
    displayer.AdjustWidth(&entry);
  }
  displayer.PrintNames(stdout);
  for (auto& entry : entries) {
    displayer.PrintSample(stdout, &entry);
  }

  for (auto& process : processes) {
    for (auto& thread : process.threads) {
      if (thread->spin_info.spinloop_count != 0u) {
        double percentage = 100.0 * thread->spin_info.max_rate;
        double duration_in_ns =
            thread->spin_info.max_rate_end_timestamp - thread->spin_info.max_rate_start_timestamp;
        double running_time_in_ns = duration_in_ns * thread->spin_info.max_rate;
        printf("Detect %" PRIu64
               " spin loops in process %s (%d) thread %s (%d),\n"
               "max rate at [%.6f s - %.6f s], taken %.3f ms / %.3f ms (%.2f%%).\n",
               thread->spin_info.spinloop_count, process.name.c_str(), process.process_id,
               thread->name.c_str(), thread->thread_id,
               thread->spin_info.max_rate_start_timestamp / 1e9,
               thread->spin_info.max_rate_end_timestamp / 1e9, running_time_in_ns / 1e6,
               duration_in_ns / 1e6, percentage);
      }
    }
  }
}

}  // namespace

void RegisterTraceSchedCommand() {
  RegisterCommand("trace-sched", [] { return std::unique_ptr<Command>(new TraceSchedCommand()); });
}

}  // namespace simpleperf
