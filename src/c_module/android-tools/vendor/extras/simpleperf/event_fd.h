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

#ifndef SIMPLE_PERF_EVENT_FD_H_
#define SIMPLE_PERF_EVENT_FD_H_

#include <sys/types.h>

#include <memory>
#include <string>
#include <vector>

#include <android-base/macros.h>

#include "IOEventLoop.h"
#include "perf_event.h"

namespace simpleperf {

struct PerfCounter {
  uint64_t value;         // The value of the event specified by the perf_event_file.
  uint64_t time_enabled;  // The enabled time.
  uint64_t time_running;  // The running time.
  uint64_t id;            // The id of the perf_event_file.
};

// EventFd represents an opened perf_event_file.
class EventFd {
 public:
  static std::unique_ptr<EventFd> OpenEventFile(const perf_event_attr& attr, pid_t tid, int cpu,
                                                EventFd* group_event_fd,
                                                const std::string& event_name,
                                                bool report_error = true);

  virtual ~EventFd();

  // Give information about this perf_event_file, like (event_name, tid, cpu).
  std::string Name() const;

  uint64_t Id() const;

  pid_t ThreadId() const { return tid_; }

  int Cpu() const { return cpu_; }

  const perf_event_attr& attr() const { return attr_; }

  // It tells the kernel to start counting and recording events specified by
  // this file.
  bool SetEnableEvent(bool enable);
  bool SetFilter(const std::string& filter);

  bool ReadCounter(PerfCounter* counter);

  // Create mapped buffer used to receive records sent by the kernel.
  // mmap_pages should be power of 2.
  virtual bool CreateMappedBuffer(size_t mmap_pages, bool report_error);

  // Share the mapped buffer used by event_fd. The two EventFds should monitor
  // the same event on the same cpu, but have different thread ids.
  bool ShareMappedBuffer(const EventFd& event_fd, bool report_error);

  bool HasMappedBuffer() const { return mmap_data_buffer_size_ != 0; }
  char* GetMappedBuffer(size_t& buffer_size) {
    buffer_size = mmap_data_buffer_size_;
    return mmap_data_buffer_;
  }

  virtual void DestroyMappedBuffer();

  // Return available data in the kernel buffer.
  std::vector<char> GetAvailableMmapData();
  // Return the size of available data in the buffer, and set data_pos to the first available data
  // position in mmap_data_buffer_.
  virtual size_t GetAvailableMmapDataSize(size_t& data_pos);
  // Discard the size of the data we have read, so the kernel can reuse the space for new data.
  virtual void DiscardMmapData(size_t discard_size);

  // Manage the aux buffer, which receive auxiliary data sent by the kernel.
  // aux_buffer_size: should be power of two, and mod PAGE_SIZE is zero.
  virtual bool CreateAuxBuffer(size_t aux_buffer_size, bool report_error);
  bool HasAuxBuffer() const { return aux_buffer_size_ != 0; }
  virtual void DestroyAuxBuffer();

  // Get available aux data, which can appear in one or two continuous buffers.
  // buf1: return pointer to the first buffer
  // size1: return data size in the first buffer
  // buf2: return pointer to the second buffer
  // size2: return data size in the second buffer
  // Return value: return how many bytes of aux data has been read before.
  virtual uint64_t GetAvailableAuxData(char** buf1, size_t* size1, char** buf2, size_t* size2);
  virtual void DiscardAuxData(size_t discard_size);

  // [callback] is called when there is data available in the mapped buffer.
  virtual bool StartPolling(IOEventLoop& loop, const std::function<bool()>& callback);
  virtual bool StopPolling();

 protected:
  EventFd(const perf_event_attr& attr, int perf_event_fd, const std::string& event_name, pid_t tid,
          int cpu)
      : attr_(attr),
        perf_event_fd_(perf_event_fd),
        id_(0),
        event_name_(event_name),
        tid_(tid),
        cpu_(cpu),
        mmap_addr_(nullptr),
        mmap_len_(0),
        mmap_metadata_page_(nullptr),
        mmap_data_buffer_(nullptr),
        mmap_data_buffer_size_(0),
        ioevent_ref_(nullptr),
        last_counter_value_(0) {}

  bool InnerReadCounter(PerfCounter* counter) const;

  const perf_event_attr attr_;
  int perf_event_fd_;
  mutable uint64_t id_;
  const std::string event_name_;
  pid_t tid_;
  int cpu_;

  void* mmap_addr_;
  size_t mmap_len_;
  // the first page of mapped area, whose content can be changed by the kernel at any time
  volatile perf_event_mmap_page* mmap_metadata_page_;
  // starting from the second page of mapped area, containing records written by the kernel
  char* mmap_data_buffer_;
  size_t mmap_data_buffer_size_;
  // receiving auxiliary data (like instruction tracing data generated by etm) from the kernel
  char* aux_buffer_ = nullptr;
  size_t aux_buffer_size_ = 0;

  IOEventRef ioevent_ref_;

  // Used by atrace to generate value difference between two ReadCounter() calls.
  uint64_t last_counter_value_;

  DISALLOW_COPY_AND_ASSIGN(EventFd);
};

bool IsEventAttrSupported(const perf_event_attr& attr, const std::string& event_name);

}  // namespace simpleperf

#endif  // SIMPLE_PERF_EVENT_FD_H_
