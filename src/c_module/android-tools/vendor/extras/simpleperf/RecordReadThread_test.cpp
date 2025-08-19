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

#include "RecordReadThread.h"

#include <gmock/gmock.h>
#include <gtest/gtest.h>

#include "event_type.h"
#include "get_test_data.h"
#include "record.h"
#include "record_equal_test.h"
#include "record_file.h"

using ::testing::_;
using ::testing::Eq;
using ::testing::Return;
using ::testing::Truly;

using namespace simpleperf;

// @CddTest = 6.1/C-0-2
class RecordBufferTest : public ::testing::Test {
 protected:
  void PushRecord(uint32_t type, size_t size) {
    char* p = buffer_->AllocWriteSpace(size);
    ASSERT_NE(p, nullptr);
    perf_event_header header;
    header.type = type;
    header.size = size;
    memcpy(p, &header, sizeof(header));
    buffer_->FinishWrite();
  }

  void PopRecord(uint32_t type, uint32_t size) {
    char* p = buffer_->GetCurrentRecord();
    ASSERT_NE(p, nullptr);
    perf_event_header header;
    memcpy(&header, p, sizeof(header));
    ASSERT_EQ(header.type, type);
    ASSERT_EQ(header.size, size);
    buffer_->MoveToNextRecord();
  }

  std::unique_ptr<RecordBuffer> buffer_;
};

// @CddTest = 6.1/C-0-2
TEST_F(RecordBufferTest, fifo) {
  for (size_t loop = 0; loop < 10; ++loop) {
    buffer_.reset(new RecordBuffer(sizeof(perf_event_header) * 10));
    size_t record_size = sizeof(perf_event_header) + loop;
    size_t max_records_in_buffer = (buffer_->size() - 2 * record_size + 1) / record_size;
    uint32_t write_id = 0;
    uint32_t read_id = 0;
    while (read_id < 100) {
      while (write_id < 100 && write_id - read_id < max_records_in_buffer) {
        ASSERT_NO_FATAL_FAILURE(PushRecord(write_id++, record_size));
      }
      ASSERT_NO_FATAL_FAILURE(PopRecord(read_id++, record_size));
    }
  }
}

// @CddTest = 6.1/C-0-2
TEST(RecordParser, smoke) {
  std::unique_ptr<RecordFileReader> reader =
      RecordFileReader::CreateInstance(GetTestData(PERF_DATA_NO_UNWIND));
  ASSERT_TRUE(reader);
  RecordParser parser(reader->AttrSection()[0].attr);
  auto process_record = [&](std::unique_ptr<Record> record) {
    if (record->type() == PERF_RECORD_MMAP || record->type() == PERF_RECORD_COMM ||
        record->type() == PERF_RECORD_FORK || record->type() == PERF_RECORD_SAMPLE) {
      perf_event_header header;
      memcpy(&header, record->Binary(), sizeof(header));
      auto read_record_fn = [&](size_t pos, size_t size, void* dest) {
        memcpy(dest, record->Binary() + pos, size);
      };
      size_t pos = parser.GetTimePos(header);
      ASSERT_NE(0u, pos);
      uint64_t time;
      read_record_fn(pos, sizeof(time), &time);
      ASSERT_EQ(record->Timestamp(), time);
      if (record->type() == PERF_RECORD_SAMPLE) {
        auto sr = static_cast<SampleRecord*>(record.get());
        pos = parser.GetStackSizePos(read_record_fn);
        ASSERT_NE(0u, pos);
        uint64_t stack_size;
        read_record_fn(pos, sizeof(stack_size), &stack_size);
        ASSERT_EQ(sr->stack_user_data.size, stack_size);

        // Test pid pos in sample records.
        pos = parser.GetPidPosInSampleRecord();
        uint32_t pid;
        read_record_fn(pos, sizeof(pid), &pid);
        ASSERT_EQ(sr->tid_data.pid, pid);
      }
    }
  };
  ASSERT_TRUE(reader->ReadDataSection([&](std::unique_ptr<Record> record) {
    process_record(std::move(record));
    return !HasFatalFailure();
  }));
}

