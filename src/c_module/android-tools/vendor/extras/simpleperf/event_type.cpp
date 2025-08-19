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

#include "event_type.h"

#include <inttypes.h>
#include <unistd.h>
#include <algorithm>
#include <string>
#include <vector>

#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/parseint.h>
#include <android-base/stringprintf.h>
#include <android-base/strings.h>

#include "ETMRecorder.h"
#include "environment.h"
#include "event_attr.h"
#include "utils.h"

namespace simpleperf {

struct EventFormat {
  EventFormat(const std::string& name, const std::string& attr, int shift)
      : name(name), attr(attr), shift(shift) {}

  std::string name;
  std::string attr;
  int shift;
};

extern std::set<EventType> builtin_event_types;

enum class EventFinderType {
  BUILTIN,
  TRACEPOINT_STRING,
  TRACEPOINT_SYSTEM,
  PMU,
  ETM,
  RAW,
  SCOPED,
};

class EventTypeFinder {
 public:
  EventTypeFinder(EventFinderType type) : finder_type_(type) {}
  virtual ~EventTypeFinder() {}

  EventFinderType GetFinderType() const { return finder_type_; }

  const std::set<EventType>& GetTypes() {
    if (!loaded_) {
      loaded_ = true;
      LoadTypes();
    }
    return types_;
  }

  virtual const EventType* FindType(const std::string& name) {
    const auto& types = GetTypes();
    auto it = types.find(EventType(name, 0, 0, "", ""));
    if (it != types.end()) {
      return &*it;
    }
    return nullptr;
  }

 protected:
  virtual void LoadTypes() = 0;

  const EventFinderType finder_type_;
  std::set<EventType> types_;
  bool loaded_ = false;
};

class BuiltinTypeFinder : public EventTypeFinder {
 public:
  BuiltinTypeFinder() : EventTypeFinder(EventFinderType::BUILTIN) {}

 protected:
  void LoadTypes() override { types_ = std::move(builtin_event_types); }
};

class TracepointStringFinder : public EventTypeFinder {
 public:
  TracepointStringFinder(std::string&& s)
      : EventTypeFinder(EventFinderType::TRACEPOINT_STRING), s_(std::move(s)) {}

 protected:
  void LoadTypes() override {
    for (const auto& line : android::base::Split(s_, "\n")) {
      std::string str = android::base::Trim(line);
      if (str.empty()) {
        continue;
      }
      std::vector<std::string> items = android::base::Split(str, " ");
      CHECK_EQ(items.size(), 2u);
      std::string event_name = items[0];
      uint64_t id;
      CHECK(android::base::ParseUint(items[1].c_str(), &id));
      types_.emplace(event_name, PERF_TYPE_TRACEPOINT, id, "", "");
    }
  }

 private:
  const std::string s_;
};

class TracepointSystemFinder : public EventTypeFinder {
 public:
  TracepointSystemFinder() : EventTypeFinder(EventFinderType::TRACEPOINT_SYSTEM) {}

  const EventType* FindType(const std::string& name) override {
    if (auto it = types_.find(EventType(name, 0, 0, "", "")); it != types_.end()) {
      return &*it;
    }
    std::vector<std::string> strs = android::base::Split(name, ":");
    if (strs.size() != 2) {
      return nullptr;
    }
    const char* tracefs_dir = GetTraceFsDir();
    if (tracefs_dir == nullptr) {
      return nullptr;
    }
    std::string path = tracefs_dir + std::string("/events/") + strs[0] + "/" + strs[1] + "/id";
    uint64_t id;
    if (!ReadEventId(path, &id)) {
      return nullptr;
    }
    auto res = types_.emplace(name, PERF_TYPE_TRACEPOINT, id, "", "");
    return &*res.first;
  }

  void RemoveType(const std::string& name) { types_.erase(EventType(name, 0, 0, "", "")); }

  std::string ToString() {
    std::string result;
    for (auto& type : GetTypes()) {
      if (!result.empty()) {
        result.push_back('\n');
      }
      result += android::base::StringPrintf("%s %" PRIu64, type.name.c_str(), type.config);
    }
    return result;
  }

 protected:
  void LoadTypes() override {
    const char* tracefs_dir = GetTraceFsDir();
    if (tracefs_dir == nullptr) {
      return;
    }
    const std::string tracepoint_dirname = tracefs_dir + std::string("/events");
    for (const auto& system_name : GetSubDirs(tracepoint_dirname)) {
      std::string system_path = tracepoint_dirname + "/" + system_name;
      for (const auto& event_name : GetSubDirs(system_path)) {
        std::string id_path = system_path + "/" + event_name + "/id";
        uint64_t id;
        if (ReadEventId(id_path, &id)) {
          types_.emplace(system_name + ":" + event_name, PERF_TYPE_TRACEPOINT, id, "", "");
        }
      }
    }
  }

