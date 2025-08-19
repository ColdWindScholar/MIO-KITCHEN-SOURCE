// Copyright (C) 2015 The Android Open Source Project
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include <memory>
#include <string>

#include <stdint.h>

#ifndef _IOTOP_TASKSTATS_H
#define _IOTOP_TASKSTATS_H

struct nl_sock;
struct taskstats;

class TaskStatistics {
 public:
  explicit TaskStatistics(const taskstats&);
  TaskStatistics() = default;
  TaskStatistics(const TaskStatistics&) = default;
  void AddPidToTgid(const TaskStatistics&);
  TaskStatistics Update(const TaskStatistics&);

  pid_t pid() const { return pid_; }
  const std::string& comm() const { return comm_; }
  uint64_t read() const { return read_bytes_; }
  uint64_t write() const { return write_bytes_; }
  uint64_t read_write() const { return read_write_bytes_; }
  uint64_t delay_io() const { return block_io_delay_ns_; }
  uint64_t delay_swap() const { return swap_in_delay_ns_; }
  uint64_t delay_sched() const { return cpu_delay_ns_; }
  uint64_t delay_mem() const { return reclaim_delay_ns_; }
  uint64_t delay_total() const { return total_delay_ns_; }
  uint64_t majflt() const { return majflt_; }
  uint64_t minflt() const { return minflt_; }
  uint64_t faults() const { return majflt_ + minflt_; }
  int threads() const { return threads_; }

  void set_pid(pid_t pid) { pid_ = pid; }

 private:
  std::string comm_;
  uid_t uid_;
  gid_t gid_;
  pid_t pid_;
  pid_t ppid_;

  uint64_t cpu_delay_count_;
  uint64_t cpu_delay_ns_;

  uint64_t block_io_delay_count_;
  uint64_t block_io_delay_ns_;

  uint64_t swap_in_delay_count_;
  uint64_t swap_in_delay_ns_;

  uint64_t reclaim_delay_count_;
  uint64_t reclaim_delay_ns_;

  uint64_t total_delay_ns_;

  uint64_t cpu_time_real_;
  uint64_t cpu_time_virtual_;

  uint64_t majflt_;
  uint64_t minflt_;

  uint64_t read_bytes_;
  uint64_t write_bytes_;
  uint64_t read_write_bytes_;
  uint64_t cancelled_write_bytes_;

  int threads_;
};

class TaskstatsSocket {
 public:
  TaskstatsSocket();
  bool Open();
  void Close();

  bool GetPidStats(int, TaskStatistics&);
  bool GetTgidStats(int, TaskStatistics&);

 private:
  bool GetStats(int, int, TaskStatistics& stats);
  std::unique_ptr<nl_sock, void (*)(nl_sock*)> nl_;
  int family_id_;
};

#endif  // _IOTOP_TASKSTATS_H
