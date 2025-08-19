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

#include <gtest/gtest.h>

#include "sample_tree.h"
#include "thread_tree.h"

using namespace simpleperf;

namespace {

struct SampleEntry {
  int pid;
  int tid;
  const char* thread_comm;
  std::string dso_name;
  uint64_t map_start_addr;
  size_t sample_count;

  SampleEntry(int pid, int tid, const char* thread_comm, const std::string& dso_name,
              uint64_t map_start_addr, size_t sample_count = 1u)
      : pid(pid),
        tid(tid),
        thread_comm(thread_comm),
        dso_name(dso_name),
        map_start_addr(map_start_addr),
        sample_count(sample_count) {}
};

BUILD_COMPARE_VALUE_FUNCTION(TestComparePid, pid);
BUILD_COMPARE_VALUE_FUNCTION(TestCompareTid, tid);
BUILD_COMPARE_STRING_FUNCTION(TestCompareDsoName, dso_name.c_str());
BUILD_COMPARE_VALUE_FUNCTION(TestCompareMapStartAddr, map_start_addr);

class TestSampleComparator : public SampleComparator<SampleEntry> {
 public:
  TestSampleComparator() {
    AddCompareFunction(TestComparePid);
    AddCompareFunction(TestCompareTid);
    AddCompareFunction(CompareComm);
    AddCompareFunction(TestCompareDsoName);
    AddCompareFunction(TestCompareMapStartAddr);
  }
};

class TestSampleTreeBuilder : public SampleTreeBuilder<SampleEntry, int> {
 public:
  explicit TestSampleTreeBuilder(ThreadTree* thread_tree)
      : SampleTreeBuilder(TestSampleComparator()), thread_tree_(thread_tree) {}

  void AddSample(int pid, int tid, uint64_t ip, bool in_kernel) {
    const ThreadEntry* thread = thread_tree_->FindThreadOrNew(pid, tid);
    const MapEntry* map = thread_tree_->FindMap(thread, ip, in_kernel);
    InsertSample(std::unique_ptr<SampleEntry>(
        new SampleEntry(pid, tid, thread->comm, map->dso->Path(), map->start_addr)));
  }

 protected:
  SampleEntry* CreateSample(const SampleRecord&, bool, int*) override { return nullptr; }
  SampleEntry* CreateBranchSample(const SampleRecord&, const BranchStackItemType&) override {
    return nullptr;
  };
  SampleEntry* CreateCallChainSample(const ThreadEntry*, const SampleEntry*, uint64_t, bool,
                                     const std::vector<SampleEntry*>&, const int&) override {
    return nullptr;
  }
  const ThreadEntry* GetThreadOfSample(SampleEntry*) override { return nullptr; }
  uint64_t GetPeriodForCallChain(const int&) override { return 0; }
  void MergeSample(SampleEntry* sample1, SampleEntry* sample2) override {
    sample1->sample_count += sample2->sample_count;
  }

 private:
  ThreadTree* thread_tree_;
};

static void SampleMatchExpectation(const SampleEntry& sample, const SampleEntry& expected,
                                   bool* has_error) {
  *has_error = true;
  ASSERT_EQ(expected.pid, sample.pid);
  ASSERT_EQ(expected.tid, sample.tid);
  ASSERT_STREQ(expected.thread_comm, sample.thread_comm);
  ASSERT_EQ(expected.dso_name, sample.dso_name);
  ASSERT_EQ(expected.map_start_addr, sample.map_start_addr);
  ASSERT_EQ(expected.sample_count, sample.sample_count);
  *has_error = false;
}

static void CheckSamples(const std::vector<SampleEntry*>& samples,
                         const std::vector<SampleEntry>& expected_samples) {
  ASSERT_EQ(samples.size(), expected_samples.size());
  for (size_t i = 0; i < samples.size(); ++i) {
    bool has_error;
    SampleMatchExpectation(*samples[i], expected_samples[i], &has_error);
    ASSERT_FALSE(has_error) << "Error matching sample at pos " << i;
  }
}
}  // namespace

class SampleTreeTest : public testing::Test {
 protected:
  virtual void SetUp() {
    thread_tree.SetThreadName(1, 1, "p1t1");
    thread_tree.SetThreadName(1, 11, "p1t11");
    thread_tree.SetThreadName(2, 2, "p2t2");
    thread_tree.AddThreadMap(1, 1, 1, 5, 0, "process1_thread1");
    thread_tree.AddThreadMap(1, 11, 6, 5, 0, "process1_thread1_map2");
    thread_tree.AddThreadMap(2, 2, 1, 20, 0, "process2_thread2");
    thread_tree.AddKernelMap(10, 20, 0, "kernel");
    sample_tree_builder.reset(new TestSampleTreeBuilder(&thread_tree));
  }

  void CheckSamples(const std::vector<SampleEntry>& expected_samples) {
    ::CheckSamples(sample_tree_builder->GetSamples(), expected_samples);
  }

  ThreadTree thread_tree;
  std::unique_ptr<TestSampleTreeBuilder> sample_tree_builder;
};

