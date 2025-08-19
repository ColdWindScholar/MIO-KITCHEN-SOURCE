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

#ifndef SIMPLE_PERF_RECORD_FILE_H_
#define SIMPLE_PERF_RECORD_FILE_H_

#include <stdio.h>

#include <functional>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

#include <android-base/macros.h>

#include "ZstdUtil.h"
#include "dso.h"
#include "event_attr.h"
#include "event_type.h"
#include "perf_event.h"
#include "record.h"
#include "record_file_format.h"
#include "thread_tree.h"

namespace simpleperf {

struct FileFeature {
  std::string path;
  DsoType type;
  uint64_t min_vaddr;
  uint64_t file_offset_of_min_vaddr;       // for DSO_ELF_FILE or DSO_KERNEL_MODULE
  std::vector<Symbol> symbols;             // used for reading symbols
  std::vector<const Symbol*> symbol_ptrs;  // used for writing symbols
  std::vector<uint64_t> dex_file_offsets;

  FileFeature() {}

  void Clear() {
    path.clear();
    type = DSO_UNKNOWN_FILE;
    min_vaddr = 0;
    file_offset_of_min_vaddr = 0;
    symbols.clear();
    symbol_ptrs.clear();
    dex_file_offsets.clear();
  }

  DISALLOW_COPY_AND_ASSIGN(FileFeature);
};

struct DebugUnwindFile {
  std::string path;
  uint64_t size;
};

using DebugUnwindFeature = std::vector<DebugUnwindFile>;

// RecordFileWriter writes to a perf record file, like perf.data.
// User should call RecordFileWriter::Close() to finish writing the file, otherwise the file will
// be removed in RecordFileWriter::~RecordFileWriter().
class RecordFileWriter {
 public:
  static std::unique_ptr<RecordFileWriter> CreateInstance(const std::string& filename);

  // If own_fp = true, close fp when we finish writing.
  RecordFileWriter(const std::string& filename, FILE* fp, bool own_fp);
  ~RecordFileWriter();

  bool SetCompressionLevel(size_t compression_level);
  bool WriteAttrSection(const EventAttrIds& attr_ids);
  bool WriteRecord(const Record& record);
  bool FinishWritingDataSection();

  uint64_t GetDataSectionSize() const { return data_section_size_; }
  bool ReadDataSection(const std::function<void(const Record*)>& callback);
  const std::vector<uint64_t>& AuxTraceRecordOffsets() const { return auxtrace_record_offsets_; }

  bool BeginWriteFeatures(size_t feature_count);
  bool WriteBuildIdFeature(const std::vector<BuildIdRecord>& build_id_records);
  bool WriteFeatureString(int feature, const std::string& s);
  bool WriteCmdlineFeature(const std::vector<std::string>& cmdline);
  bool WriteBranchStackFeature();
  bool WriteAuxTraceFeature(const std::vector<uint64_t>& auxtrace_offset);
  bool WriteFileFeatures(const std::vector<Dso*>& dsos);
  bool WriteFileFeature(const FileFeature& file);
  bool WriteMetaInfoFeature(const std::unordered_map<std::string, std::string>& info_map);
  bool WriteDebugUnwindFeature(const DebugUnwindFeature& debug_unwind);
  bool WriteInitMapFeature(const char* data, size_t size);
  bool FinishWritingInitMapFeature();
  bool WriteFeature(int feature, const char* data, size_t size);
  bool EndWriteFeatures();

  bool Close();
  Compressor* GetCompressor() { return compressor_.get(); }

 private:
  void GetHitModulesInBuffer(const char* p, const char* end,
                             std::vector<std::string>* hit_kernel_modules,
                             std::vector<std::string>* hit_user_files);
  bool WriteFileHeader();
  bool WriteAuxTraceRecord(const AuxTraceRecord& r);
  // If flush=true, the previous data can be decompressed without any following data.
  bool WriteCompressorOutput(bool flush, bool data_section);
  bool WriteCompressRecord(const char* data, size_t size, bool data_section);
  bool WriteData(const void* buf, size_t len);
  bool Write(const void* buf, size_t len);
  bool ReadFromDecompressor(Decompressor& decompressor,
                            const std::function<void(const Record*)>& callback);
  bool Read(void* buf, size_t len);
  bool GetFilePos(uint64_t* file_pos);
  bool WriteStringWithLength(const std::string& s);
  bool WriteFeatureBegin(int feature);
  bool WriteFeatureEnd(int feature);

  const std::string filename_;
  FILE* record_fp_;
  bool own_fp_;

  perf_event_attr event_attr_;
  uint64_t attr_section_offset_;
  uint64_t attr_section_size_;
  uint64_t data_section_offset_;
  uint64_t data_section_size_;
  uint64_t feature_section_offset_;

  std::map<int, PerfFileFormat::SectionDesc> features_;
  size_t feature_count_;

  std::unique_ptr<Compressor> compressor_;
  std::vector<uint64_t> auxtrace_record_offsets_;

  DISALLOW_COPY_AND_ASSIGN(RecordFileWriter);
};

// RecordFileReader read contents from a perf record file, like perf.data.
class RecordFileReader {
 public:
  static std::unique_ptr<RecordFileReader> CreateInstance(const std::string& filename);

  ~RecordFileReader();

  const std::string FileName() const { return filename_; }
  const PerfFileFormat::FileHeader& FileHeader() const { return header_; }

  const EventAttrIds& AttrSection() const { return event_attrs_; }

  const std::unordered_map<uint64_t, size_t>& EventIdMap() const { return event_id_to_attr_map_; }

