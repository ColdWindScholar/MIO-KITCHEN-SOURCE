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
#define ATRACE_TAG ATRACE_TAG_ALWAYS
#include "event_fd.h"

#include <cutils/trace.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <utils/Trace.h>
#include <atomic>
#include <memory>

#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/stringprintf.h>

#include "environment.h"
#include "event_attr.h"
#include "event_type.h"
#include "perf_event.h"
#include "utils.h"

namespace simpleperf {

static int perf_event_open(const perf_event_attr& attr, pid_t pid, int cpu, int group_fd,
                           unsigned long flags) {  // NOLINT
  return syscall(__NR_perf_event_open, &attr, pid, cpu, group_fd, flags);
}

std::unique_ptr<EventFd> EventFd::OpenEventFile(const perf_event_attr& attr, pid_t tid, int cpu,
                                                EventFd* group_event_fd,
                                                const std::string& event_name, bool report_error) {
  int group_fd = -1;
  if (group_event_fd != nullptr) {
    group_fd = group_event_fd->perf_event_fd_;
  }
  perf_event_attr real_attr = attr;
  if (attr.freq) {
    uint64_t max_sample_freq;
    if (GetMaxSampleFrequency(&max_sample_freq) && max_sample_freq < attr.sample_freq) {
      static bool warned = false;
      if (!warned) {
        warned = true;
        LOG(INFO) << "Adjust sample freq to max allowed sample freq " << max_sample_freq;
      }
      real_attr.sample_freq = max_sample_freq;
    }
  }
  int perf_event_fd = perf_event_open(real_attr, tid, cpu, group_fd, 0);
  if (perf_event_fd == -1) {
    if (report_error) {
      PLOG(ERROR) << "open perf_event_file (event " << event_name << ", tid " << tid << ", cpu "
                  << cpu << ", group_fd " << group_fd << ") failed";
    } else {
      PLOG(DEBUG) << "open perf_event_file (event " << event_name << ", tid " << tid << ", cpu "
                  << cpu << ", group_fd " << group_fd << ") failed";
    }
    return nullptr;
  }
  if (fcntl(perf_event_fd, F_SETFD, FD_CLOEXEC) == -1) {
    if (report_error) {
      PLOG(ERROR) << "fcntl(FD_CLOEXEC) for perf_event_file (event " << event_name << ", tid "
                  << tid << ", cpu " << cpu << ", group_fd " << group_fd << ") failed";
    } else {
      PLOG(DEBUG) << "fcntl(FD_CLOEXEC) for perf_event_file (event " << event_name << ", tid "
                  << tid << ", cpu " << cpu << ", group_fd " << group_fd << ") failed";
    }
    return nullptr;
  }
  return std::unique_ptr<EventFd>(new EventFd(real_attr, perf_event_fd, event_name, tid, cpu));
}

EventFd::~EventFd() {
  DestroyMappedBuffer();
  DestroyAuxBuffer();
  close(perf_event_fd_);
}

std::string EventFd::Name() const {
  return android::base::StringPrintf("perf_event_file(event %s, tid %d, cpu %d)",
                                     event_name_.c_str(), tid_, cpu_);
}

uint64_t EventFd::Id() const {
  if (id_ == 0) {
    if (ioctl(perf_event_fd_, PERF_EVENT_IOC_ID, &id_) != 0) {
      // PERF_EVENT_IOC_ID isn't available in kernel <= 3.10. Fallback to read() in this case.
      PerfCounter counter;
      if (InnerReadCounter(&counter)) {
        id_ = counter.id;
      } else {
        PLOG(WARNING) << "failed to get id of event_fd";
      }
    }
  }
  return id_;
}

bool EventFd::SetEnableEvent(bool enable) {
  int result = ioctl(perf_event_fd_, enable ? PERF_EVENT_IOC_ENABLE : PERF_EVENT_IOC_DISABLE, 0);
  if (result < 0) {
    PLOG(ERROR) << "ioctl(" << (enable ? "enable" : "disable") << ")" << Name() << " failed";
    return false;
  }
  return true;
}

bool EventFd::SetFilter(const std::string& filter) {
  bool success = ioctl(perf_event_fd_, PERF_EVENT_IOC_SET_FILTER, filter.c_str()) >= 0;
  if (!success) {
    PLOG(ERROR) << "failed to set filter";
  }
  return success;
}

bool EventFd::InnerReadCounter(PerfCounter* counter) const {
  CHECK(counter != nullptr);
  if (!android::base::ReadFully(perf_event_fd_, counter, sizeof(*counter))) {
    PLOG(ERROR) << "ReadCounter from " << Name() << " failed";
    return false;
  }
  return true;
}

bool EventFd::ReadCounter(PerfCounter* counter) {
  if (!InnerReadCounter(counter)) {
    return false;
  }
  // Trace is always available to systrace if enabled
  if (tid_ > 0) {
    ATRACE_INT64(
        android::base::StringPrintf("%s_tid%d_cpu%d", event_name_.c_str(), tid_, cpu_).c_str(),
        counter->value - last_counter_value_);
  } else {
    ATRACE_INT64(android::base::StringPrintf("%s_cpu%d", event_name_.c_str(), cpu_).c_str(),
                 counter->value - last_counter_value_);
  }
  last_counter_value_ = counter->value;
  return true;
}

bool EventFd::CreateMappedBuffer(size_t mmap_pages, bool report_error) {
  CHECK(IsPowerOfTwo(mmap_pages));
  size_t page_size = sysconf(_SC_PAGE_SIZE);
  size_t mmap_len = (mmap_pages + 1) * page_size;
  void* mmap_addr = mmap(nullptr, mmap_len, PROT_READ | PROT_WRITE, MAP_SHARED, perf_event_fd_, 0);
  if (mmap_addr == MAP_FAILED) {
    bool is_perm_error = (errno == EPERM);
    if (report_error) {
      PLOG(ERROR) << "mmap(" << mmap_pages << ") failed for " << Name();
    } else {
      PLOG(DEBUG) << "mmap(" << mmap_pages << ") failed for " << Name();
    }
    if (report_error && is_perm_error) {
      LOG(ERROR) << "It seems the kernel doesn't allow allocating enough "
                 << "buffer for dumping samples, consider decreasing mmap pages(-m).";
    }
    return false;
  }
  mmap_addr_ = mmap_addr;
  mmap_len_ = mmap_len;
  mmap_metadata_page_ = reinterpret_cast<perf_event_mmap_page*>(mmap_addr_);
  mmap_data_buffer_ = reinterpret_cast<char*>(mmap_addr_) + page_size;
  mmap_data_buffer_size_ = mmap_len_ - page_size;
  return true;
}

bool EventFd::ShareMappedBuffer(const EventFd& event_fd, bool report_error) {
  CHECK(!HasMappedBuffer());
  CHECK(event_fd.HasMappedBuffer());
  int result = ioctl(perf_event_fd_, PERF_EVENT_IOC_SET_OUTPUT, event_fd.perf_event_fd_);
  if (result != 0) {
    if (report_error) {
      PLOG(ERROR) << "failed to share mapped buffer of " << event_fd.perf_event_fd_ << " with "
                  << perf_event_fd_;
    }
    return false;
  }
  return true;
}

void EventFd::DestroyMappedBuffer() {
  if (HasMappedBuffer()) {
    munmap(mmap_addr_, mmap_len_);
    mmap_addr_ = nullptr;
    mmap_len_ = 0;
    mmap_metadata_page_ = nullptr;
    mmap_data_buffer_ = nullptr;
    mmap_data_buffer_size_ = 0;
  }
}

std::vector<char> EventFd::GetAvailableMmapData() {
  size_t data_pos;
  size_t data_size = GetAvailableMmapDataSize(data_pos);
  std::vector<char> data(data_size);
  if (data_size > 0) {
    size_t copy_size = std::min(data_size, mmap_data_buffer_size_ - data_pos);
    memcpy(&data[0], mmap_data_buffer_ + data_pos, copy_size);
    if (copy_size < data_size) {
      memcpy(&data[copy_size], mmap_data_buffer_, data_size - copy_size);
    }
    DiscardMmapData(data_size);
  }
  return data;
}

size_t EventFd::GetAvailableMmapDataSize(size_t& data_pos) {
  // The mmap_data_buffer is used as a ring buffer between the kernel and
  // simpleperf. The kernel continuously writes records to the buffer, and
  // simpleperf continuously read records out.
  //         _________________________________________
  // buffer | can write   |   can read   |  can write |
  //                      ^              ^
  //                    read_head       write_head
  //
  // So simpleperf can read records in [read_head, write_head), and the kernel
  // can write records in [write_head, read_head). The kernel is responsible
  // for updating write_head, and simpleperf is responsible for updating
  // read_head.

  uint64_t write_head = mmap_metadata_page_->data_head;
  uint64_t read_head = mmap_metadata_page_->data_tail;
  // The kernel may decrease data_head temporarily (http://b/132446871), making
  // write_head < read_head. So check it to avoid available data size underflow.
  if (write_head <= read_head) {
    // No available data.
    return 0;
  }
  // rmb() used to ensure reading data after reading data_head.
  __sync_synchronize();
  data_pos = read_head & (mmap_data_buffer_size_ - 1);
  return write_head - read_head;
}

void EventFd::DiscardMmapData(size_t discard_size) {
  // mb() used to ensure finish reading data before writing data_tail.
  __sync_synchronize();
  mmap_metadata_page_->data_tail += discard_size;
}

bool EventFd::CreateAuxBuffer(size_t aux_buffer_size, bool report_error) {
  CHECK(HasMappedBuffer());
  CHECK(IsPowerOfTwo(aux_buffer_size));
  mmap_metadata_page_->aux_offset = mmap_len_;
  mmap_metadata_page_->aux_size = aux_buffer_size;
  mmap_metadata_page_->aux_head = 0;
  mmap_metadata_page_->aux_tail = 0;
  void* mmap_addr = mmap(nullptr, aux_buffer_size, PROT_READ | PROT_WRITE, MAP_SHARED,
                         perf_event_fd_, mmap_metadata_page_->aux_offset);
  if (mmap_addr == MAP_FAILED) {
    if (report_error) {
      PLOG(ERROR) << "failed to mmap aux buffer of size " << aux_buffer_size << " for " << Name();
    } else {
      PLOG(DEBUG) << "failed to mmap aux buffer of size " << aux_buffer_size << " for " << Name();
    }
    return false;
  }
  aux_buffer_ = static_cast<char*>(mmap_addr);
  aux_buffer_size_ = aux_buffer_size;
  return true;
}

void EventFd::DestroyAuxBuffer() {
  if (HasAuxBuffer()) {
    munmap(aux_buffer_, aux_buffer_size_);
    aux_buffer_ = nullptr;
    aux_buffer_size_ = 0;
  }
}

uint64_t EventFd::GetAvailableAuxData(char** buf1, size_t* size1, char** buf2, size_t* size2) {
  // Aux buffer is similar to mapped_data_buffer. See comments in GetAvailableMmapData().
  uint64_t write_head = mmap_metadata_page_->aux_head;
  uint64_t read_head = mmap_metadata_page_->aux_tail;
  if (write_head <= read_head) {
    *size1 = *size2 = 0;
    return 0;  // No available data.
  }
  // rmb() used to ensure reading data after reading aux_head.
  __sync_synchronize();
  size_t data_pos = read_head & (aux_buffer_size_ - 1);
  size_t data_size = write_head - read_head;
  *buf1 = aux_buffer_ + data_pos;
  if (data_size <= aux_buffer_size_ - data_pos) {
    *size1 = data_size;
    *size2 = 0;
  } else {
    *size1 = aux_buffer_size_ - data_pos;
    *buf2 = aux_buffer_;
    *size2 = data_size - *size1;
  }
  return read_head;
}

void EventFd::DiscardAuxData(size_t discard_size) {
  // mb() used to ensure finish reading data before writing aux_tail.
  __sync_synchronize();
  mmap_metadata_page_->aux_tail += discard_size;
}

bool EventFd::StartPolling(IOEventLoop& loop, const std::function<bool()>& callback) {
  ioevent_ref_ = loop.AddReadEvent(perf_event_fd_, callback);
  return ioevent_ref_ != nullptr;
}

bool EventFd::StopPolling() {
  return IOEventLoop::DelEvent(ioevent_ref_);
}

bool IsEventAttrSupported(const perf_event_attr& attr, const std::string& event_name) {
  return EventFd::OpenEventFile(attr, getpid(), -1, nullptr, event_name, false) != nullptr;
}

}  // namespace simpleperf