// @CddTest = 6.1/C-0-2
TEST(RecordParser, GetStackSizePos_with_PerfSampleReadType) {
  const EventType* type = FindEventTypeByName("cpu-clock");
  ASSERT_TRUE(type != nullptr);
  perf_event_attr event_attr = CreateDefaultPerfEventAttr(*type);
  event_attr.sample_type = PERF_SAMPLE_READ | PERF_SAMPLE_STACK_USER;
  event_attr.read_format =
      PERF_FORMAT_ID | PERF_FORMAT_TOTAL_TIME_ENABLED | PERF_FORMAT_TOTAL_TIME_RUNNING;
  uint64_t nr = 10;
  RecordParser parser(event_attr);
  size_t pos =
      parser.GetStackSizePos([&](size_t, size_t size, void* dest) { memcpy(dest, &nr, size); });
  ASSERT_EQ(pos, sizeof(perf_event_header) + 4 * sizeof(uint64_t));

  event_attr.read_format |= PERF_FORMAT_GROUP;
  RecordParser parser2(event_attr);
  pos = parser2.GetStackSizePos([&](size_t, size_t size, void* dest) { memcpy(dest, &nr, size); });
  ASSERT_EQ(pos, sizeof(perf_event_header) + (nr * 2 + 3) * sizeof(uint64_t));
}

struct MockEventFd : public EventFd {
  MockEventFd(const perf_event_attr& attr, int cpu, char* buffer, size_t buffer_size,
              bool mock_aux_buffer)
      : EventFd(attr, -1, "", 0, cpu) {
    mmap_data_buffer_ = buffer;
    mmap_data_buffer_size_ = buffer_size;
    if (mock_aux_buffer) {
      aux_buffer_size_ = 1;  // Make HasAuxBuffer() return true.
    }
  }

  MOCK_METHOD2(CreateMappedBuffer, bool(size_t, bool));
  MOCK_METHOD0(DestroyMappedBuffer, void());
  MOCK_METHOD2(StartPolling, bool(IOEventLoop&, const std::function<bool()>&));
  MOCK_METHOD0(StopPolling, bool());
  MOCK_METHOD1(GetAvailableMmapDataSize, size_t(size_t&));
  MOCK_METHOD1(DiscardMmapData, void(size_t));

  MOCK_METHOD2(CreateAuxBuffer, bool(size_t, bool));
  MOCK_METHOD0(DestroyAuxBuffer, void());
  MOCK_METHOD4(GetAvailableAuxData, uint64_t(char**, size_t*, char**, size_t*));
  MOCK_METHOD1(DiscardAuxData, void(size_t));
};

static perf_event_attr CreateFakeEventAttr() {
  const EventType* type = FindEventTypeByName("cpu-clock");
  CHECK(type != nullptr);
  return CreateDefaultPerfEventAttr(*type);
}

static std::vector<std::unique_ptr<Record>> CreateFakeRecords(const perf_event_attr& attr,
                                                              size_t record_count,
                                                              size_t stack_size,
                                                              size_t dyn_stack_size) {
  std::vector<std::unique_ptr<Record>> records;
  for (size_t i = 0; i < record_count; ++i) {
    SampleRecord* r = new SampleRecord(attr, i, i + 1, i + 2, i + 3, i + 4, i + 5, i + 6, {}, {},
                                       std::vector<char>(stack_size), dyn_stack_size);
    records.emplace_back(r);
  }
  return records;
}

static size_t AlignToPowerOfTwo(size_t value) {
  size_t result = 1;
  while (result < value) {
    result <<= 1;
  }
  return result;
}

static inline std::function<bool(size_t&)> SetArg(size_t value) {
  return [value](size_t& arg) {
    arg = value;
    return true;
  };
}

