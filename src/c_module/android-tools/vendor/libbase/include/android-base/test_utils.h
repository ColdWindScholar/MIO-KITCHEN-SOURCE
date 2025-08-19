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

#pragma once

#include <regex>
#include <string>
#include <type_traits>

#include <android-base/file.h>
#include <android-base/macros.h>

class CapturedStdFd {
 public:
  CapturedStdFd(int std_fd);
  ~CapturedStdFd();

  std::string str();

  void Start();
  void Stop();
  void Reset();

 private:
  int fd() const;

  TemporaryFile temp_file_;
  int std_fd_;
  int old_fd_ = -1;

  DISALLOW_COPY_AND_ASSIGN(CapturedStdFd);
};

class CapturedStderr : public CapturedStdFd {
 public:
  CapturedStderr() : CapturedStdFd(STDERR_FILENO) {}
};

class CapturedStdout : public CapturedStdFd {
 public:
  CapturedStdout() : CapturedStdFd(STDOUT_FILENO) {}
};

#define __LIBBASE_GENERIC_REGEX_SEARCH(__s, __pattern) \
  (std::regex_search(__s, std::basic_regex<std::decay<decltype(__s[0])>::type>((__pattern))))

#define ASSERT_MATCH(__string, __pattern)                                      \
  do {                                                                         \
    auto __s = (__string);                                                     \
    if (!__LIBBASE_GENERIC_REGEX_SEARCH(__s, (__pattern))) {                   \
      FAIL() << "regex mismatch: expected " << (__pattern) << " in:\n" << __s; \
    }                                                                          \
  } while (0)

#define ASSERT_NOT_MATCH(__string, __pattern)                                              \
  do {                                                                                     \
    auto __s = (__string);                                                                 \
    if (__LIBBASE_GENERIC_REGEX_SEARCH(__s, (__pattern))) {                                \
      FAIL() << "regex mismatch: expected to not find " << (__pattern) << " in:\n" << __s; \
    }                                                                                      \
  } while (0)

#define EXPECT_MATCH(__string, __pattern)                                             \
  do {                                                                                \
    auto __s = (__string);                                                            \
    if (!__LIBBASE_GENERIC_REGEX_SEARCH(__s, (__pattern))) {                          \
      ADD_FAILURE() << "regex mismatch: expected " << (__pattern) << " in:\n" << __s; \
    }                                                                                 \
  } while (0)

#define EXPECT_NOT_MATCH(__string, __pattern)                                                     \
  do {                                                                                            \
    auto __s = (__string);                                                                        \
    if (__LIBBASE_GENERIC_REGEX_SEARCH(__s, (__pattern))) {                                       \
      ADD_FAILURE() << "regex mismatch: expected to not find " << (__pattern) << " in:\n" << __s; \
    }                                                                                             \
  } while (0)

extern "C" void __hwasan_init() __attribute__((weak));
static inline bool running_with_hwasan() {
  return &__hwasan_init != 0;
}

#define SKIP_WITH_HWASAN if (running_with_hwasan()) GTEST_SKIP()
