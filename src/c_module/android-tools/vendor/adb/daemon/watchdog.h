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

#pragma once

// A consistent problem that automated test labs have is that devices will
// gradually fall offline and require manual recovery. For automated testing
// labs and similar other uses, adbd contains a watchdog that can be enabled
// to reboot the device if no client is connected for a configurable duration.
//
// To enable it, set the system property `persist.adb.watchdog` to "1".
// The timeout can be configured by `persist.adb.watchdog.timeout_secs`,
// with a default of 600 seconds.
//
// Additionally, the watchdog is automatically enabled when the device is in
// test harness mode (https://source.android.com/compatibility/cts/harness).
// Note that if `persist.adb.watchdog` is set, it will override the default
// in test harness mode, and `persist.adb.watchdog.timeout_secs` isn't
// preserved across factory reset.

#if defined(__ANDROID__)
namespace watchdog {

void Initialize();
void Start();
void Stop();

}  // namespace watchdog
#endif
