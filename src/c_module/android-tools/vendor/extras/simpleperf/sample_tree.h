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

#ifndef SIMPLE_PERF_SAMPLE_TREE_H_
#define SIMPLE_PERF_SAMPLE_TREE_H_

#include <unordered_map>

#include "OfflineUnwinder.h"
#include "SampleComparator.h"
#include "SampleDisplayer.h"
#include "callchain.h"
#include "perf_regs.h"
#include "record.h"
#include "thread_tree.h"

namespace simpleperf {

// A SampleTree is a collection of samples. A profiling report is mainly about
// constructing a SampleTree and display it. There are three steps involved:
// build the tree, sort the tree, and display it. For example, if we want to
// show how many cpu-cycles are spent in different functions, we should do as
// follows:
// 1. Build a SampleTree from SampleRecords with each sample containing
//    (cpu-cycles, function name). When building the tree, we should merge
//    samples containing the same function name.
// 2. Sort the SampleTree by cpu-cycles in the sample. As we want to display the
//    samples in a decreasing order of cpu-cycles, we should sort it like this.
// 3. Display the SampleTree, each sample prints its (cpu-cycles, function name)
//    pair.
//
// We represent the three steps with three template classes.
// 1. A SampleTree is built by SampleTreeBuilder. The comparator passed in
//    SampleTreeBuilder's constructor decides the property of samples should be
//    merged together.
// 2. After a SampleTree is built and got from SampleTreeBuilder, it should be
//    sorted by SampleTreeSorter. The sort result decides the order to show
//    samples.
// 3. At last, the sorted SampleTree is passed to SampleTreeDisplayer, which
//    displays each sample in the SampleTree.

template <typename EntryT, typename AccumulateInfoT>
class SampleTreeBuilder {
 public:
  explicit SampleTreeBuilder(const SampleComparator<EntryT>& comparator)
      : sample_set_(comparator),
        accumulate_callchain_(false),
        sample_comparator_(comparator),
        filtered_sample_set_(comparator),
        use_branch_address_(false),
        build_callchain_(false),
        use_caller_as_callchain_root_(false) {}

  virtual ~SampleTreeBuilder() {}

  void SetBranchSampleOption(bool use_branch_address) { use_branch_address_ = use_branch_address; }

  void SetCallChainSampleOptions(bool accumulate_callchain, bool build_callchain,
                                 bool use_caller_as_callchain_root) {
    accumulate_callchain_ = accumulate_callchain;
    build_callchain_ = build_callchain;
    use_caller_as_callchain_root_ = use_caller_as_callchain_root;
    if (accumulate_callchain_) {
      offline_unwinder_ = OfflineUnwinder::Create(false);
    }
  }

  OfflineUnwinder* GetUnwinder() { return offline_unwinder_.get(); }

