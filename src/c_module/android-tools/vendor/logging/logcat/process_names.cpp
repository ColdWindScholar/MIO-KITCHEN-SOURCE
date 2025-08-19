/*
 * Copyright (C) 2023 The Android Open Source Project
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

#include "process_names.h"

#include "android-base/file.h"

const std::string ProcessNames::ReadCmdline(uint64_t pid) {
    const std::string path = std::string("/proc/") + std::to_string(pid) + "/cmdline";

    std::string cmdline;
    if (!android::base::ReadFileToString(path, &cmdline)) {
        return "";
    }

    // We need to remove anything that would be part of an absolute path for the executable
    // but also the parameters. e.g.:
    // Input : /path/to/myProgram -D --ooo
    // Output: myProgram
    return android::base::Basename(cmdline.c_str());
}

const std::string ProcessNames::ReadComm(uint64_t pid) {
    const std::string path = std::string("/proc/") + std::to_string(pid) + "/comm";
    std::string cmdline;
    bool success = android::base::ReadFileToString(path, &cmdline);
    if (!success) {
        return "";
    }
    return cmdline;
}

const std::string ProcessNames::Resolve(uint64_t pid) {
    std::string name = ReadCmdline(pid);
    if (!name.empty()) {
        return name;
    }

    // Kernel threads do not have anything in /proc/PID/cmdline. e.g.:
    // migration/0
    // cpuhp/0
    // kworker/7:1-events
    //
    // To still have a somewhat relevant name, we check /proc/PID/comm, even though
    // the max length is 16 characters.
    name = ReadComm(pid);
    if (!name.empty()) {
        return name;
    }

    return "";
}

std::string ProcessNames::Get(uint64_t pid) {
    // Cache hit!
    const std::string& cached = cache.get(pid);
    if (!cached.empty()) {
        return cached;
    }

    // Cache miss!
    std::string name = Resolve(pid);
    // When an app starts, after it forks from zygote process, the process name remains
    // zygote/zygote64, then <pre-initialized>, then the package/process name is set.
    // We don't cache until we know the final value.
    if (name != "<pre-initialized>" && !name.starts_with("zygote")) {
        cache.put(pid, name);
    }
    return name;
}
