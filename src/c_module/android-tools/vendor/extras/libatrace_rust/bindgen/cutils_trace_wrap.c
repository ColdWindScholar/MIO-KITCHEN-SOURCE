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

#include "cutils_trace_wrap.h"

void atrace_begin_wrap(uint64_t tag, const char* name) {
    atrace_begin(tag, name);
}

void atrace_end_wrap(uint64_t tag) {
    atrace_end(tag);
}

uint64_t atrace_is_tag_enabled_wrap(uint64_t tag) {
    return atrace_is_tag_enabled(tag);
}

void atrace_async_begin_wrap(uint64_t tag, const char* name, int32_t cookie) {
    atrace_async_begin(tag, name, cookie);
}

void atrace_async_end_wrap(uint64_t tag, const char* name, int32_t cookie) {
    atrace_async_end(tag, name, cookie);
}

void atrace_async_for_track_begin_wrap(uint64_t tag, const char* track_name, const char* name,
                                       int32_t cookie) {
    atrace_async_for_track_begin(tag, track_name, name, cookie);
}

void atrace_async_for_track_end_wrap(uint64_t tag, const char* track_name, int32_t cookie) {
    atrace_async_for_track_end(tag, track_name, cookie);
}

void atrace_instant_wrap(uint64_t tag, const char* name) {
    atrace_instant(tag, name);
}

void atrace_instant_for_track_wrap(uint64_t tag, const char* track_name, const char* name) {
    atrace_instant_for_track(tag, track_name, name);
}

void atrace_int_wrap(uint64_t tag, const char* name, int32_t value) {
    atrace_int(tag, name, value);
}

void atrace_int64_wrap(uint64_t tag, const char* name, int64_t value) {
    atrace_int64(tag, name, value);
}
