/*
 * Copyright (C) 2022 The Android Open Source Project
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

#include <sys/types.h>

#include <string>

enum AllocEnum : uint8_t {
    MALLOC = 0,
    CALLOC,
    MEMALIGN,
    REALLOC,
    FREE,
    THREAD_DONE,
};

struct AllocEntry {
    pid_t tid;
    AllocEnum type;
    uint64_t ptr = 0;
    size_t size = 0;
    union {
        uint64_t old_ptr = 0;
        uint64_t n_elements;
        uint64_t align;
    } u;
    uint64_t st = 0;
    uint64_t et = 0;
};

void AllocGetData(const std::string& line, AllocEntry* entry);
