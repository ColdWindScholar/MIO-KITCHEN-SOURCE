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

#include <inttypes.h>

#include <limits>
#include <memory>

#include <android-base/strings.h>

#include "system/extras/simpleperf/cmd_report_sample.pb.h"

#include <google/protobuf/io/coded_stream.h>
#include <google/protobuf/io/zero_copy_stream_impl_lite.h>

#include "OfflineUnwinder.h"
#include "RecordFilter.h"
#include "command.h"
#include "event_attr.h"
#include "event_type.h"
#include "record_file.h"
#include "report_utils.h"
#include "thread_tree.h"
#include "utils.h"

namespace simpleperf {
namespace {

namespace proto = simpleperf_report_proto;

static const char PROT_FILE_MAGIC[] = "SIMPLEPERF";
static const uint16_t PROT_FILE_VERSION = 1u;

class ProtobufFileWriter : public google::protobuf::io::CopyingOutputStream {
 public:
  explicit ProtobufFileWriter(FILE* out_fp) : out_fp_(out_fp) {}

  bool Write(const void* buffer, int size) override {
    return fwrite(buffer, size, 1, out_fp_) == 1;
  }

 private:
  FILE* out_fp_;
};

class ProtobufFileReader : public google::protobuf::io::CopyingInputStream {
 public:
  explicit ProtobufFileReader(FILE* in_fp) : in_fp_(in_fp) {}

  int Read(void* buffer, int size) override { return fread(buffer, 1, size, in_fp_); }

 private:
  FILE* in_fp_;
};

static proto::Sample_CallChainEntry_ExecutionType ToProtoExecutionType(
    CallChainExecutionType type) {
  switch (type) {
    case CallChainExecutionType::NATIVE_METHOD:
      return proto::Sample_CallChainEntry_ExecutionType_NATIVE_METHOD;
    case CallChainExecutionType::INTERPRETED_JVM_METHOD:
      return proto::Sample_CallChainEntry_ExecutionType_INTERPRETED_JVM_METHOD;
    case CallChainExecutionType::JIT_JVM_METHOD:
      return proto::Sample_CallChainEntry_ExecutionType_JIT_JVM_METHOD;
    case CallChainExecutionType::ART_METHOD:
      return proto::Sample_CallChainEntry_ExecutionType_ART_METHOD;
  }
  CHECK(false) << "unexpected execution type";
  return proto::Sample_CallChainEntry_ExecutionType_NATIVE_METHOD;
}

static const char* ProtoExecutionTypeToString(proto::Sample_CallChainEntry_ExecutionType type) {
  switch (type) {
    case proto::Sample_CallChainEntry_ExecutionType_NATIVE_METHOD:
      return "native_method";
    case proto::Sample_CallChainEntry_ExecutionType_INTERPRETED_JVM_METHOD:
      return "interpreted_jvm_method";
    case proto::Sample_CallChainEntry_ExecutionType_JIT_JVM_METHOD:
      return "jit_jvm_method";
    case proto::Sample_CallChainEntry_ExecutionType_ART_METHOD:
      return "art_method";
  }
  CHECK(false) << "unexpected execution type: " << type;
  return "";
}

static const char* ProtoUnwindingErrorCodeToString(
    proto::Sample_UnwindingResult_ErrorCode error_code) {
  switch (error_code) {
    case proto::Sample_UnwindingResult::ERROR_NONE:
      return "ERROR_NONE";
    case proto::Sample_UnwindingResult::ERROR_UNKNOWN:
      return "ERROR_UNKNOWN";
    case proto::Sample_UnwindingResult::ERROR_NOT_ENOUGH_STACK:
      return "ERROR_NOT_ENOUGH_STACK";
    case proto::Sample_UnwindingResult::ERROR_MEMORY_INVALID:
      return "ERROR_MEMORY_INVALID";
    case proto::Sample_UnwindingResult::ERROR_UNWIND_INFO:
      return "ERROR_UNWIND_INFO";
    case proto::Sample_UnwindingResult::ERROR_INVALID_MAP:
      return "ERROR_INVALID_MAP";
    case proto::Sample_UnwindingResult::ERROR_MAX_FRAME_EXCEEDED:
      return "ERROR_MAX_FRAME_EXCEEDED";
    case proto::Sample_UnwindingResult::ERROR_REPEATED_FRAME:
      return "ERROR_REPEATED_FRAME";
    case proto::Sample_UnwindingResult::ERROR_INVALID_ELF:
      return "ERROR_INVALID_ELF";
  }
}

struct SampleEntry {
  uint64_t time;
  uint64_t period;
  uint32_t event_type_id;
  bool is_complete_callchain;
  std::vector<CallChainReportEntry> callchain;
  std::optional<UnwindingResult> unwinding_result;
};

struct ThreadId {
  uint32_t pid;
  uint32_t tid;

  ThreadId(uint32_t pid, uint32_t tid) : pid(pid), tid(tid) {}

