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

#include <stdio.h>

#include <algorithm>
#include <memory>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/parseint.h>
#include <android-base/stringprintf.h>
#include <android-base/strings.h>

#include "JITDebugReader.h"
#include "OfflineUnwinder.h"
#include "command.h"
#include "environment.h"
#include "perf_regs.h"
#include "record_file.h"
#include "report_utils.h"
#include "thread_tree.h"
#include "utils.h"

namespace simpleperf {
namespace {

struct MemStat {
  std::string vm_peak;
  std::string vm_size;
  std::string vm_hwm;
  std::string vm_rss;

  std::string ToString() const {
    return android::base::StringPrintf("VmPeak:%s;VmSize:%s;VmHWM:%s;VmRSS:%s", vm_peak.c_str(),
                                       vm_size.c_str(), vm_hwm.c_str(), vm_rss.c_str());
  }
};

static bool GetMemStat(MemStat* stat) {
  std::string s;
  if (!android::base::ReadFileToString(android::base::StringPrintf("/proc/%d/status", getpid()),
                                       &s)) {
    PLOG(ERROR) << "Failed to read process status";
    return false;
  }
  std::vector<std::string> lines = android::base::Split(s, "\n");
  for (auto& line : lines) {
    if (android::base::StartsWith(line, "VmPeak:")) {
      stat->vm_peak = android::base::Trim(line.substr(strlen("VmPeak:")));
    } else if (android::base::StartsWith(line, "VmSize:")) {
      stat->vm_size = android::base::Trim(line.substr(strlen("VmSize:")));
    } else if (android::base::StartsWith(line, "VmHWM:")) {
      stat->vm_hwm = android::base::Trim(line.substr(strlen("VmHWM:")));
    } else if (android::base::StartsWith(line, "VmRSS:")) {
      stat->vm_rss = android::base::Trim(line.substr(strlen("VmRSS:")));
    }
  }
  return true;
}

struct UnwindingStat {
  // For testing unwinding performance
  uint64_t unwinding_sample_count = 0u;
  uint64_t total_unwinding_time_in_ns = 0u;
  uint64_t max_unwinding_time_in_ns = 0u;

  // For memory consumption
  MemStat mem_before_unwinding;
  MemStat mem_after_unwinding;

  void AddUnwindingResult(const UnwindingResult& result) {
    unwinding_sample_count++;
    total_unwinding_time_in_ns += result.used_time;
    max_unwinding_time_in_ns = std::max(max_unwinding_time_in_ns, result.used_time);
  }

  void Dump(FILE* fp) {
    if (unwinding_sample_count == 0) {
      return;
    }
    fprintf(fp, "unwinding_sample_count: %" PRIu64 "\n", unwinding_sample_count);
    fprintf(fp, "average_unwinding_time: %.3f us\n",
            total_unwinding_time_in_ns / 1e3 / unwinding_sample_count);
    fprintf(fp, "max_unwinding_time: %.3f us\n", max_unwinding_time_in_ns / 1e3);

    if (!mem_before_unwinding.vm_peak.empty()) {
      fprintf(fp, "memory_change_VmPeak: %s -> %s\n", mem_before_unwinding.vm_peak.c_str(),
              mem_after_unwinding.vm_peak.c_str());
      fprintf(fp, "memory_change_VmSize: %s -> %s\n", mem_before_unwinding.vm_size.c_str(),
              mem_after_unwinding.vm_size.c_str());
      fprintf(fp, "memory_change_VmHwM: %s -> %s\n", mem_before_unwinding.vm_hwm.c_str(),
              mem_after_unwinding.vm_hwm.c_str());
      fprintf(fp, "memory_change_VmRSS: %s -> %s\n", mem_before_unwinding.vm_rss.c_str(),
              mem_after_unwinding.vm_rss.c_str());
    }
  }
};

class RecordFileProcessor {
 public:
  RecordFileProcessor(const std::string& output_filename, bool output_binary_mode)
      : output_filename_(output_filename),
        output_binary_mode_(output_binary_mode),
        unwinder_(OfflineUnwinder::Create(true)),
        callchain_report_builder_(thread_tree_) {}

