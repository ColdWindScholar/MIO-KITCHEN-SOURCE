/*
 * Copyright (C) 2016 The Android Open Source Project
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

#include "IOEventLoop.h"

#include <gtest/gtest.h>

#include <atomic>
#include <chrono>
#include <thread>

#include <android-base/logging.h>

using namespace simpleperf;

// @CddTest = 6.1/C-0-2
TEST(IOEventLoop, read) {
  int fd[2];
  ASSERT_EQ(0, pipe(fd));
  IOEventLoop loop;
  int count = 0;
  int retry_count = 0;
  ASSERT_NE(nullptr, loop.AddReadEvent(fd[0], [&]() {
    while (true) {
      char c;
      int ret = read(fd[0], &c, 1);
      if (ret == 1) {
        if (++count == 100) {
          return loop.ExitLoop();
        }
      } else if (ret == -1 && errno == EAGAIN) {
        retry_count++;
        break;
      } else {
        return false;
      }
    }
    return true;
  }));
  std::thread thread([&]() {
    for (int i = 0; i < 100; ++i) {
      usleep(1000);
      char c;
      CHECK_EQ(write(fd[1], &c, 1), 1);
    }
  });
  ASSERT_TRUE(loop.RunLoop());
  thread.join();
  ASSERT_EQ(100, count);
  // Test retry_count to make sure we are not doing blocking read.
  ASSERT_GT(retry_count, 0);
  close(fd[0]);
  close(fd[1]);
}

// @CddTest = 6.1/C-0-2
TEST(IOEventLoop, write) {
  int fd[2];
  ASSERT_EQ(0, pipe(fd));
  IOEventLoop loop;
  int count = 0;
  ASSERT_NE(nullptr, loop.AddWriteEvent(fd[1], [&]() {
    int ret = 0;
    char buf[4096];
    while ((ret = write(fd[1], buf, sizeof(buf))) > 0) {
    }
    if (ret == -1 && errno == EAGAIN) {
      if (++count == 100) {
        loop.ExitLoop();
      }
      return true;
    }
    return false;
  }));
  std::thread thread([&]() {
    usleep(500000);
    while (true) {
      usleep(1000);
      char buf[4096];
      if (read(fd[0], buf, sizeof(buf)) <= 0) {
        break;
      }
    }
  });
  ASSERT_TRUE(loop.RunLoop());
  // close fd[1] to make read thread stop.
  close(fd[1]);
  thread.join();
  close(fd[0]);
  ASSERT_EQ(100, count);
}

// @CddTest = 6.1/C-0-2
TEST(IOEventLoop, signal) {
  IOEventLoop loop;
  int count = 0;
  ASSERT_TRUE(loop.AddSignalEvent(SIGINT, [&]() {
    if (++count == 100) {
      loop.ExitLoop();
    }
    return true;
  }));
  std::atomic<bool> stop_thread(false);
  std::thread thread([&]() {
    while (!stop_thread) {
      usleep(1000);
      kill(getpid(), SIGINT);
    }
  });
  ASSERT_TRUE(loop.RunLoop());
  stop_thread = true;
  thread.join();
  ASSERT_EQ(100, count);
}

void TestPeriodicEvents(int period_in_us, int iterations) {
  timeval tv;
  tv.tv_sec = period_in_us / 1000000;
  tv.tv_usec = period_in_us % 1000000;
  int count = 0;
  IOEventLoop loop;
  ASSERT_TRUE(loop.AddPeriodicEvent(tv, [&]() {
    if (++count == iterations) {
      loop.ExitLoop();
    }
    return true;
  }));
  auto start_time = std::chrono::steady_clock::now();
  ASSERT_TRUE(loop.RunLoop());
  auto end_time = std::chrono::steady_clock::now();
  ASSERT_EQ(iterations, count);
  double time_used =
      std::chrono::duration_cast<std::chrono::duration<double>>(end_time - start_time).count();
  double min_time_in_sec = period_in_us / 1e6 * iterations;
  double max_time_in_sec = min_time_in_sec + 0.3;
  ASSERT_GE(time_used, min_time_in_sec);
  ASSERT_LT(time_used, max_time_in_sec);
}

// @CddTest = 6.1/C-0-2
TEST(IOEventLoop, periodic) {
  TestPeriodicEvents(1000, 100);
}

// @CddTest = 6.1/C-0-2
TEST(IOEventLoop, one_time_event) {
  int duration_in_us = 1000;
  timeval tv = {};
  tv.tv_usec = duration_in_us;
  int count = 0;
  auto callback_time = std::chrono::steady_clock::now();
  IOEventLoop loop;
  // Add a one time event to test callback count and time.
  ASSERT_TRUE(loop.AddOneTimeEvent(tv, [&]() {
    ++count;
    callback_time = std::chrono::steady_clock::now();
    return true;
  }));
  // Add another one time event to exit loop.
  tv.tv_usec = duration_in_us * 3;
  ASSERT_TRUE(loop.AddOneTimeEvent(tv, [&]() { return loop.ExitLoop(); }));

  auto start_time = std::chrono::steady_clock::now();
  ASSERT_TRUE(loop.RunLoop());
  ASSERT_EQ(1, count);
  double time_used =
      std::chrono::duration_cast<std::chrono::duration<double>>(callback_time - start_time).count();
  double min_time_in_sec = duration_in_us / 1e6;
  double max_time_in_sec = min_time_in_sec + 0.3;
  ASSERT_GE(time_used, min_time_in_sec);
  ASSERT_LT(time_used, max_time_in_sec);
}

// @CddTest = 6.1/C-0-2
TEST(IOEventLoop, read_and_del_event) {
  int fd[2];
  ASSERT_EQ(0, pipe(fd));
  IOEventLoop loop;
  int count = 0;
  IOEventRef ref = loop.AddReadEvent(fd[0], [&]() {
    count++;
    return IOEventLoop::DelEvent(ref);
  });
  ASSERT_NE(nullptr, ref);

  std::thread thread([&]() {
    for (int i = 0; i < 100; ++i) {
      usleep(1000);
      char c;
      CHECK_EQ(write(fd[1], &c, 1), 1);
    }
  });
  ASSERT_TRUE(loop.RunLoop());
  thread.join();
  ASSERT_EQ(1, count);
  close(fd[0]);
  close(fd[1]);
}

// @CddTest = 6.1/C-0-2
TEST(IOEventLoop, disable_enable_event) {
  int fd[2];
  ASSERT_EQ(0, pipe(fd));
  IOEventLoop loop;
  int count = 0;
  IOEventRef ref = loop.AddWriteEvent(fd[1], [&]() {
    count++;
    return IOEventLoop::DisableEvent(ref);
  });
  ASSERT_NE(nullptr, ref);

  timeval tv;
  tv.tv_sec = 0;
  tv.tv_usec = 500000;
  int periodic_count = 0;
  ASSERT_TRUE(loop.AddPeriodicEvent(tv, [&]() {
    periodic_count++;
    if (periodic_count == 1) {
      if (count != 1) {
        return false;
      }
      return IOEventLoop::EnableEvent(ref);
    } else {
      if (count != 2) {
        return false;
      }
      return loop.ExitLoop();
    }
  }));

  ASSERT_TRUE(loop.RunLoop());
  ASSERT_EQ(2, count);
  ASSERT_EQ(2, periodic_count);
  close(fd[0]);
  close(fd[1]);
}

// @CddTest = 6.1/C-0-2
TEST(IOEventLoop, disable_enable_periodic_event) {
  timeval tv;
  tv.tv_sec = 0;
  tv.tv_usec = 200000;
  IOEventLoop loop;
  IOEventRef wait_ref = loop.AddPeriodicEvent(tv, [&]() { return loop.ExitLoop(); });
  ASSERT_TRUE(wait_ref != nullptr);
  ASSERT_TRUE(loop.DisableEvent(wait_ref));

  tv.tv_sec = 0;
  tv.tv_usec = 100000;
  size_t periodic_count = 0;
  IOEventRef ref = loop.AddPeriodicEvent(tv, [&]() {
    if (!loop.DisableEvent(ref)) {
      return false;
    }
    periodic_count++;
    if (periodic_count < 2u) {
      return loop.EnableEvent(ref);
    }
    return loop.EnableEvent(wait_ref);
  });
  ASSERT_TRUE(loop.RunLoop());
  ASSERT_EQ(2u, periodic_count);
}

// @CddTest = 6.1/C-0-2
TEST(IOEventLoop, exit_before_loop) {
  IOEventLoop loop;
  ASSERT_TRUE(loop.ExitLoop());
}

// @CddTest = 6.1/C-0-2
TEST(IOEventLoop, priority) {
  int low_priority_fd[2];
  ASSERT_EQ(0, pipe(low_priority_fd));
  int high_priority_fd[2];
  ASSERT_EQ(0, pipe(high_priority_fd));

  IOEventLoop loop;
  int count = 0;

  ASSERT_NE(nullptr, loop.AddReadEvent(
                         low_priority_fd[0],
                         [&]() {
                           char c;
                           read(low_priority_fd[0], &c, 1);
                           CHECK_EQ(count, 1);
                           count++;
                           return loop.ExitLoop();
                         },
                         IOEventLowPriority));

  ASSERT_NE(nullptr, loop.AddReadEvent(
                         high_priority_fd[0],
                         [&]() {
                           char c;
                           read(high_priority_fd[0], &c, 1);
                           CHECK_EQ(count, 0);
                           count++;
                           return true;
                         },
                         IOEventHighPriority));

  char c;
  CHECK_EQ(write(low_priority_fd[1], &c, 1), 1);
  CHECK_EQ(write(high_priority_fd[1], &c, 1), 1);
  ASSERT_TRUE(loop.RunLoop());
  ASSERT_EQ(2, count);
  for (int i = 0; i < 2; i++) {
    close(low_priority_fd[i]);
    close(high_priority_fd[i]);
  }
}
