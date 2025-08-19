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
#include <inttypes.h>
#include <libgen.h>
#include <signal.h>
#include <sys/mman.h>
#include <sys/prctl.h>
#include <sys/utsname.h>
#include <time.h>
#include <unistd.h>
#include <optional>
#include <set>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/parseint.h>
#include <android-base/stringprintf.h>
#include <android-base/strings.h>
#include <android-base/unique_fd.h>
#if defined(__ANDROID__)
#include <android-base/properties.h>
#endif

#include "IOEventLoop.h"
#include "MapRecordReader.h"
#include "OfflineUnwinder.h"
#include "RecordFilter.h"
#include "command.h"
#include "dso.h"
#include "environment.h"
#include "event_selection_set.h"
#include "event_type.h"
#include "read_elf.h"
#include "read_symbol_map.h"
#include "record.h"
#include "thread_tree.h"
#include "tracing.h"
#include "utils.h"

namespace simpleperf {
namespace {

using android::base::ParseUint;
using android::base::Realpath;
using android::base::StringAppendF;

struct SymbolInfo {
  Dso* dso;
  const Symbol* symbol;
  uint64_t vaddr_in_file;
};

// The max size of records dumped by kernel is 65535, and dump stack size
// should be a multiply of 8, so MAX_DUMP_STACK_SIZE is 65528.
constexpr uint32_t MAX_DUMP_STACK_SIZE = 65528;

// The max allowed pages in mapped buffer is decided by rlimit(RLIMIT_MEMLOCK).
// Here 1024 is a desired value for pages in mapped buffer. If mapped
// successfully, the buffer size = 1024 * 4K (page size) = 4M.
constexpr size_t DESIRED_PAGES_IN_MAPPED_BUFFER = 1024;

// Currently, the record buffer size in user-space is set to match the kernel
// buffer size on a 8 core system. For system-wide recording, it is 8K pages *
// 4K page_size * 8 cores = 256MB. For non system-wide recording, it is 1K pages
// * 4K page_size * 8 cores = 64MB.
static constexpr size_t kRecordBufferSize = 64 * kMegabyte;
static constexpr size_t kSystemWideRecordBufferSize = 256 * kMegabyte;

class MonitorCommand : public Command {
 public:
  MonitorCommand()
      : Command(
            "monitor", "monitor events and print their textual representations to stdout",
            // clang-format off
"Usage: simpleperf monitor [options]\n"
"       Gather sampling information and print the events on stdout.\n"
"       For precise recording, prefer the record command.\n"
"       Currently, only supports system-wide collection.\n"
"\n"
"Select monitored threads:\n"
"-a               System-wide collection. Use with --exclude-perf to exclude\n"
"                 samples for simpleperf process.\n"
"\n"
"Select monitored event types:\n"
"-e event1[:modifier1],event2[:modifier2],...\n"
"             Select a list of events to record. An event can be:\n"
"               1) an event name listed in `simpleperf list`;\n"
"               2) a raw PMU event in rN format. N is a hex number.\n"
"                  For example, r1b selects event number 0x1b.\n"
"             Modifiers can be added to define how the event should be\n"
"             monitored. Possible modifiers are:\n"
"                u - monitor user space events only\n"
"                k - monitor kernel space events only\n"
"\n"
"Select monitoring options:\n"
"-f freq      Set event sample frequency. It means recording at most [freq]\n"
"             samples every second. For non-tracepoint events, the default\n"
"             option is -f 4000. A -f/-c option affects all event types\n"
"             following it until meeting another -f/-c option. For example,\n"
"             for \"-f 1000 -e cpu-cycles -c 1 -e sched:sched_switch\", cpu-cycles\n"
"             has sample freq 1000, sched:sched_switch event has sample period 1.\n"
"-c count     Set event sample period. It means recording one sample when\n"
"             [count] events happen. For tracepoint events, the default option\n"
"             is -c 1.\n"
"--call-graph fp | dwarf[,<dump_stack_size>]\n"
"             Enable call graph recording. Use frame pointer or dwarf debug\n"
"             frame as the method to parse call graph in stack.\n"
"             Default is dwarf,65528.\n"
"-g           Same as '--call-graph dwarf'.\n"
"--duration time_in_sec  Monitor for time_in_sec seconds. Here time_in_sec"
"                        may be any positive floating point number.\n"
"--cpu-percent <percent>  Set the max percent of cpu time used for recording.\n"
"                         percent is in range [1-100], default is 25.\n"
"\n"
"Sample filter options:\n"
"--exclude-perf                Exclude samples for simpleperf process.\n"
RECORD_FILTER_OPTION_HELP_MSG_FOR_RECORDING
"\n"
            // clang-format on
            ),
        system_wide_collection_(false),
        fp_callchain_sampling_(false),
        dwarf_callchain_sampling_(false),
        dump_stack_size_in_dwarf_sampling_(MAX_DUMP_STACK_SIZE),
        unwind_dwarf_callchain_(true),
        duration_in_sec_(0),
        event_selection_set_(false),
        mmap_page_range_(std::make_pair(1, DESIRED_PAGES_IN_MAPPED_BUFFER)),
        sample_record_count_(0),
        last_record_timestamp_(0u),
        record_filter_(thread_tree_) {
    // If we run `adb shell simpleperf record xxx` and stop profiling by ctrl-c,
    // adb closes sockets connecting simpleperf. After that, simpleperf will
    // receive SIGPIPE when writing to stdout/stderr, which is a problem when we
    // use '--app' option. So ignore SIGPIPE to finish properly.
    signal(SIGPIPE, SIG_IGN);
  }

