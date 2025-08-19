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

#include <gtest/gtest.h>

#include <signal.h>

#include "IOEventLoop.h"
#include "utils.h"
#include "workload.h"

using namespace simpleperf;

// @CddTest = 6.1/C-0-2
TEST(workload, success) {
  IOEventLoop loop;
  ASSERT_TRUE(loop.AddSignalEvent(SIGCHLD, [&]() { return loop.ExitLoop(); }));
  auto workload = Workload::CreateWorkload({"sleep", "1"});
  ASSERT_TRUE(workload != nullptr);
  ASSERT_TRUE(workload->GetPid() != 0);
  ASSERT_TRUE(workload->Start());
  ASSERT_TRUE(loop.RunLoop());
}

// @CddTest = 6.1/C-0-2
TEST(workload, execvp_failure) {
  auto workload = Workload::CreateWorkload({"/dev/null"});
  ASSERT_TRUE(workload != nullptr);
  ASSERT_FALSE(workload->Start());
}

static void run_signaled_workload() {
  {
    IOEventLoop loop;
    ASSERT_TRUE(loop.AddSignalEvent(SIGCHLD, [&]() { return loop.ExitLoop(); }));
    auto workload = Workload::CreateWorkload({"sleep", "10"});
    ASSERT_TRUE(workload != nullptr);
    ASSERT_TRUE(workload->Start());
    ASSERT_EQ(0, kill(workload->GetPid(), SIGKILL));
    ASSERT_TRUE(loop.RunLoop());
  }
  // Make sure all destructors are called before exit().
  exit(0);
}

// @CddTest = 6.1/C-0-2
TEST(workload, signaled_warning) {
  ASSERT_EXIT(run_signaled_workload(), testing::ExitedWithCode(0),
              "child process was terminated by signal");
}

static void run_exit_nonzero_workload() {
  {
    IOEventLoop loop;
    ASSERT_TRUE(loop.AddSignalEvent(SIGCHLD, [&]() { return loop.ExitLoop(); }));
    auto workload = Workload::CreateWorkload({"ls", "nonexistdir"});
    ASSERT_TRUE(workload != nullptr);
    ASSERT_TRUE(workload->Start());
    ASSERT_TRUE(loop.RunLoop());
  }
  // Make sure all destructors are called before exit().
  exit(0);
}

// @CddTest = 6.1/C-0-2
TEST(workload, exit_nonzero_warning) {
  ASSERT_EXIT(run_exit_nonzero_workload(), testing::ExitedWithCode(0),
              "child process exited with exit code");
}
