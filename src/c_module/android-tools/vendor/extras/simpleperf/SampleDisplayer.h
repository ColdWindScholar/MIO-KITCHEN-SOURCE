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

#ifndef SIMPLE_PERF_SAMPLE_DISPLAYER_H_
#define SIMPLE_PERF_SAMPLE_DISPLAYER_H_

#include <inttypes.h>

#include <functional>
#include <optional>
#include <string>

#include <android-base/logging.h>
#include <android-base/stringprintf.h>

namespace simpleperf {

// The display functions below are used to show items in a sample.

template <typename EntryT, typename InfoT>
std::string DisplayAccumulatedOverhead(const EntryT* sample, const InfoT* info) {
  uint64_t period = sample->period + sample->accumulated_period;
  uint64_t total_period = info->total_period;
  double percentage = (total_period != 0) ? 100.0 * period / total_period : 0.0;
  return android::base::StringPrintf("%.2f%%", percentage);
}

template <typename EntryT>
std::string DisplayAccumulatedPeriod(const EntryT* sample) {
  return android::base::StringPrintf("%" PRIu64, sample->period + sample->accumulated_period);
}

template <typename EntryT, typename InfoT>
std::string DisplaySelfOverhead(const EntryT* sample, const InfoT* info) {
  uint64_t period = sample->period;
  uint64_t total_period = info->total_period;
  double percentage = (total_period != 0) ? 100.0 * period / total_period : 0.0;
  return android::base::StringPrintf("%.2f%%", percentage);
}

#define BUILD_DISPLAY_UINT64_FUNCTION(function_name, display_part)        \
  template <typename EntryT>                                              \
  std::string function_name(const EntryT* sample) {                       \
    return android::base::StringPrintf("%" PRIu64, sample->display_part); \
  }

#define BUILD_DISPLAY_HEX64_FUNCTION(function_name, display_part)           \
  template <typename EntryT>                                                \
  std::string function_name(const EntryT* sample) {                         \
    return android::base::StringPrintf("0x%" PRIx64, sample->display_part); \
  }

BUILD_DISPLAY_UINT64_FUNCTION(DisplaySelfPeriod, period);
BUILD_DISPLAY_UINT64_FUNCTION(DisplaySampleCount, sample_count);

template <typename EntryT>
std::string DisplayPid(const EntryT* sample) {
  return android::base::StringPrintf("%d", static_cast<int>(sample->pid));
}

template <typename EntryT>
std::string DisplayTid(const EntryT* sample) {
  return android::base::StringPrintf("%d", static_cast<int>(sample->tid));
}

template <typename EntryT>
std::string DisplayComm(const EntryT* sample) {
  return sample->thread_comm;
}

template <typename EntryT>
std::string DisplayDso(const EntryT* sample) {
  return std::string{sample->map->dso->GetReportPath()};
}

template <typename EntryT>
std::string DisplaySymbol(const EntryT* sample) {
  return sample->symbol->DemangledName();
}

template <typename EntryT>
std::string DisplayDsoFrom(const EntryT* sample) {
  return std::string{sample->branch_from.map->dso->GetReportPath()};
}

template <typename EntryT>
std::string DisplaySymbolFrom(const EntryT* sample) {
  return sample->branch_from.symbol->DemangledName();
}

template <typename SampleT, typename CallChainNodeT>
class CallgraphDisplayer {
 private:
  static constexpr int SPACES_BETWEEN_CALLGRAPH_ENTRIES = 4;

 public:
  CallgraphDisplayer(uint32_t max_stack = UINT32_MAX, double percent_limit = 0.0,
                     bool brief_callgraph = false)
      : max_stack_(max_stack), percent_limit_(percent_limit), brief_callgraph_(brief_callgraph) {}

  virtual ~CallgraphDisplayer() {}

  void operator()(FILE* fp, const SampleT* sample) {
    if (sample->callchain.children.empty()) {
      return;
    }
    std::string prefix = "       ";
    if (brief_callgraph_ && sample->callchain.duplicated) {
      fprintf(fp, "%s[skipped in brief callgraph mode]\n", prefix.c_str());
      return;
    }
    fprintf(fp, "%s|\n", prefix.c_str());
    fprintf(fp, "%s-- %s\n", prefix.c_str(), PrintSampleName(sample).c_str());
    prefix.append(3, ' ');
    for (size_t i = 0; i < sample->callchain.children.size(); ++i) {
      DisplayCallGraphEntry(fp, 1, prefix, sample->callchain.children[i],
                            sample->callchain.children_period + sample->GetPeriod(),
                            (i + 1 == sample->callchain.children.size()));
    }
  }