 private:
  bool ReadEventId(const std::string& id_path, uint64_t* id) {
    std::string id_content;
    if (!android::base::ReadFileToString(id_path, &id_content)) {
      return false;
    }
    if (!android::base::ParseUint(android::base::Trim(id_content), id)) {
      LOG(DEBUG) << "unexpected id '" << id_content << "' in " << id_path;
      return false;
    }
    return true;
  }
};

class PMUTypeFinder : public EventTypeFinder {
 public:
  PMUTypeFinder() : EventTypeFinder(EventFinderType::PMU) {}

  const EventType* FindType(const std::string& name) override {
    if (name.find('/') == std::string::npos) {
      return nullptr;
    }
    return EventTypeFinder::FindType(name);
  }

 protected:
  void LoadTypes() override {
    const std::string evtsrc_dirname = "/sys/bus/event_source/devices/";
    for (const auto& device_name : GetSubDirs(evtsrc_dirname)) {
      std::string evtdev_path = evtsrc_dirname + device_name;
      std::string type_path = evtdev_path + "/type";
      std::string type_content;

      if (!android::base::ReadFileToString(type_path, &type_content)) {
        LOG(DEBUG) << "cannot read event type: " << device_name;
        continue;
      }
      uint64_t type_id = strtoull(type_content.c_str(), NULL, 10);

      std::vector<EventFormat> formats = ParseEventFormats(evtdev_path);

      std::string events_dirname = evtdev_path + "/events/";
      for (const auto& event_name : GetEntriesInDir(events_dirname)) {
        std::string event_path = events_dirname + event_name;
        std::string event_content;
        if (!android::base::ReadFileToString(event_path, &event_content)) {
          LOG(DEBUG) << "cannot read event content in " << event_name;
          continue;
        }

        uint64_t config = MakeEventConfig(event_content, formats);
        if (config == ~0ULL) {
          LOG(DEBUG) << "cannot handle config format in " << event_name;
          continue;
        }
        types_.emplace(device_name + "/" + event_name + "/", type_id, config, "", "");
      }
    }
  }

 private:
  std::vector<EventFormat> ParseEventFormats(const std::string& evtdev_path) {
    std::vector<EventFormat> v;
    std::string formats_dirname = evtdev_path + "/format/";
    for (const auto& format_name : GetEntriesInDir(formats_dirname)) {
      std::string format_path = formats_dirname + format_name;
      std::string format_content;
      if (!android::base::ReadFileToString(format_path, &format_content)) {
        continue;
      }

      // format files look like below (currently only 'config' is supported) :
      //   # cat armv8_pmuv3/format/event
      //   config:0-15
      int shift;
      if (sscanf(format_content.c_str(), "config:%d", &shift) != 1) {
        LOG(DEBUG) << "Invalid or unsupported event format: " << format_content;
        continue;
      }

      v.emplace_back(EventFormat(format_name, "config", shift));
    }
    return v;
  }

  uint64_t MakeEventConfig(const std::string& event_str, std::vector<EventFormat>& formats) {
    uint64_t config = 0;

    // event files might have multiple terms, but usually have a term like:
    //   # cat armv8_pmuv3/events/cpu_cycles
    //   event=0x011
    for (auto& s : android::base::Split(event_str, ",")) {
      auto pos = s.find('=');
      if (pos == std::string::npos) continue;

      auto format = s.substr(0, pos);
      long val;
      if (!android::base::ParseInt(android::base::Trim(s.substr(pos + 1)), &val)) {
        LOG(DEBUG) << "Invalid event format '" << s << "'";
        continue;
      }

      for (auto& f : formats) {
        if (f.name == format) {
          if (f.attr != "config") {
            LOG(DEBUG) << "cannot support other attribute: " << s;
            return ~0ULL;
          }

          config |= val << f.shift;
          break;
        }
      }
    }
    return config;
  }
};

class ETMTypeFinder : public EventTypeFinder {
 public:
  ETMTypeFinder() : EventTypeFinder(EventFinderType::ETM) {}

  const EventType* FindType(const std::string& name) override {
    if (name != kETMEventName) {
      return nullptr;
    }
    return EventTypeFinder::FindType(name);
  }

 protected:
  void LoadTypes() override {
#if defined(__linux__)
    std::unique_ptr<EventType> etm_type = ETMRecorder::GetInstance().BuildEventType();
    if (etm_type) {
      types_.emplace(std::move(*etm_type));
    }
#endif
  }
};

class RawTypeFinder : public EventTypeFinder {
 public:
  RawTypeFinder() : EventTypeFinder(EventFinderType::RAW) {}