  virtual ~RecordFileProcessor() {
    if (out_fp_ != nullptr && out_fp_ != stdout) {
      fclose(out_fp_);
    }
  }

  bool ProcessFile(const std::string& input_filename) {
    // 1. Check input file.
    record_filename_ = input_filename;
    reader_ = RecordFileReader::CreateInstance(record_filename_);
    if (!reader_) {
      return false;
    }
    std::string record_cmd = android::base::Join(reader_->ReadCmdlineFeature(), " ");
    if (record_cmd.find("-g") == std::string::npos &&
        record_cmd.find("--call-graph dwarf") == std::string::npos) {
      LOG(ERROR) << "file isn't recorded with dwarf call graph: " << record_filename_;
      return false;
    }
    if (!CheckRecordCmd(record_cmd)) {
      return false;
    }

    // 2. Load feature sections.
    if (!reader_->LoadBuildIdAndFileFeatures(thread_tree_)) {
      return false;
    }
    ScopedCurrentArch scoped_arch(
        GetArchType(reader_->ReadFeatureString(PerfFileFormat::FEAT_ARCH)));
    unwinder_->LoadMetaInfo(reader_->GetMetaInfoFeature());
    if (reader_->HasFeature(PerfFileFormat::FEAT_DEBUG_UNWIND) &&
        reader_->HasFeature(PerfFileFormat::FEAT_DEBUG_UNWIND_FILE)) {
      auto debug_unwind_feature = reader_->ReadDebugUnwindFeature();
      if (!debug_unwind_feature.has_value()) {
        return false;
      }
      uint64_t offset =
          reader_->FeatureSectionDescriptors().at(PerfFileFormat::FEAT_DEBUG_UNWIND_FILE).offset;
      for (DebugUnwindFile& file : debug_unwind_feature.value()) {
        auto& loc = debug_unwind_files_[file.path];
        loc.offset = offset;
        loc.size = file.size;
        offset += file.size;
      }
    }
    callchain_report_builder_.SetRemoveArtFrame(false);
    callchain_report_builder_.SetConvertJITFrame(false);

    // 3. Open output file.
    if (output_filename_.empty()) {
      out_fp_ = stdout;
    } else {
      out_fp_ = fopen(output_filename_.c_str(), output_binary_mode_ ? "web+" : "we+");
      if (out_fp_ == nullptr) {
        PLOG(ERROR) << "failed to write to " << output_filename_;
        return false;
      }
    }

    // 4. Process records.
    return Process();
  }

 protected:
  struct DebugUnwindFileLocation {
    uint64_t offset;
    uint64_t size;
  };

  virtual bool CheckRecordCmd(const std::string& record_cmd) = 0;
  virtual bool Process() = 0;

  std::string record_filename_;
  std::unique_ptr<RecordFileReader> reader_;
  std::string output_filename_;
  bool output_binary_mode_;
  FILE* out_fp_ = nullptr;
  ThreadTree thread_tree_;
  std::unique_ptr<OfflineUnwinder> unwinder_;
  // Files stored in DEBUG_UNWIND_FILE feature section in the recording file.
  // Map from file path to offset in the recording file.
  std::unordered_map<std::string, DebugUnwindFileLocation> debug_unwind_files_;
  CallChainReportBuilder callchain_report_builder_;
};

static void DumpUnwindingResult(const UnwindingResult& result, FILE* fp) {
  fprintf(fp, "unwinding_used_time: %.3f us\n", result.used_time / 1e3);
  fprintf(fp, "unwinding_error_code: %" PRIu64 "\n", result.error_code);
  fprintf(fp, "unwinding_error_addr: 0x%" PRIx64 "\n", result.error_addr);
  fprintf(fp, "stack_start: 0x%" PRIx64 "\n", result.stack_start);
  fprintf(fp, "stack_end: 0x%" PRIx64 "\n", result.stack_end);
}

class SampleUnwinder : public RecordFileProcessor {
 public:
  SampleUnwinder(const std::string& output_filename,
                 const std::unordered_set<uint64_t>& sample_times, bool skip_sample_print)
      : RecordFileProcessor(output_filename, false),
        sample_times_(sample_times),
        skip_sample_print_(skip_sample_print) {}

