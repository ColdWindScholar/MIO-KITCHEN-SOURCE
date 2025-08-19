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

#ifndef SIMPLE_PERF_PERF_EVENT_H_
#define SIMPLE_PERF_PERF_EVENT_H_

#if defined(USE_BIONIC_UAPI_HEADERS)
#include <uapi/linux/perf_event.h>
#else
#include <linux/perf_event.h>
#endif

#if !defined(PERF_AUX_FLAG_CORESIGHT_FORMAT_RAW)
#define PERF_AUX_FLAG_CORESIGHT_FORMAT_RAW 0x0100
#endif

#endif  // SIMPLE_PERF_PERF_EVENT_H_
