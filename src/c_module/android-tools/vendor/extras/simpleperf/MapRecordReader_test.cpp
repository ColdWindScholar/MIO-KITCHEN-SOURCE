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

#include "MapRecordReader.h"

#include <optional>

#include <gtest/gtest.h>

#include "environment.h"
#include "event_attr.h"
#include "event_type.h"

using namespace simpleperf;

// @CddTest = 6.1/C-0-2
class MapRecordReaderTest : public ::testing::Test {
 protected:
  bool CreateMapRecordReader() {
    const EventType* event_type = FindEventTypeByName("cpu-clock");
    if (event_type == nullptr) {
      return false;
    }
    attr_ = CreateDefaultPerfEventAttr(*event_type);
    reader_.emplace(attr_, 0, true);
    reader_->SetCallback([this](Record* r) { return CountRecord(r); });
    return true;
  }

  bool CountRecord(Record* r) {
    if (r->type() == PERF_RECORD_MMAP || r->type() == PERF_RECORD_MMAP2) {
      map_record_count_++;
    } else if (r->type() == PERF_RECORD_COMM) {
      comm_record_count_++;
    }
    return true;
  }

  perf_event_attr attr_;
  std::optional<MapRecordReader> reader_;
  size_t map_record_count_ = 0;
  size_t comm_record_count_ = 0;
};

// @CddTest = 6.1/C-0-2
TEST_F(MapRecordReaderTest, ReadKernelMaps) {
  ASSERT_TRUE(CreateMapRecordReader());
  ASSERT_TRUE(reader_->ReadKernelMaps());
  ASSERT_GT(map_record_count_, 0);
}

// @CddTest = 6.1/C-0-2
TEST_F(MapRecordReaderTest, ReadProcessMaps) {
  ASSERT_TRUE(CreateMapRecordReader());
  ASSERT_TRUE(reader_->ReadProcessMaps(getpid(), 0));
  ASSERT_GT(map_record_count_, 0);
  ASSERT_GT(comm_record_count_, 0);
}

// @CddTest = 6.1/C-0-2
TEST_F(MapRecordReaderTest, MapRecordThread) {
#ifdef __ANDROID__
  std::string tmpdir = "/data/local/tmp";
#else
  std::string tmpdir = "/tmp";
#endif
  auto scoped_temp_files = ScopedTempFiles::Create(tmpdir);
  ASSERT_TRUE(scoped_temp_files);
  ASSERT_TRUE(CreateMapRecordReader());
  MapRecordThread thread(*reader_);
  ASSERT_TRUE(thread.Join());
  std::vector<char> buffer;
  ASSERT_TRUE(thread.ReadMapRecordData([&](const char* data, size_t size) {
    buffer.insert(buffer.end(), data, data + size);
    return true;
  }));
  std::vector<std::unique_ptr<Record>> records =
      ReadRecordsFromBuffer(attr_, buffer.data(), buffer.size());
  for (auto& r : records) {
    ASSERT_TRUE(CountRecord(r.get()));
  }
  ASSERT_GT(map_record_count_, 0);
  ASSERT_GT(comm_record_count_, 0);
}