// @CddTest = 6.1/C-0-2
TEST_F(SampleTreeTest, ip_in_map) {
  sample_tree_builder->AddSample(1, 1, 1, false);
  sample_tree_builder->AddSample(1, 1, 2, false);
  sample_tree_builder->AddSample(1, 1, 5, false);
  std::vector<SampleEntry> expected_samples = {
      SampleEntry(1, 1, "p1t1", "process1_thread1", 1, 3),
  };
  CheckSamples(expected_samples);
}

// @CddTest = 6.1/C-0-2
TEST_F(SampleTreeTest, different_pid) {
  sample_tree_builder->AddSample(1, 1, 1, false);
  sample_tree_builder->AddSample(2, 2, 1, false);
  std::vector<SampleEntry> expected_samples = {
      SampleEntry(1, 1, "p1t1", "process1_thread1", 1, 1),
      SampleEntry(2, 2, "p2t2", "process2_thread2", 1, 1),
  };
  CheckSamples(expected_samples);
}

// @CddTest = 6.1/C-0-2
TEST_F(SampleTreeTest, different_tid) {
  sample_tree_builder->AddSample(1, 1, 1, false);
  sample_tree_builder->AddSample(1, 11, 1, false);
  std::vector<SampleEntry> expected_samples = {
      SampleEntry(1, 1, "p1t1", "process1_thread1", 1, 1),
      SampleEntry(1, 11, "p1t11", "process1_thread1", 1, 1),
  };
  CheckSamples(expected_samples);
}

// @CddTest = 6.1/C-0-2
TEST_F(SampleTreeTest, different_comm) {
  sample_tree_builder->AddSample(1, 1, 1, false);
  thread_tree.SetThreadName(1, 1, "p1t1_comm2");
  sample_tree_builder->AddSample(1, 1, 1, false);
  std::vector<SampleEntry> expected_samples = {
      SampleEntry(1, 1, "p1t1", "process1_thread1", 1, 1),
      SampleEntry(1, 1, "p1t1_comm2", "process1_thread1", 1, 1),
  };
  CheckSamples(expected_samples);
}

// @CddTest = 6.1/C-0-2
TEST_F(SampleTreeTest, different_map) {
  sample_tree_builder->AddSample(1, 1, 1, false);
  sample_tree_builder->AddSample(1, 1, 6, false);
  std::vector<SampleEntry> expected_samples = {
      SampleEntry(1, 1, "p1t1", "process1_thread1", 1, 1),
      SampleEntry(1, 1, "p1t1", "process1_thread1_map2", 6, 1),
  };
  CheckSamples(expected_samples);
}

// @CddTest = 6.1/C-0-2
TEST_F(SampleTreeTest, unmapped_sample) {
  sample_tree_builder->AddSample(1, 1, 0, false);
  sample_tree_builder->AddSample(1, 1, 31, false);
  sample_tree_builder->AddSample(1, 1, 70, false);
  // Match the unknown map.
  std::vector<SampleEntry> expected_samples = {
      SampleEntry(1, 1, "p1t1", "unknown", 0, 3),
  };
  CheckSamples(expected_samples);
}

// @CddTest = 6.1/C-0-2
TEST_F(SampleTreeTest, map_kernel) {
  sample_tree_builder->AddSample(1, 1, 10, true);
  sample_tree_builder->AddSample(1, 1, 10, false);
  std::vector<SampleEntry> expected_samples = {
      SampleEntry(1, 1, "p1t1", "kernel", 10, 1),
      SampleEntry(1, 1, "p1t1", "process1_thread1_map2", 6, 1),
  };
  CheckSamples(expected_samples);
}

// @CddTest = 6.1/C-0-2
TEST(sample_tree, overlapped_map) {
  ThreadTree thread_tree;
  TestSampleTreeBuilder sample_tree_builder(&thread_tree);
  thread_tree.SetThreadName(1, 1, "thread1");
  thread_tree.AddThreadMap(1, 1, 1, 10, 0, "map1");  // Add map 1.
  sample_tree_builder.AddSample(1, 1, 5, false);     // Hit map 1.
  thread_tree.AddThreadMap(1, 1, 5, 20, 0, "map2");  // Add map 2.
  sample_tree_builder.AddSample(1, 1, 6, false);     // Hit map 2.
  sample_tree_builder.AddSample(1, 1, 4, false);     // Hit map 1.
  thread_tree.AddThreadMap(1, 1, 2, 7, 0, "map3");   // Add map 3.
  sample_tree_builder.AddSample(1, 1, 7, false);     // Hit map 3.
  sample_tree_builder.AddSample(1, 1, 10, false);    // Hit map 2.

  std::vector<SampleEntry> expected_samples = {
      SampleEntry(1, 1, "thread1", "map1", 1, 2),
      SampleEntry(1, 1, "thread1", "map2", 5, 1),
      SampleEntry(1, 1, "thread1", "map2", 9, 1),
      SampleEntry(1, 1, "thread1", "map3", 2, 1),
  };
  CheckSamples(sample_tree_builder.GetSamples(), expected_samples);
}

// @CddTest = 6.1/C-0-2
TEST(thread_tree, symbol_ULLONG_MAX) {
  ThreadTree thread_tree;
  thread_tree.ShowIpForUnknownSymbol();
  ASSERT_TRUE(thread_tree.FindKernelSymbol(ULLONG_MAX) != nullptr);
}
