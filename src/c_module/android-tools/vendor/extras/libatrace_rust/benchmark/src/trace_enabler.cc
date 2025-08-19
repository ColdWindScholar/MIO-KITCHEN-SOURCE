/*
 * Copyright (C) 2023 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include "trace_enabler.h"

#include <cutils/properties.h>
#include <cutils/trace.h>
#include <log/log.h>

void set_property_or_die(const char* key, const char* value) {
    LOG_ALWAYS_FATAL_IF(property_set(key, value) < 0, "Failed to set %s", key);
}

void disable_app_atrace() {
    set_property_or_die("debug.atrace.app_number", "");
    set_property_or_die("debug.atrace.app_0", "");
    atrace_update_tags();
}

void enable_atrace_for_single_app(const char* name) {
    set_property_or_die("debug.atrace.app_number", "1");
    set_property_or_die("debug.atrace.app_0", name);
    atrace_update_tags();
}