  const std::map<int, PerfFileFormat::SectionDesc>& FeatureSectionDescriptors() const {
    return feature_section_descriptors_;
  }
  bool HasFeature(int feature) const {
    return feature_section_descriptors_.find(feature) != feature_section_descriptors_.end();
  }
  bool ReadFeatureSection(int feature, std::vector<char>* data);
  bool ReadFeatureSection(int feature, std::string* data);

  // There are two ways to read records in data section: one is by calling
  // ReadDataSection(), and [callback] is called for each Record. the other
  // is by calling ReadRecord() in a loop.

  // If sorted is true, sort records before passing them to callback function.
  bool ReadDataSection(const std::function<bool(std::unique_ptr<Record>)>& callback);
  bool ReadAtOffset(uint64_t offset, void* buf, size_t len);

  // Read next record. If read successfully, set [record] and return true.
  // If there is no more records, set [record] to nullptr and return true.
  // Otherwise return false.
  bool ReadRecord(std::unique_ptr<Record>& record);

  size_t GetAttrIndexOfRecord(const Record* record);

  std::vector<std::string> ReadCmdlineFeature();
  std::vector<BuildIdRecord> ReadBuildIdFeature();
  std::string ReadFeatureString(int feature);
  std::vector<uint64_t> ReadAuxTraceFeature();

  // File feature section contains many file information. This function reads
  // one file information located at [read_pos]. [read_pos] is 0 at the first
  // call, and is updated to point to the next file information.
  // When read successfully, return true and set error to false.
  // When no more data to read, return false and set error to false.
  // When having error, return false and set error to true.
  bool ReadFileFeature(uint64_t& read_pos, FileFeature& file, bool& error);

  const std::unordered_map<std::string, std::string>& GetMetaInfoFeature() { return meta_info_; }
  std::string GetClockId();
  std::optional<DebugUnwindFeature> ReadDebugUnwindFeature();
  bool ReadInitMapFeature(const std::function<bool(std::unique_ptr<Record>)>& callback);

  bool LoadBuildIdAndFileFeatures(ThreadTree& thread_tree);

  // Read aux data into buf.
  // When read successfully, return true and set error to false.
  // When the data isn't available, return false and set error to false.
  // When having error, return false and set error to true.
  bool ReadAuxData(uint32_t cpu, uint64_t aux_offset, size_t size, std::vector<uint8_t>& buf,
                   bool& error);

  bool Close();

  // For testing only.
  std::vector<std::unique_ptr<Record>> DataSection();

 private:
  struct ReadPos {
    uint64_t pos = 0;
    uint64_t end = 0;
  };

  struct AuxDataLocation {
    uint64_t aux_offset;
    uint64_t aux_size;
    uint64_t file_offset;

    AuxDataLocation(uint64_t aux_offset = 0, uint64_t aux_size = 0, uint64_t file_offset = 0)
        : aux_offset(aux_offset), aux_size(aux_size), file_offset(file_offset) {}

    bool operator!=(const AuxDataLocation& other) const {
      return aux_offset != other.aux_offset || aux_size != other.aux_size ||
             file_offset != other.file_offset;
    }
  };

  RecordFileReader(const std::string& filename, FILE* fp);
  bool ReadHeader();
  bool CheckSectionDesc(const PerfFileFormat::SectionDesc& desc, uint64_t min_offset,
                        uint64_t alignment = 1);
  bool ReadAttrSection();
  bool ReadIdSection(const PerfFileFormat::SectionDesc& section, std::vector<uint64_t>* ids);
  bool ReadFeatureSectionDescriptors();
  bool ReadFileV1Feature(uint64_t& read_pos, uint64_t max_size, FileFeature& file);
  bool ReadFileV2Feature(uint64_t& read_pos, uint64_t max_size, FileFeature& file);
  bool ReadMetaInfoFeature();
  void UseRecordingEnvironment();
  std::unique_ptr<Record> ReadRecord(ReadPos& pos);
  std::unique_ptr<char[]> ReadRecordWithDecompression(ReadPos& pos);
  bool Read(void* buf, size_t len);
  void ProcessEventIdRecord(const EventIdRecord& r);
  bool BuildAuxDataLocation();
  bool ReadAuxDataFromDecompressor(uint32_t cpu, uint64_t aux_offset, size_t size,
                                   std::vector<uint8_t>& buf, const AuxDataLocation& location,
                                   bool& error);

  const std::string filename_;
  FILE* record_fp_;
  uint64_t file_size_;

  PerfFileFormat::FileHeader header_;
  EventAttrIds event_attrs_;
  std::unordered_map<uint64_t, size_t> event_id_to_attr_map_;
  std::map<int, PerfFileFormat::SectionDesc> feature_section_descriptors_;

  size_t event_id_pos_in_sample_records_;
  size_t event_id_reverse_pos_in_non_sample_records_;

  ReadPos read_record_pos_;

  std::unordered_map<std::string, std::string> meta_info_;
  std::unique_ptr<ScopedCurrentArch> scoped_arch_;
  std::unique_ptr<ScopedEventTypes> scoped_event_types_;

  // It maps from a cpu id to the locations (file offsets in perf.data) of aux data received from
  // that cpu's aux buffer. It is used to locate aux data in perf.data.
  std::unordered_map<uint32_t, std::vector<AuxDataLocation>> aux_data_location_;
  std::unique_ptr<Decompressor> decompressor_;

  struct AuxDataDecompressor {
    uint32_t cpu = 0;
    AuxDataLocation location;
    std::unique_ptr<Decompressor> decompressor;
  };
  std::unique_ptr<AuxDataDecompressor> auxdata_decompressor_;

  DISALLOW_COPY_AND_ASSIGN(RecordFileReader);
};

bool IsPerfDataFile(const std::string& filename);

}  // namespace simpleperf

#endif  // SIMPLE_PERF_RECORD_FILE_H_
