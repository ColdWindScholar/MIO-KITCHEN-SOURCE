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
#include <stdint.h>

#include <map>
#include <string>
#include <type_traits>
#include <vector>

#include <android-base/logging.h>
#include <android-base/stringprintf.h>
#include <android-base/strings.h>

#include "BranchListFile.h"
#include "ETMDecoder.h"
#include "command.h"
#include "dso.h"
#include "event_attr.h"
#include "event_type.h"
#include "perf_regs.h"
#include "record.h"
#include "record_file.h"
#include "tracing.h"
#include "utils.h"

namespace simpleperf {
namespace {

using namespace PerfFileFormat;

struct SymbolInfo {
  Dso* dso;
  const Symbol* symbol;
  uint64_t vaddr_in_file;
};

using ExtractFieldFn = std::function<std::string(const TracingField&, const PerfSampleRawType&)>;

struct EventInfo {
  size_t tp_data_size = 0;
  std::vector<TracingField> tp_fields;
  std::vector<ExtractFieldFn> extract_field_functions;
};

std::string ExtractStringField(const TracingField& field, const PerfSampleRawType& data) {
  std::string s;
  // data points to a char [field.elem_count] array. It is not guaranteed to be ended
  // with '\0'. So need to copy from data like strncpy.
  size_t max_len = std::min(data.size - field.offset, field.elem_count);
  const char* p = data.data + field.offset;
  for (size_t i = 0; i < max_len && *p != '\0'; i++) {
    s.push_back(*p++);
  }
  return s;
}

std::string ExtractDynamicStringField(const TracingField& field, const PerfSampleRawType& data) {
  std::string s;
  const char* p = data.data + field.offset;
  if (field.elem_size != 4 || field.offset + field.elem_size > data.size) {
    return s;
  }
  uint32_t location;
  MoveFromBinaryFormat(location, p);
  // Parse location: (max_len << 16) | off.
  uint32_t offset = location & 0xffff;
  uint32_t max_len = location >> 16;
  if (offset + max_len <= data.size) {
    p = data.data + offset;
    for (size_t i = 0; i < max_len && *p != '\0'; i++) {
      s.push_back(*p++);
    }
  }
  return s;
}

template <typename T, typename UT = typename std::make_unsigned<T>::type>
std::string ExtractIntFieldFromPointer(const TracingField& field, const char* p) {
  static_assert(std::is_signed<T>::value);
  T value;
  MoveFromBinaryFormat(value, p);

  if (field.is_signed) {
    return android::base::StringPrintf("%" PRId64, static_cast<int64_t>(value));
  }
  return android::base::StringPrintf("0x%" PRIx64, static_cast<uint64_t>(static_cast<UT>(value)));
}

template <typename T>
std::string ExtractIntField(const TracingField& field, const PerfSampleRawType& data) {
  if (field.offset + sizeof(T) > data.size) {
    return "";
  }
  return ExtractIntFieldFromPointer<T>(field, data.data + field.offset);
}

template <typename T>
std::string ExtractIntArrayField(const TracingField& field, const PerfSampleRawType& data) {
  if (field.offset + field.elem_size * field.elem_count > data.size) {
    return "";
  }
  std::string s;
  const char* p = data.data + field.offset;
  for (size_t i = 0; i < field.elem_count; i++) {
    if (i != 0) {
      s.push_back(' ');
    }
    ExtractIntFieldFromPointer<T>(field, p);
    p += field.elem_size;
  }
  return s;
}

std::string ExtractUnknownField(const TracingField& field, const PerfSampleRawType& data) {
  size_t total = field.elem_size * field.elem_count;
  if (field.offset + total > data.size) {
    return "";
  }
  uint32_t value;
  std::string s;
  const char* p = data.data + field.offset;
  for (size_t i = 0; i + sizeof(value) <= total; i += sizeof(value)) {
    if (i != 0) {
      s.push_back(' ');
    }
    MoveFromBinaryFormat(value, p);
    s += android::base::StringPrintf("0x%08x", value);
  }
  return s;
}

ExtractFieldFn GetExtractFieldFunction(const TracingField& field) {
  if (field.is_dynamic) {
    return ExtractDynamicStringField;
  }
  if (field.elem_count > 1 && field.elem_size == 1) {
    // Probably the field is a string.
    // Don't use field.is_signed, which has different values on x86 and arm.
    return ExtractStringField;
  }
  if (field.elem_count == 1) {
    switch (field.elem_size) {
      case 1:
        return ExtractIntField<int8_t>;
      case 2:
        return ExtractIntField<int16_t>;
      case 4:
        return ExtractIntField<int32_t>;
      case 8:
        return ExtractIntField<int64_t>;
    }
  } else {
    switch (field.elem_size) {
      case 1:
        return ExtractIntArrayField<int8_t>;
      case 2:
        return ExtractIntArrayField<int16_t>;
      case 4:
        return ExtractIntArrayField<int32_t>;
      case 8:
        return ExtractIntArrayField<int64_t>;
    }
  }
  return ExtractUnknownField;
}

class ETMThreadTreeForDumpCmd : public ETMThreadTree {
 public:
  ETMThreadTreeForDumpCmd(ThreadTree& thread_tree) : thread_tree_(thread_tree) {}