// @CddTest = 6.1/C-0-2
TEST(KernelRecordReader, smoke) {
  // 1. Create fake records.
  perf_event_attr attr = CreateFakeEventAttr();
  std::vector<std::unique_ptr<Record>> records = CreateFakeRecords(attr, 10, 0, 0);
  // 2. Create a buffer whose size is power of two.
  size_t data_size = records.size() * records[0]->size();
  std::vector<char> buffer(AlignToPowerOfTwo(data_size));
  // 3. Copy record data into the buffer. Since a record in a kernel buffer can be wrapped around
  // to the beginning of the buffer, create the case in the first record.
  size_t data_pos = buffer.size() - 4;
  memcpy(&buffer[data_pos], records[0]->Binary(), 4);
  memcpy(&buffer[0], records[0]->Binary() + 4, records[0]->size() - 4);
  size_t pos = records[0]->size() - 4;
  for (size_t i = 1; i < records.size(); ++i) {
    memcpy(&buffer[pos], records[i]->Binary(), records[i]->size());
    pos += records[i]->size();
  }
  // Read records using KernelRecordReader.
  MockEventFd event_fd(attr, 0, buffer.data(), buffer.size(), false);

  EXPECT_CALL(event_fd, GetAvailableMmapDataSize(Truly(SetArg(data_pos))))
      .Times(1)
      .WillOnce(Return(data_size));
  EXPECT_CALL(event_fd, DiscardMmapData(Eq(data_size))).Times(1);
  KernelRecordReader reader(&event_fd);
  RecordParser parser(attr);
  ASSERT_TRUE(reader.GetDataFromKernelBuffer());
  for (size_t i = 0; i < records.size(); ++i) {
    ASSERT_TRUE(reader.MoveToNextRecord(parser));
    ASSERT_EQ(reader.RecordHeader().type, records[i]->type());
    ASSERT_EQ(reader.RecordHeader().size, records[i]->size());
    ASSERT_EQ(reader.RecordTime(), records[i]->Timestamp());
    std::vector<char> data(reader.RecordHeader().size);
    reader.ReadRecord(0, data.size(), &data[0]);
    ASSERT_EQ(0, memcmp(&data[0], records[i]->Binary(), records[i]->size()));
  }
  ASSERT_FALSE(reader.MoveToNextRecord(parser));
}

// @CddTest = 6.1/C-0-2
class RecordReadThreadTest : public ::testing::Test {
 protected:
  std::vector<EventFd*> CreateFakeEventFds(const perf_event_attr& attr, size_t event_fd_count) {
    size_t records_per_fd = records_.size() / event_fd_count;
    buffers_.clear();
    buffers_.resize(event_fd_count);
    for (size_t i = 0; i < records_.size(); ++i) {
      std::vector<char>& buffer = buffers_[i % event_fd_count];
      buffer.insert(buffer.end(), records_[i]->Binary(),
                    records_[i]->Binary() + records_[i]->size());
    }
    size_t data_size = records_per_fd * records_[0]->size();
    size_t buffer_size = AlignToPowerOfTwo(data_size);
    for (auto& buffer : buffers_) {
      buffer.resize(buffer_size);
    }
    event_fds_.resize(event_fd_count);
    for (size_t i = 0; i < event_fd_count; ++i) {
      event_fds_[i].reset(new MockEventFd(attr, i, buffers_[i].data(), buffer_size, false));
      EXPECT_CALL(*event_fds_[i], CreateMappedBuffer(_, _)).Times(1).WillOnce(Return(true));
      EXPECT_CALL(*event_fds_[i], StartPolling(_, _)).Times(1).WillOnce(Return(true));
      EXPECT_CALL(*event_fds_[i], GetAvailableMmapDataSize(Truly(SetArg(0))))
          .Times(1)
          .WillOnce(Return(data_size));
      EXPECT_CALL(*event_fds_[i], DiscardMmapData(Eq(data_size))).Times(1);
      EXPECT_CALL(*event_fds_[i], StopPolling()).Times(1).WillOnce(Return(true));
      EXPECT_CALL(*event_fds_[i], DestroyMappedBuffer()).Times(1);
      EXPECT_CALL(*event_fds_[i], DestroyAuxBuffer()).Times(1);
    }
    std::vector<EventFd*> result;
    for (auto& fd : event_fds_) {
      result.push_back(fd.get());
    }
    return result;
  }