  void ProcessSampleRecord(const SampleRecord& r) {
    if (use_branch_address_ && (r.sample_type & PERF_SAMPLE_BRANCH_STACK)) {
      for (uint64_t i = 0; i < r.branch_stack_data.stack_nr; ++i) {
        auto& item = r.branch_stack_data.stack[i];
        if (item.from != 0 && item.to != 0) {
          CreateBranchSample(r, item);
        }
      }
      return;
    }
    bool in_kernel = r.InKernel();
    AccumulateInfoT acc_info;
    EntryT* sample = CreateSample(r, in_kernel, &acc_info);
    if (sample == nullptr) {
      return;
    }
    if (accumulate_callchain_) {
      std::vector<uint64_t> ips;
      if (r.sample_type & PERF_SAMPLE_CALLCHAIN) {
        ips.insert(ips.end(), r.callchain_data.ips, r.callchain_data.ips + r.callchain_data.ip_nr);
      }
      const ThreadEntry* thread = GetThreadOfSample(sample);
      // Use stack_user_data.data.size() instead of stack_user_data.dyn_size, to
      // make up for the missing kernel patch in N9. See b/22612370.
      if (thread != nullptr && (r.sample_type & PERF_SAMPLE_REGS_USER) &&
          (r.regs_user_data.reg_mask != 0) && (r.sample_type & PERF_SAMPLE_STACK_USER) &&
          (r.GetValidStackSize() > 0)) {
        RegSet regs(r.regs_user_data.abi, r.regs_user_data.reg_mask, r.regs_user_data.regs);
        std::vector<uint64_t> user_ips;
        std::vector<uint64_t> sps;
        if (offline_unwinder_->UnwindCallChain(*thread, regs, r.stack_user_data.data,
                                               r.GetValidStackSize(), &user_ips, &sps)) {
          ips.push_back(PERF_CONTEXT_USER);
          ips.insert(ips.end(), user_ips.begin(), user_ips.end());
        }
      }

      std::vector<EntryT*> callchain;
      callchain.push_back(sample);

      bool first_ip = true;
      for (auto& ip : ips) {
        if (ip >= PERF_CONTEXT_MAX) {
          switch (ip) {
            case PERF_CONTEXT_KERNEL:
              in_kernel = true;
              break;
            case PERF_CONTEXT_USER:
              in_kernel = false;
              break;
            default:
              LOG(DEBUG) << "Unexpected perf_context in callchain: " << ip;
          }
        } else {
          if (first_ip) {
            first_ip = false;
            // Remove duplication with sampled ip.
            if (ip == r.ip_data.ip) {
              continue;
            }
          }
          EntryT* callchain_sample =
              CreateCallChainSample(thread, sample, ip, in_kernel, callchain, acc_info);
          if (callchain_sample == nullptr) {
            break;
          }
          callchain.push_back(callchain_sample);
        }
      }

      if (build_callchain_) {
        std::set<EntryT*> added_set;
        if (use_caller_as_callchain_root_) {
          std::reverse(callchain.begin(), callchain.end());
        }
        EntryT* parent = nullptr;
        while (callchain.size() >= 2) {
          EntryT* sample = callchain[0];
          callchain.erase(callchain.begin());
          // Add only once for recursive calls on callchain.
          if (added_set.find(sample) != added_set.end()) {
            continue;
          }
          added_set.insert(sample);
          InsertCallChainForSample(sample, callchain, acc_info);
          UpdateCallChainParentInfo(sample, parent);
          parent = sample;
        }
      }
    }
  }

  std::vector<EntryT*> GetSamples() const {
    std::vector<EntryT*> result;
    for (auto& entry : sample_set_) {
      result.push_back(entry);
    }
    return result;
  }

 protected:
  virtual EntryT* CreateSample(const SampleRecord& r, bool in_kernel,
                               AccumulateInfoT* acc_info) = 0;
  virtual EntryT* CreateBranchSample(const SampleRecord& r, const BranchStackItemType& item) = 0;
  virtual EntryT* CreateCallChainSample(const ThreadEntry* thread, const EntryT* sample,
                                        uint64_t ip, bool in_kernel,
                                        const std::vector<EntryT*>& callchain,
                                        const AccumulateInfoT& acc_info) = 0;
  virtual const ThreadEntry* GetThreadOfSample(EntryT*) = 0;
  virtual uint64_t GetPeriodForCallChain(const AccumulateInfoT& acc_info) = 0;
  virtual bool FilterSample(const EntryT*) { return true; }

  virtual void UpdateSummary(const EntryT*) {}

  virtual void MergeSample(EntryT* sample1, EntryT* sample2) = 0;

  EntryT* InsertSample(std::unique_ptr<EntryT> sample) {
    if (sample == nullptr) {
      return nullptr;
    }
    if (!FilterSample(sample.get())) {
      // Store in filtered_sample_set_ for use in other EntryT's callchain.
      auto it = filtered_sample_set_.find(sample.get());
      if (it != filtered_sample_set_.end()) {
        return *it;
      }
      EntryT* result = sample.get();
      filtered_sample_set_.insert(sample.get());
      sample_storage_.push_back(std::move(sample));
      return result;
    }
    UpdateSummary(sample.get());
    EntryT* result;
    auto it = sample_set_.find(sample.get());
    if (it == sample_set_.end()) {
      result = sample.get();
      sample_set_.insert(sample.get());
      sample_storage_.push_back(std::move(sample));
    } else {
      result = *it;
      MergeSample(*it, sample.get());
    }
    return result;
  }