  bool Run(const std::vector<std::string>& args);

 private:
  bool ParseOptions(const std::vector<std::string>& args);
  bool AdjustPerfEventLimit();
  bool PrepareMonitoring();
  bool DoMonitoring();
  bool SetEventSelectionFlags();
  bool DumpProcessMaps(pid_t pid, const std::unordered_set<pid_t>& tids);
  void DumpSampleRecord(const SampleRecord& sr);
  void DumpSampleCallchain(const SampleRecord& sr);
  bool ProcessRecord(Record* record);
  SymbolInfo GetSymbolInfo(uint32_t pid, uint32_t tid, uint64_t ip, bool in_kernel);
  bool DumpMapsForRecord(Record* record);
  void UpdateRecord(Record* record);
  bool UnwindRecord(SampleRecord& r);

  uint64_t max_sample_freq_ = DEFAULT_SAMPLE_FREQ_FOR_NONTRACEPOINT_EVENT;
  size_t cpu_time_max_percent_ = 25;

  bool system_wide_collection_;
  bool fp_callchain_sampling_;
  bool dwarf_callchain_sampling_;
  uint32_t dump_stack_size_in_dwarf_sampling_;
  bool unwind_dwarf_callchain_;
  std::unique_ptr<OfflineUnwinder> offline_unwinder_;
  double duration_in_sec_;
  EventSelectionSet event_selection_set_;
  std::pair<size_t, size_t> mmap_page_range_;
  ThreadTree thread_tree_;
  uint64_t sample_record_count_;
  uint64_t last_record_timestamp_;  // used to insert Mmap2Records for JIT debug info
  // In system wide recording, record if we have dumped map info for a process.
  std::unordered_set<pid_t> dumped_processes_;
  bool exclude_perf_ = false;
  RecordFilter record_filter_;
  std::unordered_map<uint64_t, std::string> event_names_;