 protected:
  bool CheckRecordCmd(const std::string& record_cmd) override {
    if (record_cmd.find("--no-unwind") == std::string::npos &&
        record_cmd.find("--keep-failed-unwinding-debug-info") == std::string::npos) {
      LOG(ERROR) << "file isn't record with --no-unwind or --keep-failed-unwinding-debug-info: "
                 << record_filename_;
      return false;
    }
    return true;
  }

  bool Process() override {
    if (!GetMemStat(&stat_.mem_before_unwinding)) {
      return false;
    }
    if (!reader_->ReadDataSection(
            [&](std::unique_ptr<Record> r) { return ProcessRecord(std::move(r)); })) {
      return false;
    }
    if (!GetMemStat(&stat_.mem_after_unwinding)) {
      return false;
    }
    stat_.Dump(out_fp_);
    return true;
  }

  bool ProcessRecord(std::unique_ptr<Record> r) {
    UpdateRecord(r.get());
    thread_tree_.Update(*r);
    if (r->type() == SIMPLE_PERF_RECORD_UNWINDING_RESULT) {
      last_unwinding_result_.reset(static_cast<UnwindingResultRecord*>(r.release()));
    } else if (r->type() == PERF_RECORD_SAMPLE) {
      if (sample_times_.empty() || sample_times_.count(r->Timestamp())) {
        auto& sr = *static_cast<SampleRecord*>(r.get());
        const PerfSampleStackUserType* stack = &sr.stack_user_data;
        const PerfSampleRegsUserType* regs = &sr.regs_user_data;
        if (last_unwinding_result_ && last_unwinding_result_->Timestamp() == sr.Timestamp()) {
          stack = &last_unwinding_result_->stack_user_data;
          regs = &last_unwinding_result_->regs_user_data;
        }
        if (stack->size > 0 || regs->reg_mask > 0) {
          if (!UnwindRecord(sr, *regs, *stack)) {
            return false;
          }
        }
      }
      last_unwinding_result_.reset();
    }
    return true;
  }

  void UpdateRecord(Record* record) {
    if (record->type() == PERF_RECORD_MMAP) {
      UpdateMmapRecordForEmbeddedFiles(*static_cast<MmapRecord*>(record));
    } else if (record->type() == PERF_RECORD_MMAP2) {
      UpdateMmapRecordForEmbeddedFiles(*static_cast<Mmap2Record*>(record));
    }
  }

  template <typename MmapRecordType>
  void UpdateMmapRecordForEmbeddedFiles(MmapRecordType& record) {
    // Modify mmap records to point to files stored in DEBUG_UNWIND_FILE feature section.
    std::string filename = record.filename;
    if (auto it = debug_unwind_files_.find(filename); it != debug_unwind_files_.end()) {
      auto data = *record.data;
      uint64_t old_pgoff = data.pgoff;
      if (JITDebugReader::IsPathInJITSymFile(filename)) {
        data.pgoff = it->second.offset;
      } else {
        data.pgoff += it->second.offset;
      }
      debug_unwind_dsos_[data.pgoff] =
          std::make_pair(thread_tree_.FindUserDsoOrNew(filename), old_pgoff);
      record.SetDataAndFilename(data, record_filename_);
    }
  }

