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

#include <signal.h>
#include <sys/time.h>
#include <unistd.h>

#include <algorithm>
#include <mutex>
#include <thread>

#include <android-base/logging.h>
#include <android-base/parsebool.h>
#include <android-base/parseint.h>
#include <android-base/properties.h>
#include <android-base/thread_annotations.h>

#include "property_monitor.h"

static constexpr char kAdbWatchdogProperty[] = "persist.adb.watchdog";
static constexpr char kTestHarnessProperty[] = "persist.sys.test_harness";

static constexpr unsigned int kDefaultAdbWatchdogTimeoutSeconds = 600;
static unsigned int g_watchdog_timeout_seconds;

static std::mutex g_watchdog_mutex [[clang::no_destroy]];

// The watchdog is "running" when it's enabled via property and there are no connected clients.
static bool g_watchdog_running GUARDED_BY(g_watchdog_mutex) = false;

static PropertyMonitor g_property_monitor [[clang::no_destroy]];

static void UpdateWatchdog() REQUIRES(g_watchdog_mutex) {
    static std::once_flag once;
    std::call_once(once, []() {
        signal(SIGALRM, [](int) {
            LOG(WARNING) << "adbd watchdog expired; rebooting...";
            execl("/system/bin/reboot", "/system/bin/reboot", "bootloader", nullptr);
        });
    });

    static bool alarm_set = false;

    static auto Arm = []() {
        LOG(INFO) << "adb watchdog armed, triggering in " << g_watchdog_timeout_seconds
                  << " seconds";
        alarm(g_watchdog_timeout_seconds);
        alarm_set = true;
    };

    static auto Disarm = []() {
        unsigned int previous = alarm(0);
        if (previous != 0) {
            LOG(INFO) << "adb watchdog disarmed with " << previous << " seconds left";
        }
        alarm_set = false;
    };

    bool watchdog_enabled = android::base::GetBoolProperty(
            kAdbWatchdogProperty, android::base::GetBoolProperty(kTestHarnessProperty, false));
    if (!watchdog_enabled) {
        if (alarm_set) {
            Disarm();
        }
        return;
    }

    if (g_watchdog_running) {
        if (!alarm_set) {
            Arm();
        }
    } else {
        Disarm();
    }
}

namespace watchdog {

void Start() {
    std::lock_guard<std::mutex> lock(g_watchdog_mutex);
    g_watchdog_running = true;
    UpdateWatchdog();
}

void Stop() {
    std::lock_guard<std::mutex> lock(g_watchdog_mutex);
    g_watchdog_running = false;
    UpdateWatchdog();
}

void Initialize() {
    for (auto& property : {kAdbWatchdogProperty, kTestHarnessProperty}) {
        g_property_monitor.Add(property, [property](std::string value) {
            LOG(INFO) << property << " set to '" << value << "'";

            std::lock_guard<std::mutex> lock(g_watchdog_mutex);
            UpdateWatchdog();
            return true;
        });
    }

    g_property_monitor.Add("persist.adb.watchdog.timeout_secs", [](std::string value) {
        // This presumably isn't going to change while the watchdog is armed,
        // so we don't need to recalculate a timer.
        {
            std::lock_guard<std::mutex> lock(g_watchdog_mutex);
            if (!android::base::ParseUint(value, &g_watchdog_timeout_seconds)) {
                g_watchdog_timeout_seconds = kDefaultAdbWatchdogTimeoutSeconds;
            }
        }

        LOG(INFO) << "adb watchdog timeout set to " << g_watchdog_timeout_seconds << " seconds";
        return true;
    });

    Start();
    std::thread([]() { g_property_monitor.Run(); }).detach();
}

}  // namespace watchdog
