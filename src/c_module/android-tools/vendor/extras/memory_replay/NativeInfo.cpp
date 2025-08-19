/*
 * Copyright (C) 2014 The Android Open Source Project
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

#include <err.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#include <android-base/unique_fd.h>

#include "NativeInfo.h"

void NativeFormatFloat(char* buffer, size_t buffer_len, uint64_t value, uint64_t divisor) {
  uint64_t hundreds = ((((value % divisor) * 1000) / divisor) + 5) / 10;
  snprintf(buffer, buffer_len, "%" PRIu64 ".%02" PRIu64, value / divisor, hundreds);
}

// This function is not re-entrant since it uses a static buffer for
// the line data.
void NativeGetInfo(int smaps_fd, size_t* rss_bytes, size_t* va_bytes) {
  size_t total_rss_bytes = 0;
  size_t total_va_bytes = 0;
  bool native_map = false;

  char buf[1024];
  size_t buf_start = 0;
  size_t buf_bytes = 0;
  while (true) {
    ssize_t bytes =
        TEMP_FAILURE_RETRY(read(smaps_fd, buf + buf_bytes, sizeof(buf) - buf_bytes - 1));
    if (bytes <= 0) {
      break;
    }
    buf_bytes += bytes;
    while (buf_bytes > 0) {
      char* newline = reinterpret_cast<char*>(memchr(&buf[buf_start], '\n', buf_bytes));
      if (newline == nullptr) {
        break;
      }
      *newline = '\0';
      uintptr_t start, end;
      int name_pos;
      size_t native_rss_kB;
      if (sscanf(&buf[buf_start], "%" SCNxPTR "-%" SCNxPTR " %*4s %*x %*x:%*x %*d %n", &start, &end,
                 &name_pos) == 2) {
        char* map_name = &buf[buf_start + name_pos];
        if (strcmp(map_name, "[anon:libc_malloc]") == 0 || strcmp(map_name, "[heap]") == 0 ||
            strncmp(map_name, "[anon:scudo:", 12) == 0 ||
            strncmp(map_name, "[anon:GWP-ASan", 14) == 0) {
          total_va_bytes += end - start;
          native_map = true;
        } else {
          native_map = false;
        }
      } else if (native_map && sscanf(&buf[buf_start], "Rss: %zu", &native_rss_kB) == 1) {
        total_rss_bytes += native_rss_kB * 1024;
      }
      buf_bytes -= newline - &buf[buf_start] + 1;
      buf_start = newline - buf + 1;
    }
    if (buf_start > 0) {
      if (buf_bytes > 0) {
        memmove(buf, &buf[buf_start], buf_bytes);
      }
      buf_start = 0;
    }
  }
  *rss_bytes = total_rss_bytes;
  *va_bytes = total_va_bytes;
}

void NativePrintInfo(const char* preamble) {
  size_t rss_bytes;
  size_t va_bytes;

  android::base::unique_fd smaps_fd(open("/proc/self/smaps", O_RDONLY));
  if (smaps_fd == -1) {
    err(1, "Cannot open /proc/self/smaps");
  }

  NativeGetInfo(smaps_fd, &rss_bytes, &va_bytes);

  // Avoid any allocations, so use special non-allocating printfs.
  char buffer[256];
  NativeFormatFloat(buffer, sizeof(buffer), rss_bytes, 1024 * 1024);
  dprintf(STDOUT_FILENO, "%sNative RSS: %zu bytes %sMB\n", preamble, rss_bytes, buffer);
  NativeFormatFloat(buffer, sizeof(buffer), va_bytes, 1024 * 1024);
  dprintf(STDOUT_FILENO, "%sNative VA Space: %zu bytes %sMB\n", preamble, va_bytes, buffer);
}
