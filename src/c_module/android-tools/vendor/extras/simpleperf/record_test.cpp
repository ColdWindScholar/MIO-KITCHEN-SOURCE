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

#include "event_attr.h"
#include "event_type.h"
#include "record.h"
#include "record_equal_test.h"

using namespace simpleperf;

// @CddTest = 6.1/C-0-2
class RecordTest : public ::testing::Test {
 protected:
  virtual void SetUp() {
    const EventType* type = FindEventTypeByName("cpu-clock");
    ASSERT_TRUE(type != nullptr);
    event_attr = CreateDefaultPerfEventAttr(*type);
    event_attr.sample_id_all = 1;
  }

  void CheckRecordMatchBinary(Record& record) {
    std::vector<std::unique_ptr<Record>> records =
        ReadRecordsFromBuffer(event_attr, record.BinaryForTestingOnly(), record.size());
    ASSERT_EQ(1u, records.size());
    CheckRecordEqual(record, *records[0]);
  }

  perf_event_attr event_attr;
};

// @CddTest = 6.1/C-0-2
TEST_F(RecordTest, MmapRecordMatchBinary) {
  MmapRecord record(event_attr, true, 1, 2, 0x1000, 0x2000, 0x3000, "MmapRecord", 0);
  CheckRecordMatchBinary(record);
}

// @CddTest = 6.1/C-0-2
TEST_F(RecordTest, CommRecordMatchBinary) {
  CommRecord record(event_attr, 1, 2, "CommRecord", 0, 7);
  CheckRecordMatchBinary(record);
}

// @CddTest = 6.1/C-0-2
TEST_F(RecordTest, SampleRecordMatchBinary) {
  event_attr.sample_type = PERF_SAMPLE_IP | PERF_SAMPLE_TID | PERF_SAMPLE_TIME | PERF_SAMPLE_ID |
                           PERF_SAMPLE_CPU | PERF_SAMPLE_PERIOD | PERF_SAMPLE_CALLCHAIN;
  SampleRecord record(event_attr, 1, 2, 3, 4, 5, 6, 7, {}, {8, 9, 10}, {}, 0);
  CheckRecordMatchBinary(record);
}

// @CddTest = 6.1/C-0-2
TEST_F(RecordTest, SampleRecord_exclude_kernel_callchain) {
  SampleRecord r(event_attr, 0, 1, 0, 0, 0, 0, 0, {}, {}, {}, 0);
  ASSERT_TRUE(r.ExcludeKernelCallChain());

  event_attr.sample_type |= PERF_SAMPLE_CALLCHAIN;
  SampleRecord r1(event_attr, 0, 1, 0, 0, 0, 0, 0, {}, {PERF_CONTEXT_USER, 2}, {}, 0);
  ASSERT_TRUE(r1.ExcludeKernelCallChain());
  ASSERT_EQ(2u, r1.ip_data.ip);
  SampleRecord r2;
  ASSERT_TRUE(
      r2.Parse(event_attr, r1.BinaryForTestingOnly(), r1.BinaryForTestingOnly() + r1.size()));
  ASSERT_EQ(1u, r.ip_data.ip);
  ASSERT_EQ(2u, r2.callchain_data.ip_nr);
  ASSERT_EQ(PERF_CONTEXT_USER, r2.callchain_data.ips[0]);
  ASSERT_EQ(2u, r2.callchain_data.ips[1]);

  SampleRecord r3(event_attr, 0, 1, 0, 0, 0, 0, 0, {}, {1, PERF_CONTEXT_USER, 2}, {}, 0);
  ASSERT_TRUE(r3.ExcludeKernelCallChain());
  ASSERT_EQ(2u, r3.ip_data.ip);
  SampleRecord r4;
  ASSERT_TRUE(
      r4.Parse(event_attr, r3.BinaryForTestingOnly(), r3.BinaryForTestingOnly() + r3.size()));
  ASSERT_EQ(2u, r4.ip_data.ip);
  ASSERT_EQ(3u, r4.callchain_data.ip_nr);
  ASSERT_EQ(PERF_CONTEXT_USER, r4.callchain_data.ips[0]);
  ASSERT_EQ(PERF_CONTEXT_USER, r4.callchain_data.ips[1]);
  ASSERT_EQ(2u, r4.callchain_data.ips[2]);

  SampleRecord r5(event_attr, 0, 1, 0, 0, 0, 0, 0, {}, {1, 2}, {}, 0);
  ASSERT_FALSE(r5.ExcludeKernelCallChain());
  SampleRecord r6(event_attr, 0, 1, 0, 0, 0, 0, 0, {}, {1, 2, PERF_CONTEXT_USER}, {}, 0);
  ASSERT_FALSE(r6.ExcludeKernelCallChain());

  // Process consecutive context values.
  SampleRecord r7(event_attr, 0, 1, 0, 0, 0, 0, 0, {},
                  {1, 2, PERF_CONTEXT_USER, PERF_CONTEXT_USER, 3, 4}, {}, 0);
  r7.header.misc = PERF_RECORD_MISC_KERNEL;
  ASSERT_TRUE(r7.ExcludeKernelCallChain());
  CheckRecordEqual(r7, SampleRecord(event_attr, 0, 3, 0, 0, 0, 0, 0, {},
                                    {PERF_CONTEXT_USER, PERF_CONTEXT_USER, PERF_CONTEXT_USER,
                                     PERF_CONTEXT_USER, 3, 4},
                                    {}, 0));
}

