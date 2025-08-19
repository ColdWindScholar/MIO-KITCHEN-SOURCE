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

#pragma once

#include <stdint.h>
#include <string>

#include "utils/LruCache.h"

// An interface to associate pid to a name. Implemented by looking up /proc/PID.
// To lower syscall impact, results are cached.
class ProcessNames {
  public:
    ProcessNames() : cache(kMaxCacheEntries) {}

    ~ProcessNames() = default;

    // Returns the executable name or in the case of an app, the package name associated
    // with a process pid.
    std::string Get(uint64_t pid);

  private:
    const std::string ReadCmdline(uint64_t pid);
    const std::string ReadComm(uint64_t pid);
    const std::string Resolve(uint64_t pid);

    // kMaxCacheEntries should be picked to keep the memory footprint low (1) and yield a
    // high cache hit rate (2).
    // 1. We cache executable name or package name, which account for roughly 20 characters
    //    each. Using a 100 figure results in 2 KiB for cache storage.
    // 2. Difficult to tune since it depends on how many process are alive and how much they
    //    generate towards liblob. From manual testing, 100 entries resulted in 99% cache hit
    //    with AOSP 34, right after boot, and one app active. We could monitor this value by
    //    augmenting the protobuffer and have a cache hit boolean to generate a cache hit figure
    //    on the workstation.
    static const uint64_t kMaxCacheEntries = 100;
    android::LruCache<uint64_t, std::string> cache;
};