  std::vector<std::unique_ptr<Record>> records_;
  std::vector<std::vector<char>> buffers_;
  std::vector<std::unique_ptr<MockEventFd>> event_fds_;
};

// @CddTest = 6.1/C-0-2
TEST_F(RecordReadThreadTest, handle_cmds) {
  perf_event_attr attr = CreateFakeEventAttr();
  records_ = CreateFakeRecords(attr, 2, 0, 0);
  std::vector<EventFd*> event_fds = CreateFakeEventFds(attr, 2);
  RecordReadThread thread(128 * 1024, event_fds[0]->attr(), 1, 1, 0);
  IOEventLoop loop;
  bool has_notify = false;
  auto callback = [&]() {
    has_notify = true;
    return loop.ExitLoop();
  };
  ASSERT_TRUE(thread.RegisterDataCallback(loop, callback));
  ASSERT_TRUE(thread.AddEventFds(event_fds));
  ASSERT_TRUE(thread.SyncKernelBuffer());
  ASSERT_TRUE(loop.RunLoop());
  ASSERT_TRUE(has_notify);
  ASSERT_TRUE(thread.GetRecord());
  ASSERT_TRUE(thread.RemoveEventFds(event_fds));
  ASSERT_TRUE(thread.StopReadThread());
}

// @CddTest = 6.1/C-0-2
TEST_F(RecordReadThreadTest, read_records) {
  perf_event_attr attr = CreateFakeEventAttr();
  RecordReadThread thread(128 * 1024, attr, 1, 1, 0);
  IOEventLoop loop;
  size_t record_index;
  auto callback = [&]() {
    while (true) {
      std::unique_ptr<Record> r = thread.GetRecord();
      if (!r) {
        break;
      }
      std::unique_ptr<Record>& expected = records_[record_index++];
      if (r->size() != expected->size() ||
          memcmp(r->Binary(), expected->Binary(), r->size()) != 0) {
        return false;
      }
    }
    return loop.ExitLoop();
  };
  ASSERT_TRUE(thread.RegisterDataCallback(loop, callback));
  for (size_t event_fd_count = 1; event_fd_count < 10; ++event_fd_count) {
    records_ = CreateFakeRecords(attr, event_fd_count * 10, 0, 0);
    std::vector<EventFd*> event_fds = CreateFakeEventFds(attr, event_fd_count);
    record_index = 0;
    ASSERT_TRUE(thread.AddEventFds(event_fds));
    ASSERT_TRUE(thread.SyncKernelBuffer());
    ASSERT_TRUE(loop.RunLoop());
    ASSERT_EQ(record_index, records_.size());
    ASSERT_TRUE(thread.RemoveEventFds(event_fds));
  }
}

