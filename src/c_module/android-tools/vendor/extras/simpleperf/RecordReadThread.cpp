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

#include <sys/resource.h>
#include <unistd.h>

#include <algorithm>
#include <unordered_map>

#include "environment.h"
#include "event_type.h"
#include "record.h"
#include "utils.h"

namespace simpleperf {

static constexpr size_t kDefaultLowBufferLevel = 10 * kMegabyte;
static constexpr size_t kDefaultCriticalBufferLevel = 5 * kMegabyte;

RecordBuffer::RecordBuffer(size_t buffer_size)
    : read_head_(0), write_head_(0), buffer_size_(buffer_size), buffer_(new char[buffer_size]) {}

size_t RecordBuffer::GetFreeSize() const {
  size_t write_head = write_head_.load(std::memory_order_relaxed);
  size_t read_head = read_head_.load(std::memory_order_relaxed);
  size_t write_tail = read_head > 0 ? read_head - 1 : buffer_size_ - 1;
  if (write_head <= write_tail) {
    return write_tail - write_head;
  }
  return buffer_size_ - write_head + write_tail;
}

char* RecordBuffer::AllocWriteSpace(size_t record_size) {
  size_t write_head = write_head_.load(std::memory_order_relaxed);
  size_t read_head = read_head_.load(std::memory_order_acquire);
  size_t write_tail = read_head > 0 ? read_head - 1 : buffer_size_ - 1;
  cur_write_record_size_ = record_size;
  if (write_head < write_tail) {
    if (write_head + record_size > write_tail) {
      return nullptr;
    }
  } else if (write_head + record_size > buffer_size_) {
    // Not enough space at the end of the buffer, need to wrap to the start of the buffer.
    if (write_tail < record_size) {
      return nullptr;
    }
    if (buffer_size_ - write_head >= sizeof(perf_event_header)) {
      // Set the size field in perf_event_header to 0. So GetCurrentRecord() can wrap to the start
      // of the buffer when size is 0.
      memset(buffer_.get() + write_head, 0, sizeof(perf_event_header));
    }
    cur_write_record_size_ += buffer_size_ - write_head;
    write_head = 0;
  }
  return buffer_.get() + write_head;
}

void RecordBuffer::FinishWrite() {
  size_t write_head = write_head_.load(std::memory_order_relaxed);
  write_head = (write_head + cur_write_record_size_) % buffer_size_;
  write_head_.store(write_head, std::memory_order_release);
}

char* RecordBuffer::GetCurrentRecord() {
  size_t write_head = write_head_.load(std::memory_order_acquire);
  size_t read_head = read_head_.load(std::memory_order_relaxed);
  if (read_head == write_head) {
    return nullptr;
  }
  perf_event_header header;
  if (read_head > write_head) {
    if (buffer_size_ - read_head < sizeof(header) ||
        (memcpy(&header, buffer_.get() + read_head, sizeof(header)) && header.size == 0)) {
      // Need to wrap to the start of the buffer.
      cur_read_record_size_ += buffer_size_ - read_head;
      read_head = 0;
      memcpy(&header, buffer_.get(), sizeof(header));
    }
  } else {
    memcpy(&header, buffer_.get() + read_head, sizeof(header));
  }
  cur_read_record_size_ += header.size;
  return buffer_.get() + read_head;
}

void RecordBuffer::MoveToNextRecord() {
  size_t read_head = read_head_.load(std::memory_order_relaxed);
  read_head = (read_head + cur_read_record_size_) % buffer_size_;
  read_head_.store(read_head, std::memory_order_release);
  cur_read_record_size_ = 0;
}

RecordParser::RecordParser(const perf_event_attr& attr)
    : sample_type_(attr.sample_type),
      read_format_(attr.read_format),
      sample_regs_count_(__builtin_popcountll(attr.sample_regs_user)) {
  size_t pos = sizeof(perf_event_header);
  uint64_t mask = PERF_SAMPLE_IDENTIFIER | PERF_SAMPLE_IP;
  pos += __builtin_popcountll(sample_type_ & mask) * sizeof(uint64_t);
  if (sample_type_ & PERF_SAMPLE_TID) {
    pid_pos_in_sample_records_ = pos;
    pos += sizeof(uint64_t);
  }
  if (sample_type_ & PERF_SAMPLE_TIME) {
    time_pos_in_sample_records_ = pos;
    pos += sizeof(uint64_t);
  }
  mask = PERF_SAMPLE_ADDR | PERF_SAMPLE_ID | PERF_SAMPLE_STREAM_ID | PERF_SAMPLE_CPU |
         PERF_SAMPLE_PERIOD;
  pos += __builtin_popcountll(sample_type_ & mask) * sizeof(uint64_t);
  read_pos_in_sample_records_ = pos;
  if ((sample_type_ & PERF_SAMPLE_TIME) && attr.sample_id_all) {
    mask = PERF_SAMPLE_IDENTIFIER | PERF_SAMPLE_CPU | PERF_SAMPLE_STREAM_ID | PERF_SAMPLE_ID;
    time_rpos_in_non_sample_records_ =
        (__builtin_popcountll(sample_type_ & mask) + 1) * sizeof(uint64_t);
  }
}

size_t RecordParser::GetTimePos(const perf_event_header& header) const {
  if (header.type == PERF_RECORD_SAMPLE) {
    return time_pos_in_sample_records_;
  }
  if (time_rpos_in_non_sample_records_ != 0u &&
      time_rpos_in_non_sample_records_ < header.size - sizeof(perf_event_header)) {
    return header.size - time_rpos_in_non_sample_records_;
  }
  return 0;
}

size_t RecordParser::GetStackSizePos(
    const std::function<void(size_t, size_t, void*)>& read_record_fn) const {
  size_t pos = read_pos_in_sample_records_;
  if (sample_type_ & PERF_SAMPLE_READ) {
    uint64_t nr = 1;
    if (read_format_ & PERF_FORMAT_GROUP) {
      read_record_fn(pos, sizeof(nr), &nr);
      pos += sizeof(uint64_t);
    }
    size_t u64_count = nr;
    u64_count += (read_format_ & PERF_FORMAT_TOTAL_TIME_ENABLED) ? 1 : 0;
    u64_count += (read_format_ & PERF_FORMAT_TOTAL_TIME_RUNNING) ? 1 : 0;
    u64_count += (read_format_ & PERF_FORMAT_ID) ? nr : 0;
    pos += u64_count * sizeof(uint64_t);
  }
  if (sample_type_ & PERF_SAMPLE_CALLCHAIN) {
    uint64_t ip_nr;
    read_record_fn(pos, sizeof(ip_nr), &ip_nr);
    pos += (ip_nr + 1) * sizeof(uint64_t);
  }
  if (sample_type_ & PERF_SAMPLE_RAW) {
    uint32_t size;
    read_record_fn(pos, sizeof(size), &size);
    pos += size + sizeof(uint32_t);
  }
  if (sample_type_ & PERF_SAMPLE_BRANCH_STACK) {
    uint64_t stack_nr;
    read_record_fn(pos, sizeof(stack_nr), &stack_nr);
    pos += sizeof(uint64_t) + stack_nr * sizeof(BranchStackItemType);
  }
  if (sample_type_ & PERF_SAMPLE_REGS_USER) {
    uint64_t abi;
    read_record_fn(pos, sizeof(abi), &abi);
    pos += (1 + (abi == 0 ? 0 : sample_regs_count_)) * sizeof(uint64_t);
  }
  return (sample_type_ & PERF_SAMPLE_STACK_USER) ? pos : 0;
}

KernelRecordReader::KernelRecordReader(EventFd* event_fd) : event_fd_(event_fd) {
  size_t buffer_size;
  buffer_ = event_fd_->GetMappedBuffer(buffer_size);
  buffer_mask_ = buffer_size - 1;
}

bool KernelRecordReader::GetDataFromKernelBuffer() {
  data_size_ = event_fd_->GetAvailableMmapDataSize(data_pos_);
  if (data_size_ == 0) {
    return false;
  }
  init_data_size_ = data_size_;
  record_header_.size = 0;
  return true;
}

void KernelRecordReader::ReadRecord(size_t pos, size_t size, void* dest) {
  pos = (pos + data_pos_) & buffer_mask_;
  size_t copy_size = std::min(size, buffer_mask_ + 1 - pos);
  memcpy(dest, buffer_ + pos, copy_size);
  if (copy_size < size) {
    memcpy(static_cast<char*>(dest) + copy_size, buffer_, size - copy_size);
  }
}

bool KernelRecordReader::MoveToNextRecord(const RecordParser& parser) {
  data_pos_ = (data_pos_ + record_header_.size) & buffer_mask_;
  data_size_ -= record_header_.size;
  if (data_size_ == 0) {
    event_fd_->DiscardMmapData(init_data_size_);
    init_data_size_ = 0;
    return false;
  }
  ReadRecord(0, sizeof(record_header_), &record_header_);
  size_t time_pos = parser.GetTimePos(record_header_);
  if (time_pos != 0) {
    ReadRecord(time_pos, sizeof(record_time_), &record_time_);
  }
  return true;
}

RecordReadThread::RecordReadThread(size_t record_buffer_size, const perf_event_attr& attr,
                                   size_t min_mmap_pages, size_t max_mmap_pages,
                                   size_t aux_buffer_size, bool allow_truncating_samples,
                                   bool exclude_perf)
    : record_buffer_(record_buffer_size),
      record_parser_(attr),
      attr_(attr),
      min_mmap_pages_(min_mmap_pages),
      max_mmap_pages_(max_mmap_pages),
      aux_buffer_size_(aux_buffer_size) {
  if (attr.sample_type & PERF_SAMPLE_STACK_USER) {
    stack_size_in_sample_record_ = attr.sample_stack_user;
  }
  record_buffer_low_level_ = std::min(record_buffer_size / 4, kDefaultLowBufferLevel);
  record_buffer_critical_level_ = std::min(record_buffer_size / 6, kDefaultCriticalBufferLevel);
  LOG(VERBOSE) << "user buffer size = " << record_buffer_size
               << ", low_level size = " << record_buffer_low_level_
               << ", critical_level size = " << record_buffer_critical_level_;
  if (!allow_truncating_samples) {
    record_buffer_low_level_ = record_buffer_critical_level_;
  }
  if (exclude_perf) {
    exclude_pid_ = getpid();
  }
}

RecordReadThread::~RecordReadThread() {
  if (read_thread_) {
    StopReadThread();
  }
}

bool RecordReadThread::RegisterDataCallback(IOEventLoop& loop,
                                            const std::function<bool()>& data_callback) {
  int cmd_fd[2];
  int data_fd[2];
  if (pipe2(cmd_fd, O_CLOEXEC) != 0 || pipe2(data_fd, O_CLOEXEC) != 0) {
    PLOG(ERROR) << "pipe2";
    return false;
  }
  read_cmd_fd_.reset(cmd_fd[0]);
  write_cmd_fd_.reset(cmd_fd[1]);
  cmd_ = NO_CMD;
  read_data_fd_.reset(data_fd[0]);
  write_data_fd_.reset(data_fd[1]);
  has_data_notification_ = false;
  if (!loop.AddReadEvent(read_data_fd_, data_callback)) {
    return false;
  }
  read_thread_.reset(new std::thread([&]() { RunReadThread(); }));
  return true;
}

bool RecordReadThread::AddEventFds(const std::vector<EventFd*>& event_fds) {
  return SendCmdToReadThread(CMD_ADD_EVENT_FDS, const_cast<std::vector<EventFd*>*>(&event_fds));
}

bool RecordReadThread::RemoveEventFds(const std::vector<EventFd*>& event_fds) {
  return SendCmdToReadThread(CMD_REMOVE_EVENT_FDS, const_cast<std::vector<EventFd*>*>(&event_fds));
}

bool RecordReadThread::SyncKernelBuffer() {
  return SendCmdToReadThread(CMD_SYNC_KERNEL_BUFFER, nullptr);
}

bool RecordReadThread::StopReadThread() {
  bool result = true;
  if (read_thread_ != nullptr) {
    result = SendCmdToReadThread(CMD_STOP_THREAD, nullptr);
    if (result) {
      read_thread_->join();
      read_thread_ = nullptr;
    }
  }
  return result;
}

bool RecordReadThread::SendCmdToReadThread(Cmd cmd, void* cmd_arg) {
  {
    std::lock_guard<std::mutex> lock(cmd_mutex_);
    cmd_ = cmd;
    cmd_arg_ = cmd_arg;
  }
  char unused = 0;
  if (TEMP_FAILURE_RETRY(write(write_cmd_fd_, &unused, 1)) != 1) {
    return false;
  }
  std::unique_lock<std::mutex> lock(cmd_mutex_);
  while (cmd_ != NO_CMD) {
    cmd_finish_cond_.wait(lock);
  }
  return cmd_result_;
}

std::unique_ptr<Record> RecordReadThread::GetRecord() {
  record_buffer_.MoveToNextRecord();
  char* p = record_buffer_.GetCurrentRecord();
  if (p != nullptr) {
    std::unique_ptr<Record> r = ReadRecordFromBuffer(attr_, p, record_buffer_.BufferEnd());
    CHECK(r);
    if (r->type() == PERF_RECORD_AUXTRACE) {
      auto auxtrace = static_cast<AuxTraceRecord*>(r.get());
      record_buffer_.AddCurrentRecordSize(auxtrace->data->aux_size);
      auxtrace->location.addr = r->Binary() + r->size();
    }
    return r;
  }
  if (has_data_notification_) {
    char unused;
    TEMP_FAILURE_RETRY(read(read_data_fd_, &unused, 1));
    has_data_notification_ = false;
  }
  return nullptr;
}

void RecordReadThread::RunReadThread() {
  IncreaseThreadPriority();
  IOEventLoop loop;
  CHECK(loop.AddReadEvent(read_cmd_fd_, [&]() { return HandleCmd(loop); }));
  loop.RunLoop();
}

void RecordReadThread::IncreaseThreadPriority() {
  // TODO: use real time priority for root.
  rlimit rlim;
  int result = getrlimit(RLIMIT_NICE, &rlim);
  if (result == 0 && rlim.rlim_cur == 40) {
    result = setpriority(PRIO_PROCESS, gettid(), -20);
    if (result == 0) {
      LOG(VERBOSE) << "Priority of record read thread is increased";
    }
  }
}

RecordReadThread::Cmd RecordReadThread::GetCmd() {
  std::lock_guard<std::mutex> lock(cmd_mutex_);
  return cmd_;
}

bool RecordReadThread::HandleCmd(IOEventLoop& loop) {
  char unused;
  TEMP_FAILURE_RETRY(read(read_cmd_fd_, &unused, 1));
  bool result = true;
  switch (GetCmd()) {
    case CMD_ADD_EVENT_FDS:
      result = HandleAddEventFds(loop, *static_cast<std::vector<EventFd*>*>(cmd_arg_));
      break;
    case CMD_REMOVE_EVENT_FDS:
      result = HandleRemoveEventFds(*static_cast<std::vector<EventFd*>*>(cmd_arg_));
      break;
    case CMD_SYNC_KERNEL_BUFFER:
      result = ReadRecordsFromKernelBuffer();
      break;
    case CMD_STOP_THREAD:
      result = loop.ExitLoop();
      break;
    default:
      LOG(ERROR) << "Unknown cmd: " << GetCmd();
      result = false;
      break;
  }
  std::lock_guard<std::mutex> lock(cmd_mutex_);
  cmd_ = NO_CMD;
  cmd_result_ = result;
  cmd_finish_cond_.notify_one();
  return true;
}

bool RecordReadThread::HandleAddEventFds(IOEventLoop& loop,
                                         const std::vector<EventFd*>& event_fds) {
  std::unordered_map<int, EventFd*> cpu_map;
  for (size_t pages = max_mmap_pages_; pages >= min_mmap_pages_; pages >>= 1) {
    bool success = true;
    bool report_error = pages == min_mmap_pages_;
    for (EventFd* fd : event_fds) {
      auto it = cpu_map.find(fd->Cpu());
      if (it == cpu_map.end()) {
        if (!fd->CreateMappedBuffer(pages, report_error)) {
          success = false;
          break;
        }
        if (IsEtmEventType(fd->attr().type)) {
          if (!fd->CreateAuxBuffer(aux_buffer_size_, report_error)) {
            fd->DestroyMappedBuffer();
            success = false;
            break;
          }
          has_etm_events_ = true;
        }
        cpu_map[fd->Cpu()] = fd;
      } else {
        if (!fd->ShareMappedBuffer(*(it->second), pages == min_mmap_pages_)) {
          success = false;
          break;
        }
      }
    }
    if (success) {
      LOG(VERBOSE) << "Each kernel buffer is " << pages << " pages.";
      break;
    }
    for (auto& pair : cpu_map) {
      pair.second->DestroyMappedBuffer();
      pair.second->DestroyAuxBuffer();
    }
    cpu_map.clear();
  }
  if (cpu_map.empty()) {
    return false;
  }
  for (auto& pair : cpu_map) {
    if (!pair.second->StartPolling(loop, [this]() { return ReadRecordsFromKernelBuffer(); })) {
      return false;
    }
    kernel_record_readers_.emplace_back(pair.second);
  }
  return true;
}

bool RecordReadThread::HandleRemoveEventFds(const std::vector<EventFd*>& event_fds) {
  for (auto& event_fd : event_fds) {
    if (event_fd->HasMappedBuffer()) {
      auto it = std::find_if(
          kernel_record_readers_.begin(), kernel_record_readers_.end(),
          [&](const KernelRecordReader& reader) { return reader.GetEventFd() == event_fd; });
      if (it != kernel_record_readers_.end()) {
        kernel_record_readers_.erase(it);
        event_fd->StopPolling();
        event_fd->DestroyMappedBuffer();
        event_fd->DestroyAuxBuffer();
      }
    }
  }
  return true;
}

static bool CompareRecordTime(KernelRecordReader* r1, KernelRecordReader* r2) {
  return r1->RecordTime() > r2->RecordTime();
}

// When reading from mmap buffers, we prefer reading from all buffers at once rather than reading
// one buffer at a time. Because by reading all buffers at once, we can merge records from
// different buffers easily in memory. Otherwise, we have to sort records with greater effort.
bool RecordReadThread::ReadRecordsFromKernelBuffer() {
  do {
    std::vector<KernelRecordReader*> readers;
    for (auto& reader : kernel_record_readers_) {
      if (reader.GetDataFromKernelBuffer()) {
        readers.push_back(&reader);
      }
    }
    bool has_data = false;
    if (!readers.empty()) {
      has_data = true;
      if (readers.size() == 1u) {
        // Only one buffer has data, process it directly.
        while (readers[0]->MoveToNextRecord(record_parser_)) {
          PushRecordToRecordBuffer(readers[0]);
        }
      } else {
        // Use a binary heap to merge records from different buffers. As records from the same
        // buffer are already ordered by time, we only need to merge the first record from all
        // buffers. And each time a record is popped from the heap, we put the next record from its
        // buffer into the heap.
        for (auto& reader : readers) {
          reader->MoveToNextRecord(record_parser_);
        }
        std::make_heap(readers.begin(), readers.end(), CompareRecordTime);
        size_t size = readers.size();
        while (size > 0) {
          std::pop_heap(readers.begin(), readers.begin() + size, CompareRecordTime);
          PushRecordToRecordBuffer(readers[size - 1]);
          if (readers[size - 1]->MoveToNextRecord(record_parser_)) {
            std::push_heap(readers.begin(), readers.begin() + size, CompareRecordTime);
          } else {
            size--;
          }
        }
      }
    }
    ReadAuxDataFromKernelBuffer(&has_data);
    if (!has_data) {
      break;
    }
    // Having collected everything available, this is a good time to
    // try to re-enabled any events that might have been disabled by
    // the kernel.
    for (auto event_fd : event_fds_disabled_by_kernel_) {
      event_fd->SetEnableEvent(true);
    }
    event_fds_disabled_by_kernel_.clear();
    if (!SendDataNotificationToMainThread()) {
      return false;
    }
    // If there are no commands, we can loop until there is no more data from the kernel.
  } while (GetCmd() == NO_CMD);
  return true;
}

void RecordReadThread::PushRecordToRecordBuffer(KernelRecordReader* kernel_record_reader) {
  const perf_event_header& header = kernel_record_reader->RecordHeader();
  if (header.type == PERF_RECORD_SAMPLE && exclude_pid_ != -1) {
    uint32_t pid;
    kernel_record_reader->ReadRecord(record_parser_.GetPidPosInSampleRecord(), sizeof(pid), &pid);
    if (pid == exclude_pid_) {
      return;
    }
  }
  if (header.type == PERF_RECORD_SAMPLE && stack_size_in_sample_record_ > 1024) {
    size_t free_size = record_buffer_.GetFreeSize();
    if (free_size < record_buffer_critical_level_) {
      // When the free size in record buffer is below critical level, drop sample records to save
      // space for more important records (like mmap or fork records).
      stat_.userspace_lost_samples++;
      return;
    }
    size_t stack_size_limit = stack_size_in_sample_record_;
    if (free_size < record_buffer_low_level_) {
      // When the free size in record buffer is below low level, truncate the stack data in sample
      // records to 1K. This makes the unwinder unwind only part of the callchains, but hopefully
      // the call chain joiner can complete the callchains.
      stack_size_limit = 1024;
    }
    size_t stack_size_pos =
        record_parser_.GetStackSizePos([&](size_t pos, size_t size, void* dest) {
          return kernel_record_reader->ReadRecord(pos, size, dest);
        });
    uint64_t stack_size;
    kernel_record_reader->ReadRecord(stack_size_pos, sizeof(stack_size), &stack_size);
    if (stack_size > 0) {
      size_t dyn_stack_size_pos = stack_size_pos + sizeof(stack_size) + stack_size;
      uint64_t dyn_stack_size;
      kernel_record_reader->ReadRecord(dyn_stack_size_pos, sizeof(dyn_stack_size), &dyn_stack_size);
      if (dyn_stack_size == 0) {
        // If stack_user_data.dyn_size == 0, it may be because the kernel misses the patch to
        // update dyn_size, like in N9 (See b/22612370). So assume all stack data is valid if
        // dyn_size == 0.
        // TODO: Add cts test.
        dyn_stack_size = stack_size;
      }
      // When simpleperf requests the kernel to dump 64K stack per sample, it will allocate 64K
      // space in each sample to store stack data. However, a thread may use less stack than 64K.
      // So not all the 64K stack data in a sample is valid, and we only need to keep valid stack
      // data, whose size is dyn_stack_size.
      uint64_t new_stack_size = Align(std::min<uint64_t>(dyn_stack_size, stack_size_limit), 8);
      if (stack_size > new_stack_size) {
        // Remove part of the stack data.
        perf_event_header new_header = header;
        new_header.size -= stack_size - new_stack_size;
        char* p = record_buffer_.AllocWriteSpace(new_header.size);
        if (p != nullptr) {
          memcpy(p, &new_header, sizeof(new_header));
          size_t pos = sizeof(new_header);
          kernel_record_reader->ReadRecord(pos, stack_size_pos - pos, p + pos);
          memcpy(p + stack_size_pos, &new_stack_size, sizeof(uint64_t));
          pos = stack_size_pos + sizeof(uint64_t);
          kernel_record_reader->ReadRecord(pos, new_stack_size, p + pos);
          memcpy(p + pos + new_stack_size, &new_stack_size, sizeof(uint64_t));
          record_buffer_.FinishWrite();
          if (new_stack_size < dyn_stack_size) {
            stat_.userspace_truncated_stack_samples++;
          }
        } else {
          stat_.userspace_lost_samples++;
        }
        return;
      }
    }
  }
  char* p = record_buffer_.AllocWriteSpace(header.size);
  if (p != nullptr) {
    kernel_record_reader->ReadRecord(0, header.size, p);
    if (header.type == PERF_RECORD_AUX) {
      AuxRecord r;
      if (r.Parse(attr_, p, p + header.size) && (r.data->flags & PERF_AUX_FLAG_TRUNCATED)) {
        // When the kernel sees aux output flagged with PERF_AUX_FLAG_TRUNCATED,
        // it sets a pending disable on the event:
        // https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/kernel/events/ring_buffer.c?h=v5.13#n516
        // The truncated flag is set by the Coresight driver when some trace was lost,
        // which can be caused by a full buffer. Therefore, try to re-enable the event
        // only after we have collected the aux data.
        event_fds_disabled_by_kernel_.insert(kernel_record_reader->GetEventFd());
      }
    } else if (header.type == PERF_RECORD_LOST) {
      LostRecord r;
      if (r.Parse(attr_, p, p + header.size)) {
        stat_.kernelspace_lost_records += static_cast<size_t>(r.lost);
      }
    }
    record_buffer_.FinishWrite();
  } else {
    if (header.type == PERF_RECORD_SAMPLE) {
      stat_.userspace_lost_samples++;
    } else {
      stat_.userspace_lost_non_samples++;
    }
  }
}

void RecordReadThread::ReadAuxDataFromKernelBuffer(bool* has_data) {
  if (!has_etm_events_) {
    return;
  }
  for (auto& reader : kernel_record_readers_) {
    EventFd* event_fd = reader.GetEventFd();
    if (event_fd->HasAuxBuffer()) {
      char* buf[2];
      size_t size[2];
      uint64_t offset = event_fd->GetAvailableAuxData(&buf[0], &size[0], &buf[1], &size[1]);
      size_t aux_size = size[0] + size[1];
      if (aux_size == 0) {
        continue;
      }
      *has_data = true;
      AuxTraceRecord auxtrace(Align(aux_size, 8), offset, event_fd->Cpu(), 0, event_fd->Cpu());
      size_t alloc_size = auxtrace.size() + auxtrace.data->aux_size;
      char* p = nullptr;
      if ((record_buffer_.GetFreeSize() < alloc_size + record_buffer_critical_level_) ||
          (p = record_buffer_.AllocWriteSpace(alloc_size)) == nullptr) {
        stat_.lost_aux_data_size += aux_size;
      } else {
        CHECK(p != nullptr);
        MoveToBinaryFormat(auxtrace.Binary(), auxtrace.size(), p);
        MoveToBinaryFormat(buf[0], size[0], p);
        if (size[1] != 0) {
          MoveToBinaryFormat(buf[1], size[1], p);
        }
        size_t pad_size = auxtrace.data->aux_size - aux_size;
        if (pad_size != 0) {
          uint64_t pad = 0;
          memcpy(p, &pad, pad_size);
        }
        record_buffer_.FinishWrite();
        stat_.aux_data_size += aux_size;
        LOG(DEBUG) << "record aux data " << aux_size << " bytes";
      }
      event_fd->DiscardAuxData(aux_size);
    }
  }
}

bool RecordReadThread::SendDataNotificationToMainThread() {
  if (has_etm_events_) {
    // For ETM recording, the default buffer size is large enough to hold ETM data for several
    // seconds. To reduce impact of processing ETM data (especially when --decode-etm is used),
    // delay processing ETM data until the buffer is half full.
    if (record_buffer_.GetFreeSize() >= record_buffer_.size() / 2) {
      return true;
    }
  }
  if (!has_data_notification_.load(std::memory_order_relaxed)) {
    has_data_notification_ = true;
    char unused = 0;
    if (TEMP_FAILURE_RETRY(write(write_data_fd_, &unused, 1)) != 1) {
      PLOG(ERROR) << "write";
      return false;
    }
  }
  return true;
}

}  // namespace simpleperf
