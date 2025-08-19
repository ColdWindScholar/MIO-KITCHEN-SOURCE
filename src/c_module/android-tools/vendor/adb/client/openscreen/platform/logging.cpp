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

#include <platform/api/logging.h>

#include <android-base/logging.h>

namespace openscreen {

bool IsLoggingOn(LogLevel level, const char* file) {
    return true;
}

void LogWithLevel(LogLevel level, const char* file, int line, std::stringstream message) {
    switch (level) {
        case LogLevel::kInfo:
            LOG(INFO) << message.str();
            break;
        case LogLevel::kWarning:
            LOG(WARNING) << message.str();
            break;
        case LogLevel::kError:
            LOG(ERROR) << message.str();
            break;
        case LogLevel::kFatal:
            LOG(FATAL) << message.str();
            break;
        default:
            LOG(VERBOSE) << message.str();
            break;
    }
}

[[noreturn]] void Break() {
    std::abort();
}

}  // namespace openscreen
