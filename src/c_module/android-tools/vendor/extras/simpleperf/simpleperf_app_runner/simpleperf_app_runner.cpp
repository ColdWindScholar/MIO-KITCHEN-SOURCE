/*
 * Copyright (C) 2018 The Android Open Source Project
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

#include <errno.h>
#include <error.h>
#include <fcntl.h>
#include <stdio.h>
#include <sys/types.h>
#include <unistd.h>

#include <set>
#include <string>
#include <string_view>
#include <vector>

#include <android-base/file.h>
#include <android-base/parseint.h>
#include <android-base/stringprintf.h>
#include <android-base/strings.h>
#include <packagelistparser/packagelistparser.h>
#include <private/android_filesystem_config.h>
#include <scoped_minijail.h>
#include <selinux/android.h>

#include "../cmd_api_impl.h"
#include "../cmd_record_impl.h"
#include "../cmd_stat_impl.h"

using android::base::ParseInt;
using android::base::ParseUint;
using android::base::Realpath;
using android::base::StartsWith;
using android::base::StringPrintf;
using namespace simpleperf;

// simpleperf_app_runner is used to run simpleperf to profile apps with <profileable shell="true">
// on user devices. It works as below:
//   simpleperf cmds in shell -> simpleperf_app_runner -> /system/bin/simpleperf in app's context
//
// 1. User types simpleperf cmds in adb shell. If that is to profile an app, simpleperf calls
//    /system/bin/simpleperf_app_runner with profiling arguments.
// 2. simpleperf_app_runner checks if the app is profileable_from_shell. Then it switches the
//    process to the app's user id / group id, switches secontext to the app's domain, and
//    executes /system/bin/simpleperf with profiling arguments.
// 3. /system/bin/simpleperf records profiling data and writes profiling data to a file descriptor
//    opened by simpleperf cmds in shell.

struct PackageListCallbackArg {
  const char* name;
  pkg_info* info;
};

static bool PackageListParseCallback(pkg_info* info, void* userdata) {
  PackageListCallbackArg* arg = static_cast<PackageListCallbackArg*>(userdata);
  if (strcmp(arg->name, info->name) == 0) {
    arg->info = info;
    return false;
  }
  packagelist_free(info);
  return true;
}

pkg_info* ReadPackageInfo(const char* pkgname) {
  // Switch to package_info gid to read package info.
  gid_t old_egid = getegid();
  if (setegid(AID_PACKAGE_INFO) == -1) {
    error(1, errno, "setegid failed");
  }
  PackageListCallbackArg arg;
  arg.name = pkgname;
  arg.info = nullptr;
  if (!packagelist_parse(PackageListParseCallback, &arg)) {
    error(1, errno, "packagelist_parse failed");
  }
  if (setegid(old_egid) == -1) {
    error(1, errno, "setegid failed");
  }
  return arg.info;
}

std::vector<gid_t> GetSupplementaryGids(uid_t userAppId) {
  std::vector<gid_t> gids;
  int size = getgroups(0, &gids[0]);
  if (size < 0) {
    error(1, errno, "getgroups failed");
  }
  gids.resize(size);
  size = getgroups(size, &gids[0]);
  if (size != static_cast<int>(gids.size())) {
    error(1, errno, "getgroups failed");
  }
  // Profile guide compiled oat files (like /data/app/xxx/oat/arm64/base.odex) are not readable
  // worldwide (DEXOPT_PUBLIC flag isn't set). To support reading them (needed by simpleperf for
  // profiling), add shared app gid to supplementary groups.
  gid_t shared_app_gid = userAppId % AID_USER_OFFSET - AID_APP_START + AID_SHARED_GID_START;
  gids.push_back(shared_app_gid);
  return gids;
}

static void CheckSimpleperfArguments(std::string_view cmd_name, char** args) {
  const OptionFormatMap& common_formats = GetCommonOptionFormatMap();
  const OptionFormatMap* formats = nullptr;
  if (cmd_name == "api-collect") {
    formats = &GetApiCollectCmdOptionFormats();
  } else if (cmd_name == "record") {
    formats = &GetRecordCmdOptionFormats();
  } else if (cmd_name == "stat") {
    formats = &GetStatCmdOptionFormats();
  } else {
    error(1, 0, "cmd isn't allowed: %s", cmd_name.data());
  }

  for (size_t i = 0; args[i] != nullptr; ++i) {
    auto it = formats->find(args[i]);
    if (it == formats->end()) {
      it = common_formats.find(args[i]);
      if (it == common_formats.end()) {
        error(1, 0, "arg isn't allowed: %s", args[i]);
      }
    }
    const OptionFormat& format = it->second;
    if (format.value_type != OptionValueType::NONE && args[i + 1] == nullptr) {
      error(1, 0, "invalid arg: %s", args[i]);
    }
    switch (format.app_runner_type) {
      case AppRunnerType::ALLOWED:
        break;
      case AppRunnerType::NOT_ALLOWED:
        error(1, 0, "arg isn't allowed: %s", args[i]);
        break;
      case AppRunnerType::CHECK_FD: {
        int fd;
        if (!ParseInt(args[i + 1], &fd) || fd < 3 || fcntl(fd, F_GETFD) == -1) {
          error(1, 0, "invalid fd for arg: %s", args[i]);
        }
        break;
      }
      case AppRunnerType::CHECK_PATH: {
        std::string path;
        if (!Realpath(args[i + 1], &path) || !StartsWith(path, "/data/local/tmp/")) {
          error(1, 0, "invalid path for arg: %s", args[i]);
        }
        break;
      }
    }
    if (format.value_type != OptionValueType::NONE) {
      ++i;
    }
  }
}

int main(int argc, char* argv[]) {
  if (argc < 3) {
    fprintf(
        stderr,
        // clang-format off
"Usage: simpleperf_app_runner package_name [options] [simpleperf cmd simpleperf_cmd_args]\n"
"Options:\n"
"--user uid        profile app process run by uid\n"
"--show-app-type   show if the app is debuggable or profileable\n"
        // clang-format on
    );
    return 1;
  }
  int i = 1;
  char* pkgname = argv[i++];
  uint32_t user_id = 0;
  if (i + 1 < argc && strcmp(argv[i], "--user") == 0) {
    if (!ParseUint(argv[i + 1], &user_id)) {
      error(1, 0, "invalid uid");
    }
    i += 2;
  }
  if (i < argc && strcmp(argv[i], "--show-app-type") == 0) {
    pkg_info* info = ReadPackageInfo(pkgname);
    if (info == nullptr) {
      error(1, 0, "failed to find package %s", pkgname);
    }
    if (info->debuggable) {
      printf("debuggable\n");
    } else if (info->profileable_from_shell) {
      printf("profileable\n");
    } else {
      printf("non_profileable\n");
    }
    return 0;
  }

  if (i == argc) {
    error(1, 0, "no simpleperf command name");
  }
  char* simpleperf_cmdname = argv[i];
  int simpleperf_arg_start = i + 1;
  CheckSimpleperfArguments(simpleperf_cmdname, argv + simpleperf_arg_start);

  if (getuid() != AID_SHELL && getuid() != AID_ROOT) {
    error(1, 0, "program can only run from shell or root");
  }

  // Get package info.
  pkg_info* info = ReadPackageInfo(pkgname);
  if (info == nullptr) {
    error(1, 0, "failed to find package %s", pkgname);
  }
  if (info->uid < AID_APP_START || info->uid > AID_APP_END) {
    error(1, 0, "package isn't an application: %s", pkgname);
  }
  if (!(info->debuggable || info->profileable_from_shell)) {
    error(1, 0, "package is neither debuggable nor profileable from shell: %s", pkgname);
  }

  uid_t user_app_id = info->uid;
  std::string data_dir = info->data_dir;
  if (user_id > 0) {
    // Make sure user_app_id doesn't overflow.
    if ((UID_MAX - info->uid) / AID_USER_OFFSET < user_id) {
      error(1, 0, "user id is too big: %d", user_id);
    }
    user_app_id = (AID_USER_OFFSET * user_id) + info->uid;
    data_dir = StringPrintf("/data/user/%d/%s", user_id, pkgname);
  }

  // Switch to the app's user id and group id.
  uid_t uid = user_app_id;
  gid_t gid = user_app_id;
  std::vector<gid_t> supplementary_gids = GetSupplementaryGids(user_app_id);
  ScopedMinijail j(minijail_new());
  minijail_change_uid(j.get(), uid);
  minijail_change_gid(j.get(), gid);
  minijail_set_supplementary_gids(j.get(), supplementary_gids.size(), &supplementary_gids[0]);
  minijail_enter(j.get());

  // Switch to the app's selinux context.
  if (selinux_android_setcontext(uid, 0, info->seinfo, pkgname) < 0) {
    error(1, errno, "couldn't set SELinux security context");
  }

  // Switch to the app's data directory.
  if (TEMP_FAILURE_RETRY(chdir(data_dir.c_str())) == -1) {
    error(1, errno, "couldn't chdir to package's data directory");
  }

  // Run /system/bin/simpleperf.
  std::string simpleperf_in_system_img = "/system/bin/simpleperf";
  int new_argc = 4 + argc - simpleperf_arg_start;
  char* new_argv[new_argc + 1];

  new_argv[0] = &simpleperf_in_system_img[0];
  new_argv[1] = simpleperf_cmdname;
  std::string app_option = "--app";
  new_argv[2] = &app_option[0];
  new_argv[3] = pkgname;
  for (int i = 4, j = simpleperf_arg_start; j < argc;) {
    new_argv[i++] = argv[j++];
  }
  new_argv[new_argc] = nullptr;
  execvp(new_argv[0], new_argv);
  error(1, errno, "exec failed");
}