  bool UnwindRecord(const SampleRecord& r, const PerfSampleRegsUserType& regs,
                    const PerfSampleStackUserType& stack) {
    ThreadEntry* thread = thread_tree_.FindThreadOrNew(r.tid_data.pid, r.tid_data.tid);

    RegSet reg_set(regs.abi, regs.reg_mask, regs.regs);
    std::vector<uint64_t> ips;
    std::vector<uint64_t> sps;
    if (!unwinder_->UnwindCallChain(*thread, reg_set, stack.data, stack.size, &ips, &sps)) {
      return false;
    }
    stat_.AddUnwindingResult(unwinder_->GetUnwindingResult());

    if (!skip_sample_print_) {
      // Print unwinding result.
      fprintf(out_fp_, "sample_time: %" PRIu64 "\n", r.Timestamp());
      DumpUnwindingResult(unwinder_->GetUnwindingResult(), out_fp_);
      std::vector<CallChainReportEntry> entries = callchain_report_builder_.Build(thread, ips, 0);
      for (size_t i = 0; i < entries.size(); i++) {
        size_t id = i + 1;
        auto& entry = entries[i];
        fprintf(out_fp_, "ip_%zu: 0x%" PRIx64 "\n", id, entry.ip);
        fprintf(out_fp_, "sp_%zu: 0x%" PRIx64 "\n", id, sps[i]);

        Dso* dso = entry.map->dso;
        uint64_t pgoff = entry.map->pgoff;
        if (dso->Path() == record_filename_) {
          auto it = debug_unwind_dsos_.find(entry.map->pgoff);
          CHECK(it != debug_unwind_dsos_.end());
          const auto& p = it->second;
          dso = p.first;
          pgoff = p.second;
          if (!JITDebugReader::IsPathInJITSymFile(dso->Path())) {
            entry.vaddr_in_file = dso->IpToVaddrInFile(entry.ip, entry.map->start_addr, pgoff);
          }
          entry.symbol = dso->FindSymbol(entry.vaddr_in_file);
        }
        fprintf(out_fp_, "map_%zu: [0x%" PRIx64 "-0x%" PRIx64 "], pgoff 0x%" PRIx64 "\n", id,
                entry.map->start_addr, entry.map->get_end_addr(), pgoff);
        fprintf(out_fp_, "dso_%zu: %s\n", id, dso->Path().c_str());
        fprintf(out_fp_, "vaddr_in_file_%zu: 0x%" PRIx64 "\n", id, entry.vaddr_in_file);
        fprintf(out_fp_, "symbol_%zu: %s\n", id, entry.symbol->DemangledName());
      }
      fprintf(out_fp_, "\n");
    }
    return true;
  }

 private:
  const std::unordered_set<uint64_t> sample_times_;
  bool skip_sample_print_;
  // Map from offset in recording file to the corresponding debug_unwind_file.
  std::unordered_map<uint64_t, std::pair<Dso*, uint64_t>> debug_unwind_dsos_;
  UnwindingStat stat_;
  std::unique_ptr<UnwindingResultRecord> last_unwinding_result_;
};

class TestFileGenerator : public RecordFileProcessor {
 public:
  TestFileGenerator(const std::string& output_filename,
                    const std::unordered_set<uint64_t>& sample_times,
                    const std::unordered_set<std::string>& kept_binaries)
      : RecordFileProcessor(output_filename, true),
        sample_times_(sample_times),
        kept_binaries_(kept_binaries) {}

 protected:
  bool CheckRecordCmd(const std::string&) override { return true; }

  bool Process() override {
    writer_.reset(new RecordFileWriter(output_filename_, out_fp_, false));
    if (!writer_ || !writer_->WriteAttrSection(reader_->AttrSection())) {
      return false;
    }
    if (!reader_->ReadDataSection(
            [&](std::unique_ptr<Record> r) { return ProcessRecord(std::move(r)); })) {
      return false;
    }
    return WriteFeatureSections();
  }

