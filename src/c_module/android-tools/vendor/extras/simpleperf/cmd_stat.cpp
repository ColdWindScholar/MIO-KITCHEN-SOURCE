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

#include <inttypes.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/prctl.h>

#include <algorithm>
#include <chrono>
#include <optional>
#include <set>
#include <string>
#include <string_view>
#include <vector>

#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/strings.h>
#include <android-base/unique_fd.h>

#include "IOEventLoop.h"
#include "ProbeEvents.h"
#include "cmd_stat_impl.h"
#include "command.h"
#include "environment.h"
#include "event_attr.h"
#include "event_fd.h"
#include "event_selection_set.h"
#include "event_type.h"
#include "utils.h"
#include "workload.h"

namespace simpleperf {

using android::base::Split;

static std::vector<std::string> default_measured_event_types{
    "cpu-cycles",   "stalled-cycles-frontend", "stalled-cycles-backend",
    "instructions", "branch-instructions",     "branch-misses",
    "task-clock",   "context-switches",        "page-faults",
};

static const std::unordered_map<std::string_view, std::pair<std::string_view, std::string_view>>
    COMMON_EVENT_RATE_MAP = {
        {"cache-misses", {"cache-references", "miss rate"}},
        {"branch-misses", {"branch-instructions", "miss rate"}},
};

static const std::unordered_map<std::string_view, std::pair<std::string_view, std::string_view>>
    ARM_EVENT_RATE_MAP = {
        // Refer to "D6.10.5 Meaningful ratios between common microarchitectural events" in ARMv8
        // specification.
        {"raw-l1i-cache-refill", {"raw-l1i-cache", "level 1 instruction cache refill rate"}},
        {"raw-l1i-tlb-refill", {"raw-l1i-tlb", "level 1 instruction TLB refill rate"}},
        {"raw-l1d-cache-refill", {"raw-l1d-cache", "level 1 data or unified cache refill rate"}},
        {"raw-l1d-tlb-refill", {"raw-l1d-tlb", "level 1 data or unified TLB refill rate"}},
        {"raw-l2d-cache-refill", {"raw-l2d-cache", "level 2 data or unified cache refill rate"}},
        {"raw-l2i-cache-refill", {"raw-l2i-cache", "level 2 instruction cache refill rate"}},
        {"raw-l3d-cache-refill", {"raw-l3d-cache", "level 3 data or unified cache refill rate"}},
        {"raw-l2d-tlb-refill", {"raw-l2d-tlb", "level 2 data or unified TLB refill rate"}},
        {"raw-l2i-tlb-refill", {"raw-l2i-tlb", "level 2 instruction TLB refill rate"}},
        {"raw-bus-access", {"raw-bus-cycles", "bus accesses per cycle"}},
        {"raw-ll-cache-miss", {"raw-ll-cache", "last level data or unified cache refill rate"}},
        {"raw-dtlb-walk", {"raw-l1d-tlb", "data TLB miss rate"}},
        {"raw-itlb-walk", {"raw-l1i-tlb", "instruction TLB miss rate"}},
        {"raw-ll-cache-miss-rd", {"raw-ll-cache-rd", "memory read operation miss rate"}},
        {"raw-remote-access-rd",
         {"raw-remote-access", "read accesses to another socket in a multi-socket system"}},
        // Refer to "Table K3-2 Relationship between REFILL events and associated access events" in
        // ARMv8 specification.
        {"raw-l1d-cache-refill-rd", {"raw-l1d-cache-rd", "level 1 cache refill rate, read"}},
        {"raw-l1d-cache-refill-wr", {"raw-l1d-cache-wr", "level 1 cache refill rate, write"}},
        {"raw-l1d-tlb-refill-rd", {"raw-l1d-tlb-rd", "level 1 TLB refill rate, read"}},
        {"raw-l1d-tlb-refill-wr", {"raw-l1d-tlb-wr", "level 1 TLB refill rate, write"}},
        {"raw-l2d-cache-refill-rd", {"raw-l2d-cache-rd", "level 2 data cache refill rate, read"}},
        {"raw-l2d-cache-refill-wr", {"raw-l2d-cache-wr", "level 2 data cache refill rate, write"}},
        {"raw-l2d-tlb-refill-rd", {"raw-l2d-tlb-rd", "level 2 data TLB refill rate, read"}},
};

std::string CounterSummary::ReadableCountValue(bool csv) {
  if (type_name == "cpu-clock" || type_name == "task-clock") {
    // Convert nanoseconds to milliseconds.
    double value = count / 1e6;
    return android::base::StringPrintf("%lf(ms)", value);
  }
  if (csv) {
    return android::base::StringPrintf("%" PRIu64, count);
  }
  return ReadableCount(count);
}

const CounterSummary* CounterSummaries::FindSummary(const std::string& type_name,
                                                    const std::string& modifier,
                                                    const ThreadInfo* thread, int cpu) {
  for (const auto& s : summaries_) {
    if (s.type_name == type_name && s.modifier == modifier && s.thread == thread && s.cpu == cpu) {
      return &s;
    }
  }
  return nullptr;
}

void CounterSummaries::AutoGenerateSummaries() {
  for (size_t i = 0; i < summaries_.size(); ++i) {
    const CounterSummary& s = summaries_[i];
    if (s.modifier == "u") {
      const CounterSummary* other = FindSummary(s.type_name, "k", s.thread, s.cpu);
      if (other != nullptr && other->IsMonitoredAtTheSameTime(s)) {
        if (FindSummary(s.type_name, "", s.thread, s.cpu) == nullptr) {
          summaries_.emplace_back(s.type_name, "", s.group_id, s.thread, s.cpu,
                                  s.count + other->count, s.runtime_in_ns, s.scale, true, csv_);
        }
      }
    }
  }
}

void CounterSummaries::GenerateComments(double duration_in_sec) {
  for (auto& s : summaries_) {
    s.comment = GetCommentForSummary(s, duration_in_sec);
  }
}

void CounterSummaries::Show(FILE* fp) {
  bool show_thread = !summaries_.empty() && summaries_[0].thread != nullptr;
  bool show_cpu = !summaries_.empty() && summaries_[0].cpu != -1;
  if (csv_) {
    ShowCSV(fp, show_thread, show_cpu);
  } else {
    ShowText(fp, show_thread, show_cpu);
  }
}

void CounterSummaries::ShowCSV(FILE* fp, bool show_thread, bool show_cpu) {
  for (auto& s : summaries_) {
    if (show_thread) {
      fprintf(fp, "%s,%d,%d,", s.thread->name.c_str(), s.thread->pid, s.thread->tid);
    }
    if (show_cpu) {
      fprintf(fp, "%d,", s.cpu);
    }
    fprintf(fp, "%s,%s,%s,%s\n", s.readable_count.c_str(), s.Name().c_str(), s.comment.c_str(),
            (s.auto_generated ? "(generated)," : ""));
  }
}

void CounterSummaries::ShowText(FILE* fp, bool show_thread, bool show_cpu) {
  std::vector<std::string> titles;

  if (show_thread) {
    titles = {"thread_name", "pid", "tid"};
  }
  if (show_cpu) {
    titles.emplace_back("cpu");
  }
  titles.emplace_back("count");
  titles.emplace_back("event_name");
  titles.emplace_back(" # count / runtime");

  std::vector<size_t> width(titles.size(), 0);

  auto adjust_width = [](size_t& w, size_t size) { w = std::max(w, size); };

  // The last title is too long. Don't include it for width adjustment.
  for (size_t i = 0; i + 1 < titles.size(); i++) {
    adjust_width(width[i], titles[i].size());
  }

  for (auto& s : summaries_) {
    size_t i = 0;
    if (show_thread) {
      adjust_width(width[i++], s.thread->name.size());
      adjust_width(width[i++], std::to_string(s.thread->pid).size());
      adjust_width(width[i++], std::to_string(s.thread->tid).size());
    }
    if (show_cpu) {
      adjust_width(width[i++], std::to_string(s.cpu).size());
    }
    adjust_width(width[i++], s.readable_count.size());
    adjust_width(width[i++], s.Name().size());
    adjust_width(width[i++], s.comment.size());
  }

  fprintf(fp, "# ");
  for (size_t i = 0; i < titles.size(); i++) {
    if (titles[i] == "count") {
      fprintf(fp, "%*s", static_cast<int>(width[i]), titles[i].c_str());
    } else {
      fprintf(fp, "%-*s", static_cast<int>(width[i]), titles[i].c_str());
    }
    if (i + 1 < titles.size()) {
      fprintf(fp, "  ");
    }
  }
  fprintf(fp, "\n");

  for (auto& s : summaries_) {
    size_t i = 0;
    if (show_thread) {
      fprintf(fp, "  %-*s", static_cast<int>(width[i++]), s.thread->name.c_str());
      fprintf(fp, "  %-*d", static_cast<int>(width[i++]), s.thread->pid);
      fprintf(fp, "  %-*d", static_cast<int>(width[i++]), s.thread->tid);
    }
    if (show_cpu) {
      fprintf(fp, "  %-*d", static_cast<int>(width[i++]), s.cpu);
    }
    fprintf(fp, "  %*s  %-*s   # %-*s%s\n", static_cast<int>(width[i]), s.readable_count.c_str(),
            static_cast<int>(width[i + 1]), s.Name().c_str(), static_cast<int>(width[i + 2]),
            s.comment.c_str(), (s.auto_generated ? " (generated)" : ""));
  }
}

std::string CounterSummaries::GetCommentForSummary(const CounterSummary& s,
                                                   double duration_in_sec) {
  char sap_mid;
  if (csv_) {
    sap_mid = ',';
  } else {
    sap_mid = ' ';
  }
  if (s.type_name == "task-clock") {
    double run_sec = s.count / 1e9;
    double used_cpus = run_sec / duration_in_sec;
    return android::base::StringPrintf("%f%ccpus used", used_cpus, sap_mid);
  }
  if (s.type_name == "cpu-clock") {
    return "";
  }
  if (s.type_name == "cpu-cycles") {
    if (s.runtime_in_ns == 0) {
      return "";
    }
    double ghz = static_cast<double>(s.count) / s.runtime_in_ns;
    return android::base::StringPrintf("%f%cGHz", ghz, sap_mid);
  }
  if (s.type_name == "instructions" && s.count != 0) {
    const CounterSummary* other = FindSummary("cpu-cycles", s.modifier, s.thread, s.cpu);
    if (other != nullptr && other->IsMonitoredAtTheSameTime(s)) {
      double cpi = static_cast<double>(other->count) / s.count;
      return android::base::StringPrintf("%f%ccycles per instruction", cpi, sap_mid);
    }
  }
  std::string rate_comment = GetRateComment(s, sap_mid);
  if (!rate_comment.empty()) {
    return rate_comment;
  }
  if (s.runtime_in_ns == 0) {
    return "";
  }
  double runtime_in_sec = static_cast<double>(s.runtime_in_ns) / 1e9;
  double rate = s.count / runtime_in_sec;
  if (rate >= 1e9 - 1e5) {
    return android::base::StringPrintf("%.3f%cG/sec", rate / 1e9, sap_mid);
  }
  if (rate >= 1e6 - 1e2) {
    return android::base::StringPrintf("%.3f%cM/sec", rate / 1e6, sap_mid);
  }
  if (rate >= 1e3) {
    return android::base::StringPrintf("%.3f%cK/sec", rate / 1e3, sap_mid);
  }
  return android::base::StringPrintf("%.3f%c/sec", rate, sap_mid);
}

std::string CounterSummaries::GetRateComment(const CounterSummary& s, char sep) {
  std::string_view miss_event_name = s.type_name;
  std::string event_name;
  std::string rate_desc;
  if (auto it = COMMON_EVENT_RATE_MAP.find(miss_event_name); it != COMMON_EVENT_RATE_MAP.end()) {
    event_name = it->second.first;
    rate_desc = it->second.second;
  }
  if (event_name.empty() && (GetTargetArch() == ARCH_ARM || GetTargetArch() == ARCH_ARM64)) {
    if (auto it = ARM_EVENT_RATE_MAP.find(miss_event_name); it != ARM_EVENT_RATE_MAP.end()) {
      event_name = it->second.first;
      rate_desc = it->second.second;
    }
  }
  if (event_name.empty() && android::base::ConsumeSuffix(&miss_event_name, "-misses")) {
    event_name = std::string(miss_event_name) + "s";
    rate_desc = "miss rate";
  }
  if (!event_name.empty()) {
    const CounterSummary* other = FindSummary(event_name, s.modifier, s.thread, s.cpu);
    if (other != nullptr && other->IsMonitoredAtTheSameTime(s) && other->count != 0) {
      double miss_rate = static_cast<double>(s.count) / other->count;
      return android::base::StringPrintf("%f%%%c%s", miss_rate * 100, sep, rate_desc.c_str());
    }
  }
  return "";
}

namespace {

// devfreq may use performance counters to calculate memory latency (as in
// drivers/devfreq/arm-memlat-mon.c). Hopefully we can get more available counters by asking devfreq
// to not use the memory latency governor temporarily.
class DevfreqCounters {
 public:
  bool Use() {
    if (!IsRoot()) {
      LOG(ERROR) << "--use-devfreq-counters needs root permission to set devfreq governors";
      return false;
    }
    std::string devfreq_dir = "/sys/class/devfreq/";
    for (auto& name : GetSubDirs(devfreq_dir)) {
      std::string governor_path = devfreq_dir + name + "/governor";
      if (IsRegularFile(governor_path)) {
        std::string governor;
        if (!android::base::ReadFileToString(governor_path, &governor)) {
          LOG(ERROR) << "failed to read " << governor_path;
          return false;
        }
        governor = android::base::Trim(governor);
        if (governor == "mem_latency") {
          if (!android::base::WriteStringToFile("performance", governor_path)) {
            PLOG(ERROR) << "failed to write " << governor_path;
            return false;
          }
          mem_latency_governor_paths_.emplace_back(std::move(governor_path));
        }
      }
    }
    return true;
  }

