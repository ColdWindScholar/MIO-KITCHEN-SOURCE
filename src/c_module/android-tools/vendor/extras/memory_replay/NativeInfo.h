/*
 * Copyright (C) 2014 The Android Open Source Project
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

void NativeGetInfo(int smaps_fd, size_t* rss_bytes, size_t* va_bytes);

void NativePrintInfo(const char* preamble);

// Fill buffer as if %0.2f was chosen for value / divisor.
void NativeFormatFloat(char* buffer, size_t buffer_len, uint64_t value, uint64_t divisor);
