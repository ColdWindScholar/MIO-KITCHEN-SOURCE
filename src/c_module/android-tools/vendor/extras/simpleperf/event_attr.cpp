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

#include "event_attr.h"

#include <inttypes.h>
#include <stdio.h>
#include <string>
#include <unordered_map>

#include <android-base/logging.h>

#include "environment.h"
#include "event_type.h"
#include "utils.h"

namespace simpleperf {

static std::string BitsToString(const std::string& name, uint64_t bits,
                                const std::vector<std::pair<int, std::string>>& bit_names) {
  std::string result;
  for (auto& p : bit_names) {
    if (bits & p.first) {
      bits &= ~p.first;
      if (!result.empty()) {
        result += ", ";
      }
      result += p.second;
    }
  }
  if (bits != 0) {
    LOG(DEBUG) << "unknown " << name << " bits: " << std::hex << bits;
  }
  return result;
}

static std::string SampleTypeToString(uint64_t sample_type) {
  static std::vector<std::pair<int, std::string>> sample_type_names = {
      {PERF_SAMPLE_ADDR, "addr"},
      {PERF_SAMPLE_BRANCH_STACK, "branch_stack"},
      {PERF_SAMPLE_CALLCHAIN, "callchain"},
      {PERF_SAMPLE_CPU, "cpu"},
      {PERF_SAMPLE_ID, "id"},
      {PERF_SAMPLE_IP, "ip"},
      {PERF_SAMPLE_PERIOD, "period"},
      {PERF_SAMPLE_RAW, "raw"},
      {PERF_SAMPLE_READ, "read"},
      {PERF_SAMPLE_REGS_USER, "regs_user"},
      {PERF_SAMPLE_STACK_USER, "stack_user"},
      {PERF_SAMPLE_STREAM_ID, "stream_id"},
      {PERF_SAMPLE_TID, "tid"},
      {PERF_SAMPLE_TIME, "time"},
  };
  return BitsToString("sample_type", sample_type, sample_type_names);
}

static std::string ReadFormatToString(uint64_t read_format) {
  static std::vector<std::pair<int, std::string>> read_format_names = {
      {PERF_FORMAT_TOTAL_TIME_ENABLED, "total_time_enabled"},
      {PERF_FORMAT_TOTAL_TIME_RUNNING, "total_time_running"},
      {PERF_FORMAT_ID, "id"},
      {PERF_FORMAT_GROUP, "group"},
  };
  return BitsToString("read_format", read_format, read_format_names);
}

perf_event_attr CreateDefaultPerfEventAttr(const EventType& event_type) {
  perf_event_attr attr;
  memset(&attr, 0, sizeof(attr));
  attr.size = sizeof(perf_event_attr);
  attr.type = event_type.type;
  attr.config = event_type.config;
  attr.disabled = 0;
  // Changing read_format affects the layout of the data read from perf_event_file, namely
  // PerfCounter in event_fd.h.
  attr.read_format =
      PERF_FORMAT_TOTAL_TIME_ENABLED | PERF_FORMAT_TOTAL_TIME_RUNNING | PERF_FORMAT_ID;
  attr.sample_type |= PERF_SAMPLE_IP | PERF_SAMPLE_TID | PERF_SAMPLE_TIME | PERF_SAMPLE_PERIOD |
                      PERF_SAMPLE_CPU | PERF_SAMPLE_ID;

  if (attr.type == PERF_TYPE_TRACEPOINT) {
    // Tracepoint information are stored in raw data in sample records.
    if (CanRecordRawData()) {
      attr.sample_type |= PERF_SAMPLE_RAW;
    }
  }
  return attr;
}

void DumpPerfEventAttr(const perf_event_attr& attr, size_t indent) {
  std::string event_name = GetEventNameByAttr(attr);
  PrintIndented(indent, "event_attr: for event type %s\n", event_name.c_str());

  PrintIndented(indent + 1, "type %u, size %u, config %llu\n", attr.type, attr.size, attr.config);

  if (attr.freq != 0) {
    PrintIndented(indent + 1, "sample_freq %llu\n", attr.sample_freq);
  } else {
    PrintIndented(indent + 1, "sample_period %llu\n", attr.sample_period);
  }

  PrintIndented(indent + 1, "sample_type (0x%llx) %s\n", attr.sample_type,
                SampleTypeToString(attr.sample_type).c_str());

  PrintIndented(indent + 1, "read_format (0x%llx) %s\n", attr.read_format,
                ReadFormatToString(attr.read_format).c_str());

  PrintIndented(indent + 1, "disabled %u, inherit %u, pinned %u, exclusive %u\n", attr.disabled,
                attr.inherit, attr.pinned, attr.exclusive);

  PrintIndented(indent + 1, "exclude_user %u, exclude_kernel %u, exclude_hv %u\n",
                attr.exclude_user, attr.exclude_kernel, attr.exclude_hv);

  PrintIndented(indent + 1, "exclude_idle %u, mmap %u, mmap2 %u, comm %u, freq %u\n",
                attr.exclude_idle, attr.mmap, attr.mmap2, attr.comm, attr.freq);

  PrintIndented(indent + 1, "inherit_stat %u, enable_on_exec %u, task %u\n", attr.inherit_stat,
                attr.enable_on_exec, attr.task);

  PrintIndented(indent + 1, "watermark %u, precise_ip %u, mmap_data %u\n", attr.watermark,
                attr.precise_ip, attr.mmap_data);

  PrintIndented(indent + 1, "sample_id_all %u, exclude_host %u, exclude_guest %u\n",
                attr.sample_id_all, attr.exclude_host, attr.exclude_guest);
  PrintIndented(indent + 1, "config2 0x%llx\n", attr.config2);
  PrintIndented(indent + 1, "branch_sample_type 0x%" PRIx64 "\n", attr.branch_sample_type);
  PrintIndented(indent + 1, "exclude_callchain_kernel %u, exclude_callchain_user %u\n",
                attr.exclude_callchain_kernel, attr.exclude_callchain_user);
  PrintIndented(indent + 1, "comm_exec %u, use_clockid %u, context_switch %u\n", attr.comm_exec,
                attr.use_clockid, attr.context_switch);
  PrintIndented(indent + 1, "sample_regs_user 0x%" PRIx64 "\n", attr.sample_regs_user);
  PrintIndented(indent + 1, "sample_stack_user 0x%" PRIx64 "\n", attr.sample_stack_user);
}

bool GetCommonEventIdPositionsForAttrs(const EventAttrIds& attrs,
                                       size_t* event_id_pos_in_sample_records,
                                       size_t* event_id_reverse_pos_in_non_sample_records) {
  // When there are more than one perf_event_attrs, we need to read event id
  // in each record to decide current record should use which attr. So
  // we need to determine the event id position in a record here.
  std::vector<uint64_t> sample_types;
  for (const auto& attr : attrs) {
    sample_types.push_back(attr.attr.sample_type);
  }
  // First determine event_id_pos_in_sample_records.
  // If PERF_SAMPLE_IDENTIFIER is enabled, it is just after perf_event_header.
  // If PERF_SAMPLE_ID is enabled, then PERF_SAMPLE_IDENTIFIER | IP | TID | TIME | ADDR
  // should also be the same.
  bool identifier_enabled = true;
  bool id_enabled = true;
  uint64_t flags_before_id_mask = PERF_SAMPLE_IDENTIFIER | PERF_SAMPLE_IP | PERF_SAMPLE_TID |
                                  PERF_SAMPLE_TIME | PERF_SAMPLE_ADDR;
  uint64_t flags_before_id = sample_types[0] & flags_before_id_mask;
  bool flags_before_id_are_the_same = true;
  for (auto type : sample_types) {
    identifier_enabled &= (type & PERF_SAMPLE_IDENTIFIER) != 0;
    id_enabled &= (type & PERF_SAMPLE_ID) != 0;
    flags_before_id_are_the_same &= (type & flags_before_id_mask) == flags_before_id;
  }
  if (identifier_enabled) {
    *event_id_pos_in_sample_records = sizeof(perf_event_header);
  } else if (id_enabled && flags_before_id_are_the_same) {
    uint64_t pos = sizeof(perf_event_header);
    while (flags_before_id != 0) {
      // Each flags takes 8 bytes in sample records.
      flags_before_id &= flags_before_id - 1;
      pos += 8;
    }
    *event_id_pos_in_sample_records = pos;
  } else {
    LOG(ERROR) << "perf_event_attrs don't have a common event id position in sample records";
    return false;
  }

  // Secondly determine event_id_reverse_pos_in_non_sample_record.
  // If sample_id_all is not enabled, there is no event id in non sample records.
  // If PERF_SAMPLE_IDENTIFIER is enabled, it is at the last 8 bytes of the record.
  // If PERF_SAMPLE_ID is enabled, then PERF_SAMPLE_IDENTIFIER | CPU | STREAM_ID should
  // also be the same.
  bool sample_id_all_enabled = true;
  for (const auto& attr : attrs) {
    if (attr.attr.sample_id_all == 0) {
      sample_id_all_enabled = false;
    }
  }
  if (!sample_id_all_enabled) {
    LOG(ERROR) << "there are perf_event_attrs not enabling sample_id_all, so can't determine "
               << "perf_event_attr for non sample records";
    return false;
  }
  uint64_t flags_after_id_mask = PERF_SAMPLE_IDENTIFIER | PERF_SAMPLE_CPU | PERF_SAMPLE_STREAM_ID;
  uint64_t flags_after_id = sample_types[0] & flags_after_id_mask;
  bool flags_after_id_are_the_same = true;
  for (auto type : sample_types) {
    flags_after_id_are_the_same &= (type & flags_after_id_mask) == flags_after_id;
  }
  if (identifier_enabled) {
    *event_id_reverse_pos_in_non_sample_records = 8;
  } else if (id_enabled && flags_after_id_are_the_same) {
    uint64_t pos = 8;
    while (flags_after_id != 0) {
      // Each flag takes 8 bytes in sample_id of non sample records.
      flags_after_id &= flags_after_id - 1;
      pos += 8;
    }
    *event_id_reverse_pos_in_non_sample_records = pos;
  } else {
    LOG(ERROR)
        << "perf_event_attrs don't have a common event id reverse position in non sample records";
    return false;
  }
  return true;
}

bool IsTimestampSupported(const perf_event_attr& attr) {
  return attr.sample_id_all && (attr.sample_type & PERF_SAMPLE_TIME);
}

bool IsCpuSupported(const perf_event_attr& attr) {
  return attr.sample_id_all && (attr.sample_type & PERF_SAMPLE_CPU);
}

std::string GetEventNameByAttr(const perf_event_attr& attr) {
  std::string name = "unknown";
  auto callback = [&](const EventType& event_type) {
    // An event type uses both type and config value to define itself. But etm event type
    // only uses type value (whose config value is used to set etm options).
    if (event_type.type == attr.type &&
        (event_type.config == attr.config || event_type.IsEtmEvent())) {
      name = event_type.name;
      if (attr.exclude_user && !attr.exclude_kernel) {
        name += ":k";
      } else if (attr.exclude_kernel && !attr.exclude_user) {
        name += ":u";
      }
      return false;
    }
    return true;
  };
  EventTypeManager::Instance().ForEachType(callback);
  return name;
}

void ReplaceRegAndStackWithCallChain(perf_event_attr& attr) {
  attr.sample_type &= ~(PERF_SAMPLE_REGS_USER | PERF_SAMPLE_STACK_USER);
  attr.exclude_callchain_user = 0;
  attr.sample_regs_user = 0;
  attr.sample_stack_user = 0;
}

}  // namespace simpleperf