// @CddTest = 6.1/C-0-2
TEST_F(RecordReadThreadTest, process_sample_record) {
  perf_event_attr attr = CreateFakeEventAttr();
  attr.sample_type |= PERF_SAMPLE_STACK_USER;
  attr.sample_stack_user = 64 * 1024;
  size_t record_buffer_size = 128 * 1024;
  RecordReadThread thread(record_buffer_size, attr, 1, 1, 0);
  IOEventLoop loop;
  ASSERT_TRUE(thread.RegisterDataCallback(loop, []() { return true; }));

  auto read_record = [&](std::unique_ptr<Record>& r) {
    std::vector<EventFd*> event_fds = CreateFakeEventFds(attr, 1);
    ASSERT_TRUE(thread.AddEventFds(event_fds));
    ASSERT_TRUE(thread.SyncKernelBuffer());
    ASSERT_TRUE(thread.RemoveEventFds(event_fds));
    r = thread.GetRecord();
  };

  // When the free space in record buffer is above low level, only invalid stack data in sample
  // records is removed.
  thread.SetBufferLevels(0, 0);
  records_ = CreateFakeRecords(attr, 1, 8192, 8192);
  std::unique_ptr<Record> r;
  read_record(r);
  ASSERT_TRUE(r);
  SampleRecord* sr = static_cast<SampleRecord*>(r.get());
  ASSERT_EQ(sr->stack_user_data.size, 8192u);
  ASSERT_EQ(sr->stack_user_data.dyn_size, 8192u);
  records_ = CreateFakeRecords(attr, 1, 8192, 4096);
  read_record(r);
  ASSERT_TRUE(r);
  sr = static_cast<SampleRecord*>(r.get());
  ASSERT_EQ(sr->stack_user_data.size, 4096u);
  ASSERT_EQ(sr->stack_user_data.dyn_size, 4096u);

  // When the free space in record buffer is below low level but above critical level, only
  // 1K stack data in sample records is left.
  thread.SetBufferLevels(record_buffer_size, 0);
  read_record(r);
  ASSERT_TRUE(r);
  sr = static_cast<SampleRecord*>(r.get());
  ASSERT_EQ(sr->stack_user_data.size, 1024u);
  ASSERT_EQ(sr->stack_user_data.dyn_size, 1024u);

  // When the free space in record buffer is below critical level, sample records are dropped.
  thread.SetBufferLevels(record_buffer_size, record_buffer_size);
  read_record(r);
  ASSERT_FALSE(r);
  ASSERT_EQ(thread.GetStat().userspace_lost_samples, 1u);
  ASSERT_EQ(thread.GetStat().userspace_lost_non_samples, 0u);
  ASSERT_EQ(thread.GetStat().userspace_truncated_stack_samples, 1u);
}

// Test that the data notification exists until the RecordBuffer is empty. So we can read all
// records even if reading one record at a time.
// @CddTest = 6.1/C-0-2
TEST_F(RecordReadThreadTest, has_data_notification_until_buffer_empty) {
  perf_event_attr attr = CreateFakeEventAttr();
  RecordReadThread thread(128 * 1024, attr, 1, 1, 0);
  IOEventLoop loop;
  size_t record_index = 0;
  auto read_one_record = [&]() {
    std::unique_ptr<Record> r = thread.GetRecord();
    if (!r) {
      return loop.ExitLoop();
    }
    std::unique_ptr<Record>& expected = records_[record_index++];
    if (r->size() != expected->size() || memcmp(r->Binary(), expected->Binary(), r->size()) != 0) {
      return false;
    }
    return true;
  };
  ASSERT_TRUE(thread.RegisterDataCallback(loop, read_one_record));
  records_ = CreateFakeRecords(attr, 2, 0, 0);
  std::vector<EventFd*> event_fds = CreateFakeEventFds(attr, 1);
  ASSERT_TRUE(thread.AddEventFds(event_fds));
  ASSERT_TRUE(thread.SyncKernelBuffer());
  ASSERT_TRUE(loop.RunLoop());
  ASSERT_EQ(record_index, records_.size());
  ASSERT_TRUE(thread.RemoveEventFds(event_fds));
}

// @CddTest = 6.1/C-0-2
TEST_F(RecordReadThreadTest, no_truncated_samples) {
  perf_event_attr attr = CreateFakeEventAttr();
  attr.sample_type |= PERF_SAMPLE_STACK_USER;
  attr.sample_stack_user = 64 * 1024;
  RecordReadThread thread(128 * 1024, attr, 1, 1, 0, false);
  IOEventLoop loop;
  ASSERT_TRUE(thread.RegisterDataCallback(loop, []() { return true; }));
  const size_t total_samples = 100;
  records_ = CreateFakeRecords(attr, total_samples, 8 * 1024, 8 * 1024);
  std::vector<EventFd*> event_fds = CreateFakeEventFds(attr, 1);
  ASSERT_TRUE(thread.AddEventFds(event_fds));
  ASSERT_TRUE(thread.SyncKernelBuffer());
  ASSERT_TRUE(thread.RemoveEventFds(event_fds));
  size_t received_samples = 0;
  while (thread.GetRecord()) {
    received_samples++;
  }
  ASSERT_GT(received_samples, 0u);
  ASSERT_GT(thread.GetStat().userspace_lost_samples, 0u);
  ASSERT_EQ(thread.GetStat().userspace_lost_samples, total_samples - received_samples);
  ASSERT_EQ(thread.GetStat().userspace_truncated_stack_samples, 0u);
}