  void DisplayCallGraphEntry(FILE* fp, size_t depth, std::string prefix,
                             const std::unique_ptr<CallChainNodeT>& node, uint64_t parent_period,
                             bool last) {
    if (depth > max_stack_) {
      return;
    }
    std::string percentage_s = "-- ";
    if (node->period + node->children_period != parent_period) {
      double percentage = 100.0 * (node->period + node->children_period) / parent_period;
      if (percentage < percent_limit_) {
        return;
      }
      percentage_s = android::base::StringPrintf("--%.2f%%-- ", percentage);
    }
    prefix += "|";
    fprintf(fp, "%s\n", prefix.c_str());
    if (last) {
      prefix.back() = ' ';
    }
    fprintf(fp, "%s%s%s\n", prefix.c_str(), percentage_s.c_str(),
            PrintSampleName(node->chain[0]).c_str());
    for (size_t i = 1; i < node->chain.size(); ++i) {
      fprintf(fp, "%s%*s%s\n", prefix.c_str(), static_cast<int>(percentage_s.size()), "",
              PrintSampleName(node->chain[i]).c_str());
    }
    prefix.append(SPACES_BETWEEN_CALLGRAPH_ENTRIES, ' ');
    if (!node->children.empty() && node->period != 0) {
      fprintf(fp, "%s|--%.2f%%-- [hit in function]\n", prefix.c_str(),
              100.0 * node->period / (node->period + node->children_period));
    }
    for (size_t i = 0; i < node->children.size(); ++i) {
      DisplayCallGraphEntry(fp, depth + 1, prefix, node->children[i],
                            node->children_period + node->period, (i + 1 == node->children.size()));
    }
  }

 protected:
  virtual std::string PrintSampleName(const SampleT* sample) {
    return sample->symbol->DemangledName();
  }

 private:
  uint32_t max_stack_;
  double percent_limit_;
  bool brief_callgraph_;
};

// SampleDisplayer is a class using a collections of display functions to show a
// sample.

template <typename EntryT, typename InfoT>
class SampleDisplayer {
 public:
  using display_sample_func_t = std::function<std::string(const EntryT*)>;
  using display_sample_with_info_func_t = std::function<std::string(const EntryT*, const InfoT*)>;
  using exclusive_display_sample_func_t = std::function<void(FILE*, const EntryT*)>;

 private:
  struct Item {
    std::string name;
    size_t width;
    display_sample_func_t func;
    display_sample_with_info_func_t func_with_info;
  };

 public:
  void SetInfo(const InfoT* info) { info_ = info; }
  void SetReportFormat(bool report_csv, const std::string& csv_separator) {
    report_csv_ = report_csv;
    csv_separator_ = csv_separator;
  }
  void SetFilterFunction(const std::function<bool(const EntryT*, const InfoT*)>& filter) {
    filter_func_ = filter;
  }

  void AddDisplayFunction(const std::string& name, const display_sample_func_t& func) {
    Item item;
    item.name = name;
    item.width = name.size();
    item.func = func;
    item.func_with_info = nullptr;
    display_v_.push_back(item);
  }

  void AddDisplayFunction(const std::string& name,
                          const display_sample_with_info_func_t& func_with_info) {
    Item item;
    item.name = name;
    item.width = name.size();
    item.func = nullptr;
    item.func_with_info = func_with_info;
    display_v_.push_back(item);
  }

  void AddExclusiveDisplayFunction(const exclusive_display_sample_func_t& func) {
    exclusive_display_v_.push_back(func);
  }

  void AdjustWidth(const EntryT* sample) {
    if (report_csv_) {
      return;
    }
    if (filter_func_ && !filter_func_.value()(sample, info_)) {
      return;
    }
    for (auto& item : display_v_) {
      std::string data =
          (item.func != nullptr) ? item.func(sample) : item.func_with_info(sample, info_);
      item.width = std::max(item.width, data.size());
    }
  }

  void PrintNames(FILE* fp) {
    for (size_t i = 0; i < display_v_.size(); ++i) {
      auto& item = display_v_[i];
      if (report_csv_) {
        fprintf(fp, "%s%s", item.name.c_str(),
                (i + 1 == display_v_.size()) ? "\n" : csv_separator_.c_str());
      } else {
        if (i != display_v_.size() - 1) {
          fprintf(fp, "%-*s  ", static_cast<int>(item.width), item.name.c_str());
        } else {
          fprintf(fp, "%s\n", item.name.c_str());
        }
      }
    }
  }

  void PrintSample(FILE* fp, const EntryT* sample) {
    if (filter_func_ && !filter_func_.value()(sample, info_)) {
      return;
    }
    for (size_t i = 0; i < display_v_.size(); ++i) {
      auto& item = display_v_[i];
      std::string data =
          (item.func != nullptr) ? item.func(sample) : item.func_with_info(sample, info_);
      if (report_csv_) {
        if (data.find(csv_separator_) == std::string::npos) {
          fprintf(fp, "%s", data.c_str());
        } else {
          fprintf(fp, "\"%s\"", data.c_str());
        }
        fputs((i + 1 == display_v_.size()) ? "\n" : csv_separator_.c_str(), fp);
      } else {
        if (i != display_v_.size() - 1) {
          fprintf(fp, "%-*s  ", static_cast<int>(item.width), data.c_str());
        } else {
          fprintf(fp, "%s\n", data.c_str());
        }
      }
    }
    for (auto& func : exclusive_display_v_) {
      func(fp, sample);
    }
  }

 private:
  const InfoT* info_;
  std::vector<Item> display_v_;
  std::vector<exclusive_display_sample_func_t> exclusive_display_v_;
  std::optional<std::function<bool(const EntryT*, const InfoT*)>> filter_func_;
  bool report_csv_ = false;
  std::string csv_separator_;
};

}  // namespace simpleperf

#endif  // SIMPLE_PERF_SAMPLE_DISPLAYER_H_