  void DisableThreadExitRecords() override { thread_tree_.DisableThreadExitRecords(); }
  const ThreadEntry* FindThread(int tid) override { return thread_tree_.FindThread(tid); }
  const MapSet& GetKernelMaps() override { return thread_tree_.GetKernelMaps(); }

 private:
  ThreadTree& thread_tree_;
};

class DumpRecordCommand : public Command {
 public:
  DumpRecordCommand()
      : Command("dump", "dump perf record file",
                // clang-format off
"Usage: simpleperf dumprecord [options] [perf_record_file]\n"
"    Dump different parts of a perf record file. Default file is perf.data.\n"
"--dump-etm type1,type2,...   Dump etm data. A type is one of raw, packet and element.\n"
"-i <record_file>             Record file to dump. Default is perf.data.\n"
"--symdir <dir>               Look for binaries in a directory recursively.\n"
                // clang-format on
        ) {}

  bool Run(const std::vector<std::string>& args);

 private:
  bool ParseOptions(const std::vector<std::string>& args);
  void DumpFileHeader();
  void DumpAttrSection();
  bool DumpDataSection();
  bool ProcessRecord(Record* r);
  void ProcessSampleRecord(const SampleRecord& r);
  void ProcessCallChainRecord(const CallChainRecord& r);
  SymbolInfo GetSymbolInfo(uint32_t pid, uint32_t tid, uint64_t ip,
                           std::optional<bool> in_kernel = std::nullopt);
  bool ProcessTracingData(const TracingDataRecord& r);
  bool DumpAuxData(const AuxRecord& aux);
  bool DumpFeatureSection();

  // options
  std::string record_filename_ = "perf.data";
  ETMDumpOption etm_dump_option_;

  std::unique_ptr<RecordFileReader> record_file_reader_;
  std::unique_ptr<ETMDecoder> etm_decoder_;
  std::unique_ptr<ETMThreadTree> etm_thread_tree_;
  ThreadTree thread_tree_;

