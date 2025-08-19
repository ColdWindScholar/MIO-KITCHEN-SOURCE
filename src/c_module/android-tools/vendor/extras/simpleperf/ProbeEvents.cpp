/*
 * Copyright (C) 2020 The Android Open Source Project
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

#include "ProbeEvents.h"

#include <inttypes.h>

#include <memory>
#include <string>

#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/parseint.h>
#include <android-base/stringprintf.h>
#include <android-base/strings.h>
#include <android-base/unique_fd.h>

#include "RegEx.h"
#include "environment.h"
#include "event_selection_set.h"
#include "event_type.h"
#include "utils.h"

namespace simpleperf {

using android::base::ParseInt;
using android::base::ParseUint;
using android::base::Split;
using android::base::StringPrintf;
using android::base::unique_fd;
using android::base::WriteStringToFd;

static const std::string kKprobeEventPrefix = "kprobes:";

bool ProbeEvents::ParseKprobeEventName(const std::string& kprobe_cmd, ProbeEvent* event) {
  // kprobe_cmd is in formats described in <kernel>/Documentation/trace/kprobetrace.rst:
  //   p[:[GRP/]EVENT] [MOD:]SYM[+offs]|MEMADDR [FETCHARGS]
  //   r[MAXACTIVE][:[GRP/]EVENT] [MOD:]SYM[+offs] [FETCHARGS]
  std::vector<std::string> args = Split(kprobe_cmd, " ");
  if (args.size() < 2) {
    return false;
  }

  // Parse given name.
  event->group_name = "kprobes";
  auto name_reg = RegEx::Create(R"(:([a-zA-Z_][\w_]*/)?([a-zA-Z_][\w_]*))");
  auto match = name_reg->SearchAll(args[0]);
  if (match->IsValid()) {
    if (match->GetField(1).length() > 0) {
      event->group_name = match->GetField(1);
      event->group_name.pop_back();
    }
    event->event_name = match->GetField(2);
    return true;
  }

  // Generate name from MEMADDR.
  char probe_type = args[0][0];
  uint64_t kaddr;
  if (ParseUint(args[1], &kaddr)) {
    event->event_name = StringPrintf("%c_0x%" PRIx64, probe_type, kaddr);
    return true;
  }

  // Generate name from [MOD:]SYM[+offs].
  std::string symbol;
  int64_t offset;
  size_t split_pos = args[1].find_first_of("+-");
  if (split_pos == std::string::npos) {
    symbol = args[1];
    offset = 0;
  } else {
    symbol = args[1].substr(0, split_pos);
    if (!ParseInt(args[1].substr(split_pos), &offset) || offset < 0) {
      return false;
    }
  }
  std::string s = StringPrintf("%c_%s_%" PRId64, probe_type, symbol.c_str(), offset);
  event->event_name = RegEx::Create(R"(\.|:)")->Replace(s, "_").value();
  return true;
}

ProbeEvents::~ProbeEvents() {
  if (!IsEmpty()) {
    // Probe events can be deleted only when no perf event file is using them.
    event_selection_set_.CloseEventFiles();
    Clear();
  }
}

bool ProbeEvents::IsKprobeSupported() {
  if (!kprobe_control_path_.has_value()) {
    kprobe_control_path_ = "";
    if (const char* tracefs_dir = GetTraceFsDir(); tracefs_dir != nullptr) {
      std::string path = std::string(tracefs_dir) + "/kprobe_events";
      if (IsRegularFile(path)) {
        kprobe_control_path_ = std::move(path);
      }
    }
  }
  return !kprobe_control_path_.value().empty();
}

bool ProbeEvents::AddKprobe(const std::string& kprobe_cmd) {
  ProbeEvent event;
  if (!ParseKprobeEventName(kprobe_cmd, &event)) {
    LOG(ERROR) << "invalid kprobe cmd: " << kprobe_cmd;
    return false;
  }
  if (!WriteKprobeCmd(kprobe_cmd)) {
    return false;
  }
  kprobe_events_.emplace_back(std::move(event));
  return true;
}

bool ProbeEvents::IsProbeEvent(const std::string& event_name) {
  return android::base::StartsWith(event_name, kKprobeEventPrefix);
}

bool ProbeEvents::CreateProbeEventIfNotExist(const std::string& event_name) {
  if (!IsProbeEvent(event_name) || (EventTypeManager::Instance().FindType(event_name) != nullptr)) {
    // No need to create a probe event.
    return true;
  }
  std::string function_name = event_name.substr(kKprobeEventPrefix.size());
  return AddKprobe(StringPrintf("p:%s %s", function_name.c_str(), function_name.c_str()));
}

void ProbeEvents::Clear() {
  for (const auto& kprobe_event : kprobe_events_) {
    if (!WriteKprobeCmd("-:" + kprobe_event.group_name + "/" + kprobe_event.event_name)) {
      LOG(WARNING) << "failed to delete kprobe event " << kprobe_event.group_name << ":"
                   << kprobe_event.event_name;
    }
    EventTypeManager::Instance().RemoveProbeType(kprobe_event.group_name + ":" +
                                                 kprobe_event.event_name);
  }
  kprobe_events_.clear();
}

bool ProbeEvents::WriteKprobeCmd(const std::string& kprobe_cmd) {
  if (!IsKprobeSupported()) {
    LOG(ERROR) << "kprobe events isn't supported by the kernel.";
    return false;
  }
  const std::string& path = kprobe_control_path_.value();
  unique_fd fd(open(path.c_str(), O_APPEND | O_WRONLY | O_CLOEXEC));
  if (!fd.ok()) {
    PLOG(ERROR) << "failed to open " << path;
    return false;
  }
  if (!WriteStringToFd(kprobe_cmd, fd)) {
    PLOG(ERROR) << "failed to write '" << kprobe_cmd << "' to " << path;
    return false;
  }
  return true;
}

}  // namespace simpleperf
