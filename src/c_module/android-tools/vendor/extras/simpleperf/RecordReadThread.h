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

#pragma once

#include <sys/types.h>

#include <atomic>
#include <condition_variable>
#include <functional>
#include <memory>
#include <mutex>
#include <thread>
#include <unordered_set>

#include <android-base/macros.h>
#include <android-base/unique_fd.h>

#include "event_fd.h"
#include "record.h"

namespace simpleperf {

// RecordBuffer is a circular buffer used to cache records in user-space. It allows one read
// thread and one write thread. The record read thread writes records to the buffer, and the main
// thread reads records from the buffer.
class RecordBuffer {
 public:
  RecordBuffer(size_t buffer_size);
  size_t size() const { return buffer_size_; }
  char* BufferEnd() const { return buffer_.get() + buffer_size_; }

  // Return the size of writable space in the buffer.
  size_t GetFreeSize() const;
  // Allocate a writable space for a record. Return nullptr if there isn't enough space.
  char* AllocWriteSpace(size_t record_size);
  // Called after writing a record, let the read thread see the record.
  void FinishWrite();

  // Get data of the current record. Return nullptr if there is no records in the buffer.
  char* GetCurrentRecord();
  void AddCurrentRecordSize(size_t size) { cur_read_record_size_ += size; }
  // Called after reading a record, the space of the record will be writable.
  void MoveToNextRecord();

 private:
  std::atomic_size_t read_head_;
  std::atomic_size_t write_head_;
  size_t cur_write_record_size_ = 0;
  size_t cur_read_record_size_ = 0;
  const size_t buffer_size_;
  std::unique_ptr<char> buffer_;

  DISALLOW_COPY_AND_ASSIGN(RecordBuffer);
};

// Parse positions of different fields in record data.
class RecordParser {
 public:
  RecordParser(const perf_event_attr& attr);

  // Return pos of the pid field in the sample record. If not available, return 0.
  size_t GetPidPosInSampleRecord() const { return pid_pos_in_sample_records_; }
  // Return pos of the time field in the record. If not available, return 0.
  size_t GetTimePos(const perf_event_header& header) const;
  // Return pos of the user stack size field in the sample record. If not available, return 0.
  size_t GetStackSizePos(const std::function<void(size_t, size_t, void*)>& read_record_fn) const;

 private:
  uint64_t sample_type_;
  uint64_t read_format_;
  uint64_t sample_regs_count_;
  size_t pid_pos_in_sample_records_ = 0;
  size_t time_pos_in_sample_records_ = 0;
  size_t time_rpos_in_non_sample_records_ = 0;
  size_t read_pos_in_sample_records_ = 0;
};

struct RecordStat {
  size_t kernelspace_lost_records = 0;
  size_t userspace_lost_samples = 0;
  size_t userspace_lost_non_samples = 0;
  size_t userspace_truncated_stack_samples = 0;
  uint64_t aux_data_size = 0;
  uint64_t lost_aux_data_size = 0;
};

// Read records from the kernel buffer belong to an event_fd.
class KernelRecordReader {
 public:
  KernelRecordReader(EventFd* event_fd);

  EventFd* GetEventFd() const { return event_fd_; }
  // Get available data in the kernel buffer. Return true if there is some data.
  bool GetDataFromKernelBuffer();
  // Get header of the current record.
  const perf_event_header& RecordHeader() { return record_header_; }
  // Get time of the current record.
  uint64_t RecordTime() { return record_time_; }
  // Read data of the current record.
  void ReadRecord(size_t pos, size_t size, void* dest);
  // Move to the next record, return false if there is no more records.
  bool MoveToNextRecord(const RecordParser& parser);