// @CddTest = 6.1/C-0-2
TEST_F(RecordReadThreadTest, exclude_perf) {
  perf_event_attr attr = CreateFakeEventAttr();
  attr.sample_type |= PERF_SAMPLE_STACK_USER;
  size_t stack_size = 1024;
  attr.sample_stack_user = stack_size;
  records_.emplace_back(new SampleRecord(attr, 0, 1, getpid(), 3, 4, 5, 6, {}, {},
                                         std::vector<char>(stack_size), stack_size));
  records_.emplace_back(new SampleRecord(attr, 0, 1, getpid() + 1, 3, 4, 5, 6, {}, {},
                                         std::vector<char>(stack_size), stack_size));

  auto read_records = [&](RecordReadThread& thread, std::vector<std::unique_ptr<Record>>& records) {
    records.clear();
    std::vector<EventFd*> event_fds = CreateFakeEventFds(attr, 1);
    ASSERT_TRUE(thread.AddEventFds(event_fds));
    ASSERT_TRUE(thread.SyncKernelBuffer());
    ASSERT_TRUE(thread.RemoveEventFds(event_fds));
    while (auto r = thread.GetRecord()) {
      records.emplace_back(std::move(r));
    }
  };

  // By default, no samples are excluded.
  RecordReadThread thread(128 * 1024, attr, 1, 1, 0);
  IOEventLoop loop;
  ASSERT_TRUE(thread.RegisterDataCallback(loop, []() { return true; }));
  std::vector<std::unique_ptr<Record>> received_records;
  read_records(thread, received_records);
  ASSERT_EQ(received_records.size(), 2);
  CheckRecordEqual(*received_records[0], *records_[0]);
  CheckRecordEqual(*received_records[1], *records_[1]);

  // With exclude_perf, the first sample is excluded.
  RecordReadThread thread2(128 * 1024, attr, 1, 1, 0, true, true);
  ASSERT_TRUE(thread2.RegisterDataCallback(loop, []() { return true; }));
  read_records(thread2, received_records);
  ASSERT_EQ(received_records.size(), 1);
  CheckRecordEqual(*received_records[0], *records_[1]);
}

struct FakeAuxData {
  std::vector<char> buf1;
  std::vector<char> buf2;
  std::vector<char> pad;
  bool lost;

  FakeAuxData(size_t buf1_size, size_t buf2_size, char c, size_t pad_size, bool lost)
      : buf1(buf1_size, c), buf2(buf2_size, c), pad(pad_size, 0), lost(lost) {}
};

