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

#if defined(__ANDROID__)
#include <android-base/properties.h>
#endif

#include "command.h"
#include "environment.h"
#include "utils.h"

using namespace simpleperf;

#if defined(__ANDROID__)

bool AndroidSecurityCheck() {
  if (IsRoot()) {
    return true;
  }
  // Simpleperf can be executed by the shell, or by apps themselves. To avoid malicious apps
  // exploiting perf_event_open interface via simpleperf, simpleperf needs proof that the user
  // is expecting simpleperf to be ran:
  //   1) On Android < 11, perf_event_open is secured by perf_event_allow_path, which is controlled
  // by security.perf_harden property. perf_event_open syscall can be used only after user setting
  // security.perf_harden to 0 in shell. So we don't need to check security.perf_harden explicitly.
  //   2) On Android >= 11, perf_event_open may be controlled by selinux instead of
  // perf_event_allow_path. So we need to check security.perf_harden explicitly. If simpleperf is
  // running via shell, we already know the origin of the request is the user, so set the property
  // ourselves for convenience. When started by the app, we won't have the permission to set the
  // property, so the user will need to prove this intent by setting it manually via shell.
  //   3) On Android >= 13, besides perf_harden property, we use persist properties to allow an app
  // profiling itself even after device reboot. User needs to set the uid of the app which wants to
  // profile itself. And the permission has an expiration time.
  int android_version = GetAndroidVersion();
  if (android_version >= 13) {
    if (IsInAppUid() && android::base::GetUintProperty("persist.simpleperf.profile_app_uid", 0u,
                                                       UINT_MAX) == getuid()) {
      if (android::base::GetUintProperty<uint64_t>("persist.simpleperf.profile_app_expiration_time",
                                                   0, UINT64_MAX) > time(nullptr)) {
        return true;
      }
    }
  }
  if (android_version >= 11) {
    std::string prop_name = "security.perf_harden";
    if (android::base::GetProperty(prop_name, "") != "0") {
      if (!android::base::SetProperty(prop_name, "0")) {
        fprintf(stderr,
                "failed to set system property security.perf_harden to 0.\n"
                "Try using `adb shell setprop security.perf_harden 0` to allow profiling.\n");
        return false;
      }
    }
  }
  return true;
}

#endif

int main(int argc, char** argv) {
#if defined(__ANDROID__)
  if (!AndroidSecurityCheck()) {
    return 1;
  }
#endif
  RegisterAllCommands();
  return RunSimpleperfCmd(argc, argv) ? 0 : 1;
}
