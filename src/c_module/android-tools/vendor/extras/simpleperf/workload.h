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

#ifndef SIMPLE_PERF_WORKLOAD_H_
#define SIMPLE_PERF_WORKLOAD_H_

#include <sys/types.h>
#include <chrono>
#include <functional>
#include <string>
#include <vector>

#include <android-base/macros.h>

namespace simpleperf {

class Workload {
 private:
  enum WorkState {
    NotYetCreateNewProcess,
    NotYetStartNewProcess,
    Started,
    Finished,
  };

 public:
  static std::unique_ptr<Workload> CreateWorkload(const std::vector<std::string>& args);
  static std::unique_ptr<Workload> CreateWorkload(const std::function<void()>& function);
  static bool RunCmd(const std::vector<std::string>& args, bool report_error = true);

  ~Workload();

  bool SetCpuAffinity(int cpu);
  bool Start();
  bool IsStarted() { return work_state_ == Started; }
  pid_t GetPid() { return work_pid_; }

  bool WaitChildProcess(bool wait_forever, int* exit_code);

  // Set the function used to kill the workload process in ~Workload().
  void SetKillFunction(const std::function<void(pid_t)>& kill_function) {
    kill_function_ = kill_function;
  }

 private:
  explicit Workload(const std::vector<std::string>& args, const std::function<void()>& function);

  bool CreateNewProcess();
  void ChildProcessFn(int start_signal_fd, int exec_child_fd);
  bool WaitChildProcess(bool wait_forever, bool is_child_killed, int* exit_code);

  WorkState work_state_;
  // The child process either executes child_proc_args or run child_proc_function.
  std::vector<std::string> child_proc_args_;
  std::function<void()> child_proc_function_;
  pid_t work_pid_;
  int start_signal_fd_;  // The parent process writes 1 to start workload in the child process.
  int exec_child_fd_;    // The child process writes 1 to notify that execvp() failed.
  std::function<void(pid_t)> kill_function_;

  DISALLOW_COPY_AND_ASSIGN(Workload);
};

}  // namespace simpleperf

#endif  // SIMPLE_PERF_WORKLOAD_H_