// @CddTest = 6.1/C-0-2
TEST_F(RecordReadThreadTest, read_aux_data) {
  ScopedEventTypes scoped_types("cs-etm,0,0");
  const EventType* type = FindEventTypeByName("cs-etm");
  ASSERT_TRUE(type != nullptr);
  std::vector<FakeAuxData> aux_data;
  aux_data.emplace_back(40, 0, '0', 0, false);   // one buffer
  aux_data.emplace_back(40, 40, '1', 0, false);  // two buffers
  aux_data.emplace_back(36, 0, '2', 4, false);   // one buffer needs padding to 8 bytes alignment
  // one buffer too big to fit in record buffer, failing at checking free size
  aux_data.emplace_back(1024, 0, '3', 0, true);
  // one buffer too big to fit in record buffer, failing at AllocWriteSpace()
  aux_data.emplace_back(800, 0, '4', 0, true);
  size_t test_index = 0;

  auto SetBuf1 = [&](char** buf1) {
    *buf1 = aux_data[test_index].buf1.data();
    return true;
  };
  auto SetSize1 = [&](size_t* size1) {
    *size1 = aux_data[test_index].buf1.size();
    return true;
  };
  auto SetBuf2 = [&](char** buf2) {
    *buf2 = aux_data[test_index].buf2.data();
    return true;
  };
  auto SetSize2 = [&](size_t* size2) {
    *size2 = aux_data[test_index].buf2.size();
    return true;
  };
  auto CheckDiscardSize = [&](size_t size) {
    return size == aux_data[test_index].buf1.size() + aux_data[test_index].buf2.size();
  };

  const size_t AUX_BUFFER_SIZE = 4096;

  perf_event_attr attr = CreateDefaultPerfEventAttr(*type);
  MockEventFd fd(attr, 0, nullptr, 1, true);
  EXPECT_CALL(fd, CreateMappedBuffer(_, _)).Times(1).WillOnce(Return(true));
  EXPECT_CALL(fd, CreateAuxBuffer(Eq(AUX_BUFFER_SIZE), _)).Times(1).WillOnce(Return(true));
  EXPECT_CALL(fd, StartPolling(_, _)).Times(1).WillOnce(Return(true));
  EXPECT_CALL(fd, GetAvailableMmapDataSize(_)).Times(aux_data.size()).WillRepeatedly(Return(0));
  EXPECT_CALL(fd,
              GetAvailableAuxData(Truly(SetBuf1), Truly(SetSize1), Truly(SetBuf2), Truly(SetSize2)))
      .Times(aux_data.size());
  EXPECT_CALL(fd, DiscardAuxData(Truly(CheckDiscardSize))).Times(aux_data.size());
  EXPECT_CALL(fd, StopPolling()).Times(1).WillOnce(Return(true));
  EXPECT_CALL(fd, DestroyMappedBuffer()).Times(1);
  EXPECT_CALL(fd, DestroyAuxBuffer()).Times(1);

  RecordReadThread thread(1024, attr, 1, 1, AUX_BUFFER_SIZE);
  IOEventLoop loop;
  ASSERT_TRUE(thread.RegisterDataCallback(loop, []() { return true; }));
  ASSERT_TRUE(thread.AddEventFds({&fd}));
  for (; test_index < aux_data.size(); ++test_index) {
    ASSERT_TRUE(thread.SyncKernelBuffer());
    std::unique_ptr<Record> r = thread.GetRecord();
    if (aux_data[test_index].lost) {
      ASSERT_TRUE(r == nullptr);
      continue;
    }
    ASSERT_TRUE(r);
    ASSERT_EQ(r->type(), PERF_RECORD_AUXTRACE);
    auto auxtrace = static_cast<AuxTraceRecord*>(r.get());
    auto& expected = aux_data[test_index];
    ASSERT_EQ(auxtrace->data->aux_size,
              expected.buf1.size() + expected.buf2.size() + expected.pad.size());
    const char* p = auxtrace->location.addr;
    ASSERT_TRUE(p != nullptr);
    if (!expected.buf1.empty()) {
      ASSERT_EQ(memcmp(p, expected.buf1.data(), expected.buf1.size()), 0);
      p += expected.buf1.size();
    }
    if (!expected.buf2.empty()) {
      ASSERT_EQ(memcmp(p, expected.buf2.data(), expected.buf2.size()), 0);
      p += expected.buf2.size();
    }
    if (!expected.pad.empty()) {
      ASSERT_EQ(memcmp(p, expected.pad.data(), expected.pad.size()), 0);
    }
  }
  ASSERT_TRUE(thread.GetRecord() == nullptr);
  ASSERT_TRUE(thread.RemoveEventFds({&fd}));
  size_t aux_data_size = 0;
  size_t lost_aux_data_size = 0;
  for (auto& aux : aux_data) {
    if (aux.lost) {
      lost_aux_data_size += aux.buf1.size() + aux.buf2.size();
    } else {
      aux_data_size += aux.buf1.size() + aux.buf2.size();
    }
  }
  ASSERT_EQ(aux_data_size, thread.GetStat().aux_data_size);
  ASSERT_EQ(lost_aux_data_size, thread.GetStat().lost_aux_data_size);
}
