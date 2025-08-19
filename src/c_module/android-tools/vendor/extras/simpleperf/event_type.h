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

#ifndef SIMPLE_PERF_EVENT_H_
#define SIMPLE_PERF_EVENT_H_

#include <stdint.h>
#include <strings.h>
#include <memory>
#include <set>
#include <string>
#include <vector>

#include "perf_event.h"

namespace simpleperf {

inline const std::string kETMEventName = "cs-etm";

// EventType represents one type of event, like cpu_cycle_event, cache_misses_event.
// The user knows one event type by its name, and the kernel knows one event type by its
// (type, config) pair. EventType connects the two representations, and tells the user if
// the event type is supported by the kernel.

struct EventType {
  EventType(const std::string& name, uint32_t type, uint64_t config, const std::string& description,
            const std::string& limited_arch)
      : name(name),
        type(type),
        config(config),
        description(description),
        limited_arch(limited_arch) {}

  EventType() : type(0), config(0) {}

  bool operator<(const EventType& other) const {
    return strcasecmp(name.c_str(), other.name.c_str()) < 0;
  }

  bool IsPmuEvent() const { return name.find('/') != std::string::npos; }
  bool IsEtmEvent() const { return name == kETMEventName; }
  bool IsHardwareEvent() const {
    return type == PERF_TYPE_HARDWARE || type == PERF_TYPE_HW_CACHE || type == PERF_TYPE_RAW;
  }
  bool IsTracepointEvent() const { return type == PERF_TYPE_TRACEPOINT; }

  std::vector<int> GetPmuCpumask();

  std::string name;
  uint32_t type;
  uint64_t config;
  std::string description;
  std::string limited_arch;
};

// Used to temporarily change event types returned by GetAllEventTypes().
class ScopedEventTypes {
 public:
  static std::string BuildString(const std::vector<const EventType*>& event_types);

  ScopedEventTypes(const std::string& event_type_str);
  ~ScopedEventTypes();
};

struct EventTypeAndModifier {
  std::string name;
  EventType event_type;
  std::string modifier;
  bool exclude_user;
  bool exclude_kernel;
  bool exclude_hv;
  bool exclude_host;
  bool exclude_guest;
  int precise_ip : 2;

  EventTypeAndModifier()
      : exclude_user(false),
        exclude_kernel(false),
        exclude_hv(false),
        exclude_host(false),
        exclude_guest(false),
        precise_ip(0) {}
};

enum class EventFinderType;
class EventTypeFinder;
class RawTypeFinder;
class TracepointSystemFinder;

class EventTypeManager {
 public:
  static EventTypeManager& Instance() { return instance_; }
  ~EventTypeManager();

  bool ReadTracepointsFromFile(const std::string& filepath);
  bool WriteTracepointsToFile(const std::string& filepath);

  // Iterate through all event types, and stop when callback returns false.
  bool ForEachType(const std::function<bool(const EventType&)>& callback);
  const EventType* FindType(const std::string& name);
  const EventType* AddRawType(const std::string& name);
  void RemoveProbeType(const std::string& name);
  const EventTypeFinder* GetScopedFinder() { return scoped_finder_.get(); }
  void SetScopedFinder(std::unique_ptr<EventTypeFinder>&& finder);

 private:
  EventTypeManager();
  std::unique_ptr<EventTypeFinder>& GetFinder(EventFinderType type);
  RawTypeFinder& GetRawTypeFinder();
  TracepointSystemFinder& GetTracepointSystemFinder();

  static EventTypeManager instance_;

  std::vector<std::unique_ptr<EventTypeFinder>> type_finders_;
  std::unique_ptr<EventTypeFinder> scoped_finder_;
};

const EventType* FindEventTypeByName(const std::string& name, bool report_error = true);
std::unique_ptr<EventTypeAndModifier> ParseEventType(const std::string& event_type_str);
bool IsEtmEventType(uint32_t type);

}  // namespace simpleperf

#endif  // SIMPLE_PERF_EVENT_H_