// @CddTest = 6.1/C-0-2
TEST_F(RecordTest, SampleRecord_ReplaceRegAndStackWithCallChain) {
  event_attr.sample_type |= PERF_SAMPLE_CALLCHAIN;
  std::vector<std::vector<uint64_t>> user_ip_tests = {
      {},                     // no userspace ips, just remove stack and reg fields
      {2},                    // add one userspace ip, no need to allocate new binary
      {2, 3, 4, 5, 6, 7, 8},  // add more userspace ips, may need to allocate new binary
  };
  std::vector<uint64_t> stack_size_tests = {0, 8, 1024};

  for (const auto& user_ips : user_ip_tests) {
    std::vector<uint64_t> ips = {1};
    if (!user_ips.empty()) {
      ips.push_back(PERF_CONTEXT_USER);
      ips.insert(ips.end(), user_ips.begin(), user_ips.end());
    }
    SampleRecord expected(event_attr, 0, 1, 2, 3, 4, 5, 6, {}, ips, {}, 0);
    for (size_t stack_size : stack_size_tests) {
      event_attr.sample_type |= PERF_SAMPLE_REGS_USER | PERF_SAMPLE_STACK_USER;
      SampleRecord r(event_attr, 0, 1, 2, 3, 4, 5, 6, {}, {1}, std::vector<char>(stack_size), 10);
      event_attr.sample_type &= ~(PERF_SAMPLE_REGS_USER | PERF_SAMPLE_STACK_USER);
      r.ReplaceRegAndStackWithCallChain(user_ips);
      CheckRecordMatchBinary(r);
      CheckRecordEqual(r, expected);

      // Test a sample with record size > the end of user stack (). See
      // https://lkml.org/lkml/2024/5/28/1224.
      event_attr.sample_type |= PERF_SAMPLE_REGS_USER | PERF_SAMPLE_STACK_USER;
      SampleRecord r2(event_attr, 0, 1, 2, 3, 4, 5, 6, {}, {1}, std::vector<char>(stack_size), 10);

      std::vector<char> big_binary(r2.size() + 72, '\0');
      memcpy(big_binary.data(), r2.Binary(), r2.size());
      perf_event_header header;
      memcpy(&header, big_binary.data(), sizeof(perf_event_header));
      header.size = big_binary.size();
      SampleRecord r3;
      ASSERT_TRUE(r3.Parse(event_attr, big_binary.data(), big_binary.data() + big_binary.size()));
      event_attr.sample_type &= ~(PERF_SAMPLE_REGS_USER | PERF_SAMPLE_STACK_USER);
      r3.ReplaceRegAndStackWithCallChain(user_ips);
      CheckRecordMatchBinary(r3);
      CheckRecordEqual(r3, expected);
    }
  }
}

// @CddTest = 6.1/C-0-2
TEST_F(RecordTest, SampleRecord_UpdateUserCallChain) {
  event_attr.sample_type |= PERF_SAMPLE_CALLCHAIN;
  SampleRecord r(event_attr, 0, 1, 2, 3, 4, 5, 6, {}, {1, PERF_CONTEXT_USER, 2}, {}, 0);
  r.UpdateUserCallChain({3, 4, 5});
  CheckRecordMatchBinary(r);
  SampleRecord expected(event_attr, 0, 1, 2, 3, 4, 5, 6, {}, {1, PERF_CONTEXT_USER, 3, 4, 5}, {},
                        0);
  CheckRecordEqual(r, expected);
}