  ~DevfreqCounters() {
    for (auto& path : mem_latency_governor_paths_) {
      android::base::WriteStringToFile("mem_latency", path);
    }
  }

 private:
  std::vector<std::string> mem_latency_governor_paths_;
};

class StatCommand : public Command {
 public:
  StatCommand()
      : Command(
            "stat", "gather performance counter information",
            // clang-format off
"Usage: simpleperf stat [options] [command [command-args]]\n"
"       Gather performance counter information of running [command].\n"
"       And -a/-p/-t option can be used to change target of counter information.\n"
"-a           Collect system-wide information.\n"
#if defined(__ANDROID__)
"--app package_name    Profile the process of an Android application.\n"
"                      On non-rooted devices, the app must be debuggable,\n"
"                      because we use run-as to switch to the app's context.\n"
#endif
"--cpu cpu_item1,cpu_item2,...  Monitor events on selected cpus. cpu_item can be a number like\n"
"                               1, or a range like 0-3. A --cpu option affects all event types\n"
"                               following it until meeting another --cpu option.\n"
"--csv            Write report in comma separate form.\n"
"--duration time_in_sec  Monitor for time_in_sec seconds instead of running\n"
"                        [command]. Here time_in_sec may be any positive\n"
"                        floating point number.\n"
"--interval time_in_ms   Print stat for every time_in_ms milliseconds.\n"
"                        Here time_in_ms may be any positive floating point\n"
"                        number. Simpleperf prints total values from the\n"
"                        starting point. But this can be changed by\n"
"                        --interval-only-values.\n"
"--interval-only-values  Print numbers of events happened in each interval.\n"
"-e event1[:modifier1],event2[:modifier2],...\n"
"                 Select a list of events to count. An event can be:\n"
"                   1) an event name listed in `simpleperf list`;\n"
"                   2) a raw PMU event in rN format. N is a hex number.\n"
"                      For example, r1b selects event number 0x1b.\n"
"                 Modifiers can be added to define how the event should be\n"
"                 monitored. Possible modifiers are:\n"
"                   u - monitor user space events only\n"
"                   k - monitor kernel space events only\n"
"--group event1[:modifier],event2[:modifier2],...\n"
"             Similar to -e option. But events specified in the same --group\n"
"             option are monitored as a group, and scheduled in and out at the\n"
"             same time.\n"
"--kprobe kprobe_event1,kprobe_event2,...\n"
"             Add kprobe events during stating. The kprobe_event format is in\n"
"             Documentation/trace/kprobetrace.rst in the kernel. Examples:\n"
"               'p:myprobe do_sys_openat2 $arg2:string'   - add event kprobes:myprobe\n"
"               'r:myretprobe do_sys_openat2 $retval:s64' - add event kprobes:myretprobe\n"
"--no-inherit     Don't stat created child threads/processes.\n"
"-o output_filename  Write report to output_filename instead of standard output.\n"
"--per-core       Print counters for each cpu core.\n"
"--per-thread     Print counters for each thread.\n"
"-p pid_or_process_name_regex1,pid_or_process_name_regex2,...\n"
"                      Stat events on existing processes. Processes are searched either by pid\n"
"                      or process name regex. Mutually exclusive with -a.\n"
"-t tid1,tid2,...      Stat events on existing threads. Mutually exclusive with -a.\n"
"--tp-filter filter_string    Set filter_string for the previous tracepoint event.\n"
"                             Format is in Documentation/trace/events.rst in the kernel.\n"
"                             An example: 'prev_comm != \"simpleperf\" && (prev_pid > 1)'.\n"
"--print-hw-counter    Test and print CPU PMU hardware counters available on the device.\n"
"--sort key1,key2,...  Select keys used to sort the report, used when --per-thread\n"
"                      or --per-core appears. The appearance order of keys decides\n"
"                      the order of keys used to sort the report.\n"
"                      Possible keys include:\n"
"                        count             -- event count for each entry\n"
"                        count_per_thread  -- event count for a thread on all cpus\n"
"                        cpu               -- cpu id\n"
"                        pid               -- process id\n"
"                        tid               -- thread id\n"
"                        comm              -- thread name\n"
"                      The default sort keys are:\n"
"                        count_per_thread,tid,cpu,count\n"
#if defined(__ANDROID__)
"--use-devfreq-counters    On devices with Qualcomm SOCs, some hardware counters may be used\n"
"                          to monitor memory latency (in drivers/devfreq/arm-memlat-mon.c),\n"
"                          making fewer counters available to users. This option asks devfreq\n"
"                          to temporarily release counters by replacing memory-latency governor\n"
"                          with performance governor. It affects memory latency during profiling,\n"
"                          and may cause wedged power if simpleperf is killed in between.\n"
#endif
"--verbose        Show result in verbose mode.\n"
#if 0
// Below options are only used internally and shouldn't be visible to the public.
"--in-app         We are already running in the app's context.\n"
"--tracepoint-events file_name   Read tracepoint events from [file_name] instead of tracefs.\n"
"--out-fd <fd>    Write output to a file descriptor.\n"
"--stop-signal-fd <fd>   Stop stating when fd is readable.\n"
#endif
            // clang-format on
            ),
        verbose_mode_(false),
        system_wide_collection_(false),
        child_inherit_(true),
        duration_in_sec_(0),
        interval_in_ms_(0),
        interval_only_values_(false),
        event_selection_set_(true),
        csv_(false),
        in_app_context_(false) {
    // Die if parent exits.
    prctl(PR_SET_PDEATHSIG, SIGHUP, 0, 0, 0);
    // Set default sort keys. Full key list is in BuildSummaryComparator().
    sort_keys_ = {"count_per_thread", "tid", "cpu", "count"};
  }

