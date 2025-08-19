/*
 * Copyright 2020 The Android Open Source Project
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

#include <LogSize.h>

#include <array>
#include <optional>
#include <string>

#include <android-base/parseint.h>
#include <android-base/properties.h>

bool IsValidBufferSize(size_t value) {
    return kLogBufferMinSize <= value && value <= kLogBufferMaxSize;
}

static std::optional<size_t> GetBufferSizeProperty(const std::string& key) {
    std::string value = android::base::GetProperty(key, "");
    if (value.empty()) {
        return {};
    }

    uint32_t size;
    if (!android::base::ParseByteCount(value, &size)) {
        return {};
    }

    if (!IsValidBufferSize(size)) {
        return {};
    }

    return size;
}

static std::optional<size_t> GetBufferSizePropertyOverride(log_id_t log_id) {
    std::string buffer_name = android_log_id_to_name(log_id);
    std::array<std::string, 4> properties = {
            "persist.logd.size." + buffer_name,
            "ro.logd.size." + buffer_name,
            "persist.logd.size",
            "ro.logd.size",
    };

    for (const auto& property : properties) {
        if (auto size = GetBufferSizeProperty(property)) {
            return size;
        }
    }
    return {};
}

/* This method should only be used for debuggable devices. */
static bool isAllowedToOverrideBufferSize() {
    const auto hwType = android::base::GetProperty("ro.hardware.type", "");
    /* We allow automotive devices to optionally override the default. */
    return (hwType == "automotive");
}

size_t GetBufferSizeFromProperties(log_id_t log_id) {
    /*
     * http://b/196856709
     *
     * We've been seeing timeouts from logcat in bugreports for years, but the
     * rate has gone way up lately. The suspicion is that this is because we
     * have a lot of dogfooders who still have custom (large) log sizes but
     * the new compressed logging is cramming way more in. The bugreports I've seen
     * have had 1,000,000+ lines, so taking 10s to collect that much logging seems
     * plausible. Of course, it's also possible that logcat is timing out because
     * the log is being *spammed* as it's being read. But temporarily disabling
     * custom log sizes like this should help us confirm (or deny) whether the
     * problem really is this simple.
     */
    static const bool isDebuggable = android::base::GetBoolProperty("ro.debuggable", false);
    if (isDebuggable) {
        static const bool mayOverride = isAllowedToOverrideBufferSize();
        if (mayOverride) {
            if (auto size = GetBufferSizePropertyOverride(log_id)) {
                return *size;
            }
        }
    } else {
        static const bool isLowRam = android::base::GetBoolProperty("ro.config.low_ram", false);
        /*
         * For non-debuggable low_ram devices, we want to save memory here and
         * use the minimum size.
         */
        if (isLowRam) {
            return kLogBufferMinSize;
        }
    }

    return kDefaultLogBufferSize;
}
