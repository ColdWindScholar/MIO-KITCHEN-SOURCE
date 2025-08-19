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

#include <stdio.h>

#include <memory>
#include <regex>
#include <string>

#include <android-base/macros.h>
#include <android-base/strings.h>

#include "command.h"
#include "event_attr.h"
#include "record_file.h"
#include "thread_tree.h"
#include "utils.h"

namespace simpleperf {
namespace {

class MergedFileFeature {
 public:
  MergedFileFeature(FileFeature& file)
      : path_(file.path),
        type_(file.type),
        min_vaddr_(file.min_vaddr),
        file_offset_of_min_vaddr_(file.file_offset_of_min_vaddr),
        dex_file_offsets_(std::move(file.dex_file_offsets)) {
    for (auto& symbol : file.symbols) {
      symbol_map_.emplace(symbol.addr, std::move(symbol));
    }
  }

  bool Merge(FileFeature& file) {
    if (file.type != type_ || file.min_vaddr != min_vaddr_ ||
        file.file_offset_of_min_vaddr != file_offset_of_min_vaddr_ ||
        file.dex_file_offsets != dex_file_offsets_) {
      return false;
    }
    for (auto& symbol : file.symbols) {
      auto it = symbol_map_.lower_bound(symbol.addr);
      if (it != symbol_map_.end()) {
        const auto& found = it->second;
        if (found.addr == symbol.addr && found.len == symbol.len &&
            strcmp(found.Name(), symbol.Name()) == 0) {
          // The symbol already exists in symbol_map.
          continue;
        }
        if (symbol.addr + symbol.len > found.addr) {
          // an address conflict with the next symbol
          return false;
        }
      }
      if (it != symbol_map_.begin()) {
        --it;
        if (it->second.addr + it->second.len > symbol.addr) {
          // an address conflict with the previous symbol
          return false;
        }
      }
      symbol_map_.emplace(symbol.addr, std::move(symbol));
    }
    return true;
  }

  void ToFileFeature(FileFeature* file) const {
    file->path = path_;
    file->type = type_;
    file->min_vaddr = min_vaddr_;
    file->file_offset_of_min_vaddr = file_offset_of_min_vaddr_;
    file->symbol_ptrs.clear();
    for (const auto& [_, symbol] : symbol_map_) {
      file->symbol_ptrs.emplace_back(&symbol);
    }
    file->dex_file_offsets = dex_file_offsets_;
  }

 private:
  std::string path_;
  DsoType type_;
  uint64_t min_vaddr_;
  uint64_t file_offset_of_min_vaddr_;
  std::map<uint64_t, Symbol> symbol_map_;
  std::vector<uint64_t> dex_file_offsets_;

  DISALLOW_COPY_AND_ASSIGN(MergedFileFeature);
};

class MergeCommand : public Command {
 public:
  MergeCommand()
      : Command("merge", "merge multiple perf.data into one",
                // clang-format off
"Usage: simpleperf merge [options]\n"
"       Merge multiple perf.data into one. The input files should be recorded on the same\n"
"       device using the same event types.\n"
"-i <file1>,<file2>,...       Input recording files separated by comma\n"
"-o <file>                    output recording file\n"
"\n"
"Examples:\n"
"$ simpleperf merge -i perf1.data,perf2.data -o perf.data\n"
                // clang-format on
        ) {}

  bool Run(const std::vector<std::string>& args) override {
    // 1. Parse options.
    if (!ParseOptions(args)) {
      return false;
    }

    // 2. Open input files and check if they are mergeable.
    for (const auto& file : input_files_) {
      readers_.emplace_back(RecordFileReader::CreateInstance(file));
      if (!readers_.back()) {
        return false;
      }
    }
    if (!IsMergeable()) {
      return false;
    }

    // 3. Merge files.
    writer_ = RecordFileWriter::CreateInstance(output_file_);
    if (!writer_) {
      return false;
    }
    if (!MergeAttrSection() || !MergeDataSection() || !MergeFeatureSection()) {
      return false;
    }
    return writer_->Close();
  }

 private:
  bool ParseOptions(const std::vector<std::string>& args) {
    const OptionFormatMap option_formats = {
        {"-i", {OptionValueType::STRING, OptionType::MULTIPLE}},
        {"-o", {OptionValueType::STRING, OptionType::SINGLE}},
    };
    OptionValueMap options;
    std::vector<std::pair<OptionName, OptionValue>> ordered_options;
    if (!PreprocessOptions(args, option_formats, &options, &ordered_options, nullptr)) {
      return false;
    }
    for (const OptionValue& value : options.PullValues("-i")) {
      auto files = android::base::Split(value.str_value, ",");
      input_files_.insert(input_files_.end(), files.begin(), files.end());
    }
    options.PullStringValue("-o", &output_file_);

    CHECK(options.values.empty());

    if (input_files_.empty()) {
      LOG(ERROR) << "missing input files";
      return false;
    }
    if (output_file_.empty()) {
      LOG(ERROR) << "missing output file";
      return false;
    }
    return true;
  }

