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

#ifndef __MEMTRACK_H__
#define __MEMTRACK_H__

#include <sys/types.h>

#include <map>
#include <string>
#include <vector>

#define DEFAULT_SLEEP_DELAY_SECONDS 5
#ifndef NS_PER_SEC
#define NS_PER_SEC 1000000000ULL
#endif

class FileData {
public:
  FileData(char *filename, char *buffer, size_t buffer_len);
  ~FileData();

  // Get the PSS information from the file data. If there are no more
  // PSS values to be found, return false.
  bool getPss(size_t *pss);

  // Check if there is at least bytes available in the file data.
  bool isAvail(size_t bytes);

private:
  int fd_;
  char *data_;
  size_t max_;
  size_t cur_idx_;
  size_t len_;
  bool read_complete_;
};

typedef struct {
  std::string name;

  size_t max_num_pids;

  size_t num_samples;
  double avg_pss_kb;
  size_t min_pss_kb;
  size_t max_pss_kb;
  size_t last_pss_kb;

  std::vector<int> pids;
} process_info_t;
typedef std::map<std::string, process_info_t> processes_t;

typedef struct {
  size_t pss_kb;

  std::vector<int> pids;
} cur_process_info_t;
typedef std::map<std::string, cur_process_info_t> cur_processes_t;

class ProcessInfo {
public:
  ProcessInfo();
  ~ProcessInfo();

  // Get the information about a single process.
  bool getInformation(int pid, char *pid_str, size_t pid_str_len);

  // Scan all of the running processes.
  void scan();

  // Dump the information about all of the processes in the system to the log.
  void dumpToLog();

private:
  static const size_t kBufferLen = 4096;
  static const size_t kCmdNameLen = 1024;

  static const char *kProc;
  static const size_t kProcLen = 6;

  static const char *kCmdline;
  static const size_t kCmdlineLen = 9;  // Includes \0 at end of string.

  static const char *kSmaps;
  static const size_t kSmapsLen = 7;  // Includes \0 at end of string.

  static const char *kStatus;
  static const size_t kStatusLen = 8;  // Includes \0 at end of string.

  static const size_t kInitialEntries = 1000;

  char proc_file_[PATH_MAX];
  char buffer_[kBufferLen];

  char cmd_name_[kCmdNameLen];

  // Minimize a need for a lot of allocations by keeping our maps and
  // lists in this object.
  processes_t all_;
  cur_processes_t cur_;
  std::vector<const process_info_t *> list_;

  // Compute a running average.
  static inline void computeAvg(double *running_avg, size_t cur_avg,
                                size_t num_samples) {
    *running_avg = (*running_avg/(num_samples+1))*num_samples
                   + (double)cur_avg/(num_samples+1);
  }
};

#endif  // __MEMTRACK_H__
