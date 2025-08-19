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

#include "workload.h"

#include <errno.h>
#include <fcntl.h>
#include <sched.h>
#include <sys/prctl.h>
#include <sys/wait.h>
#include <unistd.h>

#include <android-base/logging.h>
#include <android-base/strings.h>

#include "environment.h"

namespace simpleperf {

std::unique_ptr<Workload> Workload::CreateWorkload(const std::vector<std::string>& args) {
#if defined(__ANDROID__)
  if (IsInAppUid()) {
    LOG(ERROR) << "Running child command in app uid isn't allowed.";
    return nullptr;
  }
#endif
  std::unique_ptr<Workload> workload(new Workload(args, std::function<void()>()));
  if (workload != nullptr && workload->CreateNewProcess()) {
    return workload;
  }
  return nullptr;
}

std::unique_ptr<Workload> Workload::CreateWorkload(const std::function<void()>& function) {
  std::unique_ptr<Workload> workload(new Workload(std::vector<std::string>(), function));
  if (workload != nullptr && workload->CreateNewProcess()) {
    return workload;
  }
  return nullptr;
}

bool Workload::RunCmd(const std::vector<std::string>& args, bool report_error) {
  std::string arg_str = android::base::Join(args, ' ');
  int ret = system(arg_str.c_str());
  if (ret != 0 && report_error) {
    LOG(ERROR) << "Failed to run cmd " << arg_str << ", exitcode " << ret;
    return false;
  }
  return ret == 0;
}

Workload::Workload(const std::vector<std::string>& args, const std::function<void()>& function)
    : work_state_(NotYetCreateNewProcess),
      child_proc_args_(args),
      child_proc_function_(function),
      work_pid_(-1),
      start_signal_fd_(-1),
      exec_child_fd_(-1) {
  kill_function_ = [](pid_t pid) { kill(pid, SIGKILL); };
}

Workload::~Workload() {
  if (work_pid_ != -1 && work_state_ != NotYetCreateNewProcess) {
    if (!Workload::WaitChildProcess(false, false, nullptr)) {
      kill_function_(work_pid_);
      Workload::WaitChildProcess(true, true, nullptr);
    }
  }
  if (start_signal_fd_ != -1) {
    close(start_signal_fd_);
  }
  if (exec_child_fd_ != -1) {
    close(exec_child_fd_);
  }
}

bool Workload::CreateNewProcess() {
  CHECK_EQ(work_state_, NotYetCreateNewProcess);

  int start_signal_pipe[2];
  if (pipe2(start_signal_pipe, O_CLOEXEC) != 0) {
    PLOG(ERROR) << "pipe2() failed";
    return false;
  }

  int exec_child_pipe[2];
  if (pipe2(exec_child_pipe, O_CLOEXEC) != 0) {
    PLOG(ERROR) << "pipe2() failed";
    close(start_signal_pipe[0]);
    close(start_signal_pipe[1]);
    return false;
  }

  pid_t pid = fork();
  if (pid == -1) {
    PLOG(ERROR) << "fork() failed";
    close(start_signal_pipe[0]);
    close(start_signal_pipe[1]);
    close(exec_child_pipe[0]);
    close(exec_child_pipe[1]);
    return false;
  } else if (pid == 0) {
    // In child process.
    close(start_signal_pipe[1]);
    close(exec_child_pipe[0]);
    ChildProcessFn(start_signal_pipe[0], exec_child_pipe[1]);
    _exit(0);
  }
  // In parent process.
  close(start_signal_pipe[0]);
  close(exec_child_pipe[1]);
  start_signal_fd_ = start_signal_pipe[1];
  exec_child_fd_ = exec_child_pipe[0];
  work_pid_ = pid;
  work_state_ = NotYetStartNewProcess;
  return true;
}

void Workload::ChildProcessFn(int start_signal_fd, int exec_child_fd) {
  // Die if parent exits.
  prctl(PR_SET_PDEATHSIG, SIGHUP, 0, 0, 0);

  char start_signal = 0;
  ssize_t nread = TEMP_FAILURE_RETRY(read(start_signal_fd, &start_signal, 1));
  if (nread == 1 && start_signal == 1) {
    close(start_signal_fd);
    if (child_proc_function_) {
      close(exec_child_fd);
      child_proc_function_();
    } else {
      char* argv[child_proc_args_.size() + 1];
      for (size_t i = 0; i < child_proc_args_.size(); ++i) {
        argv[i] = &child_proc_args_[i][0];
      }
      argv[child_proc_args_.size()] = nullptr;
      execvp(argv[0], argv);
      // If execvp() succeed, we will not arrive here. But if it failed, we need to
      // report the failure to the parent process by writing 1 to exec_child_fd.
      int saved_errno = errno;
      char exec_child_failed = 1;
      TEMP_FAILURE_RETRY(write(exec_child_fd, &exec_child_failed, 1));
      close(exec_child_fd);
      errno = saved_errno;
      PLOG(ERROR) << "child process failed to execvp(" << argv[0] << ")";
    }
  } else {
    PLOG(ERROR) << "child process failed to receive start_signal, nread = " << nread;
  }
}

bool Workload::SetCpuAffinity(int cpu) {
  CHECK_EQ(work_state_, NotYetStartNewProcess);
  cpu_set_t mask;
  CPU_ZERO(&mask);
  CPU_SET(cpu, &mask);
  if (sched_setaffinity(GetPid(), sizeof(mask), &mask) != 0) {
    PLOG(WARNING) << "sched_setaffinity failed";
    return false;
  }
  return true;
}

bool Workload::Start() {
  CHECK_EQ(work_state_, NotYetStartNewProcess);
  char start_signal = 1;
  ssize_t nwrite = TEMP_FAILURE_RETRY(write(start_signal_fd_, &start_signal, 1));
  if (nwrite != 1) {
    PLOG(ERROR) << "write start signal failed";
    return false;
  }
  char exec_child_failed;
  ssize_t nread = TEMP_FAILURE_RETRY(read(exec_child_fd_, &exec_child_failed, 1));
  if (nread != 0) {
    if (nread == -1) {
      PLOG(ERROR) << "failed to receive error message from child process";
    } else {
      LOG(ERROR) << "received error message from child process";
    }
    return false;
  }
  work_state_ = Started;
  return true;
}

bool Workload::WaitChildProcess(bool wait_forever, int* exit_code) {
  return WaitChildProcess(wait_forever, false, exit_code);
}

bool Workload::WaitChildProcess(bool wait_forever, bool is_child_killed, int* exit_code) {
  if (work_state_ == Finished) {
    return true;
  }
  bool finished = false;
  int status;
  pid_t result = TEMP_FAILURE_RETRY(waitpid(work_pid_, &status, (wait_forever ? 0 : WNOHANG)));
  if (result == work_pid_) {
    finished = true;
    work_state_ = Finished;
    if (WIFSIGNALED(status)) {
      if (!(is_child_killed && WTERMSIG(status) == SIGKILL)) {
        LOG(WARNING) << "child process was terminated by signal " << strsignal(WTERMSIG(status));
      }
    } else if (WIFEXITED(status)) {
      if (exit_code != nullptr) {
        *exit_code = WEXITSTATUS(status);
      } else if (WEXITSTATUS(status) != 0) {
        LOG(WARNING) << "child process exited with exit code " << WEXITSTATUS(status);
      }
    }
  } else if (result == -1) {
    PLOG(ERROR) << "waitpid() failed";
  }
  return finished;
}

}  // namespace simpleperf