// @CddTest = 6.1/C-0-2
TEST_F(RecordTest, SampleRecord_AdjustCallChainGeneratedByKernel) {
  event_attr.sample_type |= PERF_SAMPLE_CALLCHAIN | PERF_SAMPLE_REGS_USER | PERF_SAMPLE_STACK_USER;
  SampleRecord r(event_attr, 0, 1, 2, 3, 4, 5, 6, {}, {1, 5, 0, PERF_CONTEXT_USER, 6, 0}, {}, 0);
  r.header.misc = PERF_RECORD_MISC_KERNEL;
  r.AdjustCallChainGeneratedByKernel();
  uint64_t adjustValue = (GetTargetArch() == ARCH_ARM || GetTargetArch() == ARCH_ARM64) ? 2 : 1;
  SampleRecord expected(event_attr, 0, 1, 2, 3, 4, 5, 6, {},
                        {1, 5 - adjustValue, PERF_CONTEXT_KERNEL, PERF_CONTEXT_USER,
                         6 - adjustValue, PERF_CONTEXT_USER},
                        {}, 0);
  expected.header.misc = PERF_RECORD_MISC_KERNEL;
  CheckRecordEqual(r, expected);
}

// @CddTest = 6.1/C-0-2
TEST_F(RecordTest, SampleRecord_PerfSampleReadData) {
  event_attr.sample_type |= PERF_SAMPLE_READ;
  event_attr.read_format =
      PERF_FORMAT_TOTAL_TIME_ENABLED | PERF_FORMAT_TOTAL_TIME_RUNNING | PERF_FORMAT_ID;
  PerfSampleReadType read_data;
  read_data.time_enabled = 1000;
  read_data.time_running = 500;
  read_data.counts = {100};
  read_data.ids = {200};
  SampleRecord r(event_attr, 0, 1, 2, 3, 4, 5, 6, read_data, {}, {}, 0);
  ASSERT_EQ(read_data.time_enabled, r.read_data.time_enabled);
  ASSERT_EQ(read_data.time_running, r.read_data.time_running);
  ASSERT_TRUE(read_data.counts == r.read_data.counts);
  ASSERT_TRUE(read_data.ids == r.read_data.ids);
  CheckRecordMatchBinary(r);
  event_attr.read_format |= PERF_FORMAT_GROUP;
  read_data.counts = {100, 200, 300, 400};
  read_data.ids = {500, 600, 700, 800};
  SampleRecord r2(event_attr, 0, 1, 2, 3, 4, 5, 6, read_data, {}, {}, 0);
  ASSERT_EQ(read_data.time_enabled, r2.read_data.time_enabled);
  ASSERT_EQ(read_data.time_running, r2.read_data.time_running);
  ASSERT_TRUE(read_data.counts == r2.read_data.counts);
  ASSERT_TRUE(read_data.ids == r2.read_data.ids);
  CheckRecordMatchBinary(r2);
}

// @CddTest = 6.1/C-0-2
TEST_F(RecordTest, CommRecord) {
  CommRecord r(event_attr, 1, 2, "init_name", 3, 4);
  size_t record_size = r.size();
  std::string new_name = "a_much_longer_name";
  r.SetCommandName(new_name);
  ASSERT_EQ(r.size(), record_size + 8);
  ASSERT_EQ(std::string(r.comm), new_name);
  ASSERT_EQ(r.data->pid, 1u);
  ASSERT_EQ(r.data->tid, 2u);
  ASSERT_EQ(r.sample_id.id_data.id, 3u);
  ASSERT_EQ(r.sample_id.time_data.time, 4u);
  CheckRecordMatchBinary(r);
}

// @CddTest = 6.1/C-0-2
TEST_F(RecordTest, DebugRecord) {
  DebugRecord r(1234, "hello");
  ASSERT_EQ(r.size() % sizeof(uint64_t), 0);
  ASSERT_EQ(r.Timestamp(), 1234);
  ASSERT_STREQ(r.s, "hello");
  CheckRecordMatchBinary(r);
}