  std::vector<EventInfo> events_;
};

bool DumpRecordCommand::Run(const std::vector<std::string>& args) {
  if (!ParseOptions(args)) {
    return false;
  }
  record_file_reader_ = RecordFileReader::CreateInstance(record_filename_);
  if (record_file_reader_ == nullptr) {
    return false;
  }
  DumpFileHeader();
  DumpAttrSection();
  if (!DumpDataSection()) {
    return false;
  }
  return DumpFeatureSection();
}

bool DumpRecordCommand::ParseOptions(const std::vector<std::string>& args) {
  const OptionFormatMap option_formats = {
      {"--dump-etm", {OptionValueType::STRING, OptionType::SINGLE}},
      {"-i", {OptionValueType::STRING, OptionType::SINGLE}},
      {"--symdir", {OptionValueType::STRING, OptionType::MULTIPLE}},
  };
  OptionValueMap options;
  std::vector<std::pair<OptionName, OptionValue>> ordered_options;
  std::vector<std::string> non_option_args;
  if (!PreprocessOptions(args, option_formats, &options, &ordered_options, &non_option_args)) {
    return false;
  }
  if (auto value = options.PullValue("--dump-etm"); value) {
    if (!ParseEtmDumpOption(value->str_value, &etm_dump_option_)) {
      return false;
    }
  }
  options.PullStringValue("-i", &record_filename_);
  for (const OptionValue& value : options.PullValues("--symdir")) {
    if (!Dso::AddSymbolDir(value.str_value)) {
      return false;
    }
  }
  CHECK(options.values.empty());
  if (non_option_args.size() > 1) {
    LOG(ERROR) << "too many record files";
    return false;
  }
  if (non_option_args.size() == 1) {
    record_filename_ = non_option_args[0];
  }
  return true;
}

static const std::string GetFeatureNameOrUnknown(int feature) {
  std::string name = GetFeatureName(feature);
  return name.empty() ? android::base::StringPrintf("unknown_feature(%d)", feature) : name;
}

void DumpRecordCommand::DumpFileHeader() {
  const FileHeader& header = record_file_reader_->FileHeader();
  printf("magic: ");
  for (size_t i = 0; i < 8; ++i) {
    printf("%c", header.magic[i]);
  }
  printf("\n");
  printf("header_size: %" PRId64 "\n", header.header_size);
  if (header.header_size != sizeof(header)) {
    PLOG(WARNING) << "record file header size " << header.header_size
                  << "doesn't match expected header size " << sizeof(header);
  }
  printf("attr_size: %" PRId64 "\n", header.attr_size);
  printf("attrs[file section]: offset %" PRId64 ", size %" PRId64 "\n", header.attrs.offset,
         header.attrs.size);
  printf("data[file section]: offset %" PRId64 ", size %" PRId64 "\n", header.data.offset,
         header.data.size);
  printf("event_types[file section]: offset %" PRId64 ", size %" PRId64 "\n",
         header.event_types.offset, header.event_types.size);

  std::vector<int> features;
  for (size_t i = 0; i < FEAT_MAX_NUM; ++i) {
    size_t j = i / 8;
    size_t k = i % 8;
    if ((header.features[j] & (1 << k)) != 0) {
      features.push_back(i);
    }
  }
  for (auto& feature : features) {
    printf("feature: %s\n", GetFeatureNameOrUnknown(feature).c_str());
  }
}

void DumpRecordCommand::DumpAttrSection() {
  const EventAttrIds& attrs = record_file_reader_->AttrSection();
  for (size_t i = 0; i < attrs.size(); ++i) {
    const auto& attr = attrs[i];
    printf("attr %zu:\n", i + 1);
    DumpPerfEventAttr(attr.attr, 1);
    if (!attr.ids.empty()) {
      printf("  ids:");
      for (const auto& id : attr.ids) {
        printf(" %" PRId64, id);
      }
      printf("\n");
    }
  }
}

bool DumpRecordCommand::DumpDataSection() {
  thread_tree_.ShowIpForUnknownSymbol();
  if (!record_file_reader_->LoadBuildIdAndFileFeatures(thread_tree_)) {
    return false;
  }

  auto record_callback = [&](std::unique_ptr<Record> r) { return ProcessRecord(r.get()); };
  return record_file_reader_->ReadDataSection(record_callback);
}

bool DumpRecordCommand::ProcessRecord(Record* r) {
  r->Dump();
  thread_tree_.Update(*r);

  bool res = true;
  switch (r->type()) {
    case PERF_RECORD_SAMPLE:
      ProcessSampleRecord(*static_cast<SampleRecord*>(r));
      break;
    case SIMPLE_PERF_RECORD_CALLCHAIN:
      ProcessCallChainRecord(*static_cast<CallChainRecord*>(r));
      break;
    case PERF_RECORD_AUXTRACE_INFO: {
      etm_thread_tree_.reset(new ETMThreadTreeForDumpCmd(thread_tree_));
      etm_decoder_ = ETMDecoder::Create(*static_cast<AuxTraceInfoRecord*>(r), *etm_thread_tree_);
      if (etm_decoder_) {
        etm_decoder_->EnableDump(etm_dump_option_);
      } else {
        res = false;
      }
      break;
    }
    case PERF_RECORD_AUX: {
      res = DumpAuxData(*static_cast<AuxRecord*>(r));
      break;
    }
    case PERF_RECORD_TRACING_DATA:
    case SIMPLE_PERF_RECORD_TRACING_DATA: {
      res = ProcessTracingData(*static_cast<TracingDataRecord*>(r));
      break;
    }
  }
  return res;
}

void DumpRecordCommand::ProcessSampleRecord(const SampleRecord& sr) {
  bool in_kernel = sr.InKernel();
  if (sr.sample_type & PERF_SAMPLE_CALLCHAIN) {
    PrintIndented(1, "callchain:\n");
    for (size_t i = 0; i < sr.callchain_data.ip_nr; ++i) {
      if (sr.callchain_data.ips[i] >= PERF_CONTEXT_MAX) {
        if (sr.callchain_data.ips[i] == PERF_CONTEXT_USER) {
          in_kernel = false;
        }
        continue;
      }
      SymbolInfo s =
          GetSymbolInfo(sr.tid_data.pid, sr.tid_data.tid, sr.callchain_data.ips[i], in_kernel);
      PrintIndented(2, "%s (%s[+%" PRIx64 "])\n", s.symbol->DemangledName(), s.dso->Path().c_str(),
                    s.vaddr_in_file);
    }
  }
  if (sr.sample_type & PERF_SAMPLE_BRANCH_STACK) {
    PrintIndented(1, "branch_stack:\n");
    for (size_t i = 0; i < sr.branch_stack_data.stack_nr; ++i) {
      uint64_t from_ip = sr.branch_stack_data.stack[i].from;
      uint64_t to_ip = sr.branch_stack_data.stack[i].to;
      SymbolInfo from_symbol = GetSymbolInfo(sr.tid_data.pid, sr.tid_data.tid, from_ip);
      SymbolInfo to_symbol = GetSymbolInfo(sr.tid_data.pid, sr.tid_data.tid, to_ip);
      PrintIndented(2, "%s (%s[+%" PRIx64 "]) -> %s (%s[+%" PRIx64 "])\n",
                    from_symbol.symbol->DemangledName(), from_symbol.dso->Path().c_str(),
                    from_symbol.vaddr_in_file, to_symbol.symbol->DemangledName(),
                    to_symbol.dso->Path().c_str(), to_symbol.vaddr_in_file);
    }
  }
  // Dump tracepoint fields.
  if (!events_.empty()) {
    size_t attr_index = record_file_reader_->GetAttrIndexOfRecord(&sr);
    auto& event = events_[attr_index];
    if (event.tp_data_size > 0 && sr.raw_data.size >= event.tp_data_size) {
      PrintIndented(1, "tracepoint fields:\n");
      for (size_t i = 0; i < event.tp_fields.size(); i++) {
        auto& field = event.tp_fields[i];
        std::string s = event.extract_field_functions[i](field, sr.raw_data);
        PrintIndented(2, "%s: %s\n", field.name.c_str(), s.c_str());
      }
    }
  }
}

void DumpRecordCommand::ProcessCallChainRecord(const CallChainRecord& cr) {
  PrintIndented(1, "callchain:\n");
  for (size_t i = 0; i < cr.ip_nr; ++i) {
    SymbolInfo s = GetSymbolInfo(cr.pid, cr.tid, cr.ips[i], false);
    PrintIndented(2, "%s (%s[+%" PRIx64 "])\n", s.symbol->DemangledName(), s.dso->Path().c_str(),
                  s.vaddr_in_file);
  }
}

SymbolInfo DumpRecordCommand::GetSymbolInfo(uint32_t pid, uint32_t tid, uint64_t ip,
                                            std::optional<bool> in_kernel) {
  ThreadEntry* thread = thread_tree_.FindThreadOrNew(pid, tid);
  const MapEntry* map;
  if (in_kernel.has_value()) {
    map = thread_tree_.FindMap(thread, ip, in_kernel.value());
  } else {
    map = thread_tree_.FindMap(thread, ip);
  }
  SymbolInfo info;
  info.symbol = thread_tree_.FindSymbol(map, ip, &info.vaddr_in_file, &info.dso);
  return info;
}

bool DumpRecordCommand::DumpAuxData(const AuxRecord& aux) {
  if (aux.data->aux_size > SIZE_MAX) {
    LOG(ERROR) << "invalid aux size";
    return false;
  }
  size_t size = aux.data->aux_size;
  if (size > 0) {
    std::vector<uint8_t> data;
    bool error = false;
    if (!record_file_reader_->ReadAuxData(aux.Cpu(), aux.data->aux_offset, size, data, error)) {
      return !error;
    }
    if (!etm_decoder_) {
      LOG(ERROR) << "ETMDecoder isn't created";
      return false;
    }
    return etm_decoder_->ProcessData(data.data(), size, !aux.Unformatted(), aux.Cpu());
  }
  return true;
}

bool DumpRecordCommand::ProcessTracingData(const TracingDataRecord& r) {
  auto tracing = Tracing::Create(std::vector<char>(r.data, r.data + r.data_size));
  if (!tracing) {
    return false;
  }
  const EventAttrIds& attrs = record_file_reader_->AttrSection();
  events_.resize(attrs.size());
  for (size_t i = 0; i < attrs.size(); i++) {
    auto& attr = attrs[i].attr;
    auto& event = events_[i];

    if (attr.type != PERF_TYPE_TRACEPOINT) {
      continue;
    }
    std::optional<TracingFormat> format = tracing->GetTracingFormatHavingId(attr.config);
    if (!format.has_value()) {
      LOG(ERROR) << "failed to get tracing format";
      return false;
    }
    event.tp_fields = format.value().fields;
    // Decide dump function for each field.
    for (size_t j = 0; j < event.tp_fields.size(); j++) {
      auto& field = event.tp_fields[j];
      event.extract_field_functions.push_back(GetExtractFieldFunction(field));
      event.tp_data_size += field.elem_count * field.elem_size;
    }
  }
  return true;
}

bool DumpRecordCommand::DumpFeatureSection() {
  std::map<int, SectionDesc> section_map = record_file_reader_->FeatureSectionDescriptors();
  for (const auto& pair : section_map) {
    int feature = pair.first;
    const auto& section = pair.second;
    printf("feature section for %s: offset %" PRId64 ", size %" PRId64 "\n",
           GetFeatureNameOrUnknown(feature).c_str(), section.offset, section.size);
    if (feature == FEAT_BUILD_ID) {
      std::vector<BuildIdRecord> records = record_file_reader_->ReadBuildIdFeature();
      for (auto& r : records) {
        r.Dump(1);
      }
    } else if (feature == FEAT_OSRELEASE) {
      std::string s = record_file_reader_->ReadFeatureString(feature);
      PrintIndented(1, "osrelease: %s\n", s.c_str());
    } else if (feature == FEAT_ARCH) {
      std::string s = record_file_reader_->ReadFeatureString(feature);
      PrintIndented(1, "arch: %s\n", s.c_str());
    } else if (feature == FEAT_CMDLINE) {
      std::vector<std::string> cmdline = record_file_reader_->ReadCmdlineFeature();
      PrintIndented(1, "cmdline: %s\n", android::base::Join(cmdline, ' ').c_str());
    } else if (feature == FEAT_FILE || feature == FEAT_FILE2) {
      FileFeature file;
      uint64_t read_pos = 0;
      bool error = false;
      PrintIndented(1, "file:\n");
      while (record_file_reader_->ReadFileFeature(read_pos, file, error)) {
        PrintIndented(2, "file_path %s\n", file.path.c_str());
        PrintIndented(2, "file_type %s\n", DsoTypeToString(file.type));
        PrintIndented(2, "min_vaddr 0x%" PRIx64 "\n", file.min_vaddr);
        PrintIndented(2, "file_offset_of_min_vaddr 0x%" PRIx64 "\n", file.file_offset_of_min_vaddr);
        PrintIndented(2, "symbols:\n");
        for (const auto& symbol : file.symbols) {
          PrintIndented(3, "%s [0x%" PRIx64 "-0x%" PRIx64 "]\n", symbol.DemangledName(),
                        symbol.addr, symbol.addr + symbol.len);
        }
        if (file.type == DSO_DEX_FILE) {
          PrintIndented(2, "dex_file_offsets:\n");
          for (uint64_t offset : file.dex_file_offsets) {
            PrintIndented(3, "0x%" PRIx64 "\n", offset);
          }
        }
      }
      if (error) {
        return false;
      }
    } else if (feature == FEAT_META_INFO) {
      PrintIndented(1, "meta_info:\n");
      for (auto& pair : record_file_reader_->GetMetaInfoFeature()) {
        PrintIndented(2, "%s = %s\n", pair.first.c_str(), pair.second.c_str());
      }
    } else if (feature == FEAT_AUXTRACE) {
      PrintIndented(1, "file_offsets_of_auxtrace_records:\n");
      for (auto offset : record_file_reader_->ReadAuxTraceFeature()) {
        PrintIndented(2, "%" PRIu64 "\n", offset);
      }
    } else if (feature == FEAT_DEBUG_UNWIND) {
      PrintIndented(1, "debug_unwind:\n");
      if (auto opt_debug_unwind = record_file_reader_->ReadDebugUnwindFeature(); opt_debug_unwind) {
        for (const DebugUnwindFile& file : opt_debug_unwind.value()) {
          PrintIndented(2, "path: %s\n", file.path.c_str());
          PrintIndented(2, "size: %" PRIu64 "\n", file.size);
        }
      }
    } else if (feature == FEAT_ETM_BRANCH_LIST) {
      std::string data;
      if (!record_file_reader_->ReadFeatureSection(FEAT_ETM_BRANCH_LIST, &data)) {
        return false;
      }
      ETMBinaryMap binary_map;
      if (!StringToETMBinaryMap(data, binary_map)) {
        return false;
      }
      PrintIndented(1, "etm_branch_list:\n");
      for (const auto& [key, binary] : binary_map) {
        PrintIndented(2, "path: %s\n", key.path.c_str());
        PrintIndented(2, "build_id: %s\n", key.build_id.ToString().c_str());
        PrintIndented(2, "binary_type: %s\n", DsoTypeToString(binary.dso_type));
        if (binary.dso_type == DSO_KERNEL) {
          PrintIndented(2, "kernel_start_addr: 0x%" PRIx64 "\n", key.kernel_start_addr);
        }
        for (const auto& [addr, branches] : binary.GetOrderedBranchMap()) {
          PrintIndented(3, "addr: 0x%" PRIx64 "\n", addr);
          for (const auto& [branch, count] : branches) {
            std::string s = "0b";
            for (auto it = branch.rbegin(); it != branch.rend(); ++it) {
              s.push_back(*it ? '1' : '0');
            }
            PrintIndented(3, "branch: %s\n", s.c_str());
            PrintIndented(3, "count: %" PRIu64 "\n", count);
          }
        }
      }
    } else if (feature == FEAT_INIT_MAP) {
      PrintIndented(1, "init_map:\n");
      auto callback = [&](std::unique_ptr<Record> r) { return ProcessRecord(r.get()); };
      if (!record_file_reader_->ReadInitMapFeature(callback)) {
        return false;
      }
    }
  }
  return true;
}

}  // namespace

void RegisterDumpRecordCommand() {
  RegisterCommand("dump", [] { return std::unique_ptr<Command>(new DumpRecordCommand); });
}

}  // namespace simpleperf