  bool ProcessRecord(std::unique_ptr<Record> r) {
    thread_tree_.Update(*r);
    bool keep_record = false;
    if (r->type() == SIMPLE_PERF_RECORD_UNWINDING_RESULT) {
      keep_record = (sample_times_.count(r->Timestamp()) > 0);
    } else if (r->type() == PERF_RECORD_SAMPLE) {
      keep_record = (sample_times_.count(r->Timestamp()) > 0);
      if (keep_record) {
        // Dump maps needed to unwind this sample.
        if (!WriteMapsForSample(*static_cast<SampleRecord*>(r.get()))) {
          return false;
        }
      }
    }
    if (keep_record) {
      return writer_->WriteRecord(*r);
    }
    return true;
  }

  bool WriteMapsForSample(const SampleRecord& r) {
    ThreadEntry* thread = thread_tree_.FindThread(r.tid_data.tid);
    if (thread != nullptr && thread->maps) {
      const EventAttrIds& attrs = reader_->AttrSection();
      const perf_event_attr& attr = attrs[0].attr;
      uint64_t event_id = attrs[0].ids[0];

      for (const auto& p : thread->maps->maps) {
        const MapEntry* map = p.second;
        Mmap2Record map_record(attr, false, r.tid_data.pid, r.tid_data.tid, map->start_addr,
                               map->len, map->pgoff, map->flags, map->dso->Path(), event_id,
                               r.Timestamp());
        if (!writer_->WriteRecord(map_record)) {
          return false;
        }
      }
    }
    return true;
  }

  bool WriteFeatureSections() {
    if (!writer_->BeginWriteFeatures(reader_->FeatureSectionDescriptors().size())) {
      return false;
    }
    std::unordered_set<int> feature_types_to_copy = {
        PerfFileFormat::FEAT_ARCH, PerfFileFormat::FEAT_CMDLINE, PerfFileFormat::FEAT_META_INFO};
    const size_t BUFFER_SIZE = 64 * kKilobyte;
    std::string buffer(BUFFER_SIZE, '\0');
    for (const auto& p : reader_->FeatureSectionDescriptors()) {
      auto feat_type = p.first;
      if (feat_type == PerfFileFormat::FEAT_DEBUG_UNWIND) {
        DebugUnwindFeature feature;
        buffer.resize(BUFFER_SIZE);
        for (const auto& file_p : debug_unwind_files_) {
          if (kept_binaries_.count(file_p.first)) {
            feature.resize(feature.size() + 1);
            feature.back().path = file_p.first;
            feature.back().size = file_p.second.size;
            if (!CopyDebugUnwindFile(file_p.second, buffer)) {
              return false;
            }
          }
        }
        if (!writer_->WriteDebugUnwindFeature(feature)) {
          return false;
        }
      } else if (feat_type == PerfFileFormat::FEAT_FILE ||
                 feat_type == PerfFileFormat::FEAT_FILE2) {
        uint64_t read_pos = 0;
        FileFeature file_feature;
        bool error = false;
        while (reader_->ReadFileFeature(read_pos, file_feature, error)) {
          if (kept_binaries_.count(file_feature.path) && !writer_->WriteFileFeature(file_feature)) {
            return false;
          }
        }
        if (error) {
          return false;
        }
      } else if (feat_type == PerfFileFormat::FEAT_BUILD_ID) {
        std::vector<BuildIdRecord> build_ids = reader_->ReadBuildIdFeature();
        std::vector<BuildIdRecord> write_build_ids;
        for (auto& build_id : build_ids) {
          if (kept_binaries_.count(build_id.filename)) {
            write_build_ids.emplace_back(std::move(build_id));
          }
        }
        if (!writer_->WriteBuildIdFeature(write_build_ids)) {
          return false;
        }
      } else if (feature_types_to_copy.count(feat_type)) {
        if (!reader_->ReadFeatureSection(feat_type, &buffer) ||
            !writer_->WriteFeature(feat_type, buffer.data(), buffer.size())) {
          return false;
        }
      }
    }
    return writer_->EndWriteFeatures() && writer_->Close();
  }