  bool IsMergeable() { return CheckFeatureSection() && CheckAttrSection(); }

  // Check feature sections to know if the recording environments are the same.
  bool CheckFeatureSection() {
    auto get_arch = [](std::unique_ptr<RecordFileReader>& reader) {
      return reader->ReadFeatureString(PerfFileFormat::FEAT_ARCH);
    };
    auto get_kernel_version = [](std::unique_ptr<RecordFileReader>& reader) {
      return reader->ReadFeatureString(PerfFileFormat::FEAT_OSRELEASE);
    };
    auto get_meta_info = [](std::unique_ptr<RecordFileReader>& reader, const char* key) {
      auto it = reader->GetMetaInfoFeature().find(key);
      return it == reader->GetMetaInfoFeature().end() ? "" : it->second;
    };
    auto get_simpleperf_version = [&](std::unique_ptr<RecordFileReader>& reader) {
      return get_meta_info(reader, "simpleperf_version");
    };
    auto get_trace_offcpu = [&](std::unique_ptr<RecordFileReader>& reader) {
      return get_meta_info(reader, "trace_offcpu");
    };
    auto get_event_types = [&](std::unique_ptr<RecordFileReader>& reader) {
      std::string s = get_meta_info(reader, "event_type_info");
      std::vector<std::string> v = android::base::Split(s, "\n");
      std::sort(v.begin(), v.end());
      return android::base::Join(v, ";");
    };
    auto get_android_device = [&](std::unique_ptr<RecordFileReader>& reader) {
      return get_meta_info(reader, "product_props");
    };
    auto get_android_version = [&](std::unique_ptr<RecordFileReader>& reader) {
      return get_meta_info(reader, "android_version");
    };
    auto get_app_package_name = [&](std::unique_ptr<RecordFileReader>& reader) {
      return get_meta_info(reader, "app_package_name");
    };
    auto get_clockid = [&](std::unique_ptr<RecordFileReader>& reader) {
      return get_meta_info(reader, "clockid");
    };
    auto get_used_features = [](std::unique_ptr<RecordFileReader>& reader) {
      std::string s;
      for (const auto& [key, _] : reader->FeatureSectionDescriptors()) {
        s += std::to_string(key) + ",";
      }
      return s;
    };

    using value_func_t = std::function<std::string(std::unique_ptr<RecordFileReader>&)>;
    std::vector<std::pair<std::string, value_func_t>> check_entries = {
        std::make_pair("arch", get_arch),
        std::make_pair("kernel_version", get_kernel_version),
        std::make_pair("simpleperf_version", get_simpleperf_version),
        std::make_pair("trace_offcpu", get_trace_offcpu),
        std::make_pair("event_types", get_event_types),
        std::make_pair("android_device", get_android_device),
        std::make_pair("android_version", get_android_version),
        std::make_pair("app_package_name", get_app_package_name),
        std::make_pair("clockid", get_clockid),
        std::make_pair("used_features", get_used_features),
    };

    for (const auto& [name, get_value] : check_entries) {
      std::string value0 = get_value(readers_[0]);
      for (size_t i = 1; i < readers_.size(); i++) {
        std::string value = get_value(readers_[i]);
        if (value != value0) {
          LOG(ERROR) << input_files_[0] << " and " << input_files_[i] << " are not mergeable for "
                     << name << " difference: " << value0 << " vs " << value;
          return false;
        }
      }
    }

    if (readers_[0]->HasFeature(PerfFileFormat::FEAT_AUXTRACE)) {
      LOG(ERROR) << "merging of recording files with auxtrace feature isn't supported";
      return false;
    }
    return true;
  }

  // Check attr sections to know if recorded event types are the same.
  bool CheckAttrSection() {
    const EventAttrIds& attrs0 = readers_[0]->AttrSection();
    for (size_t i = 1; i < readers_.size(); i++) {
      const EventAttrIds& attrs = readers_[i]->AttrSection();
      if (attrs.size() != attrs0.size()) {
        LOG(ERROR) << input_files_[0] << " and " << input_files_[i]
                   << " are not mergeable for recording different event types";
        return false;
      }
      for (size_t attr_id = 0; attr_id < attrs.size(); attr_id++) {
        if (attrs[attr_id].attr != attrs0[attr_id].attr) {
          LOG(ERROR) << input_files_[0] << " and " << input_files_[i]
                     << " are not mergeable for recording different event types";
          return false;
        }
      }
    }
    return true;
  }

  bool MergeAttrSection() { return writer_->WriteAttrSection(readers_[0]->AttrSection()); }

  bool MergeDataSection() {
    for (size_t i = 0; i < readers_.size(); i++) {
      if (i != 0) {
        if (!WriteGapInDataSection(i - 1, i)) {
          return false;
        }
      }
      auto callback = [this](std::unique_ptr<Record> record) {
        return ProcessRecord(record.get());
      };
      if (!readers_[i]->ReadDataSection(callback)) {
        return false;
      }
    }
    return true;
  }

