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

#ifndef SIMPLE_PERF_EVENT_ATTR_H_
#define SIMPLE_PERF_EVENT_ATTR_H_

#include <stddef.h>
#include <string.h>

#include <string>
#include <vector>

#include "perf_event.h"

namespace simpleperf {

struct EventType;

struct EventAttrWithId {
  perf_event_attr attr;
  std::vector<uint64_t> ids;
};

using EventAttrIds = std::vector<EventAttrWithId>;

inline constexpr uint64_t INFINITE_SAMPLE_PERIOD = 1ULL << 62;

perf_event_attr CreateDefaultPerfEventAttr(const EventType& event_type);
void DumpPerfEventAttr(const perf_event_attr& attr, size_t indent = 0);
bool GetCommonEventIdPositionsForAttrs(const EventAttrIds& attrs,
                                       size_t* event_id_pos_in_sample_records,
                                       size_t* event_id_reverse_pos_in_non_sample_records);
bool IsTimestampSupported(const perf_event_attr& attr);
bool IsCpuSupported(const perf_event_attr& attr);
// Return event name with modifier if the event is found, otherwise return "unknown".
// This function is slow for using linear search, so only used when reporting.
std::string GetEventNameByAttr(const perf_event_attr& attr);
void ReplaceRegAndStackWithCallChain(perf_event_attr& attr);

inline bool operator==(const perf_event_attr& attr1, const perf_event_attr& attr2) {
  return memcmp(&attr1, &attr2, sizeof(perf_event_attr)) == 0;
}

inline bool operator!=(const perf_event_attr& attr1, const perf_event_attr& attr2) {
  return !(attr1 == attr2);
}

}  // namespace simpleperf

#endif  // SIMPLE_PERF_EVENT_ATTR_H_