  bool CopyDebugUnwindFile(const DebugUnwindFileLocation& loc, std::string& buffer) {
    uint64_t offset = loc.offset;
    uint64_t left_size = loc.size;
    while (left_size > 0) {
      size_t nread = std::min<size_t>(left_size, buffer.size());
      if (!reader_->ReadAtOffset(offset, buffer.data(), nread) ||
          !writer_->WriteFeature(PerfFileFormat::FEAT_DEBUG_UNWIND_FILE, buffer.data(), nread)) {
        return false;
      }
      offset += nread;
      left_size -= nread;
    }
    return true;
  }

 private:
  const std::unordered_set<uint64_t> sample_times_;
  const std::unordered_set<std::string> kept_binaries_;
  std::unique_ptr<RecordFileWriter> writer_;
};

class ReportGenerator : public RecordFileProcessor {
 public:
  ReportGenerator(const std::string& output_filename)
      : RecordFileProcessor(output_filename, false) {}

 protected:
  bool CheckRecordCmd(const std::string& record_cmd) override {
    if (record_cmd.find("--keep-failed-unwinding-debug-info") == std::string::npos &&
        record_cmd.find("--keep-failed-unwinding-result") == std::string::npos) {
      LOG(ERROR) << "file isn't record with --keep-failed-unwinding-debug-info or "
                 << "--keep-failed-unwinding-result: " << record_filename_;
      return false;
    }
    return true;
  }

  bool Process() override {
    if (!reader_->ReadDataSection(
            [&](std::unique_ptr<Record> r) { return ProcessRecord(std::move(r)); })) {
      return false;
    }
    return true;
  }

 private:
  bool ProcessRecord(std::unique_ptr<Record> r) {
    thread_tree_.Update(*r);
    if (r->type() == SIMPLE_PERF_RECORD_UNWINDING_RESULT) {
      last_unwinding_result_.reset(static_cast<UnwindingResultRecord*>(r.release()));
    } else if (r->type() == PERF_RECORD_SAMPLE) {
      if (last_unwinding_result_) {
        ReportUnwindingResult(*static_cast<SampleRecord*>(r.get()), *last_unwinding_result_);
        last_unwinding_result_.reset();
      }
    }
    return true;
  }

