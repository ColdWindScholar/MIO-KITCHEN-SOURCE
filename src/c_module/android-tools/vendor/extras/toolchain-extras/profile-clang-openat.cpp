/*
 * Copyright (C) 2020 The Android Open Source Project
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

#include <fcntl.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

// This file provides a wrapper for open.

extern "C" {

int __real_open(const char* pathname, int flags, ...);

static bool needs_mode(int flags) {
  return ((flags & O_CREAT) == O_CREAT) || ((flags & O_TMPFILE) == O_TMPFILE);
}

static const char* PROFRAW_START = "/data/misc/trace/";
static bool is_coverage_trace(const char* pathname) {
  if (strncmp(pathname, PROFRAW_START, strlen(PROFRAW_START)) == 0) return true;
  return false;
}

__attribute__((weak)) int __wrap_open(const char* pathname, int flags, ...) {
  if (!needs_mode(flags)) {
    return __real_open(pathname, flags);
  }

  va_list args;
  va_start(args, flags);
  mode_t mode = static_cast<mode_t>(va_arg(args, int));
  va_end(args);

  int ret = __real_open(pathname, flags, mode);
  if (ret != -1 && is_coverage_trace(pathname)) fchmod(ret, mode);
  return ret;
}
}
