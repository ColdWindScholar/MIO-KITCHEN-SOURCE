/*
 * Copyright (C) 2016 The Android Open Source Project
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

#ifndef SIMPLE_PERF_TRACING_H_
#define SIMPLE_PERF_TRACING_H_

#include <optional>
#include <set>
#include <vector>

#include <android-base/logging.h>

#include "event_type.h"
#include "utils.h"

namespace simpleperf {

struct TracingField {
  std::string name;
  size_t offset = 0;
  size_t elem_size = 0;
  size_t elem_count = 1;
  bool is_signed = false;
  bool is_dynamic = false;

  bool operator==(const TracingField& other) const {
    return name == other.name && offset == other.offset && elem_size == other.elem_size &&
           elem_count == other.elem_count && is_signed == other.is_signed &&
           is_dynamic == other.is_dynamic;
  }
};

struct TracingFieldPlace {
  uint32_t offset;
  uint32_t size;

  uint64_t ReadFromData(const char* raw_data) {
    return ConvertBytesToValue(raw_data + offset, size);
  }
};

struct StringTracingFieldPlace {
  uint32_t offset;
  uint32_t size;

  std::string ReadFromData(const char* raw_data) {
    char s[size + 1];
    s[size] = '\0';
    memcpy(s, raw_data + offset, size);
    return s;
  }
};

struct TracingFormat {
  std::string system_name;
  std::string name;
  uint64_t id = 0;
  std::vector<TracingField> fields;

  void GetField(const std::string& name, TracingFieldPlace& place) const {
    const TracingField& field = GetField(name);
    place.offset = field.offset;
    place.size = field.elem_size;
  }

  void GetField(const std::string& name, StringTracingFieldPlace& place) const {
    const TracingField& field = GetField(name);
    place.offset = field.offset;
    place.size = field.elem_count;
  }

 private:
  const TracingField& GetField(const std::string& name) const {
    for (const auto& field : fields) {
      if (field.name == name) {
        return field;
      }
    }
    LOG(FATAL) << "Couldn't find field " << name << "in TracingFormat of " << this->name;
    return fields[0];
  }
};

class TracingFile;

class Tracing {
 public:
  static std::unique_ptr<Tracing> Create(const std::vector<char>& data);
  ~Tracing();
  void Dump(size_t indent);
  std::optional<TracingFormat> GetTracingFormatHavingId(uint64_t trace_event_id);
  std::string GetTracingEventNameHavingId(uint64_t trace_event_id);
  const std::string& GetKallsyms() const;
  uint32_t GetPageSize() const;

 private:
  Tracing();

  std::unique_ptr<TracingFile> tracing_file_;
  std::vector<TracingFormat> tracing_formats_;
};

bool GetTracingData(const std::vector<const EventType*>& event_types, std::vector<char>* data);

// use_quote: whether or not to use quotes in string operands
// used_fields: field names used in the filter
// Return adjusted filter on success, otherwise return std::nullopt.
using FieldNameSet = std::set<std::string>;
std::optional<std::string> AdjustTracepointFilter(const std::string& filter, bool use_quote,
                                                  FieldNameSet* used_fields);
std::optional<FieldNameSet> GetFieldNamesForTracepointEvent(const EventType& event);
TracingFormat ParseTracingFormat(const std::string& data);

}  // namespace simpleperf

#endif  // SIMPLE_PERF_TRACING_H_