  void ReportUnwindingResult(const SampleRecord& sr, const UnwindingResultRecord& unwinding_r) {
    ThreadEntry* thread = thread_tree_.FindThreadOrNew(sr.tid_data.pid, sr.tid_data.tid);
    size_t kernel_ip_count;
    std::vector<uint64_t> ips = sr.GetCallChain(&kernel_ip_count);
    if (kernel_ip_count != 0) {
      ips.erase(ips.begin(), ips.begin() + kernel_ip_count);
    }

    fprintf(out_fp_, "sample_time: %" PRIu64 "\n", sr.Timestamp());
    DumpUnwindingResult(unwinding_r.unwinding_result, out_fp_);
    // Print callchain.
    std::vector<CallChainReportEntry> entries = callchain_report_builder_.Build(thread, ips, 0);
    for (size_t i = 0; i < entries.size(); i++) {
      size_t id = i + 1;
      const auto& entry = entries[i];
      fprintf(out_fp_, "ip_%zu: 0x%" PRIx64 "\n", id, entry.ip);
      if (i < unwinding_r.callchain.length) {
        fprintf(out_fp_, "unwinding_ip_%zu: 0x%" PRIx64 "\n", id, unwinding_r.callchain.ips[i]);
        fprintf(out_fp_, "unwinding_sp_%zu: 0x%" PRIx64 "\n", id, unwinding_r.callchain.sps[i]);
      }
      fprintf(out_fp_, "map_%zu: [0x%" PRIx64 "-0x%" PRIx64 "], pgoff 0x%" PRIx64 "\n", id,
              entry.map->start_addr, entry.map->get_end_addr(), entry.map->pgoff);
      fprintf(out_fp_, "dso_%zu: %s\n", id, entry.map->dso->Path().c_str());
      fprintf(out_fp_, "vaddr_in_file_%zu: 0x%" PRIx64 "\n", id, entry.vaddr_in_file);
      fprintf(out_fp_, "symbol_%zu: %s\n", id, entry.symbol->DemangledName());
    }
    // Print regs.
    uint64_t stack_addr = 0;
    if (unwinding_r.regs_user_data.reg_nr > 0) {
      auto& reg_data = unwinding_r.regs_user_data;
      RegSet regs(reg_data.abi, reg_data.reg_mask, reg_data.regs);
      uint64_t value;
      if (regs.GetSpRegValue(&value)) {
        stack_addr = value;
        for (size_t i = 0; i < 64; i++) {
          if (regs.GetRegValue(i, &value)) {
            fprintf(out_fp_, "reg_%s: 0x%" PRIx64 "\n", GetRegName(i, regs.arch).c_str(), value);
          }
        }
      }
    }
    // Print stack.
    if (unwinding_r.stack_user_data.size > 0) {
      auto& stack = unwinding_r.stack_user_data;
      const char* p = stack.data;
      const char* end = stack.data + stack.size;
      uint64_t value;
      while (p + 8 <= end) {
        fprintf(out_fp_, "stack_%" PRIx64 ":", stack_addr);
        for (size_t i = 0; i < 4 && p + 8 <= end; ++i) {
          MoveFromBinaryFormat(value, p);
          fprintf(out_fp_, " %016" PRIx64, value);
        }
        fprintf(out_fp_, "\n");
        stack_addr += 32;
      }
      fprintf(out_fp_, "\n");
    }
  }

  std::unique_ptr<UnwindingResultRecord> last_unwinding_result_;
};

class DebugUnwindCommand : public Command {
 public:
  DebugUnwindCommand()
      : Command(
            "debug-unwind", "Debug/test offline unwinding.",
            // clang-format off
"Usage: simpleperf debug-unwind [options]\n"
"--generate-report         Generate a failed unwinding report.\n"
"--generate-test-file      Generate a test file with only one sample.\n"
"-i <file>                 Input recording file. Default is perf.data.\n"
"-o <file>                 Output file. Default is stdout.\n"
"--keep-binaries-in-test-file  binary1,binary2...   Keep binaries in test file.\n"
"--sample-time time1,time2...      Only process samples recorded at selected times.\n"
"--symfs <dir>                     Look for files with symbols relative to this directory.\n"
"--unwind-sample                   Unwind samples.\n"
"--skip-sample-print               Skip printing unwound samples.\n"
"\n"
"Examples:\n"
"1. Unwind a sample.\n"
"$ simpleperf debug-unwind -i perf.data --unwind-sample --sample-time 626970493946976\n"
"  perf.data should be generated with \"--no-unwind\" or \"--keep-failed-unwinding-debug-info\".\n"
"2. Generate a test file.\n"
"$ simpleperf debug-unwind -i perf.data --generate-test-file -o test.data --sample-time \\\n"
"     626970493946976 --keep-binaries-in-test-file perf.data_jit_app_cache:255984-259968\n"
"3. Generate a failed unwinding report.\n"
"$ simpleperf debug-unwind -i perf.data --generate-report -o report.txt\n"
"  perf.data should be generated with \"--keep-failed-unwinding-debug-info\" or \\\n"
"  \"--keep-failed-unwinding-result\".\n"
"\n"
            // clang-format on
        ) {}

  bool Run(const std::vector<std::string>& args);

 private:
  bool ParseOptions(const std::vector<std::string>& args);

