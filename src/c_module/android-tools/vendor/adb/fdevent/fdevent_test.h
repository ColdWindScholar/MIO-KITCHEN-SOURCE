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

#include <gtest/gtest.h>

#include <condition_variable>
#include <mutex>
#include <thread>

#include "adb_io.h"
#include "adb_unique_fd.h"
#include "socket.h"
#include "sysdeps.h"
#include "sysdeps/chrono.h"

static void WaitForFdeventLoop() {
    // Sleep for a bit to make sure that network events have propagated.
    std::this_thread::sleep_for(100ms);

    // fdevent_run_on_looper has a guaranteed ordering, and is guaranteed to happen after
    // socket events, so as soon as our function is called, we know that we've processed all
    // previous events.
    std::mutex mutex;
    std::condition_variable cv;
    std::unique_lock<std::mutex> lock(mutex);
    fdevent_run_on_looper([&]() {
        mutex.lock();
        mutex.unlock();
        cv.notify_one();
    });
    cv.wait(lock);
}

class FdeventTest : public ::testing::Test {
  protected:
    ~FdeventTest() {
        if (thread_.joinable()) {
            TerminateThread();
        }
    }

    static void SetUpTestCase() {
#if !defined(_WIN32)
        ASSERT_NE(SIG_ERR, signal(SIGPIPE, SIG_IGN));
#endif
    }

    void SetUp() override {
        fdevent_reset();
        ASSERT_EQ(0u, fdevent_installed_count());
    }

    void PrepareThread() {
        thread_ = std::thread([]() { fdevent_loop(); });
        WaitForFdeventLoop();
    }

    void TerminateThread() {
        fdevent_terminate_loop();
        thread_.join();
    }

    std::thread thread_;
};
