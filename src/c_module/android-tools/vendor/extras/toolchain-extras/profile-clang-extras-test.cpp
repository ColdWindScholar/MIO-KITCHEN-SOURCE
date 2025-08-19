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
#include <gtest/gtest.h>
#include <sys/stat.h>

#include "profile-extras.h"

static int flush_count = 0;

extern "C" {
int __llvm_profile_write_file() {
  flush_count++;
  return 0;
}
}

TEST(profile_extras, smoke) {
  flush_count = 0;

  ASSERT_EQ(0, flush_count);
  kill(getpid(), COVERAGE_FLUSH_SIGNAL);
  sleep(2);
  ASSERT_EQ(1, flush_count);
}

static const char* OPEN_AT_TEST_FNAME = "/data/misc/trace/test.profraw";
TEST(profile_extras, openat) {
  mode_t old_umask = umask(0077);
  unlink(OPEN_AT_TEST_FNAME);

  int fd = open(OPEN_AT_TEST_FNAME, O_RDWR | O_CREAT, 0666);
  ASSERT_NE(fd, -1);
  close(fd);
  umask(old_umask);

  struct stat stat_buf;
  ASSERT_EQ(stat(OPEN_AT_TEST_FNAME, &stat_buf), 0);
  ASSERT_EQ(stat_buf.st_mode & 0777, 0666);
  unlink(OPEN_AT_TEST_FNAME);
}
