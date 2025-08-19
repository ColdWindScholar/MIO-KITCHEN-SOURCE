/*
 * Copyright 2013 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
#define LOG_TAG "MemTracker"

#include "memtrack.h"

#include <ctype.h>
#include <dirent.h>
#include <fcntl.h>
#include <limits.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#include <algorithm>
#include <vector>

#include <log/log.h>

FileData::FileData(char *filename, char *buffer, size_t buffer_len)
    : data_(buffer), max_(buffer_len), cur_idx_(0), len_(0),
      read_complete_(false) {
  fd_ = open(filename, O_RDONLY);
  if (fd_ < 0) {
    read_complete_ = true;
  }
}

FileData::~FileData() {
  if (fd_ >= 0) {
    close(fd_);
  }
}

bool FileData::isAvail(size_t bytes_needed) {
  if (cur_idx_ + bytes_needed < len_) {
    return true;
  }

  if (read_complete_) {
    return false;
  }

  if (cur_idx_ != len_) {
    // Copy the leftover to the front of the buffer.
    len_ = len_ - cur_idx_;
    memcpy(data_, data_ + cur_idx_, len_);
  }

  ssize_t bytes;
  cur_idx_ = 0;
  while (cur_idx_ + bytes_needed >= len_) {
    bytes = read(fd_, data_ + len_, max_ - len_);
    if (bytes == 0 || bytes == -1) {
      read_complete_ = true;
      break;
    }
    len_ += bytes;
  }

  return cur_idx_ + bytes_needed < len_;
}

bool FileData::getPss(size_t *pss) {
  size_t value;
  while (true) {
    if (!isAvail(4)) {
      return false;
    }

    if (data_[cur_idx_] != 'P' || data_[cur_idx_+1] != 's' ||
        data_[cur_idx_+2] != 's' || data_[cur_idx_+3] != ':') {
      // Consume the rest of the line.
      while (isAvail(1) && data_[cur_idx_++] != '\n');
    } else {
      cur_idx_ += 4;
      while (isAvail(1) && isspace(data_[cur_idx_])) {
        cur_idx_++;
      }

      value = 0;
      while (isAvail(1) && isdigit(data_[cur_idx_])) {
        value = value * 10 + data_[cur_idx_] - '0';
        cur_idx_++;
      }
      *pss = value;

      // Consume the rest of the line.
      while (isAvail(1) && data_[cur_idx_++] != '\n');

      return true;
    }
  }
}

const char *ProcessInfo::kProc = "/proc/";
const char *ProcessInfo::kCmdline = "/cmdline";
const char *ProcessInfo::kSmaps = "/smaps";

ProcessInfo::ProcessInfo() {
  memcpy(proc_file_, kProc, kProcLen);
}

ProcessInfo::~ProcessInfo() {
}

bool ProcessInfo::getInformation(int pid, char *pid_str, size_t pid_str_len) {
  memcpy(proc_file_ + kProcLen, pid_str, pid_str_len);
  memcpy(proc_file_ + kProcLen + pid_str_len, kCmdline, kCmdlineLen);

  // Read the cmdline for the process.
  int fd = open(proc_file_, O_RDONLY);
  if (fd < 0) {
    return false;
  }

  ssize_t bytes = read(fd, cmd_name_, sizeof(cmd_name_));
  close(fd);
  if (bytes == -1 || bytes == 0) {
    return false;
  }

  memcpy(proc_file_ + kProcLen + pid_str_len, kSmaps, kSmapsLen);
  FileData smaps(proc_file_, buffer_, sizeof(buffer_));

  cur_process_info_t process_info;
  size_t pss_kb;
  process_info.pss_kb = 0;
  while (smaps.getPss(&pss_kb)) {
    process_info.pss_kb += pss_kb;
  }

  if (cur_.count(cmd_name_) == 0) {
    cur_[cmd_name_] = process_info;
  } else {
    cur_[cmd_name_].pss_kb += process_info.pss_kb;
  }
  cur_[cmd_name_].pids.push_back(pid);

  return true;
}

void ProcessInfo::scan() {
  DIR *proc_dir = opendir(kProc);
  if (proc_dir == NULL) {
    perror("Cannot open directory.\n");
    exit(1);
  }

  // Clear any current pids.
  for (processes_t::iterator it = all_.begin(); it != all_.end(); ++it) {
    it->second.pids.clear();
  }

  struct dirent *dir_data;
  int len;
  bool is_pid;
  size_t pid;
  cur_.clear();
  while ((dir_data = readdir(proc_dir))) {
    // Check if the directory entry represents a pid.
    len = strlen(dir_data->d_name);
    is_pid = true;
    pid = 0;
    for (int i = 0; i < len; i++) {
      if (!isdigit(dir_data->d_name[i])) {
        is_pid = false;
        break;
      }
      pid = pid * 10 + dir_data->d_name[i] - '0';
    }
    if (is_pid) {
      getInformation(pid, dir_data->d_name, len);
    }
  }
  closedir(proc_dir);

  // Loop through the current processes and add them into our real list.
  for (cur_processes_t::const_iterator it = cur_.begin();
       it != cur_.end(); ++it) {

    if (all_.count(it->first) == 0) {
      // Initialize all of the variables.
      all_[it->first].num_samples = 0;
      all_[it->first].name = it->first;
      all_[it->first].avg_pss_kb = 0;
      all_[it->first].min_pss_kb = 0;
      all_[it->first].max_pss_kb = 0;
    }

    if (it->second.pids.size() > all_[it->first].max_num_pids) {
      all_[it->first].max_num_pids = it->second.pids.size();
    }

    all_[it->first].pids = it->second.pids;

    if (it->second.pss_kb > all_[it->first].max_pss_kb) {
      all_[it->first].max_pss_kb = it->second.pss_kb;
    }

    if (all_[it->first].min_pss_kb == 0 ||
        it->second.pss_kb < all_[it->first].min_pss_kb) {
      all_[it->first].min_pss_kb = it->second.pss_kb;
    }

    all_[it->first].last_pss_kb = it->second.pss_kb;

    computeAvg(&all_[it->first].avg_pss_kb, it->second.pss_kb,
               all_[it->first].num_samples);
    all_[it->first].num_samples++;
  }
}

bool comparePss(const process_info_t *first, const process_info_t *second) {
  return first->max_pss_kb > second->max_pss_kb;
}

void ProcessInfo::dumpToLog() {
  list_.clear();
  for (processes_t::const_iterator it = all_.begin(); it != all_.end(); ++it) {
    list_.push_back(&it->second);
  }

  // Now sort the list.
  std::sort(list_.begin(), list_.end(), comparePss);

  ALOGI("Dumping process list");
  for (std::vector<const process_info_t *>::const_iterator it = list_.begin();
       it != list_.end(); ++it) {
    ALOGI("  Name: %s", (*it)->name.c_str());
    ALOGI("    Max running processes: %zu", (*it)->max_num_pids);
    if ((*it)->pids.size() > 0) {
      ALOGI("    Currently running pids:");
      for (std::vector<int>::const_iterator pid_it = (*it)->pids.begin();
           pid_it != (*it)->pids.end(); ++pid_it) {
        ALOGI("      %d", *pid_it);
      }
    }

    ALOGI("    Min  PSS %0.4fM", (*it)->min_pss_kb/1024.0);
    ALOGI("    Avg  PSS %0.4fM", (*it)->avg_pss_kb/1024.0);
    ALOGI("    Max  PSS %0.4fM", (*it)->max_pss_kb/1024.0);
    ALOGI("    Last PSS %0.4fM", (*it)->last_pss_kb/1024.0);
  }
}

void usage() {
  printf("Usage: memtrack [--verbose | --quiet] [--scan_delay TIME_SECS]\n");
  printf("  --scan_delay TIME_SECS\n");
  printf("    The amount of delay in seconds between scans.\n");
  printf("  --verbose\n");
  printf("    Print information about the scans to stdout only.\n");
  printf("  --quiet\n");
  printf("    Nothing will be printed to stdout.\n");
  printf("  All scan data is dumped to the android log using the tag %s\n",
         LOG_TAG);
}

int SignalReceived = 0;

int SignalsToHandle[] = {
  SIGTSTP,
  SIGINT,
  SIGHUP,
  SIGPIPE,
  SIGUSR1,
};

void handleSignal(int signo) {
  if (SignalReceived == 0) {
    SignalReceived = signo;
  }
}

int main(int argc, char **argv) {
  if (geteuid() != 0) {
    printf("Must be run as root.\n");
    exit(1);
  }

  bool verbose = false;
  bool quiet = false;
  unsigned int scan_delay_sec = DEFAULT_SLEEP_DELAY_SECONDS;
  for (int i = 1; i < argc; i++) {
    if (strcmp(argv[i], "--verbose") == 0) {
      verbose = true;
    } else if (strcmp(argv[i], "--quiet") == 0) {
      quiet = true;
    } else if (strcmp(argv[i], "--scan_delay") == 0) {
      if (i+1 == argc) {
        printf("The %s options requires a single argument.\n", argv[i]);
        usage();
        exit(1);
      }
      scan_delay_sec = atoi(argv[++i]);
    } else {
      printf("Unknown option %s\n", argv[i]);
      usage();
      exit(1);
    }
  }
  if (quiet && verbose) {
    printf("Both --quiet and --verbose cannot be specified.\n");
    usage();
    exit(1);
  }

  // Set up the signal handlers.
  for (size_t i = 0; i < sizeof(SignalsToHandle)/sizeof(int); i++) {
    if (signal(SignalsToHandle[i], handleSignal) == SIG_ERR) {
      printf("Unable to handle signal %d\n", SignalsToHandle[i]);
      exit(1);
    }
  }

  ProcessInfo proc_info;

  if (!quiet) {
    printf("Hit Ctrl-Z or send SIGUSR1 to pid %d to print the current list of\n",
           getpid());
    printf("processes.\n");
    printf("Hit Ctrl-C to print the list of processes and terminate.\n");
  }

  struct timespec t;
  unsigned long long nsecs;
  while (true) {
    if (verbose) {
      memset(&t, 0, sizeof(t));
      clock_gettime(CLOCK_MONOTONIC, &t);
      nsecs = (unsigned long long)t.tv_sec*NS_PER_SEC + t.tv_nsec;
    }
    proc_info.scan();
    if (verbose) {
      memset(&t, 0, sizeof(t));
      clock_gettime(CLOCK_MONOTONIC, &t);
      nsecs = ((unsigned long long)t.tv_sec*NS_PER_SEC + t.tv_nsec) - nsecs;
      printf("Scan Time %0.4f\n", ((double)nsecs)/NS_PER_SEC);
    }

    if (SignalReceived != 0) {
      proc_info.dumpToLog();
      if (SignalReceived != SIGUSR1 && SignalReceived != SIGTSTP) {
        if (!quiet) {
          printf("Terminating...\n");
        }
        exit(1);
      }
      SignalReceived = 0;
    }
    sleep(scan_delay_sec);
  }
}
