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

#include <dirent.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>

#include <map>
#include <memory>
#include <string>
#include <vector>

#include <android-base/stringprintf.h>

#include "tasklist.h"

template <typename Func>
static bool ScanPidsInDir(const std::string& name, Func f) {
  std::unique_ptr<DIR, decltype(&closedir)> dir(opendir(name.c_str()), closedir);
  if (!dir) {
    return false;
  }

  dirent* entry;
  while ((entry = readdir(dir.get())) != nullptr) {
    if (isdigit(entry->d_name[0])) {
      pid_t pid = atoi(entry->d_name);
      f(pid);
    }
  }

  return true;
}

bool TaskList::Scan(std::map<pid_t, std::vector<pid_t>>& tgid_map) {
  tgid_map.clear();

  return ScanPidsInDir("/proc", [&tgid_map](pid_t tgid) {
    std::vector<pid_t> pid_list;
    if (ScanPid(tgid, pid_list)) {
      tgid_map.insert({tgid, pid_list});
    }
  });
}

bool TaskList::ScanPid(pid_t tgid, std::vector<pid_t>& pid_list) {
  std::string filename = android::base::StringPrintf("/proc/%d/task", tgid);

  return ScanPidsInDir(filename, [&pid_list](pid_t pid) { pid_list.push_back(pid); });
}