  bool Run(const std::vector<std::string>& args);

 private:
  bool ParseOptions(const std::vector<std::string>& args, std::vector<std::string>* non_option_args,
                    ProbeEvents& probe_events);
  void PrintHardwareCounters();
  bool AddDefaultMeasuredEventTypes();
  void SetEventSelectionFlags();
  void MonitorEachThread();
  void AdjustToIntervalOnlyValues(std::vector<CountersInfo>& counters);
  bool ShowCounters(const std::vector<CountersInfo>& counters, double duration_in_sec, FILE* fp);
  void CheckHardwareCounterMultiplexing();
  void PrintWarningForInaccurateEvents();

  bool verbose_mode_;
  bool system_wide_collection_;
  bool child_inherit_;
  double duration_in_sec_;
  double interval_in_ms_;
  bool interval_only_values_;
  std::vector<std::vector<CounterSum>> last_sum_values_;
  EventSelectionSet event_selection_set_;
  std::string output_filename_;
  android::base::unique_fd out_fd_;
  bool csv_;
  std::string app_package_name_;
  bool in_app_context_;
  android::base::unique_fd stop_signal_fd_;
  bool use_devfreq_counters_ = false;

  bool report_per_core_ = false;
  bool report_per_thread_ = false;
  // used to report event count for each thread
  std::unordered_map<pid_t, ThreadInfo> thread_info_;
  // used to sort report
  std::vector<std::string> sort_keys_;
  std::optional<SummaryComparator> summary_comparator_;
  bool print_hw_counter_ = false;
};

bool StatCommand::Run(const std::vector<std::string>& args) {
  if (!CheckPerfEventLimit()) {
    return false;
  }
  AllowMoreOpenedFiles();

  // 1. Parse options, and use default measured event types if not given.
  std::vector<std::string> workload_args;
  ProbeEvents probe_events(event_selection_set_);
  if (!ParseOptions(args, &workload_args, probe_events)) {
    return false;
  }
  if (print_hw_counter_) {
    PrintHardwareCounters();
    return true;
  }
  if (!app_package_name_.empty() && !in_app_context_) {
    if (!IsRoot()) {
      return RunInAppContext(app_package_name_, "stat", args, workload_args.size(),
                             output_filename_, !event_selection_set_.GetTracepointEvents().empty());
    }
  }
  DevfreqCounters devfreq_counters;
  if (use_devfreq_counters_) {
    if (!devfreq_counters.Use()) {
      return false;
    }
  }
  if (event_selection_set_.empty()) {
    if (!AddDefaultMeasuredEventTypes()) {
      return false;
    }
  }
  SetEventSelectionFlags();

  // 2. Create workload.
  std::unique_ptr<Workload> workload;
  if (!workload_args.empty()) {
    workload = Workload::CreateWorkload(workload_args);
    if (workload == nullptr) {
      return false;
    }
  }
  bool need_to_check_targets = false;
  if (system_wide_collection_) {
    if (report_per_thread_) {
      event_selection_set_.AddMonitoredProcesses(GetAllProcesses());
    } else {
      event_selection_set_.AddMonitoredThreads({-1});
    }
  } else if (!event_selection_set_.HasMonitoredTarget()) {
    if (workload != nullptr) {
      event_selection_set_.AddMonitoredProcesses({workload->GetPid()});
      event_selection_set_.SetEnableCondition(false, true);
    } else if (!app_package_name_.empty()) {
      std::set<pid_t> pids = WaitForAppProcesses(app_package_name_);
      event_selection_set_.AddMonitoredProcesses(pids);
    } else {
      LOG(ERROR) << "No threads to monitor. Try `simpleperf help stat` for help\n";
      return false;
    }
  } else {
    need_to_check_targets = true;
  }

  if (report_per_thread_) {
    MonitorEachThread();
  }

  // 3. Open perf_event_files and output file if defined.
  if (!event_selection_set_.OpenEventFiles()) {
    return false;
  }
  std::unique_ptr<FILE, decltype(&fclose)> fp_holder(nullptr, fclose);
  if (!output_filename_.empty()) {
    fp_holder.reset(fopen(output_filename_.c_str(), "we"));
    if (fp_holder == nullptr) {
      PLOG(ERROR) << "failed to open " << output_filename_;
      return false;
    }
  } else if (out_fd_ != -1) {
    fp_holder.reset(fdopen(out_fd_.release(), "we"));
    if (fp_holder == nullptr) {
      PLOG(ERROR) << "failed to write output.";
      return false;
    }
  }
  FILE* fp = fp_holder ? fp_holder.get() : stdout;

  // 4. Add signal/periodic Events.
  IOEventLoop* loop = event_selection_set_.GetIOEventLoop();
  std::chrono::time_point<std::chrono::steady_clock> start_time;
  std::vector<CountersInfo> counters;
  if (need_to_check_targets && !event_selection_set_.StopWhenNoMoreTargets()) {
    return false;
  }
  auto exit_loop_callback = [loop]() { return loop->ExitLoop(); };
  if (!loop->AddSignalEvents({SIGCHLD, SIGINT, SIGTERM, SIGHUP}, exit_loop_callback)) {
    return false;
  }
  if (stop_signal_fd_ != -1) {
    if (!loop->AddReadEvent(stop_signal_fd_, exit_loop_callback)) {
      return false;
    }
  }
  if (duration_in_sec_ != 0) {
    if (!loop->AddPeriodicEvent(SecondToTimeval(duration_in_sec_), exit_loop_callback)) {
      return false;
    }
  }
  auto print_counters = [&]() {
    auto end_time = std::chrono::steady_clock::now();
    if (!event_selection_set_.ReadCounters(&counters)) {
      return false;
    }
    double duration_in_sec =
        std::chrono::duration_cast<std::chrono::duration<double>>(end_time - start_time).count();
    if (interval_only_values_) {
      AdjustToIntervalOnlyValues(counters);
    }
    if (!ShowCounters(counters, duration_in_sec, fp)) {
      return false;
    }
    return true;
  };

  if (interval_in_ms_ != 0) {
    if (!loop->AddPeriodicEvent(SecondToTimeval(interval_in_ms_ / 1000.0), print_counters)) {
      return false;
    }
  }

  // 5. Count events while workload running.
  start_time = std::chrono::steady_clock::now();
  if (workload != nullptr && !workload->Start()) {
    return false;
  }
  if (!loop->RunLoop()) {
    return false;
  }

  // 6. Read and print counters.
  if (interval_in_ms_ == 0) {
    if (!print_counters()) {
      return false;
    }
  }

  // 7. Print warnings when needed.
  event_selection_set_.CloseEventFiles();
  CheckHardwareCounterMultiplexing();
  PrintWarningForInaccurateEvents();

  return true;
}

bool StatCommand::ParseOptions(const std::vector<std::string>& args,
                               std::vector<std::string>* non_option_args,
                               ProbeEvents& probe_events) {
  OptionValueMap options;
  std::vector<std::pair<OptionName, OptionValue>> ordered_options;

  if (!PreprocessOptions(args, GetStatCmdOptionFormats(), &options, &ordered_options,
                         non_option_args)) {
    return false;
  }

  // Process options.
  system_wide_collection_ = options.PullBoolValue("-a");

  if (auto value = options.PullValue("--app"); value) {
    app_package_name_ = value->str_value;
  }
  csv_ = options.PullBoolValue("--csv");

  if (!options.PullDoubleValue("--duration", &duration_in_sec_, 1e-9)) {
    return false;
  }
  if (!options.PullDoubleValue("--interval", &interval_in_ms_, 1e-9)) {
    return false;
  }
  interval_only_values_ = options.PullBoolValue("--interval-only-values");

  in_app_context_ = options.PullBoolValue("--in-app");
  for (const OptionValue& value : options.PullValues("--kprobe")) {
    for (const auto& cmd : Split(value.str_value, ",")) {
      if (!probe_events.AddKprobe(cmd)) {
        return false;
      }
    }
  }
  child_inherit_ = !options.PullBoolValue("--no-inherit");

  if (auto value = options.PullValue("-o"); value) {
    output_filename_ = value->str_value;
  }
  if (auto value = options.PullValue("--out-fd"); value) {
    out_fd_.reset(static_cast<int>(value->uint_value));
  }

  report_per_core_ = options.PullBoolValue("--per-core");
  report_per_thread_ = options.PullBoolValue("--per-thread");

  if (auto strs = options.PullStringValues("-p"); !strs.empty()) {
    if (auto pids = GetPidsFromStrings(strs, true, true); pids) {
      event_selection_set_.AddMonitoredProcesses(pids.value());
    } else {
      return false;
    }
  }
  print_hw_counter_ = options.PullBoolValue("--print-hw-counter");

  if (auto value = options.PullValue("--sort"); value) {
    sort_keys_ = Split(value->str_value, ",");
  }

  if (auto value = options.PullValue("--stop-signal-fd"); value) {
    stop_signal_fd_.reset(static_cast<int>(value->uint_value));
  }

  for (const OptionValue& value : options.PullValues("-t")) {
    if (auto tids = GetTidsFromString(value.str_value, true); tids) {
      event_selection_set_.AddMonitoredThreads(tids.value());
    } else {
      return false;
    }
  }

  if (auto value = options.PullValue("--tracepoint-events"); value) {
    if (!EventTypeManager::Instance().ReadTracepointsFromFile(value->str_value)) {
      return false;
    }
  }

  use_devfreq_counters_ = options.PullBoolValue("--use-devfreq-counters");
  verbose_mode_ = options.PullBoolValue("--verbose");

  CHECK(options.values.empty());

  // Process ordered options.
  for (const auto& pair : ordered_options) {
    const OptionName& name = pair.first;
    const OptionValue& value = pair.second;

    if (name == "--cpu") {
      if (auto v = GetCpusFromString(value.str_value); v) {
        std::set<int>& cpus = v.value();
        event_selection_set_.SetCpusForNewEvents(std::vector<int>(cpus.begin(), cpus.end()));
      } else {
        return false;
      }
    } else if (name == "-e") {
      for (const auto& event_type : Split(value.str_value, ",")) {
        if (!probe_events.CreateProbeEventIfNotExist(event_type)) {
          return false;
        }
        if (!event_selection_set_.AddEventType(event_type)) {
          return false;
        }
      }
    } else if (name == "--group") {
      std::vector<std::string> event_types = Split(value.str_value, ",");
      for (const auto& event_type : event_types) {
        if (!probe_events.CreateProbeEventIfNotExist(event_type)) {
          return false;
        }
      }
      if (!event_selection_set_.AddEventGroup(event_types)) {
        return false;
      }
    } else if (name == "--tp-filter") {
      if (!event_selection_set_.SetTracepointFilter(value.str_value)) {
        return false;
      }
    } else {
      LOG(ERROR) << "unprocessed option: " << name;
      return false;
    }
  }

  if (system_wide_collection_ && event_selection_set_.HasMonitoredTarget()) {
    LOG(ERROR) << "Stat system wide and existing processes/threads can't be "
                  "used at the same time.";
    return false;
  }
  if (system_wide_collection_ && !IsRoot()) {
    LOG(ERROR) << "System wide profiling needs root privilege.";
    return false;
  }

  if (report_per_core_ || report_per_thread_) {
    summary_comparator_ = BuildSummaryComparator(sort_keys_, report_per_thread_, report_per_core_);
    if (!summary_comparator_) {
      return false;
    }
  }
  return true;
}

std::optional<bool> CheckHardwareCountersOnCpu(int cpu, size_t counters) {
  if (counters == 0) {
    return true;
  }
  const EventType* event = FindEventTypeByName("cpu-cycles", true);
  if (event == nullptr) {
    return std::nullopt;
  }
  perf_event_attr attr = CreateDefaultPerfEventAttr(*event);
  auto workload = Workload::CreateWorkload({"sleep", "0.1"});
  if (!workload || !workload->SetCpuAffinity(cpu)) {
    return std::nullopt;
  }
  std::vector<std::unique_ptr<EventFd>> event_fds;
  for (size_t i = 0; i < counters; i++) {
    EventFd* group_event_fd = event_fds.empty() ? nullptr : event_fds[0].get();
    auto event_fd =
        EventFd::OpenEventFile(attr, workload->GetPid(), cpu, group_event_fd, "cpu-cycles", false);
    if (!event_fd) {
      return false;
    }
    event_fds.emplace_back(std::move(event_fd));
  }
  if (!workload->Start() || !workload->WaitChildProcess(true, nullptr)) {
    return std::nullopt;
  }
  for (auto& event_fd : event_fds) {
    PerfCounter counter;
    if (!event_fd->ReadCounter(&counter)) {
      return std::nullopt;
    }
    if (counter.time_enabled == 0 || counter.time_enabled > counter.time_running) {
      return false;
    }
  }
  return true;
}

std::optional<size_t> GetHardwareCountersOnCpu(int cpu) {
  size_t available_counters = 0;
  while (true) {
    std::optional<bool> result = CheckHardwareCountersOnCpu(cpu, available_counters + 1);
    if (!result.has_value()) {
      return std::nullopt;
    }
    if (!result.value()) {
      break;
    }
    available_counters++;
  }
  return available_counters;
}

void StatCommand::PrintHardwareCounters() {
  for (int cpu : GetOnlineCpus()) {
    std::optional<size_t> counters = GetHardwareCountersOnCpu(cpu);
    if (!counters) {
      // When built as a 32-bit program, we can't set sched_affinity to a 64-bit only CPU. So we
      // may not be able to get hardware counters on that CPU.
      LOG(WARNING) << "Failed to get CPU PMU hardware counters on cpu " << cpu;
      continue;
    }
    printf("There are %zu CPU PMU hardware counters available on cpu %d.\n", counters.value(), cpu);
  }
}

bool StatCommand::AddDefaultMeasuredEventTypes() {
  for (auto& name : default_measured_event_types) {
    // It is not an error when some event types in the default list are not
    // supported by the kernel.
    const EventType* type = FindEventTypeByName(name);
    if (type != nullptr && IsEventAttrSupported(CreateDefaultPerfEventAttr(*type), name)) {
      if (!event_selection_set_.AddEventType(name)) {
        return false;
      }
    }
  }
  if (event_selection_set_.empty()) {
    LOG(ERROR) << "Failed to add any supported default measured types";
    return false;
  }
  return true;
}

void StatCommand::SetEventSelectionFlags() {
  event_selection_set_.SetInherit(child_inherit_);
}

void StatCommand::MonitorEachThread() {
  std::vector<pid_t> threads;
  for (auto pid : event_selection_set_.GetMonitoredProcesses()) {
    for (auto tid : GetThreadsInProcess(pid)) {
      ThreadInfo info;
      if (GetThreadName(tid, &info.name)) {
        info.tid = tid;
        info.pid = pid;
        thread_info_[tid] = std::move(info);
        threads.push_back(tid);
      }
    }
  }
  for (auto tid : event_selection_set_.GetMonitoredThreads()) {
    ThreadInfo info;
    if (ReadThreadNameAndPid(tid, &info.name, &info.pid)) {
      info.tid = tid;
      thread_info_[tid] = std::move(info);
      threads.push_back(tid);
    }
  }
  event_selection_set_.ClearMonitoredTargets();
  event_selection_set_.AddMonitoredThreads(threads);
}

void StatCommand::AdjustToIntervalOnlyValues(std::vector<CountersInfo>& counters) {
  if (last_sum_values_.size() < counters.size()) {
    last_sum_values_.resize(counters.size());
  }
  for (size_t i = 0; i < counters.size(); i++) {
    std::vector<CounterInfo>& counters_per_event = counters[i].counters;
    std::vector<CounterSum>& last_sum = last_sum_values_[i];

    if (last_sum.size() < counters_per_event.size()) {
      last_sum.resize(counters_per_event.size());
    }
    for (size_t j = 0; j < counters_per_event.size(); j++) {
      PerfCounter& counter = counters_per_event[j].counter;
      CounterSum new_sum;
      new_sum.FromCounter(counter);
      CounterSum delta = new_sum - last_sum[j];
      delta.ToCounter(counter);
      last_sum[j] = new_sum;
    }
  }
}

bool StatCommand::ShowCounters(const std::vector<CountersInfo>& counters, double duration_in_sec,
                               FILE* fp) {
  if (csv_) {
    fprintf(fp, "Performance counter statistics,\n");
  } else {
    fprintf(fp, "Performance counter statistics:\n\n");
  }

  if (verbose_mode_) {
    for (auto& counters_info : counters) {
      for (auto& counter_info : counters_info.counters) {
        if (csv_) {
          fprintf(fp,
                  "%s,tid,%d,cpu,%d,count,%" PRIu64 ",time_enabled,%" PRIu64
                  ",time running,%" PRIu64 ",id,%" PRIu64 ",\n",
                  counters_info.event_name.c_str(), counter_info.tid, counter_info.cpu,
                  counter_info.counter.value, counter_info.counter.time_enabled,
                  counter_info.counter.time_running, counter_info.counter.id);
        } else {
          fprintf(fp,
                  "%s(tid %d, cpu %d): count %" PRIu64 ", time_enabled %" PRIu64
                  ", time running %" PRIu64 ", id %" PRIu64 "\n",
                  counters_info.event_name.c_str(), counter_info.tid, counter_info.cpu,
                  counter_info.counter.value, counter_info.counter.time_enabled,
                  counter_info.counter.time_running, counter_info.counter.id);
        }
      }
    }
  }

  CounterSummaryBuilder builder(report_per_thread_, report_per_core_, csv_, thread_info_,
                                summary_comparator_);
  for (const auto& info : counters) {
    builder.AddCountersForOneEventType(info);
  }
  CounterSummaries summaries(builder.Build(), csv_);
  summaries.AutoGenerateSummaries();
  summaries.GenerateComments(duration_in_sec);
  summaries.Show(fp);

  if (csv_) {
    fprintf(fp, "Total test time,%lf,seconds,\n", duration_in_sec);
  } else {
    fprintf(fp, "\nTotal test time: %lf seconds.\n", duration_in_sec);
  }
  return true;
}

void StatCommand::CheckHardwareCounterMultiplexing() {
  for (const auto& [cpu, hardware_events] : event_selection_set_.GetHardwareCountersForCpus()) {
    std::optional<bool> result = CheckHardwareCountersOnCpu(cpu, hardware_events);
    if (result.has_value() && !result.value()) {
      LOG(WARNING) << "It seems the number of hardware events are more than the number of\n"
                   << "available CPU PMU hardware counters. That will trigger hardware counter\n"
                   << "multiplexing. As a result, events are not counted all the time processes\n"
                   << "running, and event counts are smaller than what really happen.\n"
                   << "Use --print-hw-counter to show available hardware counters.\n"
#if defined(__ANDROID__)
                   << "If on a rooted device, try --use-devfreq-counters to get more counters.\n"
#endif
          ;
      break;
    }
  }
}

void StatCommand::PrintWarningForInaccurateEvents() {
  for (const EventType* event : event_selection_set_.GetEvents()) {
    if (event->name == "raw-l3d-cache-lmiss-rd") {
      LOG(WARNING) << "PMU event L3D_CACHE_LMISS_RD might undercount on A510. Please use "
                      "L3D_CACHE_REFILL_RD instead.";
      break;
    }
  }
}

}  // namespace

void RegisterStatCommand() {
  RegisterCommand("stat", [] { return std::unique_ptr<Command>(new StatCommand); });
}

}  // namespace simpleperf