  bool operator==(const ThreadId& other) const { return pid == other.pid && tid == other.tid; }
};

struct ThreadIdHash {
  size_t operator()(const ThreadId& thread_id) const noexcept {
    size_t seed = 0;
    HashCombine(seed, thread_id.pid);
    HashCombine(seed, thread_id.tid);
    return seed;
  }
};

struct ThreadData {
  std::string thread_name;
  std::queue<SampleEntry> stack_gap_samples;
};

class ReportSampleCommand : public Command {
 public:
  ReportSampleCommand()
      : Command(
            "report-sample", "report raw sample information in perf.data",
            // clang-format off
"Usage: simpleperf report-sample [options]\n"
"--dump-protobuf-report <file>      Dump report file generated by\n"
"                                   `simpleperf report-sample --protobuf -o <file>`.\n"
"-i <file>                          Specify path of record file, default is perf.data.\n"
"-o report_file_name                Set report file name. When --protobuf is used, default is\n"
"                                   report_sample.trace. Otherwise, default writes to stdout.\n"
"--proguard-mapping-file <file>     Add proguard mapping file to de-obfuscate symbols.\n"
"--protobuf                         Use protobuf format in cmd_report_sample.proto to output\n"
"                                   samples.\n"
"--remove-gaps MAX_GAP_LENGTH       Ideally all callstacks are complete. But some may be broken\n"
"                                   for different reasons. To create a smooth view in Stack\n"
"                                   Chart, remove small gaps of broken callstacks. MAX_GAP_LENGTH\n"
"                                   is the max length of continuous broken-stack samples we want\n"
"                                   to remove. Default is 3.\n"
"--remove-unknown-kernel-symbols    Remove kernel callchains when kernel symbols are not\n"
"                                   available.\n"
"--show-art-frames                  Show frames of internal methods in the ART Java interpreter.\n"
"--show-callchain                   Show callchain with samples.\n"
"--show-execution-type              Show execution type of a method\n"
"--symdir <dir>                     Look for files with symbols in a directory recursively.\n"
"\n"
"Sample filter options:\n"
RECORD_FILTER_OPTION_HELP_MSG_FOR_REPORTING
            // clang-format on
            ),
        record_filename_("perf.data"),
        show_callchain_(false),
        use_protobuf_(false),
        report_fp_(nullptr),
        coded_os_(nullptr),
        sample_count_(0),
        lost_count_(0),
        trace_offcpu_(false),
        remove_unknown_kernel_symbols_(false),
        kernel_symbols_available_(false),
        callchain_report_builder_(thread_tree_),
        record_filter_(thread_tree_) {}

  bool Run(const std::vector<std::string>& args) override;

 private:
  bool ParseOptions(const std::vector<std::string>& args);
  bool DumpProtobufReport(const std::string& filename);
  bool OpenRecordFile();
  bool PrintMetaInfo();
  bool ProcessRecord(std::unique_ptr<Record> record);
  void UpdateThreadName(uint32_t pid, uint32_t tid);
  bool ProcessSampleRecord(const SampleRecord& r);
  bool ProcessSample(const ThreadEntry& thread, SampleEntry& sample);
  bool ReportSample(const ThreadId& thread_id, const SampleEntry& sample, size_t stack_gap_length);
  bool FinishReportSamples();
  bool PrintSampleInProtobuf(const ThreadId& thread_id, const SampleEntry& sample);
  void AddUnwindingResultInProtobuf(const UnwindingResult& unwinding_result,
                                    proto::Sample_UnwindingResult* proto_unwinding_result);
  bool ProcessSwitchRecord(Record* r);
  bool WriteRecordInProtobuf(proto::Record& proto_record);
  bool PrintLostSituationInProtobuf();
  bool PrintFileInfoInProtobuf();
  bool PrintThreadInfoInProtobuf();
  bool PrintSample(const ThreadId& thread_id, const SampleEntry& sample);
  void PrintLostSituation();

