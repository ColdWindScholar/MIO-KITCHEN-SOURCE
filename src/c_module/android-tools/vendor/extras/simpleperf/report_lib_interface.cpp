/*
 * Copyright (C) 2016 The Android Open Source Project
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
#include <optional>
#include <queue>
#include <utility>

#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/strings.h>

#include "JITDebugReader.h"
#include "RecordFilter.h"
#include "dso.h"
#include "event_attr.h"
#include "event_type.h"
#include "record_file.h"
#include "report_utils.h"
#include "thread_tree.h"
#include "tracing.h"
#include "utils.h"

extern "C" {

struct Sample {
  uint64_t ip;
  uint32_t pid;
  uint32_t tid;
  const char* thread_comm;
  uint64_t time;
  uint32_t in_kernel;
  uint32_t cpu;
  uint64_t period;
};

struct TracingFieldFormat {
  const char* name;
  uint32_t offset;
  uint32_t elem_size;
  uint32_t elem_count;
  uint32_t is_signed;
  uint32_t is_dynamic;
};

struct TracingDataFormat {
  uint32_t size;
  uint32_t field_count;
  TracingFieldFormat* fields;
};

struct Event {
  const char* name;
  TracingDataFormat tracing_data_format;
};

struct Mapping {
  uint64_t start;
  uint64_t end;
  uint64_t pgoff;
};

struct SymbolEntry {
  const char* dso_name;
  uint64_t vaddr_in_file;
  const char* symbol_name;
  uint64_t symbol_addr;
  uint64_t symbol_len;
  Mapping* mapping;
};

struct CallChainEntry {
  uint64_t ip;
  SymbolEntry symbol;
};

struct CallChain {
  uint32_t nr;
  CallChainEntry* entries;
};

struct FeatureSection {
  const char* data;
  uint32_t data_size;
};

}  // extern "C"

namespace simpleperf {
namespace {

struct EventInfo {
  perf_event_attr attr;
  std::string name;

  struct TracingInfo {
    TracingDataFormat data_format;
    std::vector<std::string> field_names;
    std::vector<TracingFieldFormat> fields;
  } tracing_info;
};

// If a recording file is generated with --trace-offcpu, we can select TraceOffCpuMode to report.
// It affects which samples are reported, and how period in each sample is calculated.
enum class TraceOffCpuMode {
  // Only report on-cpu samples, with period representing time spent on cpu.
  ON_CPU,
  // Only report off-cpu samples, with period representing time spent off cpu.
  OFF_CPU,
  // Report both on-cpu and off-cpu samples.
  ON_OFF_CPU,
  // Report on-cpu and off-cpu samples under the same event type.
  MIXED_ON_OFF_CPU,
};

static std::string TraceOffCpuModeToString(TraceOffCpuMode mode) {
  switch (mode) {
    case TraceOffCpuMode::ON_CPU:
      return "on-cpu";
    case TraceOffCpuMode::OFF_CPU:
      return "off-cpu";
    case TraceOffCpuMode::ON_OFF_CPU:
      return "on-off-cpu";
    case TraceOffCpuMode::MIXED_ON_OFF_CPU:
      return "mixed-on-off-cpu";
  }
}

static std::optional<TraceOffCpuMode> StringToTraceOffCpuMode(const std::string& s) {
  if (s == "on-cpu") {
    return TraceOffCpuMode::ON_CPU;
  }
  if (s == "off-cpu") {
    return TraceOffCpuMode::OFF_CPU;
  }
  if (s == "on-off-cpu") {
    return TraceOffCpuMode::ON_OFF_CPU;
  }
  if (s == "mixed-on-off-cpu") {
    return TraceOffCpuMode::MIXED_ON_OFF_CPU;
  }
  return std::nullopt;
}

struct TraceOffCpuData {
  std::vector<TraceOffCpuMode> supported_modes;
  std::string supported_modes_string;
  std::optional<TraceOffCpuMode> mode;
  std::unordered_map<pid_t, std::unique_ptr<SampleRecord>> thread_map;
};

}  // namespace

class ReportLib {
 public:
  ReportLib()
      : log_severity_(new android::base::ScopedLogSeverity(android::base::INFO)),
        record_filename_("perf.data"),
        current_thread_(nullptr),
        callchain_report_builder_(thread_tree_),
        record_filter_(thread_tree_) {}

  bool SetLogSeverity(const char* log_level);

  bool SetSymfs(const char* symfs_dir) { return Dso::SetSymFsDir(symfs_dir); }

  bool SetRecordFile(const char* record_file) {
    if (record_file_reader_) {
      LOG(ERROR) << "recording file " << record_filename_ << " has been opened";
      return false;
    }
    record_filename_ = record_file;
    return OpenRecordFileIfNecessary();
  }

  bool SetKallsymsFile(const char* kallsyms_file);

  void ShowIpForUnknownSymbol() { thread_tree_.ShowIpForUnknownSymbol(); }
  void ShowArtFrames(bool show) {
    bool remove_art_frame = !show;
    callchain_report_builder_.SetRemoveArtFrame(remove_art_frame);
  }
  bool RemoveMethod(const char* method_name_regex) {
    return callchain_report_builder_.RemoveMethod(method_name_regex);
  }
  void MergeJavaMethods(bool merge) { callchain_report_builder_.SetConvertJITFrame(merge); }
  bool AddProguardMappingFile(const char* mapping_file) {
    return callchain_report_builder_.AddProguardMappingFile(mapping_file);
  }
  const char* GetSupportedTraceOffCpuModes();
  bool SetTraceOffCpuMode(const char* mode);
  bool SetSampleFilter(const char** filters, int filters_len);
  bool AggregateThreads(const char** thread_name_regex, int thread_name_regex_len);

  Sample* GetNextSample();
  Event* GetEventOfCurrentSample() { return &current_event_; }
  SymbolEntry* GetSymbolOfCurrentSample() { return current_symbol_; }
  CallChain* GetCallChainOfCurrentSample() { return &current_callchain_; }
  const char* GetTracingDataOfCurrentSample() { return current_tracing_data_; }
  const char* GetProcessNameOfCurrentSample() {
    const ThreadEntry* thread = thread_tree_.FindThread(current_sample_.pid);
    return (thread != nullptr) ? thread->comm : "unknown";
  }

  const char* GetBuildIdForPath(const char* path);
  FeatureSection* GetFeatureSection(const char* feature_name);

 private:
  std::unique_ptr<SampleRecord> GetNextSampleRecord();
  void ProcessSampleRecord(std::unique_ptr<Record> r);
  void ProcessSwitchRecord(std::unique_ptr<Record> r);
  void AddSampleRecordToQueue(SampleRecord* r);
  bool SetCurrentSample(std::unique_ptr<SampleRecord> sample_record);
  const EventInfo& FindEvent(const SampleRecord& r);
  void CreateEvents();

  bool OpenRecordFileIfNecessary();
  Mapping* AddMapping(const MapEntry& map);

  std::unique_ptr<android::base::ScopedLogSeverity> log_severity_;
  std::string record_filename_;
  std::unique_ptr<RecordFileReader> record_file_reader_;
  ThreadTree thread_tree_;
  std::queue<std::unique_ptr<SampleRecord>> sample_record_queue_;
  const ThreadEntry* current_thread_;
  Sample current_sample_;
  Event current_event_;
  SymbolEntry* current_symbol_;
  CallChain current_callchain_;
  const char* current_tracing_data_;
  std::vector<std::unique_ptr<Mapping>> current_mappings_;
  std::vector<CallChainEntry> callchain_entries_;
  std::string build_id_string_;
  std::vector<EventInfo> events_;
  TraceOffCpuData trace_offcpu_;
  FeatureSection feature_section_;
  std::vector<char> feature_section_data_;
  CallChainReportBuilder callchain_report_builder_;
  ThreadReportBuilder thread_report_builder_;
  std::unique_ptr<Tracing> tracing_;
  RecordFilter record_filter_;
};

bool ReportLib::SetLogSeverity(const char* log_level) {
  android::base::LogSeverity severity;
  if (!GetLogSeverity(log_level, &severity)) {
    LOG(ERROR) << "Unknown log severity: " << log_level;
    return false;
  }
  log_severity_ = nullptr;
  log_severity_.reset(new android::base::ScopedLogSeverity(severity));
  return true;
}

bool ReportLib::SetKallsymsFile(const char* kallsyms_file) {
  std::string kallsyms;
  if (!android::base::ReadFileToString(kallsyms_file, &kallsyms)) {
    LOG(WARNING) << "Failed to read in kallsyms file from " << kallsyms_file;
    return false;
  }
  Dso::SetKallsyms(std::move(kallsyms));
  return true;
}

const char* ReportLib::GetSupportedTraceOffCpuModes() {
  if (!OpenRecordFileIfNecessary()) {
    return nullptr;
  }
  std::string& s = trace_offcpu_.supported_modes_string;
  s.clear();
  for (auto mode : trace_offcpu_.supported_modes) {
    if (!s.empty()) {
      s += ",";
    }
    s += TraceOffCpuModeToString(mode);
  }
  return s.data();
}

bool ReportLib::SetTraceOffCpuMode(const char* mode) {
  auto mode_value = StringToTraceOffCpuMode(mode);
  if (!mode_value) {
    return false;
  }
  if (!OpenRecordFileIfNecessary()) {
    return false;
  }
  auto& modes = trace_offcpu_.supported_modes;
  if (std::find(modes.begin(), modes.end(), mode_value) == modes.end()) {
    return false;
  }
  trace_offcpu_.mode = mode_value;
  return true;
}

bool ReportLib::SetSampleFilter(const char** filters, int filters_len) {
  std::vector<std::string> args;
  for (int i = 0; i < filters_len; i++) {
    args.emplace_back(filters[i]);
  }
  OptionFormatMap option_formats = GetRecordFilterOptionFormats(false);
  OptionValueMap options;
  std::vector<std::pair<OptionName, OptionValue>> ordered_options;
  if (!ConvertArgsToOptions(args, option_formats, "", &options, &ordered_options, nullptr)) {
    return false;
  }
  return record_filter_.ParseOptions(options);
}

bool ReportLib::AggregateThreads(const char** thread_name_regex, int thread_name_regex_len) {
  std::vector<std::string> regs(thread_name_regex_len);
  for (int i = 0; i < thread_name_regex_len; ++i) {
    regs[i] = thread_name_regex[i];
  }
  return thread_report_builder_.AggregateThreads(regs);
}

bool ReportLib::OpenRecordFileIfNecessary() {
  if (record_file_reader_ == nullptr) {
    record_file_reader_ = RecordFileReader::CreateInstance(record_filename_);
    if (record_file_reader_ == nullptr) {
      return false;
    }
    if (!record_file_reader_->LoadBuildIdAndFileFeatures(thread_tree_)) {
      return false;
    }
    auto& meta_info = record_file_reader_->GetMetaInfoFeature();
    if (auto it = meta_info.find("trace_offcpu"); it != meta_info.end() && it->second == "true") {
      // If recorded with --trace-offcpu, default is to report on-off-cpu samples.
      std::string event_name = GetEventNameByAttr(record_file_reader_->AttrSection()[0].attr);
      if (!android::base::StartsWith(event_name, "cpu-clock") &&
          !android::base::StartsWith(event_name, "task-clock")) {
        LOG(ERROR) << "Recording file " << record_filename_ << " is no longer supported. "
                   << "--trace-offcpu must be used with `-e cpu-clock` or `-e task-clock`.";
        return false;
      }
      trace_offcpu_.mode = TraceOffCpuMode::MIXED_ON_OFF_CPU;
      trace_offcpu_.supported_modes.push_back(TraceOffCpuMode::MIXED_ON_OFF_CPU);
      trace_offcpu_.supported_modes.push_back(TraceOffCpuMode::ON_OFF_CPU);
      trace_offcpu_.supported_modes.push_back(TraceOffCpuMode::ON_CPU);
      trace_offcpu_.supported_modes.push_back(TraceOffCpuMode::OFF_CPU);
    }
    if (!record_filter_.CheckClock(record_file_reader_->GetClockId())) {
      LOG(ERROR) << "Recording file " << record_filename_ << " doesn't match the clock of filter.";
      return false;
    }
  }
  return true;
}

Sample* ReportLib::GetNextSample() {
  if (!OpenRecordFileIfNecessary()) {
    return nullptr;
  }

  while (true) {
    std::unique_ptr<SampleRecord> r = GetNextSampleRecord();
    if (!r) {
      break;
    }
    if (SetCurrentSample(std::move(r))) {
      return &current_sample_;
    }
  }
  return nullptr;
}

std::unique_ptr<SampleRecord> ReportLib::GetNextSampleRecord() {
  while (sample_record_queue_.empty()) {
    std::unique_ptr<Record> record;
    if (!record_file_reader_->ReadRecord(record) || record == nullptr) {
      return nullptr;
    }
    thread_tree_.Update(*record);
    if (record->type() == PERF_RECORD_SAMPLE) {
      ProcessSampleRecord(std::move(record));
    } else if (record->type() == PERF_RECORD_SWITCH ||
               record->type() == PERF_RECORD_SWITCH_CPU_WIDE) {
      ProcessSwitchRecord(std::move(record));
    } else if (record->type() == PERF_RECORD_TRACING_DATA ||
               record->type() == SIMPLE_PERF_RECORD_TRACING_DATA) {
      const auto& r = *static_cast<TracingDataRecord*>(record.get());
      tracing_ = Tracing::Create(std::vector<char>(r.data, r.data + r.data_size));
      if (!tracing_) {
        return nullptr;
      }
    }
  }
  std::unique_ptr<SampleRecord> result = std::move(sample_record_queue_.front());
  sample_record_queue_.pop();
  return result;
}

void ReportLib::ProcessSampleRecord(std::unique_ptr<Record> r) {
  auto sr = static_cast<SampleRecord*>(r.get());
  if (!trace_offcpu_.mode) {
    r.release();
    AddSampleRecordToQueue(sr);
    return;
  }
  size_t attr_index = record_file_reader_->GetAttrIndexOfRecord(sr);
  bool offcpu_sample = attr_index > 0;
  if (trace_offcpu_.mode == TraceOffCpuMode::ON_CPU) {
    if (!offcpu_sample) {
      r.release();
      AddSampleRecordToQueue(sr);
    }
    return;
  }
  uint32_t tid = sr->tid_data.tid;
  auto it = trace_offcpu_.thread_map.find(tid);
  if (it == trace_offcpu_.thread_map.end() || !it->second) {
    // If there is no previous off-cpu sample, then store the current off-cpu sample.
    if (offcpu_sample) {
      r.release();
      if (it == trace_offcpu_.thread_map.end()) {
        trace_offcpu_.thread_map[tid].reset(sr);
      } else {
        it->second.reset(sr);
      }
    }
  } else {
    // If there is a previous off-cpu sample, update its period.
    SampleRecord* prev_sr = it->second.get();
    prev_sr->period_data.period =
        (prev_sr->Timestamp() < sr->Timestamp()) ? (sr->Timestamp() - prev_sr->Timestamp()) : 1;
    it->second.release();
    AddSampleRecordToQueue(prev_sr);
    if (offcpu_sample) {
      r.release();
      it->second.reset(sr);
    }
  }
  if (!offcpu_sample && (trace_offcpu_.mode == TraceOffCpuMode::ON_OFF_CPU ||
                         trace_offcpu_.mode == TraceOffCpuMode::MIXED_ON_OFF_CPU)) {
    r.release();
    AddSampleRecordToQueue(sr);
  }
}

void ReportLib::ProcessSwitchRecord(std::unique_ptr<Record> r) {
  if (r->header.misc & PERF_RECORD_MISC_SWITCH_OUT) {
    return;
  }
  uint32_t tid = r->sample_id.tid_data.tid;
  auto it = trace_offcpu_.thread_map.find(tid);
  if (it != trace_offcpu_.thread_map.end() && it->second) {
    // If there is a previous off-cpu sample, update its period.
    SampleRecord* prev_sr = it->second.get();
    prev_sr->period_data.period =
        (prev_sr->Timestamp() < r->Timestamp()) ? (r->Timestamp() - prev_sr->Timestamp()) : 1;
    it->second.release();
    AddSampleRecordToQueue(prev_sr);
  }
}

void ReportLib::AddSampleRecordToQueue(SampleRecord* r) {
  if (record_filter_.Check(*r)) {
    sample_record_queue_.emplace(r);
  }
}

bool ReportLib::SetCurrentSample(std::unique_ptr<SampleRecord> sample_record) {
  const SampleRecord& r = *sample_record;
  current_mappings_.clear();
  callchain_entries_.clear();
  current_sample_.ip = r.ip_data.ip;
  current_thread_ = thread_tree_.FindThreadOrNew(r.tid_data.pid, r.tid_data.tid);
  ThreadReport thread_report = thread_report_builder_.Build(*current_thread_);
  current_sample_.pid = thread_report.pid;
  current_sample_.tid = thread_report.tid;
  current_sample_.thread_comm = thread_report.thread_name;
  current_sample_.time = r.time_data.time;
  current_sample_.in_kernel = r.InKernel();
  current_sample_.cpu = r.cpu_data.cpu;
  current_sample_.period = r.period_data.period;

  size_t kernel_ip_count;
  std::vector<uint64_t> ips = r.GetCallChain(&kernel_ip_count);
  std::vector<CallChainReportEntry> report_entries =
      callchain_report_builder_.Build(current_thread_, ips, kernel_ip_count);
  if (report_entries.empty()) {
    // Skip samples with callchain fully removed by RemoveMethod().
    return false;
  }

  for (const auto& report_entry : report_entries) {
    callchain_entries_.resize(callchain_entries_.size() + 1);
    CallChainEntry& entry = callchain_entries_.back();
    entry.ip = report_entry.ip;
    if (report_entry.dso_name != nullptr) {
      entry.symbol.dso_name = report_entry.dso_name;
    } else {
      entry.symbol.dso_name = report_entry.dso->GetReportPath().data();
    }
    entry.symbol.vaddr_in_file = report_entry.vaddr_in_file;
    entry.symbol.symbol_name = report_entry.symbol->DemangledName();
    entry.symbol.symbol_addr = report_entry.symbol->addr;
    entry.symbol.symbol_len = report_entry.symbol->len;
    entry.symbol.mapping = AddMapping(*report_entry.map);
  }
  current_sample_.ip = callchain_entries_[0].ip;
  current_symbol_ = &(callchain_entries_[0].symbol);
  current_callchain_.nr = callchain_entries_.size() - 1;
  current_callchain_.entries = &callchain_entries_[1];
  const EventInfo& event = FindEvent(r);
  current_event_.name = event.name.c_str();
  current_event_.tracing_data_format = event.tracing_info.data_format;
  if (current_event_.tracing_data_format.size > 0u && (r.sample_type & PERF_SAMPLE_RAW)) {
    CHECK_GE(r.raw_data.size, current_event_.tracing_data_format.size);
    current_tracing_data_ = r.raw_data.data;
  } else {
    current_tracing_data_ = nullptr;
  }
  return true;
}

const EventInfo& ReportLib::FindEvent(const SampleRecord& r) {
  if (events_.empty()) {
    CreateEvents();
  }
  if (trace_offcpu_.mode == TraceOffCpuMode::MIXED_ON_OFF_CPU) {
    // To mix on-cpu and off-cpu samples, pretend they are from the same event type.
    // Otherwise, some report scripts may split them.
    return events_[0];
  }
  size_t attr_index = record_file_reader_->GetAttrIndexOfRecord(&r);
  return events_[attr_index];
}

void ReportLib::CreateEvents() {
  const EventAttrIds& attrs = record_file_reader_->AttrSection();
  events_.resize(attrs.size());
  for (size_t i = 0; i < attrs.size(); ++i) {
    events_[i].attr = attrs[i].attr;
    events_[i].name = GetEventNameByAttr(events_[i].attr);
    EventInfo::TracingInfo& tracing_info = events_[i].tracing_info;
    tracing_info.data_format.size = 0;
    tracing_info.data_format.field_count = 0;
    tracing_info.data_format.fields = nullptr;

    if (events_[i].attr.type == PERF_TYPE_TRACEPOINT && tracing_) {
      std::optional<TracingFormat> opt_format =
          tracing_->GetTracingFormatHavingId(events_[i].attr.config);
      if (!opt_format.has_value() || opt_format.value().fields.empty()) {
        continue;
      }
      const TracingFormat& format = opt_format.value();
      tracing_info.field_names.resize(format.fields.size());
      tracing_info.fields.resize(format.fields.size());
      for (size_t i = 0; i < format.fields.size(); ++i) {
        tracing_info.field_names[i] = format.fields[i].name;
        TracingFieldFormat& field = tracing_info.fields[i];
        field.name = tracing_info.field_names[i].c_str();
        field.offset = format.fields[i].offset;
        field.elem_size = format.fields[i].elem_size;
        field.elem_count = format.fields[i].elem_count;
        field.is_signed = format.fields[i].is_signed;
        field.is_dynamic = format.fields[i].is_dynamic;
      }
      TracingFieldFormat& field = tracing_info.fields.back();
      tracing_info.data_format.size = field.offset + field.elem_size * field.elem_count;
      tracing_info.data_format.field_count = tracing_info.fields.size();
      tracing_info.data_format.fields = &tracing_info.fields[0];
    }
  }
}

Mapping* ReportLib::AddMapping(const MapEntry& map) {
  current_mappings_.emplace_back(std::unique_ptr<Mapping>(new Mapping));
  Mapping* mapping = current_mappings_.back().get();
  mapping->start = map.start_addr;
  mapping->end = map.start_addr + map.len;
  mapping->pgoff = map.pgoff;
  return mapping;
}

const char* ReportLib::GetBuildIdForPath(const char* path) {
  if (!OpenRecordFileIfNecessary()) {
    build_id_string_.clear();
    return build_id_string_.c_str();
  }
  BuildId build_id = Dso::FindExpectedBuildIdForPath(path);
  if (build_id.IsEmpty()) {
    build_id_string_.clear();
  } else {
    build_id_string_ = build_id.ToString();
  }
  return build_id_string_.c_str();
}

FeatureSection* ReportLib::GetFeatureSection(const char* feature_name) {
  if (!OpenRecordFileIfNecessary()) {
    return nullptr;
  }
  int feature = PerfFileFormat::GetFeatureId(feature_name);
  if (feature == -1 || !record_file_reader_->ReadFeatureSection(feature, &feature_section_data_)) {
    return nullptr;
  }
  feature_section_.data = feature_section_data_.data();
  feature_section_.data_size = feature_section_data_.size();
  return &feature_section_;
}

}  // namespace simpleperf

using ReportLib = simpleperf::ReportLib;

extern "C" {

#define EXPORT __attribute__((visibility("default")))

// Create a new instance,
// pass the instance to the other functions below.
ReportLib* CreateReportLib() EXPORT;
void DestroyReportLib(ReportLib* report_lib) EXPORT;

// Set log severity, different levels are:
// verbose, debug, info, warning, error, fatal.
bool SetLogSeverity(ReportLib* report_lib, const char* log_level) EXPORT;
bool SetSymfs(ReportLib* report_lib, const char* symfs_dir) EXPORT;
bool SetRecordFile(ReportLib* report_lib, const char* record_file) EXPORT;
bool SetKallsymsFile(ReportLib* report_lib, const char* kallsyms_file) EXPORT;
void ShowIpForUnknownSymbol(ReportLib* report_lib) EXPORT;
void ShowArtFrames(ReportLib* report_lib, bool show) EXPORT;
bool RemoveMethod(ReportLib* report_lib, const char* method_name_regex) EXPORT;
void MergeJavaMethods(ReportLib* report_lib, bool merge) EXPORT;
bool AddProguardMappingFile(ReportLib* report_lib, const char* mapping_file) EXPORT;
const char* GetSupportedTraceOffCpuModes(ReportLib* report_lib) EXPORT;
bool SetTraceOffCpuMode(ReportLib* report_lib, const char* mode) EXPORT;
bool SetSampleFilter(ReportLib* report_lib, const char** filters, int filters_len) EXPORT;
bool AggregateThreads(ReportLib* report_lib, const char** thread_name_regex,
                      int thread_name_regex_len) EXPORT;

Sample* GetNextSample(ReportLib* report_lib) EXPORT;
Event* GetEventOfCurrentSample(ReportLib* report_lib) EXPORT;
SymbolEntry* GetSymbolOfCurrentSample(ReportLib* report_lib) EXPORT;
CallChain* GetCallChainOfCurrentSample(ReportLib* report_lib) EXPORT;
const char* GetTracingDataOfCurrentSample(ReportLib* report_lib) EXPORT;
const char* GetProcessNameOfCurrentSample(ReportLib* report_lib) EXPORT;

const char* GetBuildIdForPath(ReportLib* report_lib, const char* path) EXPORT;
FeatureSection* GetFeatureSection(ReportLib* report_lib, const char* feature_name) EXPORT;
}

// Exported methods working with a client created instance
ReportLib* CreateReportLib() {
  return new ReportLib();
}

void DestroyReportLib(ReportLib* report_lib) {
  delete report_lib;
}

bool SetLogSeverity(ReportLib* report_lib, const char* log_level) {
  return report_lib->SetLogSeverity(log_level);
}

bool SetSymfs(ReportLib* report_lib, const char* symfs_dir) {
  return report_lib->SetSymfs(symfs_dir);
}

bool SetRecordFile(ReportLib* report_lib, const char* record_file) {
  return report_lib->SetRecordFile(record_file);
}

void ShowIpForUnknownSymbol(ReportLib* report_lib) {
  return report_lib->ShowIpForUnknownSymbol();
}

void ShowArtFrames(ReportLib* report_lib, bool show) {
  return report_lib->ShowArtFrames(show);
}

bool RemoveMethod(ReportLib* report_lib, const char* method_name_regex) {
  return report_lib->RemoveMethod(method_name_regex);
}

void MergeJavaMethods(ReportLib* report_lib, bool merge) {
  return report_lib->MergeJavaMethods(merge);
}

bool SetKallsymsFile(ReportLib* report_lib, const char* kallsyms_file) {
  return report_lib->SetKallsymsFile(kallsyms_file);
}

bool AddProguardMappingFile(ReportLib* report_lib, const char* mapping_file) {
  return report_lib->AddProguardMappingFile(mapping_file);
}

const char* GetSupportedTraceOffCpuModes(ReportLib* report_lib) {
  return report_lib->GetSupportedTraceOffCpuModes();
}

bool SetTraceOffCpuMode(ReportLib* report_lib, const char* mode) {
  return report_lib->SetTraceOffCpuMode(mode);
}

bool SetSampleFilter(ReportLib* report_lib, const char** filters, int filters_len) {
  return report_lib->SetSampleFilter(filters, filters_len);
}

bool AggregateThreads(ReportLib* report_lib, const char** thread_name_regex,
                      int thread_name_regex_len) {
  return report_lib->AggregateThreads(thread_name_regex, thread_name_regex_len);
}

Sample* GetNextSample(ReportLib* report_lib) {
  return report_lib->GetNextSample();
}

Event* GetEventOfCurrentSample(ReportLib* report_lib) {
  return report_lib->GetEventOfCurrentSample();
}

SymbolEntry* GetSymbolOfCurrentSample(ReportLib* report_lib) {
  return report_lib->GetSymbolOfCurrentSample();
}

CallChain* GetCallChainOfCurrentSample(ReportLib* report_lib) {
  return report_lib->GetCallChainOfCurrentSample();
}

const char* GetTracingDataOfCurrentSample(ReportLib* report_lib) {
  return report_lib->GetTracingDataOfCurrentSample();
}

const char* GetProcessNameOfCurrentSample(ReportLib* report_lib) {
  return report_lib->GetProcessNameOfCurrentSample();
}

const char* GetBuildIdForPath(ReportLib* report_lib, const char* path) {
  return report_lib->GetBuildIdForPath(path);
}

FeatureSection* GetFeatureSection(ReportLib* report_lib, const char* feature_name) {
  return report_lib->GetFeatureSection(feature_name);
}
