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

#ifndef SIMPLE_PERF_SAMPLE_COMPARATOR_H_
#define SIMPLE_PERF_SAMPLE_COMPARATOR_H_

#include <string.h>

#include <vector>

namespace simpleperf {

// The compare functions below are used to compare two samples by their item
// content.

template <typename T>
int Compare(const T& a, const T& b) {
  if (a != b) {
    return a < b ? -1 : 1;
  }
  return 0;
}

#define BUILD_COMPARE_VALUE_FUNCTION(function_name, compare_part)   \
  template <typename EntryT>                                        \
  int function_name(const EntryT* sample1, const EntryT* sample2) { \
    return Compare(sample1->compare_part, sample2->compare_part);   \
  }

#define BUILD_COMPARE_VALUE_FUNCTION_REVERSE(function_name, compare_part) \
  template <typename EntryT>                                              \
  int function_name(const EntryT* sample1, const EntryT* sample2) {       \
    return Compare(sample2->compare_part, sample1->compare_part);         \
  }

#define BUILD_COMPARE_STRING_FUNCTION(function_name, compare_part)  \
  template <typename EntryT>                                        \
  int function_name(const EntryT* sample1, const EntryT* sample2) { \
    return strcmp(sample1->compare_part, sample2->compare_part);    \
  }

BUILD_COMPARE_VALUE_FUNCTION(ComparePid, pid);
BUILD_COMPARE_VALUE_FUNCTION(CompareTid, tid);
BUILD_COMPARE_VALUE_FUNCTION_REVERSE(CompareSampleCount, sample_count);
BUILD_COMPARE_STRING_FUNCTION(CompareComm, thread_comm);
BUILD_COMPARE_STRING_FUNCTION(CompareDso, map->dso->GetReportPath().data());
BUILD_COMPARE_STRING_FUNCTION(CompareSymbol, symbol->DemangledName());
BUILD_COMPARE_STRING_FUNCTION(CompareDsoFrom, branch_from.map->dso->GetReportPath().data());
BUILD_COMPARE_STRING_FUNCTION(CompareSymbolFrom, branch_from.symbol->DemangledName());
BUILD_COMPARE_VALUE_FUNCTION(CompareCallGraphDuplicated, callchain.duplicated);

template <typename EntryT>
int CompareTotalPeriod(const EntryT* sample1, const EntryT* sample2) {
  uint64_t period1 = sample1->period + sample1->accumulated_period;
  uint64_t period2 = sample2->period + sample2->accumulated_period;
  return Compare(period2, period1);
}

template <typename EntryT>
int ComparePeriod(const EntryT* sample1, const EntryT* sample2) {
  return Compare(sample2->period, sample1->period);
}

// SampleComparator is a class using a collection of compare functions to
// compare two samples.

template <typename EntryT>
class SampleComparator {
 public:
  typedef int (*compare_sample_func_t)(const EntryT*, const EntryT*);

  void AddCompareFunction(compare_sample_func_t func) { compare_v_.push_back(func); }

  void AddComparator(const SampleComparator<EntryT>& other) {
    compare_v_.insert(compare_v_.end(), other.compare_v_.begin(), other.compare_v_.end());
  }

  bool operator()(const EntryT* sample1, const EntryT* sample2) const {
    for (const auto& func : compare_v_) {
      int ret = func(sample1, sample2);
      if (ret != 0) {
        return ret < 0;
      }
    }
    return false;
  }

  bool operator()(const EntryT& sample1, const EntryT& sample2) const {
    for (const auto& func : compare_v_) {
      int ret = func(&sample1, &sample2);
      if (ret != 0) {
        return ret < 0;
      }
    }
    return false;
  }

  bool IsSameSample(const EntryT* sample1, const EntryT* sample2) const {
    for (const auto& func : compare_v_) {
      if (func(sample1, sample2) != 0) {
        return false;
      }
    }
    return true;
  }

  bool empty() const { return compare_v_.empty(); }

 private:
  std::vector<compare_sample_func_t> compare_v_;
};

}  // namespace simpleperf

#endif  // SIMPLE_PERF_SAMPLE_COMPARATOR_H_
