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

#include "record_file.h"

#include <fcntl.h>
#include <string.h>

#include <set>
#include <string_view>
#include <vector>

#include <android-base/logging.h>
#include <android-base/scopeguard.h>

#include "event_attr.h"
#include "record.h"
#include "system/extras/simpleperf/record_file.pb.h"
#include "utils.h"

namespace simpleperf {

using namespace PerfFileFormat;

namespace PerfFileFormat {

static const std::map<int, std::string> feature_name_map = {
    {FEAT_TRACING_DATA, "tracing_data"},
    {FEAT_BUILD_ID, "build_id"},
    {FEAT_HOSTNAME, "hostname"},
    {FEAT_OSRELEASE, "osrelease"},
    {FEAT_VERSION, "version"},
    {FEAT_ARCH, "arch"},
    {FEAT_NRCPUS, "nrcpus"},
    {FEAT_CPUDESC, "cpudesc"},
    {FEAT_CPUID, "cpuid"},
    {FEAT_TOTAL_MEM, "total_mem"},
    {FEAT_CMDLINE, "cmdline"},
    {FEAT_EVENT_DESC, "event_desc"},
    {FEAT_CPU_TOPOLOGY, "cpu_topology"},
    {FEAT_NUMA_TOPOLOGY, "numa_topology"},
    {FEAT_BRANCH_STACK, "branch_stack"},
    {FEAT_PMU_MAPPINGS, "pmu_mappings"},
    {FEAT_GROUP_DESC, "group_desc"},
    {FEAT_AUXTRACE, "auxtrace"},
    {FEAT_FILE, "file"},
    {FEAT_META_INFO, "meta_info"},
    {FEAT_DEBUG_UNWIND, "debug_unwind"},
    {FEAT_DEBUG_UNWIND_FILE, "debug_unwind_file"},
    {FEAT_FILE2, "file2"},
    {FEAT_ETM_BRANCH_LIST, "etm_branch_list"},
    {FEAT_INIT_MAP, "init_map"},
};

std::string GetFeatureName(int feature_id) {
  auto it = feature_name_map.find(feature_id);
  return it == feature_name_map.end() ? "" : it->second;
}

int GetFeatureId(const std::string& feature_name) {
  for (auto& pair : feature_name_map) {
    if (pair.second == feature_name) {
      return pair.first;
    }
  }
  return -1;
}

}  // namespace PerfFileFormat

std::unique_ptr<RecordFileReader> RecordFileReader::CreateInstance(const std::string& filename) {
  std::string mode = std::string("rb") + CLOSE_ON_EXEC_MODE;
  FILE* fp = fopen(filename.c_str(), mode.c_str());
  if (fp == nullptr) {
    PLOG(ERROR) << "failed to open record file '" << filename << "'";
    return nullptr;
  }
  auto reader = std::unique_ptr<RecordFileReader>(new RecordFileReader(filename, fp));
  if (!reader->ReadHeader() || !reader->ReadAttrSection() ||
      !reader->ReadFeatureSectionDescriptors() || !reader->ReadMetaInfoFeature()) {
    return nullptr;
  }
  reader->UseRecordingEnvironment();
  return reader;
}

RecordFileReader::RecordFileReader(const std::string& filename, FILE* fp)
    : filename_(filename),
      record_fp_(fp),
      event_id_pos_in_sample_records_(0),
      event_id_reverse_pos_in_non_sample_records_(0) {
  file_size_ = GetFileSize(filename_);
}

RecordFileReader::~RecordFileReader() {
  if (record_fp_ != nullptr) {
    Close();
  }
}

bool RecordFileReader::Close() {
  bool result = true;
  if (fclose(record_fp_) != 0) {
    PLOG(ERROR) << "failed to close record file '" << filename_ << "'";
    result = false;
  }
  record_fp_ = nullptr;
  return result;
}

bool RecordFileReader::ReadHeader() {
  if (!Read(&header_, sizeof(header_))) {
    return false;
  }
  if (memcmp(header_.magic, PERF_MAGIC, sizeof(header_.magic)) != 0) {
    LOG(ERROR) << filename_ << " is not a valid profiling record file.";
    return false;
  }
  if (header_.attr_size == 0 || !CheckSectionDesc(header_.attrs, sizeof(header_)) ||
      !CheckSectionDesc(header_.data, sizeof(header_))) {
    LOG(ERROR) << "invalid header in " << filename_;
    return false;
  }
  return true;
}

bool RecordFileReader::CheckSectionDesc(const SectionDesc& desc, uint64_t min_offset,
                                        uint64_t alignment) {
  uint64_t desc_end;
  if (desc.offset < min_offset || __builtin_add_overflow(desc.offset, desc.size, &desc_end) ||
      desc_end > file_size_) {
    return false;
  }
  if (desc.size % alignment != 0) {
    return false;
  }
  return true;
}

bool RecordFileReader::ReadAttrSection() {
  size_t attr_count = header_.attrs.size / header_.attr_size;
  if (header_.attr_size != sizeof(FileAttr)) {
    if (header_.attr_size <= sizeof(SectionDesc)) {
      LOG(ERROR) << "invalid attr section in " << filename_;
      return false;
    }
    LOG(DEBUG) << "attr size (" << header_.attr_size << ") in " << filename_
               << " doesn't match expected size (" << sizeof(FileAttr) << ")";
  }
  if (attr_count == 0) {
    LOG(ERROR) << "no attr in file " << filename_;
    return false;
  }
  if (fseek(record_fp_, header_.attrs.offset, SEEK_SET) != 0) {
    PLOG(ERROR) << "fseek() failed";
    return false;
  }
  event_attrs_.resize(attr_count);
  std::vector<SectionDesc> id_sections(attr_count);
  size_t attr_size_in_file = header_.attr_size - sizeof(SectionDesc);
  for (size_t i = 0; i < attr_count; ++i) {
    std::vector<char> buf(header_.attr_size);
    if (!Read(buf.data(), buf.size())) {
      return false;
    }
    // The struct perf_event_attr is defined in a Linux header file. It can be extended in newer
    // kernel versions with more fields and a bigger size. To disable these extensions, set their
    // values to zero. So to copy perf_event_attr from file to memory safely, ensure the copy
    // doesn't overflow the file or memory, and set the values of any extra fields in memory to
    // zero.
    if (attr_size_in_file >= sizeof(perf_event_attr)) {
      memcpy(&event_attrs_[i].attr, &buf[0], sizeof(perf_event_attr));
    } else {
      memset(&event_attrs_[i].attr, 0, sizeof(perf_event_attr));
      memcpy(&event_attrs_[i].attr, &buf[0], attr_size_in_file);
    }
    memcpy(&id_sections[i], &buf[attr_size_in_file], sizeof(SectionDesc));
    if (!CheckSectionDesc(id_sections[i], 0, sizeof(uint64_t))) {
      LOG(ERROR) << "invalid attr section in " << filename_;
      return false;
    }
  }
  if (event_attrs_.size() > 1) {
    if (!GetCommonEventIdPositionsForAttrs(event_attrs_, &event_id_pos_in_sample_records_,
                                           &event_id_reverse_pos_in_non_sample_records_)) {
      return false;
    }
  }
  for (size_t i = 0; i < attr_count; ++i) {
    if (!ReadIdSection(id_sections[i], &event_attrs_[i].ids)) {
      return false;
    }
    for (auto id : event_attrs_[i].ids) {
      event_id_to_attr_map_[id] = i;
    }
  }
  return true;
}

bool RecordFileReader::ReadFeatureSectionDescriptors() {
  std::vector<int> features;
  for (size_t i = 0; i < sizeof(header_.features); ++i) {
    for (size_t j = 0; j < 8; ++j) {
      if (header_.features[i] & (1 << j)) {
        features.push_back(i * 8 + j);
      }
    }
  }
  uint64_t feature_section_offset = header_.data.offset + header_.data.size;
  if (fseek(record_fp_, feature_section_offset, SEEK_SET) != 0) {
    PLOG(ERROR) << "fseek() failed";
    return false;
  }
  uint64_t min_section_data_pos = feature_section_offset + sizeof(SectionDesc) * features.size();
  for (const auto& id : features) {
    SectionDesc desc;
    if (!Read(&desc, sizeof(desc))) {
      return false;
    }
    if (!CheckSectionDesc(desc, min_section_data_pos)) {
      LOG(ERROR) << "invalid feature section descriptor in " << filename_;
      return false;
    }
    feature_section_descriptors_.emplace(id, desc);
  }
  return true;
}

bool RecordFileReader::ReadIdSection(const SectionDesc& section, std::vector<uint64_t>* ids) {
  size_t id_count = section.size / sizeof(uint64_t);
  if (fseek(record_fp_, section.offset, SEEK_SET) != 0) {
    PLOG(ERROR) << "fseek() failed";
    return false;
  }
  ids->resize(id_count);
  if (!Read(ids->data(), section.size)) {
    return false;
  }
  return true;
}

void RecordFileReader::UseRecordingEnvironment() {
  std::string arch = ReadFeatureString(FEAT_ARCH);
  if (!arch.empty()) {
    scoped_arch_.reset(new ScopedCurrentArch(GetArchType(arch)));
  }
  auto& meta_info = GetMetaInfoFeature();
  if (auto it = meta_info.find("event_type_info"); it != meta_info.end()) {
    if (EventTypeManager::Instance().GetScopedFinder() == nullptr) {
      scoped_event_types_.reset(new ScopedEventTypes(it->second));
    }
  }
}

bool RecordFileReader::ReadDataSection(
    const std::function<bool(std::unique_ptr<Record>)>& callback) {
  std::unique_ptr<Record> record;
  while (ReadRecord(record)) {
    if (record == nullptr) {
      return true;
    }
    if (!callback(std::move(record))) {
      return false;
    }
  }
  return false;
}

bool RecordFileReader::ReadRecord(std::unique_ptr<Record>& record) {
  if (read_record_pos_.end == 0) {
    if (fseek(record_fp_, header_.data.offset, SEEK_SET) != 0) {
      PLOG(ERROR) << "fseek() failed";
      return false;
    }
    read_record_pos_.end = header_.data.size;
  }
  record = nullptr;
  if (read_record_pos_.pos < read_record_pos_.end ||
      (decompressor_ && decompressor_->HasOutputData())) {
    record = ReadRecord(read_record_pos_);
    if (record == nullptr) {
      return false;
    }
    if (record->type() == SIMPLE_PERF_RECORD_EVENT_ID) {
      ProcessEventIdRecord(*static_cast<EventIdRecord*>(record.get()));
    }
  }
  return true;
}

std::unique_ptr<Record> RecordFileReader::ReadRecord(ReadPos& pos) {
  std::unique_ptr<char[]> p = ReadRecordWithDecompression(pos);
  if (!p) {
    return nullptr;
  }
  RecordHeader header;
  if (!header.Parse(p.get())) {
    return nullptr;
  }

  if (header.type == SIMPLE_PERF_RECORD_SPLIT) {
    // Read until meeting a RECORD_SPLIT_END record.
    std::vector<char> buf;
    while (header.type == SIMPLE_PERF_RECORD_SPLIT) {
      buf.insert(buf.end(), p.get() + Record::header_size(), p.get() + header.size);
      p = ReadRecordWithDecompression(pos);
      if (!p || !header.Parse(p.get())) {
        return nullptr;
      }
    }
    if (header.type != SIMPLE_PERF_RECORD_SPLIT_END) {
      LOG(ERROR) << "SPLIT records are not followed by a SPLIT_END record.";
      return nullptr;
    }
    if (buf.size() < Record::header_size() || !header.Parse(buf.data()) ||
        header.size != buf.size()) {
      LOG(ERROR) << "invalid record merged from SPLIT records";
      return nullptr;
    }
    p.reset(new char[buf.size()]);
    memcpy(p.get(), buf.data(), buf.size());
  }

  const perf_event_attr* attr = &event_attrs_[0].attr;
  if (event_attrs_.size() > 1 && header.type < PERF_RECORD_USER_DEFINED_TYPE_START) {
    bool has_event_id = false;
    uint64_t event_id;
    if (header.type == PERF_RECORD_SAMPLE) {
      if (header.size > event_id_pos_in_sample_records_ + sizeof(uint64_t)) {
        has_event_id = true;
        event_id = *reinterpret_cast<uint64_t*>(p.get() + event_id_pos_in_sample_records_);
      }
    } else {
      if (header.size > event_id_reverse_pos_in_non_sample_records_) {
        has_event_id = true;
        event_id = *reinterpret_cast<uint64_t*>(p.get() + header.size -
                                                event_id_reverse_pos_in_non_sample_records_);
      }
    }
    if (has_event_id) {
      auto it = event_id_to_attr_map_.find(event_id);
      if (it != event_id_to_attr_map_.end()) {
        attr = &event_attrs_[it->second].attr;
      }
    }
  }
  auto r = ReadRecordFromBuffer(*attr, header.type, p.get(), p.get() + header.size);
  if (!r) {
    return nullptr;
  }
  p.release();
  r->OwnBinary();
  if (r->type() == PERF_RECORD_AUXTRACE) {
    auto auxtrace = static_cast<AuxTraceRecord*>(r.get());
    auxtrace->location.file_offset = header_.data.offset + read_record_pos_.pos;
    read_record_pos_.pos += auxtrace->data->aux_size;
    if (fseek(record_fp_, auxtrace->data->aux_size, SEEK_CUR) != 0) {
      PLOG(ERROR) << "fseek() failed";
      return nullptr;
    }
  }
  return r;
}

std::unique_ptr<char[]> RecordFileReader::ReadRecordWithDecompression(ReadPos& pos) {
  while (true) {
    if (decompressor_) {
      std::string_view output = decompressor_->GetOutputData();
      if (output.size() >= sizeof(perf_event_header)) {
        auto header = reinterpret_cast<const perf_event_header*>(output.data());
        if (header->size <= output.size()) {
          std::unique_ptr<char[]> p(new char[header->size]);
          memcpy(p.get(), output.data(), header->size);
          decompressor_->ConsumeOutputData(header->size);
          return p;
        }
      }
    }
    if (pos.pos == pos.end) {
      break;
    }
    perf_event_header header;
    if (!Read(&header, sizeof(header))) {
      return nullptr;
    }
    pos.pos += header.size;
    if (header.type == PERF_RECORD_COMPRESSED) {
      if (!decompressor_) {
        decompressor_ = CreateZstdDecompressor();
        if (!decompressor_) {
          return nullptr;
        }
      }
      std::vector<char> buf(header.size - sizeof(header));
      if (!Read(buf.data(), buf.size())) {
        return nullptr;
      }
      if (!decompressor_->AddInputData(buf.data(), buf.size())) {
        return nullptr;
      }
    } else {
      std::unique_ptr<char[]> p(new char[header.size]);
      memcpy(p.get(), &header, sizeof(header));
      if (!Read(p.get() + sizeof(header), header.size - sizeof(header))) {
        return nullptr;
      }
      return p;
    }
  }
  return nullptr;
}

bool RecordFileReader::Read(void* buf, size_t len) {
  if (len != 0 && fread(buf, len, 1, record_fp_) != 1) {
    PLOG(ERROR) << "failed to read file " << filename_;
    return false;
  }
  return true;
}

bool RecordFileReader::ReadAtOffset(uint64_t offset, void* buf, size_t len) {
  if (fseek(record_fp_, offset, SEEK_SET) != 0) {
    PLOG(ERROR) << "failed to seek to " << offset;
    return false;
  }
  return Read(buf, len);
}

void RecordFileReader::ProcessEventIdRecord(const EventIdRecord& r) {
  for (size_t i = 0; i < r.count; ++i) {
    const auto& data = r.data[i];
    event_attrs_[data.attr_id].ids.push_back(data.event_id);
    event_id_to_attr_map_[data.event_id] = data.attr_id;
  }
}

size_t RecordFileReader::GetAttrIndexOfRecord(const Record* record) {
  auto it = event_id_to_attr_map_.find(record->Id());
  if (it != event_id_to_attr_map_.end()) {
    return it->second;
  }
  return 0;
}

bool RecordFileReader::ReadFeatureSection(int feature, std::vector<char>* data) {
  const std::map<int, SectionDesc>& section_map = FeatureSectionDescriptors();
  auto it = section_map.find(feature);
  if (it == section_map.end()) {
    return false;
  }
  SectionDesc section = it->second;
  data->resize(section.size);
  if (section.size == 0) {
    return true;
  }
  if (!ReadAtOffset(section.offset, data->data(), data->size())) {
    return false;
  }
  return true;
}

bool RecordFileReader::ReadFeatureSection(int feature, std::string* data) {
  const std::map<int, SectionDesc>& section_map = FeatureSectionDescriptors();
  auto it = section_map.find(feature);
  if (it == section_map.end()) {
    return false;
  }
  SectionDesc section = it->second;
  data->resize(section.size);
  if (section.size == 0) {
    return true;
  }
  if (!ReadAtOffset(section.offset, data->data(), data->size())) {
    return false;
  }
  return true;
}

std::vector<std::string> RecordFileReader::ReadCmdlineFeature() {
  std::vector<char> buf;
  if (!ReadFeatureSection(FEAT_CMDLINE, &buf)) {
    return {};
  }
  BinaryReader reader(buf.data(), buf.size());
  std::vector<std::string> cmdline;

  uint32_t arg_count = 0;
  reader.Read(arg_count);
  for (size_t i = 0; i < arg_count && !reader.error; ++i) {
    uint32_t aligned_len;
    reader.Read(aligned_len);
    cmdline.emplace_back(reader.ReadString());
    uint32_t len = cmdline.back().size() + 1;
    if (aligned_len != Align(len, 64)) {
      reader.error = true;
      break;
    }
    reader.Move(aligned_len - len);
  }
  return reader.error ? std::vector<std::string>() : cmdline;
}

std::vector<BuildIdRecord> RecordFileReader::ReadBuildIdFeature() {
  std::vector<char> buf;
  if (!ReadFeatureSection(FEAT_BUILD_ID, &buf)) {
    return {};
  }
  const char* p = buf.data();
  const char* end = buf.data() + buf.size();
  std::vector<BuildIdRecord> result;
  while (p + sizeof(perf_event_header) < end) {
    auto header = reinterpret_cast<const perf_event_header*>(p);
    if ((header->size <= sizeof(perf_event_header)) || (header->size > end - p)) {
      return {};
    }
    std::unique_ptr<char[]> binary(new char[header->size]);
    memcpy(binary.get(), p, header->size);
    p += header->size;
    BuildIdRecord record;
    if (!record.Parse(event_attrs_[0].attr, binary.get(), binary.get() + header->size)) {
      return {};
    }
    binary.release();
    record.OwnBinary();
    // Set type explicitly as the perf.data produced by perf doesn't set it.
    record.SetTypeAndMisc(PERF_RECORD_BUILD_ID, record.misc());
    result.push_back(std::move(record));
  }
  return result;
}

std::string RecordFileReader::ReadFeatureString(int feature) {
  std::vector<char> buf;
  if (!ReadFeatureSection(feature, &buf)) {
    return std::string();
  }
  BinaryReader reader(buf.data(), buf.size());
  uint32_t len = 0;
  reader.Read(len);
  std::string s = reader.ReadString();
  return reader.error ? "" : s;
}

std::vector<uint64_t> RecordFileReader::ReadAuxTraceFeature() {
  std::vector<char> buf;
  if (!ReadFeatureSection(FEAT_AUXTRACE, &buf)) {
    return {};
  }
  BinaryReader reader(buf.data(), buf.size());
  if (reader.LeftSize() % sizeof(uint64_t) != 0) {
    return {};
  }
  if (reader.LeftSize() / sizeof(uint64_t) % 2 == 1) {
    // Recording files generated by linux perf contain an extra uint64 field. Skip it here.
    reader.Move(sizeof(uint64_t));
  }

  std::vector<uint64_t> auxtrace_offset;
  while (!reader.error && reader.LeftSize() > 0u) {
    uint64_t offset;
    uint64_t size;
    reader.Read(offset);
    reader.Read(size);
    auxtrace_offset.push_back(offset);
    if (size != AuxTraceRecord::Size()) {
      reader.error = true;
    }
  }
  return reader.error ? std::vector<uint64_t>() : auxtrace_offset;
}

bool RecordFileReader::ReadFileFeature(uint64_t& read_pos, FileFeature& file, bool& error) {
  file.Clear();
  error = false;

  bool use_v1 = false;
  PerfFileFormat::SectionDesc desc;
  if (auto it = feature_section_descriptors_.find(FEAT_FILE);
      it != feature_section_descriptors_.end()) {
    use_v1 = true;
    desc = it->second;
  } else if (auto it = feature_section_descriptors_.find(FEAT_FILE2);
             it != feature_section_descriptors_.end()) {
    desc = it->second;
  } else {
    return false;
  }

  if (read_pos >= desc.size) {
    return false;
  }
  if (read_pos == 0) {
    if (fseek(record_fp_, desc.offset, SEEK_SET) != 0) {
      PLOG(ERROR) << "fseek() failed";
      error = true;
      return false;
    }
  }

  bool result = false;
  if (use_v1) {
    result = ReadFileV1Feature(read_pos, desc.size - read_pos, file);
  } else {
    result = ReadFileV2Feature(read_pos, desc.size - read_pos, file);
  }
  if (!result) {
    LOG(ERROR) << "failed to read file feature section";
    error = true;
  }
  return result;
}

bool RecordFileReader::ReadFileV1Feature(uint64_t& read_pos, uint64_t max_size, FileFeature& file) {
  uint32_t size = 0;
  if (max_size < 4 || !Read(&size, 4) || max_size - 4 < size) {
    return false;
  }
  read_pos += 4;
  std::vector<char> buf(size);
  if (!Read(buf.data(), size)) {
    return false;
  }
  read_pos += size;
  BinaryReader reader(buf.data(), buf.size());
  file.path = reader.ReadString();
  uint32_t file_type = 0;
  reader.Read(file_type);
  if (file_type > DSO_UNKNOWN_FILE) {
    LOG(ERROR) << "unknown file type for " << file.path
               << " in file feature section: " << file_type;
    return false;
  }
  file.type = static_cast<DsoType>(file_type);
  reader.Read(file.min_vaddr);
  uint32_t symbol_count = 0;
  reader.Read(symbol_count);
  if (symbol_count > size) {
    return false;
  }
  file.symbols.reserve(symbol_count);
  while (symbol_count-- > 0) {
    uint64_t start_vaddr = 0;
    uint32_t len = 0;
    reader.Read(start_vaddr);
    reader.Read(len);
    std::string name = reader.ReadString();
    file.symbols.emplace_back(name, start_vaddr, len);
  }
  if (file.type == DSO_DEX_FILE) {
    uint32_t offset_count = 0;
    reader.Read(offset_count);
    if (offset_count > size) {
      return false;
    }
    file.dex_file_offsets.resize(offset_count);
    reader.Read(file.dex_file_offsets.data(), offset_count);
  }
  file.file_offset_of_min_vaddr = std::numeric_limits<uint64_t>::max();
  if ((file.type == DSO_ELF_FILE || file.type == DSO_KERNEL_MODULE) && !reader.error &&
      reader.LeftSize() > 0) {
    reader.Read(file.file_offset_of_min_vaddr);
  }
  return !reader.error && reader.LeftSize() == 0;
}

bool RecordFileReader::ReadFileV2Feature(uint64_t& read_pos, uint64_t max_size, FileFeature& file) {
  uint32_t size;
  if (max_size < 4 || !Read(&size, 4) || max_size - 4 < size) {
    return false;
  }
  read_pos += 4;
  std::string s(size, '\0');
  if (!Read(s.data(), size)) {
    return false;
  }
  read_pos += size;
  proto::FileFeature proto_file;
  if (!proto_file.ParseFromString(s)) {
    return false;
  }
  file.path = proto_file.path();
  file.type = static_cast<DsoType>(proto_file.type());
  file.min_vaddr = proto_file.min_vaddr();
  file.symbols.reserve(proto_file.symbol_size());
  for (size_t i = 0; i < proto_file.symbol_size(); i++) {
    const auto& proto_symbol = proto_file.symbol(i);
    file.symbols.emplace_back(proto_symbol.name(), proto_symbol.vaddr(), proto_symbol.len());
  }
  if (file.type == DSO_DEX_FILE) {
    if (!proto_file.has_dex_file()) {
      return false;
    }
    const auto& dex_file_offsets = proto_file.dex_file().dex_file_offset();
    file.dex_file_offsets.insert(file.dex_file_offsets.end(), dex_file_offsets.begin(),
                                 dex_file_offsets.end());
  } else if (file.type == DSO_ELF_FILE) {
    if (!proto_file.has_elf_file()) {
      return false;
    }
    file.file_offset_of_min_vaddr = proto_file.elf_file().file_offset_of_min_vaddr();
  } else if (file.type == DSO_KERNEL_MODULE) {
    if (!proto_file.has_kernel_module()) {
      return false;
    }
    file.file_offset_of_min_vaddr = proto_file.kernel_module().memory_offset_of_min_vaddr();
  }
  return true;
}

bool RecordFileReader::ReadMetaInfoFeature() {
  if (feature_section_descriptors_.count(FEAT_META_INFO)) {
    std::vector<char> buf;
    if (!ReadFeatureSection(FEAT_META_INFO, &buf)) {
      return false;
    }
    std::string_view s(buf.data(), buf.size());
    size_t key_start = 0;
    while (key_start < s.size()) {
      // Parse a C-string for key.
      size_t key_end = s.find('\0', key_start);
      if (key_end == key_start || key_end == s.npos) {
        LOG(ERROR) << "invalid meta info in " << filename_;
        return false;
      }
      // Parse a C-string for value.
      size_t value_start = key_end + 1;
      size_t value_end = s.find('\0', value_start);
      if (value_end == value_start || value_end == s.npos) {
        LOG(ERROR) << "invalid meta info in " << filename_;
        return false;
      }
      meta_info_[&s[key_start]] = &s[value_start];
      key_start = value_end + 1;
    }
  }
  return true;
}

std::string RecordFileReader::GetClockId() {
  if (auto it = meta_info_.find("clockid"); it != meta_info_.end()) {
    return it->second;
  }
  return "perf";
}

std::optional<DebugUnwindFeature> RecordFileReader::ReadDebugUnwindFeature() {
  if (feature_section_descriptors_.count(FEAT_DEBUG_UNWIND)) {
    std::string s;
    if (!ReadFeatureSection(FEAT_DEBUG_UNWIND, &s)) {
      return std::nullopt;
    }
    proto::DebugUnwindFeature proto_debug_unwind;
    proto_debug_unwind.ParseFromString(s);
    DebugUnwindFeature debug_unwind(proto_debug_unwind.file_size());
    for (size_t i = 0; i < proto_debug_unwind.file_size(); i++) {
      debug_unwind[i].path = proto_debug_unwind.file(i).path();
      debug_unwind[i].size = proto_debug_unwind.file(i).size();
    }
    return debug_unwind;
  }
  return std::nullopt;
}

bool RecordFileReader::ReadInitMapFeature(
    const std::function<bool(std::unique_ptr<Record>)>& callback) {
  auto it = feature_section_descriptors_.find(FEAT_INIT_MAP);
  if (it == feature_section_descriptors_.end()) {
    return false;
  }
  if (fseek(record_fp_, it->second.offset, SEEK_SET) != 0) {
    PLOG(ERROR) << "fseek() failed";
    return false;
  }
  ReadPos pos = {0, it->second.size};
  while (pos.pos < pos.end || (decompressor_ && decompressor_->HasOutputData())) {
    auto r = ReadRecord(pos);
    if (!r) {
      return false;
    }
    if (!callback(std::move(r))) {
      return false;
    }
  }
  return true;
}

bool RecordFileReader::LoadBuildIdAndFileFeatures(ThreadTree& thread_tree) {
  std::vector<BuildIdRecord> records = ReadBuildIdFeature();
  std::vector<std::pair<std::string, BuildId>> build_ids;
  for (auto& r : records) {
    build_ids.push_back(std::make_pair(r.filename, r.build_id));
  }
  Dso::SetBuildIds(build_ids);

  FileFeature file_feature;
  uint64_t read_pos = 0;
  bool error = false;
  while (ReadFileFeature(read_pos, file_feature, error)) {
    if (!thread_tree.AddDsoInfo(file_feature)) {
      return false;
    }
  }
  return !error;
}

bool RecordFileReader::ReadAuxData(uint32_t cpu, uint64_t aux_offset, size_t size,
                                   std::vector<uint8_t>& buf, bool& error) {
  error = false;
  long saved_pos = ftell(record_fp_);
  if (saved_pos == -1) {
    PLOG(ERROR) << "ftell() failed";
    error = true;
    return false;
  }
  android::base::ScopeGuard guard([&]() { fseek(record_fp_, saved_pos, SEEK_SET); });

  OverflowResult aux_end = SafeAdd(aux_offset, size);
  if (aux_end.overflow) {
    LOG(ERROR) << "aux_end overflow";
    error = true;
    return false;
  }
  if (aux_data_location_.empty() && !BuildAuxDataLocation()) {
    error = true;
    return false;
  }
  AuxDataLocation* location = nullptr;
  auto it = aux_data_location_.find(cpu);
  if (it != aux_data_location_.end()) {
    auto comp = [](uint64_t aux_offset, const AuxDataLocation& location) {
      return aux_offset < location.aux_offset;
    };
    auto location_it = std::upper_bound(it->second.begin(), it->second.end(), aux_offset, comp);
    if (location_it != it->second.begin()) {
      --location_it;
      location = &*location_it;
    }
  }
  if (location == nullptr) {
    // ETM data can be dropped when recording if the userspace buffer is full. This isn't an error.
    LOG(INFO) << "aux data is missing: cpu " << cpu << ", aux_offset " << aux_offset << ", size "
              << size << ". Probably the data is lost when recording.";
    return false;
  }
  if (decompressor_) {
    return ReadAuxDataFromDecompressor(cpu, aux_offset, size, buf, *location, error);
  }
  if (buf.size() < size) {
    buf.resize(size);
  }
  if (!ReadAtOffset(aux_offset - location->aux_offset + location->file_offset, buf.data(), size)) {
    error = true;
    return false;
  }
  return true;
}

bool RecordFileReader::BuildAuxDataLocation() {
  std::vector<uint64_t> auxtrace_offset = ReadAuxTraceFeature();
  std::unique_ptr<char[]> buf(new char[AuxTraceRecord::Size()]);
  for (auto offset : auxtrace_offset) {
    if (!ReadAtOffset(offset, buf.get(), AuxTraceRecord::Size())) {
      return false;
    }
    AuxTraceRecord auxtrace;
    if (!auxtrace.Parse(event_attrs_[0].attr, buf.get(), buf.get() + AuxTraceRecord::Size())) {
      return false;
    }
    AuxDataLocation location(auxtrace.data->offset, auxtrace.data->aux_size,
                             offset + auxtrace.size());
    OverflowResult aux_end = SafeAdd(location.aux_offset, location.aux_size);
    OverflowResult file_end = SafeAdd(location.file_offset, location.aux_size);
    if (aux_end.overflow || file_end.overflow || file_end.value > file_size_) {
      LOG(ERROR) << "invalid auxtrace feature section";
      return false;
    }
    auto location_it = aux_data_location_.find(auxtrace.data->cpu);
    if (location_it != aux_data_location_.end()) {
      const AuxDataLocation& prev_location = location_it->second.back();
      // The AuxTraceRecords should be sorted by aux_offset for each cpu.
      if (prev_location.aux_offset > location.aux_offset) {
        LOG(ERROR) << "invalid auxtrace feature section";
        return false;
      }
      location_it->second.emplace_back(location);
    } else {
      aux_data_location_[auxtrace.data->cpu].emplace_back(location);
    }
  }
  return true;
}

bool RecordFileReader::ReadAuxDataFromDecompressor(uint32_t cpu, uint64_t aux_offset, size_t size,
                                                   std::vector<uint8_t>& buf,
                                                   const AuxDataLocation& location, bool& error) {
  if (!auxdata_decompressor_) {
    auxdata_decompressor_.reset(new AuxDataDecompressor);
    auxdata_decompressor_->decompressor = CreateZstdDecompressor();
    if (!auxdata_decompressor_->decompressor) {
      error = true;
      return false;
    }
  }
  if (auxdata_decompressor_->cpu != cpu || auxdata_decompressor_->location != location) {
    auxdata_decompressor_->cpu = cpu;
    auxdata_decompressor_->location = location;
    Decompressor& decompressor = *auxdata_decompressor_->decompressor;
    // Read and decompress new aux data.
    std::string_view output = decompressor.GetOutputData();
    if (!output.empty()) {
      decompressor.ConsumeOutputData(output.size());
    }
    std::vector<char> input(location.aux_size);
    if (!ReadAtOffset(location.file_offset, input.data(), input.size()) ||
        !decompressor.AddInputData(input.data(), input.size())) {
      error = true;
      return false;
    }
  }
  std::string_view data = auxdata_decompressor_->decompressor->GetOutputData();
  if (location.aux_offset + data.size() < aux_offset + size) {
    // ETM data can be dropped when recording if the userspace buffer is full. This isn't an
    // error.
    LOG(INFO) << "aux data is missing: cpu " << cpu << ", aux_offset " << aux_offset << ", size "
              << size << ". Probably the data is lost when recording.";
    return false;
  }
  if (buf.size() < size) {
    buf.resize(size);
  }
  memcpy(buf.data(), &data[aux_offset - location.aux_offset], size);
  return true;
}

std::vector<std::unique_ptr<Record>> RecordFileReader::DataSection() {
  std::vector<std::unique_ptr<Record>> records;
  ReadDataSection([&](std::unique_ptr<Record> record) {
    records.push_back(std::move(record));
    return true;
  });
  return records;
}

bool IsPerfDataFile(const std::string& filename) {
  auto fd = FileHelper::OpenReadOnly(filename);
  if (fd.ok()) {
    PerfFileFormat::FileHeader header;
    return android::base::ReadFully(fd, &header, sizeof(header)) &&
           memcmp(header.magic, PERF_MAGIC, sizeof(header.magic)) == 0;
  }
  return false;
}

}  // namespace simpleperf