  std::optional<MapRecordReader> map_record_reader_;
};

bool MonitorCommand::Run(const std::vector<std::string>& args) {
  ScopedCurrentArch scoped_arch(GetMachineArch());
  if (!CheckPerfEventLimit()) {
    return false;
  }
  AllowMoreOpenedFiles();

  if (!ParseOptions(args)) {
    return false;
  }
  if (!AdjustPerfEventLimit()) {
    return false;
  }

  if (!PrepareMonitoring()) {
    return false;
  }
  return DoMonitoring();
}

bool MonitorCommand::PrepareMonitoring() {
  // 1. Process options before opening perf event files.
  if (!SetEventSelectionFlags()) {
    return false;
  }
  if (unwind_dwarf_callchain_) {
    offline_unwinder_ = OfflineUnwinder::Create(false);
  }

  // 2. Add monitored targets.
  if (system_wide_collection_) {
    event_selection_set_.AddMonitoredThreads({-1});
  } else {
    LOG(ERROR) << "No threads to monitor. Try `simpleperf help monitor` for help";
    return false;
  }

  // 3. Open perf event files and create mapped buffers.
  if (!event_selection_set_.OpenEventFiles()) {
    return false;
  }
  size_t record_buffer_size =
      system_wide_collection_ ? kSystemWideRecordBufferSize : kRecordBufferSize;
  if (!event_selection_set_.MmapEventFiles(mmap_page_range_.first, mmap_page_range_.second,
                                           0 /* aux_buffer_size */, record_buffer_size,
                                           false /* allow_truncating_samples */, exclude_perf_)) {
    return false;
  }
  auto callback = std::bind(&MonitorCommand::ProcessRecord, this, std::placeholders::_1);
  if (!event_selection_set_.PrepareToReadMmapEventData(callback)) {
    return false;
  }

  // Keep track of the event names per id.
  event_names_ = event_selection_set_.GetEventNamesById();

  // Use first perf_event_attr and first event id to dump mmap and comm records.
  EventAttrWithId dumping_attr_id = event_selection_set_.GetEventAttrWithId()[0];
  map_record_reader_.emplace(dumping_attr_id.attr, dumping_attr_id.ids[0],
                             event_selection_set_.RecordNotExecutableMaps());
  map_record_reader_->SetCallback([this](Record* r) { return ProcessRecord(r); });

  // 4. Load kallsyms, if possible.
  std::string kallsyms;
  if (LoadKernelSymbols(&kallsyms)) {
    Dso::SetKallsyms(std::move(kallsyms));
  }
  map_record_reader_->ReadKernelMaps();

  // 5. Add read/signal/periodic Events.
  IOEventLoop* loop = event_selection_set_.GetIOEventLoop();
  auto exit_loop_callback = [loop]() { return loop->ExitLoop(); };
  if (!loop->AddSignalEvents({SIGCHLD, SIGINT, SIGTERM}, exit_loop_callback, IOEventHighPriority)) {
    return false;
  }

  // Only add an event for SIGHUP if we didn't inherit SIG_IGN (e.g. from
  // nohup).
  if (!SignalIsIgnored(SIGHUP)) {
    if (!loop->AddSignalEvent(SIGHUP, exit_loop_callback, IOEventHighPriority)) {
      return false;
    }
  }

  if (duration_in_sec_ != 0) {
    if (!loop->AddPeriodicEvent(
            SecondToTimeval(duration_in_sec_), [loop]() { return loop->ExitLoop(); },
            IOEventHighPriority)) {
      return false;
    }
  }
  return true;
}

bool MonitorCommand::DoMonitoring() {
  if (!event_selection_set_.GetIOEventLoop()->RunLoop()) {
    return false;
  }
  if (!event_selection_set_.SyncKernelBuffer()) {
    return false;
  }
  event_selection_set_.CloseEventFiles();
  if (!event_selection_set_.FinishReadMmapEventData()) {
    return false;
  }
  LOG(ERROR) << "Processed samples: " << sample_record_count_;
  return true;
}

inline const OptionFormatMap& GetMonitorCmdOptionFormats() {
  static OptionFormatMap option_formats;
  if (option_formats.empty()) {
    option_formats = {
        {"-a", {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::NOT_ALLOWED}},
        {"-c", {OptionValueType::UINT, OptionType::ORDERED, AppRunnerType::ALLOWED}},
        {"--call-graph", {OptionValueType::STRING, OptionType::ORDERED, AppRunnerType::ALLOWED}},
        {"--cpu-percent", {OptionValueType::UINT, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--duration", {OptionValueType::DOUBLE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"-e", {OptionValueType::STRING, OptionType::ORDERED, AppRunnerType::ALLOWED}},
        {"--exclude-perf", {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"-f", {OptionValueType::UINT, OptionType::ORDERED, AppRunnerType::ALLOWED}},
        {"-g", {OptionValueType::NONE, OptionType::ORDERED, AppRunnerType::ALLOWED}},
        {"-t", {OptionValueType::STRING, OptionType::MULTIPLE, AppRunnerType::ALLOWED}},
    };
    OptionFormatMap record_filter_options = GetRecordFilterOptionFormats(true);
    option_formats.insert(record_filter_options.begin(), record_filter_options.end());
  }
  return option_formats;
}

bool MonitorCommand::ParseOptions(const std::vector<std::string>& args) {
  OptionValueMap options;
  std::vector<std::pair<OptionName, OptionValue>> ordered_options;

  if (!PreprocessOptions(args, GetMonitorCmdOptionFormats(), &options, &ordered_options, nullptr)) {
    return false;
  }

  // Process options.
  system_wide_collection_ = options.PullBoolValue("-a");

  if (!options.PullUintValue("--cpu-percent", &cpu_time_max_percent_, 1, 100)) {
    return false;
  }

  if (!options.PullDoubleValue("--duration", &duration_in_sec_, 1e-9)) {
    return false;
  }

  exclude_perf_ = options.PullBoolValue("--exclude-perf");
  if (!record_filter_.ParseOptions(options)) {
    return false;
  }

  CHECK(options.values.empty());

  // Process ordered options.
  for (const auto& pair : ordered_options) {
    const OptionName& name = pair.first;
    const OptionValue& value = pair.second;

    if (name == "-c" || name == "-f") {
      if (value.uint_value < 1) {
        LOG(ERROR) << "invalid " << name << ": " << value.uint_value;
        return false;
      }
      SampleRate rate;
      if (name == "-c") {
        rate.sample_period = value.uint_value;
      } else {
        if (value.uint_value >= INT_MAX) {
          LOG(ERROR) << "sample freq can't be bigger than INT_MAX: " << value.uint_value;
          return false;
        }
        rate.sample_freq = value.uint_value;
      }
      event_selection_set_.SetSampleRateForNewEvents(rate);

    } else if (name == "--call-graph") {
      std::vector<std::string> strs = android::base::Split(value.str_value, ",");
      if (strs[0] == "fp") {
        fp_callchain_sampling_ = true;
        dwarf_callchain_sampling_ = false;
      } else if (strs[0] == "dwarf") {
        fp_callchain_sampling_ = false;
        dwarf_callchain_sampling_ = true;
        if (strs.size() > 1) {
          uint64_t size;
          if (!ParseUint(strs[1], &size)) {
            LOG(ERROR) << "invalid dump stack size in --call-graph option: " << strs[1];
            return false;
          }
          if ((size & 7) != 0) {
            LOG(ERROR) << "dump stack size " << size << " is not 8-byte aligned.";
            return false;
          }
          if (size >= MAX_DUMP_STACK_SIZE) {
            LOG(ERROR) << "dump stack size " << size << " is bigger than max allowed size "
                       << MAX_DUMP_STACK_SIZE << ".";
            return false;
          }
          dump_stack_size_in_dwarf_sampling_ = static_cast<uint32_t>(size);
        }
      }

    } else if (name == "-e") {
      std::vector<std::string> event_types = android::base::Split(value.str_value, ",");
      for (auto& event_type : event_types) {
        if (!event_selection_set_.AddEventType(event_type)) {
          return false;
        }
      }

    } else if (name == "-g") {
      fp_callchain_sampling_ = false;
      dwarf_callchain_sampling_ = true;
    } else {
      CHECK(false) << "unprocessed option: " << name;
    }
  }

  if (event_selection_set_.empty()) {
    LOG(ERROR) << "No event to record. Use `-e` to specify which event should be monitored.";
    return false;
  }

  if (fp_callchain_sampling_) {
    if (GetTargetArch() == ARCH_ARM) {
      LOG(WARNING) << "`--callgraph fp` option doesn't work well on arm architecture, "
                   << "consider using `-g` option or profiling on aarch64 architecture.";
    }
  }

  if (system_wide_collection_ && event_selection_set_.HasMonitoredTarget()) {
    LOG(ERROR) << "Record system wide and existing processes/threads can't be "
                  "used at the same time.";
    return false;
  }

  if (system_wide_collection_ && !IsRoot()) {
    LOG(ERROR) << "System wide profiling needs root privilege.";
    return false;
  }
  return true;
}

bool MonitorCommand::AdjustPerfEventLimit() {
  bool set_prop = false;
  // 1. Adjust max_sample_rate.
  uint64_t cur_max_freq;
  if (GetMaxSampleFrequency(&cur_max_freq) && cur_max_freq < max_sample_freq_ &&
      !SetMaxSampleFrequency(max_sample_freq_)) {
    set_prop = true;
  }
  // 2. Adjust perf_cpu_time_max_percent.
  size_t cur_percent;
  if (GetCpuTimeMaxPercent(&cur_percent) && cur_percent != cpu_time_max_percent_ &&
      !SetCpuTimeMaxPercent(cpu_time_max_percent_)) {
    set_prop = true;
  }
  // 3. Adjust perf_event_mlock_kb.
  long cpus = sysconf(_SC_NPROCESSORS_CONF);
  uint64_t mlock_kb = cpus * (mmap_page_range_.second + 1) * 4;

  uint64_t cur_mlock_kb;
  if (GetPerfEventMlockKb(&cur_mlock_kb) && cur_mlock_kb < mlock_kb &&
      !SetPerfEventMlockKb(mlock_kb)) {
    set_prop = true;
  }

  if (GetAndroidVersion() >= kAndroidVersionQ && set_prop) {
    return SetPerfEventLimits(std::max(max_sample_freq_, cur_max_freq), cpu_time_max_percent_,
                              std::max(mlock_kb, cur_mlock_kb));
  }
  return true;
}

bool MonitorCommand::SetEventSelectionFlags() {
  event_selection_set_.SampleIdAll();
  event_selection_set_.WakeupPerSample();
  if (fp_callchain_sampling_) {
    event_selection_set_.EnableFpCallChainSampling();
  } else if (dwarf_callchain_sampling_) {
    if (!event_selection_set_.EnableDwarfCallChainSampling(dump_stack_size_in_dwarf_sampling_)) {
      return false;
    }
  }
  return true;
}

bool MonitorCommand::ProcessRecord(Record* record) {
  UpdateRecord(record);
  last_record_timestamp_ = std::max(last_record_timestamp_, record->Timestamp());
  // In system wide recording, maps are dumped when they are needed by records.
  if (system_wide_collection_ && !DumpMapsForRecord(record)) {
    return false;
  }
  if (record->type() == PERF_RECORD_SAMPLE) {
    auto& r = *static_cast<SampleRecord*>(record);

    // Record filter check should go after DumpMapsForRecord(). Otherwise, process/thread name
    // filters don't work in system wide collection.
    if (!record_filter_.Check(r)) {
      return true;
    }

    // AdjustCallChainGeneratedByKernel() should go before UnwindRecord().
    // Because we don't want to adjust callchains generated by dwarf unwinder.
    if (fp_callchain_sampling_ || dwarf_callchain_sampling_) {
      r.AdjustCallChainGeneratedByKernel();
      if (!UnwindRecord(r)) {
        return false;
      }
    }
    DumpSampleRecord(r);
    if (fp_callchain_sampling_ || dwarf_callchain_sampling_) {
      DumpSampleCallchain(r);
    }
    sample_record_count_++;
  } else {
    // Other types of record are forwarded to the thread tree to build the
    // representation of each processes (mmap, comm, etc).
    thread_tree_.Update(*record);
  }
  return true;
}

void MonitorCommand::DumpSampleRecord(const SampleRecord& sr) {
  std::string output("sample");
  StringAppendF(&output, " name=%s", event_names_[sr.id_data.id].c_str());
  StringAppendF(&output, " ip=%p", reinterpret_cast<void*>(sr.ip_data.ip));
  SymbolInfo s = GetSymbolInfo(sr.tid_data.pid, sr.tid_data.tid, sr.ip_data.ip, sr.InKernel());
  StringAppendF(&output, " symbol=%s (%s[+%" PRIx64 "])", s.symbol->DemangledName(),
                s.dso->Path().c_str(), s.vaddr_in_file);
  StringAppendF(&output, " pid=%u tid=%u", sr.tid_data.pid, sr.tid_data.tid);
  StringAppendF(&output, " cpu=%u", sr.cpu_data.cpu);
  printf("%s\n", output.c_str());
  fflush(stdout);
}

void MonitorCommand::DumpSampleCallchain(const SampleRecord& sr) {
  bool in_kernel = sr.InKernel();
  if (sr.sample_type & PERF_SAMPLE_CALLCHAIN) {
    for (size_t i = 0; i < sr.callchain_data.ip_nr; ++i) {
      if (sr.callchain_data.ips[i] >= PERF_CONTEXT_MAX) {
        if (sr.callchain_data.ips[i] == PERF_CONTEXT_USER) {
          in_kernel = false;
        }
        continue;
      }
      SymbolInfo s =
          GetSymbolInfo(sr.tid_data.pid, sr.tid_data.tid, sr.callchain_data.ips[i], in_kernel);
      std::string output("sample callchain");
      StringAppendF(&output, " %s (%s[+%" PRIx64 "])", s.symbol->DemangledName(),
                    s.dso->Path().c_str(), s.vaddr_in_file);
      printf("%s\n", output.c_str());
    }
    fflush(stdout);
  }
}

SymbolInfo MonitorCommand::GetSymbolInfo(uint32_t pid, uint32_t tid, uint64_t ip, bool in_kernel) {
  ThreadEntry* thread = thread_tree_.FindThreadOrNew(pid, tid);
  const MapEntry* map = thread_tree_.FindMap(thread, ip, in_kernel);
  SymbolInfo info;
  info.symbol = thread_tree_.FindSymbol(map, ip, &info.vaddr_in_file, &info.dso);
  return info;
}

bool MonitorCommand::DumpMapsForRecord(Record* record) {
  if (record->type() == PERF_RECORD_SAMPLE) {
    pid_t pid = static_cast<SampleRecord*>(record)->tid_data.pid;
    if (dumped_processes_.find(pid) == dumped_processes_.end()) {
      // Dump map info and all thread names for that process.
      if (!map_record_reader_->ReadProcessMaps(pid, last_record_timestamp_)) {
        return false;
      }
      dumped_processes_.insert(pid);
    }
  }
  return true;
}

void MonitorCommand::UpdateRecord(Record* record) {
  if (record->type() == PERF_RECORD_COMM) {
    auto r = static_cast<CommRecord*>(record);
    if (r->data->pid == r->data->tid) {
      std::string s = GetCompleteProcessName(r->data->pid);
      if (!s.empty()) {
        r->SetCommandName(s);
      }
    }
  }
}

bool MonitorCommand::UnwindRecord(SampleRecord& r) {
  if ((r.sample_type & PERF_SAMPLE_CALLCHAIN) && (r.sample_type & PERF_SAMPLE_REGS_USER) &&
      (r.regs_user_data.reg_mask != 0) && (r.sample_type & PERF_SAMPLE_STACK_USER) &&
      (r.GetValidStackSize() > 0)) {
    ThreadEntry* thread = thread_tree_.FindThreadOrNew(r.tid_data.pid, r.tid_data.tid);
    RegSet regs(r.regs_user_data.abi, r.regs_user_data.reg_mask, r.regs_user_data.regs);
    std::vector<uint64_t> ips;
    std::vector<uint64_t> sps;
    if (!offline_unwinder_->UnwindCallChain(*thread, regs, r.stack_user_data.data,
                                            r.GetValidStackSize(), &ips, &sps)) {
      return false;
    }
    r.ReplaceRegAndStackWithCallChain(ips);
  }
  return true;
}
}  // namespace

void RegisterMonitorCommand() {
  RegisterCommand("monitor", [] { return std::unique_ptr<Command>(new MonitorCommand()); });
}

}  // namespace simpleperf