  EntryT* InsertCallChainSample(std::unique_ptr<EntryT> sample,
                                const std::vector<EntryT*>& callchain) {
    if (sample == nullptr) {
      return nullptr;
    }
    auto it = sample_set_.find(sample.get());
    if (it != sample_set_.end()) {
      EntryT* sample = *it;
      // Process only once for recursive function call.
      if (std::find(callchain.begin(), callchain.end(), sample) != callchain.end()) {
        return sample;
      }
    }
    return InsertSample(std::move(sample));
  }

  void InsertCallChainForSample(EntryT* sample, const std::vector<EntryT*>& callchain,
                                const AccumulateInfoT& acc_info) {
    uint64_t period = GetPeriodForCallChain(acc_info);
    sample->callchain.AddCallChain(callchain, period, [&](const EntryT* s1, const EntryT* s2) {
      return sample_comparator_.IsSameSample(s1, s2);
    });
  }

  void AddCallChainDuplicateInfo() {
    if (build_callchain_) {
      for (EntryT* sample : sample_set_) {
        auto it = callchain_parent_map_.find(sample);
        if (it != callchain_parent_map_.end() && !it->second.has_multiple_parents) {
          sample->callchain.duplicated = true;
        }
      }
    }
  }

  std::set<EntryT*, SampleComparator<EntryT>> sample_set_;
  bool accumulate_callchain_;

 private:
  void UpdateCallChainParentInfo(EntryT* sample, EntryT* parent) {
    if (parent == nullptr) {
      return;
    }
    auto it = callchain_parent_map_.find(sample);
    if (it == callchain_parent_map_.end()) {
      CallChainParentInfo info;
      info.parent = parent;
      info.has_multiple_parents = false;
      callchain_parent_map_[sample] = info;
    } else if (it->second.parent != parent) {
      it->second.has_multiple_parents = true;
    }
  }

  const SampleComparator<EntryT> sample_comparator_;
  // If a Sample/CallChainSample is filtered out, it is stored in filtered_sample_set_,
  // and only used in other EntryT's callchain.
  std::set<EntryT*, SampleComparator<EntryT>> filtered_sample_set_;
  std::vector<std::unique_ptr<EntryT>> sample_storage_;

  struct CallChainParentInfo {
    EntryT* parent;
    bool has_multiple_parents;
  };
  std::unordered_map<EntryT*, CallChainParentInfo> callchain_parent_map_;

  bool use_branch_address_;
  bool build_callchain_;
  bool use_caller_as_callchain_root_;
  std::unique_ptr<OfflineUnwinder> offline_unwinder_;
};

template <typename EntryT>
class SampleTreeSorter {
 public:
  explicit SampleTreeSorter(SampleComparator<EntryT> comparator) : comparator_(comparator) {}

  virtual ~SampleTreeSorter() {}

  void Sort(std::vector<EntryT*>& v, bool sort_callchain) {
    if (sort_callchain) {
      for (auto& sample : v) {
        SortCallChain(sample);
      }
    }
    if (!comparator_.empty()) {
      std::sort(v.begin(), v.end(),
                [this](const EntryT* s1, const EntryT* s2) { return comparator_(s1, s2); });
    }
  }

 protected:
  void SortCallChain(EntryT* sample) { sample->callchain.SortByPeriod(); }

 private:
  SampleComparator<EntryT> comparator_;
};

template <typename EntryT, typename InfoT>
class SampleTreeDisplayer {
 public:
  explicit SampleTreeDisplayer(SampleDisplayer<EntryT, InfoT> displayer) : displayer_(displayer) {}

  virtual ~SampleTreeDisplayer() {}

  void DisplaySamples(FILE* fp, const std::vector<EntryT*>& samples, const InfoT* info) {
    displayer_.SetInfo(info);
    for (const auto& sample : samples) {
      displayer_.AdjustWidth(sample);
    }
    displayer_.PrintNames(fp);
    for (const auto& sample : samples) {
      displayer_.PrintSample(fp, sample);
    }
  }

 private:
  SampleDisplayer<EntryT, InfoT> displayer_;
};

}  // namespace simpleperf

#endif  // SIMPLE_PERF_SAMPLE_TREE_H_