  std::string input_filename_ = "perf.data";
  std::string output_filename_;
  bool unwind_sample_ = false;
  bool skip_sample_print_ = false;
  bool generate_report_ = false;
  bool generate_test_file_;
  std::unordered_set<std::string> kept_binaries_in_test_file_;
  std::unordered_set<uint64_t> sample_times_;
};

bool DebugUnwindCommand::Run(const std::vector<std::string>& args) {
  // 1. Parse options.
  if (!ParseOptions(args)) {
    return false;
  }

  // 2. Distribute sub commands.
  if (unwind_sample_) {
    SampleUnwinder sample_unwinder(output_filename_, sample_times_, skip_sample_print_);
    return sample_unwinder.ProcessFile(input_filename_);
  }
  if (generate_test_file_) {
    TestFileGenerator test_file_generator(output_filename_, sample_times_,
                                          kept_binaries_in_test_file_);
    return test_file_generator.ProcessFile(input_filename_);
  }
  if (generate_report_) {
    ReportGenerator report_generator(output_filename_);
    return report_generator.ProcessFile(input_filename_);
  }
  return true;
}

bool DebugUnwindCommand::ParseOptions(const std::vector<std::string>& args) {
  const OptionFormatMap option_formats = {
      {"--generate-report", {OptionValueType::NONE, OptionType::SINGLE}},
      {"--generate-test-file", {OptionValueType::NONE, OptionType::SINGLE}},
      {"-i", {OptionValueType::STRING, OptionType::SINGLE}},
      {"--keep-binaries-in-test-file", {OptionValueType::STRING, OptionType::MULTIPLE}},
      {"-o", {OptionValueType::STRING, OptionType::SINGLE}},
      {"--sample-time", {OptionValueType::STRING, OptionType::MULTIPLE}},
      {"--skip-sample-print", {OptionValueType::NONE, OptionType::SINGLE}},
      {"--symfs", {OptionValueType::STRING, OptionType::MULTIPLE}},
      {"--unwind-sample", {OptionValueType::NONE, OptionType::SINGLE}},
  };
  OptionValueMap options;
  std::vector<std::pair<OptionName, OptionValue>> ordered_options;
  if (!PreprocessOptions(args, option_formats, &options, &ordered_options)) {
    return false;
  }
  generate_report_ = options.PullBoolValue("--generate-report");
  generate_test_file_ = options.PullBoolValue("--generate-test-file");
  options.PullStringValue("-i", &input_filename_);
  for (auto& value : options.PullValues("--keep-binaries-in-test-file")) {
    std::vector<std::string> binaries = android::base::Split(value.str_value, ",");
    kept_binaries_in_test_file_.insert(binaries.begin(), binaries.end());
  }
  skip_sample_print_ = options.PullBoolValue("--skip-sample-print");
  options.PullStringValue("-o", &output_filename_);
  for (auto& value : options.PullValues("--sample-time")) {
    auto times = ParseUintVector<uint64_t>(value.str_value);
    if (!times) {
      return false;
    }
    sample_times_.insert(times.value().begin(), times.value().end());
  }
  if (auto value = options.PullValue("--symfs"); value) {
    if (!Dso::SetSymFsDir(value->str_value)) {
      return false;
    }
  }
  unwind_sample_ = options.PullBoolValue("--unwind-sample");
  CHECK(options.values.empty());

  if (generate_test_file_) {
    if (output_filename_.empty()) {
      LOG(ERROR) << "no output path for generated test file";
      return false;
    }
    if (sample_times_.empty()) {
      LOG(ERROR) << "no samples are selected via --sample-time";
      return false;
    }
  }

  return true;
}

}  // namespace

void RegisterDebugUnwindCommand() {
  RegisterCommand("debug-unwind",
                  [] { return std::unique_ptr<Command>(new DebugUnwindCommand()); });
}

}  // namespace simpleperf