  bool ProcessRecord(Record* record) { return writer_->WriteRecord(*record); }

  bool WriteGapInDataSection(size_t prev_reader_id, size_t next_reader_id) {
    // MergeAttrSection() only maps event_ids in readers_[0] to event attrs. So we need to
    // map event_ids in readers_[next_read_id] to event attrs. The map info is put into an
    // EventIdRecord.
    const std::unordered_map<uint64_t, size_t>& cur_map = readers_[prev_reader_id]->EventIdMap();
    const EventAttrIds& attrs = readers_[next_reader_id]->AttrSection();
    std::vector<uint64_t> event_id_data;
    for (size_t attr_id = 0; attr_id < attrs.size(); attr_id++) {
      for (size_t event_id : attrs[attr_id].ids) {
        if (auto it = cur_map.find(event_id); it == cur_map.end() || it->second != attr_id) {
          event_id_data.push_back(attr_id);
          event_id_data.push_back(event_id);
        }
      }
    }
    if (!event_id_data.empty()) {
      EventIdRecord record(event_id_data);
      if (!ProcessRecord(&record)) {
        return false;
      }
    }
    return true;
  }

  bool MergeFeatureSection() {
    std::vector<int> features;
    for (const auto& [key, _] : readers_[0]->FeatureSectionDescriptors()) {
      features.push_back(key);
    }
    if (!writer_->BeginWriteFeatures(features.size())) {
      return false;
    }
    for (int feature : features) {
      if (feature == PerfFileFormat::FEAT_OSRELEASE || feature == PerfFileFormat::FEAT_ARCH ||
          feature == PerfFileFormat::FEAT_BRANCH_STACK ||
          feature == PerfFileFormat::FEAT_META_INFO || feature == PerfFileFormat::FEAT_CMDLINE) {
        std::vector<char> data;
        if (!readers_[0]->ReadFeatureSection(feature, &data) ||
            !writer_->WriteFeature(feature, data.data(), data.size())) {
          return false;
        }
      } else if (feature == PerfFileFormat::FEAT_BUILD_ID) {
        WriteBuildIdFeature();
      } else if (feature == PerfFileFormat::FEAT_FILE || feature == PerfFileFormat::FEAT_FILE2) {
        WriteFileFeature();
      } else {
        LOG(WARNING) << "Drop feature " << feature << ", which isn't supported in the merge cmd.";
      }
    }
    return writer_->EndWriteFeatures();
  }

  bool WriteBuildIdFeature() {
    std::map<std::string, BuildIdRecord> build_ids;
    std::unordered_set<std::string> files_to_drop;
    for (auto& reader : readers_) {
      for (auto& record : reader->ReadBuildIdFeature()) {
        auto it = build_ids.find(record.filename);
        if (it == build_ids.end()) {
          build_ids.emplace(record.filename, std::move(record));
        } else if (it->second.build_id != record.build_id) {
          if (files_to_drop.count(record.filename) == 0) {
            files_to_drop.emplace(record.filename);
            LOG(WARNING)
                << record.filename
                << " has different build ids in different record files. So drop its build ids.";
          }
        }
      }
    }
    std::vector<BuildIdRecord> records;
    for (auto& [filename, record] : build_ids) {
      if (files_to_drop.count(filename) == 0) {
        records.emplace_back(std::move(record));
      }
    }
    return writer_->WriteBuildIdFeature(records);
  }

  bool WriteFileFeature() {
    std::map<std::string, MergedFileFeature> file_map;
    std::unordered_set<std::string> files_to_drop;

    // Read file features.
    for (auto& reader : readers_) {
      FileFeature file;
      uint64_t read_pos = 0;
      bool error = false;
      while (reader->ReadFileFeature(read_pos, file, error)) {
        if (files_to_drop.count(file.path) != 0) {
          continue;
        }
        if (auto it = file_map.find(file.path); it == file_map.end()) {
          file_map.emplace(file.path, file);
        } else if (!it->second.Merge(file)) {
          LOG(WARNING)
              << file.path
              << " has address-conflict symbols in different record files. So drop its symbols.";
          files_to_drop.emplace(file.path);
        }
      }
      if (error) {
        return false;
      }
    }
    // Write file features.
    for (const auto& [file_path, file] : file_map) {
      if (files_to_drop.count(file_path) != 0) {
        continue;
      }
      FileFeature file_feature;
      file.ToFileFeature(&file_feature);
      if (!writer_->WriteFileFeature(file_feature)) {
        return false;
      }
    }
    return true;
  }

  std::vector<std::string> input_files_;
  std::vector<std::unique_ptr<RecordFileReader>> readers_;
  std::string output_file_;
  std::unique_ptr<RecordFileWriter> writer_;
};

}  // namespace

void RegisterMergeCommand() {
  return RegisterCommand("merge", [] { return std::unique_ptr<Command>(new MergeCommand); });
}

}  // namespace simpleperf