  const EventType* AddType(EventType&& type) {
    auto result = types_.emplace(std::move(type));
    return &*(result.first);
  }

 protected:
  void LoadTypes() override {}
};

class ScopedTypeFinder : public EventTypeFinder {
 public:
  ScopedTypeFinder(std::set<EventType>&& types) : EventTypeFinder(EventFinderType::SCOPED) {
    types_ = std::move(types);
  }

 protected:
  void LoadTypes() override {}
};

EventTypeManager EventTypeManager::instance_;

EventTypeManager::EventTypeManager() {
  type_finders_.emplace_back(new BuiltinTypeFinder());
  type_finders_.emplace_back(new TracepointSystemFinder());
  type_finders_.emplace_back(new PMUTypeFinder());
  type_finders_.emplace_back(new ETMTypeFinder());
  type_finders_.emplace_back(new RawTypeFinder());
}

EventTypeManager::~EventTypeManager() {}

std::unique_ptr<EventTypeFinder>& EventTypeManager::GetFinder(EventFinderType type) {
  for (auto& finder : type_finders_) {
    if (finder->GetFinderType() == type) {
      return finder;
    }
  }
  LOG(FATAL) << "Failed to get EventTypeFinder";
  __builtin_unreachable();
}

RawTypeFinder& EventTypeManager::GetRawTypeFinder() {
  return *static_cast<RawTypeFinder*>(GetFinder(EventFinderType::RAW).get());
}

TracepointSystemFinder& EventTypeManager::GetTracepointSystemFinder() {
  return *static_cast<TracepointSystemFinder*>(GetFinder(EventFinderType::TRACEPOINT_SYSTEM).get());
}

bool EventTypeManager::ReadTracepointsFromFile(const std::string& filepath) {
  std::string data;
  if (!android::base::ReadFileToString(filepath, &data)) {
    PLOG(ERROR) << "Failed to read " << filepath;
    return false;
  }
  // Replace TracepointSystemFinder with TracepointStringFinder.
  auto& finder = GetFinder(EventFinderType::TRACEPOINT_SYSTEM);
  finder.reset(new TracepointStringFinder(std::move(data)));
  return true;
}

bool EventTypeManager::WriteTracepointsToFile(const std::string& filepath) {
  auto& tp_finder = GetTracepointSystemFinder();
  std::string s = tp_finder.ToString();
  if (!android::base::WriteStringToFile(s, filepath)) {
    PLOG(ERROR) << "Failed to store tracepoint events";
    return false;
  }
  return true;
}

bool EventTypeManager::ForEachType(const std::function<bool(const EventType&)>& callback) {
  if (scoped_finder_) {
    for (const auto& type : scoped_finder_->GetTypes()) {
      if (!callback(type)) {
        return false;
      }
    }
  } else {
    for (auto& finder : type_finders_) {
      for (const auto& type : finder->GetTypes()) {
        if (!callback(type)) {
          return false;
        }
      }
    }
  }
  return true;
}

const EventType* EventTypeManager::FindType(const std::string& name) {
  if (scoped_finder_) {
    return scoped_finder_->FindType(name);
  }
  for (auto& finder : type_finders_) {
    if (auto type = finder->FindType(name)) {
      return type;
    }
  }
  return nullptr;
}

const EventType* EventTypeManager::AddRawType(const std::string& name) {
  if (name.empty() || name[0] != 'r') {
    return nullptr;
  }
  errno = 0;
  char* end;
  uint64_t config = strtoull(&name[1], &end, 16);
  if (errno != 0 || *end != '\0') {
    return nullptr;
  }
  auto& raw_finder = GetRawTypeFinder();
  return raw_finder.AddType(EventType(name, PERF_TYPE_RAW, config, "", ""));
}

void EventTypeManager::RemoveProbeType(const std::string& name) {
  GetTracepointSystemFinder().RemoveType(name);
}

void EventTypeManager::SetScopedFinder(std::unique_ptr<EventTypeFinder>&& finder) {
  scoped_finder_ = std::move(finder);
}

std::vector<int> EventType::GetPmuCpumask() {
  std::vector<int> empty_result;
  if (!IsPmuEvent()) return empty_result;

  std::string pmu = name.substr(0, name.find('/'));
  std::string cpumask_path = "/sys/bus/event_source/devices/" + pmu + "/cpumask";
  std::string cpumask_content;
  if (!android::base::ReadFileToString(cpumask_path, &cpumask_content)) {
    LOG(DEBUG) << "cannot read cpumask content in " << pmu;
    return empty_result;
  }
  if (auto cpus = GetCpusFromString(cpumask_content); cpus) {
    return std::vector<int>(cpus->begin(), cpus->end());
  }
  return empty_result;
}

std::string ScopedEventTypes::BuildString(const std::vector<const EventType*>& event_types) {
  std::string result;
  for (auto type : event_types) {
    if (!result.empty()) {
      result.push_back('\n');
    }
    result +=
        android::base::StringPrintf("%s,%u,%" PRIu64, type->name.c_str(), type->type, type->config);
  }
  return result;
}

ScopedEventTypes::ScopedEventTypes(const std::string& event_type_str) {
  std::set<EventType> event_types;
  for (auto& s : android::base::Split(event_type_str, "\n")) {
    std::string name = s.substr(0, s.find(','));
    uint32_t type;
    uint64_t config;
    sscanf(s.c_str() + name.size(), ",%u,%" PRIu64, &type, &config);
    event_types.emplace(name, type, config, "", "");
  }
  CHECK(EventTypeManager::Instance().GetScopedFinder() == nullptr);
  EventTypeManager::Instance().SetScopedFinder(
      std::make_unique<ScopedTypeFinder>(std::move(event_types)));
}

ScopedEventTypes::~ScopedEventTypes() {
  CHECK(EventTypeManager::Instance().GetScopedFinder() != nullptr);
  EventTypeManager::Instance().SetScopedFinder(nullptr);
}

const EventType* FindEventTypeByName(const std::string& name, bool report_error) {
  const EventType* event_type = EventTypeManager::Instance().FindType(name);
  if (event_type != nullptr) {
    return event_type;
  }
  event_type = EventTypeManager::Instance().AddRawType(name);
  if (event_type != nullptr) {
    return event_type;
  }
  if (report_error) {
    LOG(ERROR) << "Unknown event_type '" << name
               << "', try `simpleperf list` to list all possible event type names";
  }
  return nullptr;
}

std::unique_ptr<EventTypeAndModifier> ParseEventType(const std::string& event_type_str) {
  static std::string modifier_characters = "ukhGHp";
  std::unique_ptr<EventTypeAndModifier> event_type_modifier(new EventTypeAndModifier);
  event_type_modifier->name = event_type_str;
  std::string event_type_name = event_type_str;
  std::string modifier;
  size_t comm_pos = event_type_str.rfind(':');
  if (comm_pos != std::string::npos) {
    bool match_modifier = true;
    for (size_t i = comm_pos + 1; i < event_type_str.size(); ++i) {
      char c = event_type_str[i];
      if (c != ' ' && modifier_characters.find(c) == std::string::npos) {
        match_modifier = false;
        break;
      }
    }
    if (match_modifier) {
      event_type_name = event_type_str.substr(0, comm_pos);
      modifier = event_type_str.substr(comm_pos + 1);
    }
  }
  const EventType* event_type = FindEventTypeByName(event_type_name);
  if (event_type == nullptr) {
    // Try if the modifier belongs to the event type name, like some tracepoint events.
    if (!modifier.empty()) {
      event_type_name = event_type_str;
      modifier.clear();
      event_type = FindEventTypeByName(event_type_name);
    }
    if (event_type == nullptr) {
      return nullptr;
    }
  }
  event_type_modifier->event_type = *event_type;
  if (modifier.find_first_of("ukh") != std::string::npos) {
    event_type_modifier->exclude_user = true;
    event_type_modifier->exclude_kernel = true;
    event_type_modifier->exclude_hv = true;
  }
  if (modifier.find_first_of("GH") != std::string::npos) {
    event_type_modifier->exclude_guest = true;
    event_type_modifier->exclude_host = true;
  }

  for (auto& c : modifier) {
    switch (c) {
      case 'u':
        event_type_modifier->exclude_user = false;
        break;
      case 'k':
        event_type_modifier->exclude_kernel = false;
        break;
      case 'h':
        event_type_modifier->exclude_hv = false;
        break;
      case 'G':
        event_type_modifier->exclude_guest = false;
        break;
      case 'H':
        event_type_modifier->exclude_host = false;
        break;
      case 'p':
        event_type_modifier->precise_ip++;
        break;
      case ' ':
        break;
      default:
        LOG(ERROR) << "Unknown event type modifier '" << c << "'";
    }
  }
  event_type_modifier->modifier = modifier;
  return event_type_modifier;
}

bool IsEtmEventType(uint32_t type) {
  const EventType* event_type = EventTypeManager::Instance().FindType(kETMEventName);
  return (event_type != nullptr) && (event_type->type == type);
}

}  // namespace simpleperf