  std::string record_filename_;
  std::unique_ptr<RecordFileReader> record_file_reader_;
  std::string dump_protobuf_report_file_;
  bool show_callchain_;
  bool use_protobuf_;
  ThreadTree thread_tree_;
  std::string report_filename_;
  FILE* report_fp_;
  google::protobuf::io::CodedOutputStream* coded_os_;
  size_t sample_count_;
  size_t lost_count_;
  bool trace_offcpu_;
  std::vector<std::string> event_types_;
  bool remove_unknown_kernel_symbols_;
  bool kernel_symbols_available_;
  bool show_execution_type_ = false;
  CallChainReportBuilder callchain_report_builder_;
  std::unordered_map<ThreadId, ThreadData, ThreadIdHash> per_thread_data_;
  std::unique_ptr<UnwindingResultRecord> last_unwinding_result_;
  RecordFilter record_filter_;
  uint32_t max_remove_gap_length_ = 3;
};

bool ReportSampleCommand::Run(const std::vector<std::string>& args) {
  // 1. Parse options.
  if (!ParseOptions(args)) {
    return false;
  }
  // 2. Prepare report fp.
  report_fp_ = stdout;
  std::unique_ptr<FILE, decltype(&fclose)> fp(nullptr, fclose);
  if (!report_filename_.empty()) {
    const char* open_mode = use_protobuf_ ? "wb" : "w";
    fp.reset(fopen(report_filename_.c_str(), open_mode));
    if (fp == nullptr) {
      PLOG(ERROR) << "failed to open " << report_filename_;
      return false;
    }
    report_fp_ = fp.get();
  }

  // 3. Dump protobuf report.
  if (!dump_protobuf_report_file_.empty()) {
    return DumpProtobufReport(dump_protobuf_report_file_);
  }

  // 4. Open record file.
  if (!OpenRecordFile()) {
    return false;
  }
  if (use_protobuf_) {
    GOOGLE_PROTOBUF_VERIFY_VERSION;
  } else {
    thread_tree_.ShowMarkForUnknownSymbol();
    thread_tree_.ShowIpForUnknownSymbol();
  }

  // 5. Prepare protobuf output stream.
  std::unique_ptr<ProtobufFileWriter> protobuf_writer;
  std::unique_ptr<google::protobuf::io::CopyingOutputStreamAdaptor> protobuf_os;
  std::unique_ptr<google::protobuf::io::CodedOutputStream> protobuf_coded_os;
  if (use_protobuf_) {
    if (fprintf(report_fp_, "%s", PROT_FILE_MAGIC) != 10 ||
        fwrite(&PROT_FILE_VERSION, sizeof(uint16_t), 1, report_fp_) != 1u) {
      PLOG(ERROR) << "Failed to write magic/version";
      return false;
    }
    protobuf_writer.reset(new ProtobufFileWriter(report_fp_));
    protobuf_os.reset(new google::protobuf::io::CopyingOutputStreamAdaptor(protobuf_writer.get()));
    protobuf_coded_os.reset(new google::protobuf::io::CodedOutputStream(protobuf_os.get()));
    coded_os_ = protobuf_coded_os.get();
  }

  // 6. Read record file, and print samples online.
  if (!PrintMetaInfo()) {
    return false;
  }
  if (!record_file_reader_->ReadDataSection(
          [this](std::unique_ptr<Record> record) { return ProcessRecord(std::move(record)); })) {
    return false;
  }

  if (!FinishReportSamples()) {
    return false;
  }

  if (use_protobuf_) {
    if (!PrintLostSituationInProtobuf()) {
      return false;
    }
    if (!PrintFileInfoInProtobuf()) {
      return false;
    }
    if (!PrintThreadInfoInProtobuf()) {
      return false;
    }
    coded_os_->WriteLittleEndian32(0);
    if (coded_os_->HadError()) {
      LOG(ERROR) << "print protobuf report failed";
      return false;
    }
    protobuf_coded_os.reset(nullptr);
  } else {
    PrintLostSituation();
    fflush(report_fp_);
  }
  if (ferror(report_fp_) != 0) {
    PLOG(ERROR) << "print report failed";
    return false;
  }
  return true;
}

bool ReportSampleCommand::ParseOptions(const std::vector<std::string>& args) {
  OptionFormatMap option_formats = {
      {"--dump-protobuf-report", {OptionValueType::STRING, OptionType::SINGLE}},
      {"-i", {OptionValueType::STRING, OptionType::SINGLE}},
      {"-o", {OptionValueType::STRING, OptionType::SINGLE}},
      {"--proguard-mapping-file", {OptionValueType::STRING, OptionType::MULTIPLE}},
      {"--protobuf", {OptionValueType::NONE, OptionType::SINGLE}},
      {"--show-callchain", {OptionValueType::NONE, OptionType::SINGLE}},
      {"--remove-gaps", {OptionValueType::UINT, OptionType::SINGLE}},
      {"--remove-unknown-kernel-symbols", {OptionValueType::NONE, OptionType::SINGLE}},
      {"--show-art-frames", {OptionValueType::NONE, OptionType::SINGLE}},
      {"--show-execution-type", {OptionValueType::NONE, OptionType::SINGLE}},
      {"--symdir", {OptionValueType::STRING, OptionType::MULTIPLE}},
  };
  OptionFormatMap record_filter_options = GetRecordFilterOptionFormats(false);
  option_formats.insert(record_filter_options.begin(), record_filter_options.end());
  OptionValueMap options;
  std::vector<std::pair<OptionName, OptionValue>> ordered_options;
  if (!PreprocessOptions(args, option_formats, &options, &ordered_options, nullptr)) {
    return false;
  }
  options.PullStringValue("--dump-protobuf-report", &dump_protobuf_report_file_);
  options.PullStringValue("-i", &record_filename_);
  options.PullStringValue("-o", &report_filename_);
  for (const OptionValue& value : options.PullValues("--proguard-mapping-file")) {
    if (!callchain_report_builder_.AddProguardMappingFile(value.str_value)) {
      return false;
    }
  }
  use_protobuf_ = options.PullBoolValue("--protobuf");
  show_callchain_ = options.PullBoolValue("--show-callchain");
  if (!options.PullUintValue("--remove-gaps", &max_remove_gap_length_)) {
    return false;
  }
  remove_unknown_kernel_symbols_ = options.PullBoolValue("--remove-unknown-kernel-symbols");
  if (options.PullBoolValue("--show-art-frames")) {
    callchain_report_builder_.SetRemoveArtFrame(false);
  }
  show_execution_type_ = options.PullBoolValue("--show-execution-type");
  for (const OptionValue& value : options.PullValues("--symdir")) {
    if (!Dso::AddSymbolDir(value.str_value)) {
      return false;
    }
  }
  if (!record_filter_.ParseOptions(options)) {
    return false;
  }
  CHECK(options.values.empty());

  if (use_protobuf_ && report_filename_.empty()) {
    report_filename_ = "report_sample.trace";
  }
  return true;
}

bool ReportSampleCommand::DumpProtobufReport(const std::string& filename) {
  GOOGLE_PROTOBUF_VERIFY_VERSION;
  std::unique_ptr<FILE, decltype(&fclose)> fp(fopen(filename.c_str(), "rb"), fclose);
  if (fp == nullptr) {
    PLOG(ERROR) << "failed to open " << filename;
    return false;
  }
  char magic[11] = {};
  if (fread(magic, 10, 1, fp.get()) != 1u || memcmp(magic, PROT_FILE_MAGIC, 10) != 0) {
    PLOG(ERROR) << filename << " isn't a file generated by report-sample command.";
    return false;
  }
  FprintIndented(report_fp_, 0, "magic: %s\n", magic);
  uint16_t version;
  if (fread(&version, sizeof(uint16_t), 1, fp.get()) != 1u || version != PROT_FILE_VERSION) {
    PLOG(ERROR) << filename << " doesn't have the expected version.";
    return false;
  }
  FprintIndented(report_fp_, 0, "version: %u\n", version);

  ProtobufFileReader protobuf_reader(fp.get());
  google::protobuf::io::CopyingInputStreamAdaptor adaptor(&protobuf_reader);
  google::protobuf::io::CodedInputStream coded_is(&adaptor);
  // map from file_id to max_symbol_id requested on the file.
  std::unordered_map<uint32_t, int32_t> max_symbol_id_map;
  // files[file_id] is the number of symbols in the file.
  std::vector<uint32_t> files;
  uint32_t max_message_size = 64 * (1 << 20);
  coded_is.SetTotalBytesLimit(max_message_size);
  while (true) {
    uint32_t size;
    if (!coded_is.ReadLittleEndian32(&size)) {
      PLOG(ERROR) << "failed to read " << filename;
      return false;
    }
    if (size == 0) {
      break;
    }
    // Handle files having large symbol table.
    if (size > max_message_size) {
      max_message_size = size;
      coded_is.SetTotalBytesLimit(max_message_size);
    }
    auto limit = coded_is.PushLimit(size);
    proto::Record proto_record;
    if (!proto_record.ParseFromCodedStream(&coded_is)) {
      PLOG(ERROR) << "failed to read " << filename;
      return false;
    }
    coded_is.PopLimit(limit);
    if (proto_record.has_sample()) {
      auto& sample = proto_record.sample();
      static size_t sample_count = 0;
      FprintIndented(report_fp_, 0, "sample %zu:\n", ++sample_count);
      FprintIndented(report_fp_, 1, "event_type_id: %zu\n", sample.event_type_id());
      FprintIndented(report_fp_, 1, "time: %" PRIu64 "\n", sample.time());
      FprintIndented(report_fp_, 1, "event_count: %" PRIu64 "\n", sample.event_count());
      FprintIndented(report_fp_, 1, "thread_id: %d\n", sample.thread_id());
      FprintIndented(report_fp_, 1, "callchain:\n");
      for (int i = 0; i < sample.callchain_size(); ++i) {
        const proto::Sample_CallChainEntry& callchain = sample.callchain(i);
        FprintIndented(report_fp_, 2, "vaddr_in_file: %" PRIx64 "\n", callchain.vaddr_in_file());
        FprintIndented(report_fp_, 2, "file_id: %u\n", callchain.file_id());
        int32_t symbol_id = callchain.symbol_id();
        FprintIndented(report_fp_, 2, "symbol_id: %d\n", symbol_id);
        if (symbol_id < -1) {
          LOG(ERROR) << "unexpected symbol_id " << symbol_id;
          return false;
        }
        if (symbol_id != -1) {
          max_symbol_id_map[callchain.file_id()] =
              std::max(max_symbol_id_map[callchain.file_id()], symbol_id);
        }
        if (callchain.has_execution_type()) {
          FprintIndented(report_fp_, 2, "execution_type: %s\n",
                         ProtoExecutionTypeToString(callchain.execution_type()));
        }
      }
      if (sample.has_unwinding_result()) {
        FprintIndented(report_fp_, 1, "unwinding_result:\n");
        FprintIndented(report_fp_, 2, "raw_error_code: %u\n",
                       sample.unwinding_result().raw_error_code());
        FprintIndented(report_fp_, 2, "error_addr: 0x%" PRIx64 "\n",
                       sample.unwinding_result().error_addr());
        FprintIndented(report_fp_, 2, "error_code: %s\n",
                       ProtoUnwindingErrorCodeToString(sample.unwinding_result().error_code()));
      }
    } else if (proto_record.has_lost()) {
      auto& lost = proto_record.lost();
      FprintIndented(report_fp_, 0, "lost_situation:\n");
      FprintIndented(report_fp_, 1, "sample_count: %" PRIu64 "\n", lost.sample_count());
      FprintIndented(report_fp_, 1, "lost_count: %" PRIu64 "\n", lost.lost_count());
    } else if (proto_record.has_file()) {
      auto& file = proto_record.file();
      FprintIndented(report_fp_, 0, "file:\n");
      FprintIndented(report_fp_, 1, "id: %u\n", file.id());
      FprintIndented(report_fp_, 1, "path: %s\n", file.path().c_str());
      for (int i = 0; i < file.symbol_size(); ++i) {
        FprintIndented(report_fp_, 1, "symbol: %s\n", file.symbol(i).c_str());
      }
      for (int i = 0; i < file.mangled_symbol_size(); ++i) {
        FprintIndented(report_fp_, 1, "mangled_symbol: %s\n", file.mangled_symbol(i).c_str());
      }
      if (file.id() != files.size()) {
        LOG(ERROR) << "file id doesn't increase orderly, expected " << files.size() << ", really "
                   << file.id();
        return false;
      }
      files.push_back(file.symbol_size());
    } else if (proto_record.has_thread()) {
      auto& thread = proto_record.thread();
      FprintIndented(report_fp_, 0, "thread:\n");
      FprintIndented(report_fp_, 1, "thread_id: %u\n", thread.thread_id());
      FprintIndented(report_fp_, 1, "process_id: %u\n", thread.process_id());
      FprintIndented(report_fp_, 1, "thread_name: %s\n", thread.thread_name().c_str());
    } else if (proto_record.has_meta_info()) {
      auto& meta_info = proto_record.meta_info();
      FprintIndented(report_fp_, 0, "meta_info:\n");
      for (int i = 0; i < meta_info.event_type_size(); ++i) {
        FprintIndented(report_fp_, 1, "event_type: %s\n", meta_info.event_type(i).c_str());
      }
      if (meta_info.has_app_package_name()) {
        FprintIndented(report_fp_, 1, "app_package_name: %s\n",
                       meta_info.app_package_name().c_str());
      }
      if (meta_info.has_app_type()) {
        FprintIndented(report_fp_, 1, "app_type: %s\n", meta_info.app_type().c_str());
      }
      if (meta_info.has_android_sdk_version()) {
        FprintIndented(report_fp_, 1, "android_sdk_version: %s\n",
                       meta_info.android_sdk_version().c_str());
      }
      if (meta_info.has_android_build_type()) {
        FprintIndented(report_fp_, 1, "android_build_type: %s\n",
                       meta_info.android_build_type().c_str());
      }
      if (meta_info.has_trace_offcpu()) {
        FprintIndented(report_fp_, 1, "trace_offcpu: %s\n",
                       meta_info.trace_offcpu() ? "true" : "false");
      }
    } else if (proto_record.has_context_switch()) {
      auto& context_switch = proto_record.context_switch();
      FprintIndented(report_fp_, 0, "context_switch:\n");
      FprintIndented(report_fp_, 1, "switch_on: %s\n",
                     context_switch.switch_on() ? "true" : "false");
      FprintIndented(report_fp_, 1, "time: %" PRIu64 "\n", context_switch.time());
      FprintIndented(report_fp_, 1, "thread_id: %u\n", context_switch.thread_id());
    } else {
      LOG(ERROR) << "unexpected record type ";
      return false;
    }
  }
  for (auto pair : max_symbol_id_map) {
    if (pair.first >= files.size()) {
      LOG(ERROR) << "file_id(" << pair.first << ") >= file count (" << files.size() << ")";
      return false;
    }
    if (static_cast<uint32_t>(pair.second) >= files[pair.first]) {
      LOG(ERROR) << "symbol_id(" << pair.second << ") >= symbol count (" << files[pair.first]
                 << ") in file_id( " << pair.first << ")";
      return false;
    }
  }
  return true;
}

bool ReportSampleCommand::OpenRecordFile() {
  record_file_reader_ = RecordFileReader::CreateInstance(record_filename_);
  if (record_file_reader_ == nullptr) {
    return false;
  }
  if (!record_file_reader_->LoadBuildIdAndFileFeatures(thread_tree_)) {
    return false;
  }
  auto& meta_info = record_file_reader_->GetMetaInfoFeature();
  if (auto it = meta_info.find("trace_offcpu"); it != meta_info.end()) {
    trace_offcpu_ = it->second == "true";
    if (trace_offcpu_) {
      std::string event_name = GetEventNameByAttr(record_file_reader_->AttrSection()[0].attr);
      if (!android::base::StartsWith(event_name, "cpu-clock") &&
          !android::base::StartsWith(event_name, "task-clock")) {
        LOG(ERROR) << "Recording file " << record_filename_ << " is no longer supported. "
                   << "--trace-offcpu must be used with `-e cpu-clock` or `-e task-clock`.";
        return false;
      }
    }
  }
  if (auto it = meta_info.find("kernel_symbols_available"); it != meta_info.end()) {
    kernel_symbols_available_ = it->second == "true";
  }
  if (!record_filter_.CheckClock(record_file_reader_->GetClockId())) {
    return false;
  }
  for (const EventAttrWithId& attr : record_file_reader_->AttrSection()) {
    event_types_.push_back(GetEventNameByAttr(attr.attr));
  }
  return true;
}

bool ReportSampleCommand::PrintMetaInfo() {
  auto& meta_info = record_file_reader_->GetMetaInfoFeature();

  auto get_meta_info_value = [&meta_info](const char* key) -> std::string {
    if (auto it = meta_info.find(key); it != meta_info.end()) {
      return it->second;
    }
    return "";
  };

  std::string app_package_name = get_meta_info_value("app_package_name");
  std::string app_type = get_meta_info_value("app_type");
  std::string android_sdk_version = get_meta_info_value("android_sdk_version");
  std::string android_build_type = get_meta_info_value("android_build_type");

  if (use_protobuf_) {
    proto::Record proto_record;
    proto::MetaInfo* proto_meta_info = proto_record.mutable_meta_info();
    for (auto& event_type : event_types_) {
      *(proto_meta_info->add_event_type()) = event_type;
    }
    if (!app_package_name.empty()) {
      proto_meta_info->set_app_package_name(app_package_name);
    }
    if (!app_type.empty()) {
      proto_meta_info->set_app_type(app_type);
    }
    if (!android_sdk_version.empty()) {
      proto_meta_info->set_android_sdk_version(android_sdk_version);
    }
    if (!android_build_type.empty()) {
      proto_meta_info->set_android_build_type(android_build_type);
    }
    proto_meta_info->set_trace_offcpu(trace_offcpu_);
    return WriteRecordInProtobuf(proto_record);
  }
  FprintIndented(report_fp_, 0, "meta_info:\n");
  FprintIndented(report_fp_, 1, "trace_offcpu: %s\n", trace_offcpu_ ? "true" : "false");
  for (auto& event_type : event_types_) {
    FprintIndented(report_fp_, 1, "event_type: %s\n", event_type.c_str());
  }
  if (!app_package_name.empty()) {
    FprintIndented(report_fp_, 1, "app_package_name: %s\n", app_package_name.c_str());
  }
  if (!app_type.empty()) {
    FprintIndented(report_fp_, 1, "app_type: %s\n", app_type.c_str());
  }
  if (!android_sdk_version.empty()) {
    FprintIndented(report_fp_, 1, "android_sdk_version: %s\n", android_sdk_version.c_str());
  }
  if (!android_build_type.empty()) {
    FprintIndented(report_fp_, 1, "android_build_type: %s\n", android_build_type.c_str());
  }
  return true;
}

bool ReportSampleCommand::ProcessRecord(std::unique_ptr<Record> record) {
  thread_tree_.Update(*record);
  bool result = true;
  switch (record->type()) {
    case PERF_RECORD_SAMPLE: {
      result = ProcessSampleRecord(*static_cast<SampleRecord*>(record.get()));
      last_unwinding_result_.reset();
      break;
    }
    case SIMPLE_PERF_RECORD_UNWINDING_RESULT: {
      last_unwinding_result_.reset(static_cast<UnwindingResultRecord*>(record.release()));
      break;
    }
    case PERF_RECORD_LOST: {
      lost_count_ += static_cast<const LostRecord*>(record.get())->lost;
      break;
    }
    case PERF_RECORD_SWITCH:
      [[fallthrough]];
    case PERF_RECORD_SWITCH_CPU_WIDE: {
      result = ProcessSwitchRecord(record.get());
      break;
    }
  }
  return result;
}

static bool IsThreadStartPoint(CallChainReportEntry& entry) {
  // Android studio wants a clear call chain end to notify whether a call chain is complete.
  // For the main thread, the call chain ends at __libc_init in libc.so. For other threads,
  // the call chain ends at __start_thread in libc.so.
  // The call chain of the main thread can go beyond __libc_init, to _start (<= android O) or
  // _start_main (> android O).
  return entry.dso->FileName() == "libc.so" &&
         (strcmp(entry.symbol->Name(), "__libc_init") == 0 ||
          strcmp(entry.symbol->Name(), "__start_thread") == 0);
}

bool ReportSampleCommand::ProcessSampleRecord(const SampleRecord& r) {
  if (!record_filter_.Check(r)) {
    return true;
  }
  size_t kernel_ip_count;
  std::vector<uint64_t> ips = r.GetCallChain(&kernel_ip_count);
  if (kernel_ip_count > 0u && remove_unknown_kernel_symbols_ && !kernel_symbols_available_) {
    ips.erase(ips.begin(), ips.begin() + kernel_ip_count);
    kernel_ip_count = 0;
  }
  if (ips.empty()) {
    return true;
  }
  if (!show_callchain_) {
    ips.resize(1);
    kernel_ip_count = std::min(kernel_ip_count, static_cast<size_t>(1u));
  }
  const ThreadEntry* thread = thread_tree_.FindThreadOrNew(r.tid_data.pid, r.tid_data.tid);
  std::vector<CallChainReportEntry> callchain =
      callchain_report_builder_.Build(thread, ips, kernel_ip_count);

  bool complete_callchain = false;
  for (size_t i = 1; i < callchain.size(); i++) {
    // Stop at unknown callchain.
    if (thread_tree_.IsUnknownDso(callchain[i].dso)) {
      callchain.resize(i);
      break;
    }
    // Stop at thread start point. Because Android studio wants a clear call chain end.
    if (IsThreadStartPoint(callchain[i])) {
      complete_callchain = true;
      callchain.resize(i + 1);
      break;
    }
  }
  SampleEntry sample;
  sample.time = r.time_data.time;
  sample.period = r.period_data.period;
  sample.event_type_id = record_file_reader_->GetAttrIndexOfRecord(&r);
  sample.is_complete_callchain = complete_callchain;
  sample.callchain = std::move(callchain);
  // No need to add unwinding result for callchains fixed by callchain joiner.
  if (!complete_callchain && last_unwinding_result_) {
    sample.unwinding_result = last_unwinding_result_->unwinding_result;
  }

  return ProcessSample(*thread, sample);
}

bool ReportSampleCommand::ProcessSample(const ThreadEntry& thread, SampleEntry& sample) {
  ThreadId thread_id(thread.pid, thread.tid);
  ThreadData& data = per_thread_data_[thread_id];
  if (data.thread_name != thread.comm) {
    data.thread_name = thread.comm;
  }

  // If the sample has incomplete callchain, we push it to stack gap sample queue, to calculate
  // stack gap length later.
  if (!sample.is_complete_callchain) {
    data.stack_gap_samples.push(std::move(sample));
    return true;
  }
  // Otherwise, we can clean up stack gap sample queue and report the sample immediately.
  size_t gap_length = data.stack_gap_samples.size();
  while (!data.stack_gap_samples.empty()) {
    if (!ReportSample(thread_id, data.stack_gap_samples.front(), gap_length)) {
      return false;
    }
    data.stack_gap_samples.pop();
  }
  return ReportSample(thread_id, sample, 0);
}

bool ReportSampleCommand::ReportSample(const ThreadId& thread_id, const SampleEntry& sample,
                                       size_t stack_gap_length) {
  // Remove samples within a stack gap <= max_remove_gap_length_.
  if (stack_gap_length > 0 && stack_gap_length <= max_remove_gap_length_) {
    return true;
  }
  sample_count_++;
  if (use_protobuf_) {
    return PrintSampleInProtobuf(thread_id, sample);
  }
  return PrintSample(thread_id, sample);
}

bool ReportSampleCommand::FinishReportSamples() {
  for (auto& p : per_thread_data_) {
    const auto& thread_id = p.first;
    auto& sample_queue = p.second.stack_gap_samples;
    size_t gap_length = sample_queue.size();
    while (!sample_queue.empty()) {
      if (!ReportSample(thread_id, sample_queue.front(), gap_length)) {
        return false;
      }
      sample_queue.pop();
    }
  }
  return true;
}

bool ReportSampleCommand::PrintSampleInProtobuf(const ThreadId& thread_id,
                                                const SampleEntry& sample) {
  proto::Record proto_record;
  proto::Sample* proto_sample = proto_record.mutable_sample();
  proto_sample->set_time(sample.time);
  proto_sample->set_event_count(sample.period);
  proto_sample->set_thread_id(thread_id.tid);
  proto_sample->set_event_type_id(sample.event_type_id);

  for (const auto& node : sample.callchain) {
    proto::Sample_CallChainEntry* callchain = proto_sample->add_callchain();
    uint32_t file_id;
    if (!node.dso->GetDumpId(&file_id)) {
      file_id = node.dso->CreateDumpId();
    }
    int32_t symbol_id = -1;
    if (node.symbol != thread_tree_.UnknownSymbol()) {
      if (!node.symbol->GetDumpId(reinterpret_cast<uint32_t*>(&symbol_id))) {
        symbol_id = node.dso->CreateSymbolDumpId(node.symbol);
      }
    }
    callchain->set_vaddr_in_file(node.vaddr_in_file);
    callchain->set_file_id(file_id);
    callchain->set_symbol_id(symbol_id);
    if (show_execution_type_) {
      callchain->set_execution_type(ToProtoExecutionType(node.execution_type));
    }
  }
  if (sample.unwinding_result.has_value()) {
    AddUnwindingResultInProtobuf(sample.unwinding_result.value(),
                                 proto_sample->mutable_unwinding_result());
  }
  return WriteRecordInProtobuf(proto_record);
}

void ReportSampleCommand::AddUnwindingResultInProtobuf(
    const UnwindingResult& unwinding_result,
    proto::Sample_UnwindingResult* proto_unwinding_result) {
  proto_unwinding_result->set_raw_error_code(unwinding_result.error_code);
  proto_unwinding_result->set_error_addr(unwinding_result.error_addr);
  proto::Sample_UnwindingResult_ErrorCode error_code;
  switch (unwinding_result.error_code) {
    case UnwindStackErrorCode::ERROR_NONE:
      error_code = proto::Sample_UnwindingResult::ERROR_NONE;
      break;
    case UnwindStackErrorCode::ERROR_MEMORY_INVALID: {
      // We dumped stack data in range [stack_start, stack_end) for dwarf unwinding.
      // If the failed-to-read memory addr is within [stack_end, stack_end + 128k], then
      // probably we didn't dump enough stack data.
      // 128k is a guess number. The size of stack used in one function layer is usually smaller
      // than it. And using a bigger value is more likely to be false positive.
      if (unwinding_result.error_addr >= unwinding_result.stack_end &&
          unwinding_result.error_addr <= unwinding_result.stack_end + 128 * 1024) {
        error_code = proto::Sample_UnwindingResult::ERROR_NOT_ENOUGH_STACK;
      } else {
        error_code = proto::Sample_UnwindingResult::ERROR_MEMORY_INVALID;
      }
      break;
    }
    case UnwindStackErrorCode::ERROR_UNWIND_INFO:
      error_code = proto::Sample_UnwindingResult::ERROR_UNWIND_INFO;
      break;
    case UnwindStackErrorCode::ERROR_INVALID_MAP:
      error_code = proto::Sample_UnwindingResult::ERROR_INVALID_MAP;
      break;
    case UnwindStackErrorCode::ERROR_MAX_FRAMES_EXCEEDED:
      error_code = proto::Sample_UnwindingResult::ERROR_MAX_FRAME_EXCEEDED;
      break;
    case UnwindStackErrorCode::ERROR_REPEATED_FRAME:
      error_code = proto::Sample_UnwindingResult::ERROR_REPEATED_FRAME;
      break;
    case UnwindStackErrorCode::ERROR_INVALID_ELF:
      error_code = proto::Sample_UnwindingResult::ERROR_INVALID_ELF;
      break;
    case UnwindStackErrorCode::ERROR_UNSUPPORTED:
    case UnwindStackErrorCode::ERROR_THREAD_DOES_NOT_EXIST:
    case UnwindStackErrorCode::ERROR_THREAD_TIMEOUT:
    case UnwindStackErrorCode::ERROR_SYSTEM_CALL:
      // These error_codes shouldn't happen in simpleperf's use of libunwindstack.
      error_code = proto::Sample_UnwindingResult::ERROR_UNKNOWN;
      break;
    default:
      LOG(ERROR) << "unknown unwinding error code: " << unwinding_result.error_code;
      error_code = proto::Sample_UnwindingResult::ERROR_UNKNOWN;
      break;
  }
  proto_unwinding_result->set_error_code(error_code);
}

bool ReportSampleCommand::ProcessSwitchRecord(Record* r) {
  bool switch_on = !(r->header.misc & PERF_RECORD_MISC_SWITCH_OUT);
  uint64_t time = r->Timestamp();
  uint32_t tid = r->sample_id.tid_data.tid;
  if (use_protobuf_) {
    proto::Record proto_record;
    proto::ContextSwitch* proto_switch = proto_record.mutable_context_switch();
    proto_switch->set_switch_on(switch_on);
    proto_switch->set_time(time);
    proto_switch->set_thread_id(tid);
    return WriteRecordInProtobuf(proto_record);
  }
  FprintIndented(report_fp_, 0, "context_switch:\n");
  FprintIndented(report_fp_, 1, "switch_on: %s\n", switch_on ? "true" : "false");
  FprintIndented(report_fp_, 1, "time: %" PRIu64 "\n", time);
  FprintIndented(report_fp_, 1, "thread_id: %u\n", tid);
  return true;
}

bool ReportSampleCommand::WriteRecordInProtobuf(proto::Record& proto_record) {
  coded_os_->WriteLittleEndian32(static_cast<uint32_t>(proto_record.ByteSizeLong()));
  if (!proto_record.SerializeToCodedStream(coded_os_)) {
    LOG(ERROR) << "failed to write record to protobuf";
    return false;
  }
  return true;
}

bool ReportSampleCommand::PrintLostSituationInProtobuf() {
  proto::Record proto_record;
  proto::LostSituation* lost = proto_record.mutable_lost();
  lost->set_sample_count(sample_count_);
  lost->set_lost_count(lost_count_);
  return WriteRecordInProtobuf(proto_record);
}

static bool CompareDsoByDumpId(Dso* d1, Dso* d2) {
  uint32_t id1 = UINT_MAX;
  d1->GetDumpId(&id1);
  uint32_t id2 = UINT_MAX;
  d2->GetDumpId(&id2);
  return id1 < id2;
}

bool ReportSampleCommand::PrintFileInfoInProtobuf() {
  std::vector<Dso*> dsos = thread_tree_.GetAllDsos();
  std::sort(dsos.begin(), dsos.end(), CompareDsoByDumpId);
  for (Dso* dso : dsos) {
    uint32_t file_id;
    if (!dso->GetDumpId(&file_id)) {
      continue;
    }
    proto::Record proto_record;
    proto::File* file = proto_record.mutable_file();
    file->set_id(file_id);
    file->set_path(std::string{dso->GetReportPath()});
    const std::vector<Symbol>& symbols = dso->GetSymbols();
    std::vector<const Symbol*> dump_symbols;
    for (const auto& sym : symbols) {
      if (sym.HasDumpId()) {
        dump_symbols.push_back(&sym);
      }
    }
    std::sort(dump_symbols.begin(), dump_symbols.end(), Symbol::CompareByDumpId);

    for (const auto& sym : dump_symbols) {
      file->add_symbol(sym->DemangledName());
      file->add_mangled_symbol(sym->Name());
    }
    if (!WriteRecordInProtobuf(proto_record)) {
      return false;
    }
  }
  return true;
}

bool ReportSampleCommand::PrintThreadInfoInProtobuf() {
  for (const auto& p : per_thread_data_) {
    const auto& thread_id = p.first;
    const auto& thread_data = p.second;
    proto::Record proto_record;
    proto::Thread* proto_thread = proto_record.mutable_thread();
    proto_thread->set_thread_id(thread_id.tid);
    proto_thread->set_process_id(thread_id.pid);
    proto_thread->set_thread_name(thread_data.thread_name);
    if (!WriteRecordInProtobuf(proto_record)) {
      return false;
    }
  }
  return true;
}

bool ReportSampleCommand::PrintSample(const ThreadId& thread_id, const SampleEntry& sample) {
  FprintIndented(report_fp_, 0, "sample:\n");
  FprintIndented(report_fp_, 1, "event_type: %s\n", event_types_[sample.event_type_id].data());
  FprintIndented(report_fp_, 1, "time: %" PRIu64 "\n", sample.time);
  FprintIndented(report_fp_, 1, "event_count: %" PRIu64 "\n", sample.period);
  FprintIndented(report_fp_, 1, "thread_id: %d\n", thread_id.tid);
  FprintIndented(report_fp_, 1, "thread_name: %s\n",
                 per_thread_data_[thread_id].thread_name.c_str());
  const auto& entries = sample.callchain;
  CHECK(!entries.empty());
  FprintIndented(report_fp_, 1, "vaddr_in_file: %" PRIx64 "\n", entries[0].vaddr_in_file);
  FprintIndented(report_fp_, 1, "file: %s\n", entries[0].dso->GetReportPath().data());
  FprintIndented(report_fp_, 1, "symbol: %s\n", entries[0].symbol->DemangledName());
  if (show_execution_type_) {
    FprintIndented(report_fp_, 1, "execution_type: %s\n",
                   ProtoExecutionTypeToString(ToProtoExecutionType(entries[0].execution_type)));
  }

  if (entries.size() > 1u) {
    FprintIndented(report_fp_, 1, "callchain:\n");
    for (size_t i = 1u; i < entries.size(); ++i) {
      FprintIndented(report_fp_, 2, "vaddr_in_file: %" PRIx64 "\n", entries[i].vaddr_in_file);
      FprintIndented(report_fp_, 2, "file: %s\n", entries[i].dso->GetReportPath().data());
      FprintIndented(report_fp_, 2, "symbol: %s\n", entries[i].symbol->DemangledName());
      if (show_execution_type_) {
        FprintIndented(report_fp_, 2, "execution_type: %s\n",
                       ProtoExecutionTypeToString(ToProtoExecutionType(entries[i].execution_type)));
      }
    }
  }
  return true;
}

void ReportSampleCommand::PrintLostSituation() {
  FprintIndented(report_fp_, 0, "lost_situation:\n");
  FprintIndented(report_fp_, 1, "sample_count: %" PRIu64 "\n", sample_count_);
  FprintIndented(report_fp_, 1, "lost_count: %" PRIu64 "\n", lost_count_);
}

}  // namespace

void RegisterReportSampleCommand() {
  RegisterCommand("report-sample",
                  [] { return std::unique_ptr<Command>(new ReportSampleCommand()); });
}

}  // namespace simpleperf