 private:
  EventFd* event_fd_;
  char* buffer_;
  size_t buffer_mask_;
  size_t data_pos_ = 0;
  size_t data_size_ = 0;
  size_t init_data_size_ = 0;
  perf_event_header record_header_ = {};
  uint64_t record_time_ = 0;
};

// To reduce sample lost rate when recording dwarf based call graph, RecordReadThread uses a
// separate high priority (nice -20) thread to read records from kernel buffers to a RecordBuffer.
class RecordReadThread {
 public:
  RecordReadThread(size_t record_buffer_size, const perf_event_attr& attr, size_t min_mmap_pages,
                   size_t max_mmap_pages, size_t aux_buffer_size,
                   bool allow_truncating_samples = true, bool exclude_perf = false);
  ~RecordReadThread();
  void SetBufferLevels(size_t record_buffer_low_level, size_t record_buffer_critical_level) {
    record_buffer_low_level_ = record_buffer_low_level;
    record_buffer_critical_level_ = record_buffer_critical_level;
  }

  // Below functions are called in the main thread:

  // When there are records in the RecordBuffer, data_callback will be called in the main thread.
  bool RegisterDataCallback(IOEventLoop& loop, const std::function<bool()>& data_callback);
  // Create and read kernel buffers for new event fds.
  bool AddEventFds(const std::vector<EventFd*>& event_fds);
  // Destroy kernel buffers of existing event fds.
  bool RemoveEventFds(const std::vector<EventFd*>& event_fds);
  // Move all available records in kernel buffers to the RecordBuffer.
  bool SyncKernelBuffer();
  // Stop the read thread, no more records will be put into the RecordBuffer.
  bool StopReadThread();

  // If available, return the next record in the RecordBuffer, otherwise return nullptr.
  std::unique_ptr<Record> GetRecord();

  const RecordStat& GetStat() const { return stat_; }

 private:
  enum Cmd {
    NO_CMD,
    CMD_ADD_EVENT_FDS,
    CMD_REMOVE_EVENT_FDS,
    CMD_SYNC_KERNEL_BUFFER,
    CMD_STOP_THREAD,
  };

  bool SendCmdToReadThread(Cmd cmd, void* cmd_arg);

  // Below functions are called in the read thread:

  void RunReadThread();
  void IncreaseThreadPriority();
  Cmd GetCmd();
  bool HandleCmd(IOEventLoop& loop);
  bool HandleAddEventFds(IOEventLoop& loop, const std::vector<EventFd*>& event_fds);
  bool HandleRemoveEventFds(const std::vector<EventFd*>& event_fds);
  bool ReadRecordsFromKernelBuffer();
  void PushRecordToRecordBuffer(KernelRecordReader* kernel_record_reader);
  void ReadAuxDataFromKernelBuffer(bool* has_data);
  bool SendDataNotificationToMainThread();

  RecordBuffer record_buffer_;
  // When free size in record buffer is below low level, we cut stack data of sample records to 1K.
  size_t record_buffer_low_level_;
  // When free size in record buffer is below critical level, we drop sample records to avoid
  // losing more important records (like mmap or fork records).
  size_t record_buffer_critical_level_;
  RecordParser record_parser_;
  perf_event_attr attr_;
  size_t stack_size_in_sample_record_ = 0;
  size_t min_mmap_pages_;
  size_t max_mmap_pages_;
  size_t aux_buffer_size_;

  // Used to pass command notification from the main thread to the read thread.
  android::base::unique_fd write_cmd_fd_;
  android::base::unique_fd read_cmd_fd_;
  std::mutex cmd_mutex_;
  std::condition_variable cmd_finish_cond_;
  Cmd cmd_;
  void* cmd_arg_;
  bool cmd_result_;

  // Used to send data notification from the read thread to the main thread.
  android::base::unique_fd write_data_fd_;
  android::base::unique_fd read_data_fd_;
  std::atomic_bool has_data_notification_;

  std::unique_ptr<std::thread> read_thread_;
  std::vector<KernelRecordReader> kernel_record_readers_;
  pid_t exclude_pid_ = -1;
  bool has_etm_events_ = false;

  std::unordered_set<EventFd*> event_fds_disabled_by_kernel_;

  RecordStat stat_;
};

}  // namespace simpleperf
