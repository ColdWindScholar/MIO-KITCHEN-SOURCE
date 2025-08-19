/*
 * Copyright (C) 2023 The Android Open Source Project
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

#include "adbconnection/common.h"

#include <sys/socket.h>

#include <string_view>

namespace {
using namespace std::string_view_literals;
constexpr std::string_view kJdwpControlName = "\0jdwp-control"sv;
static_assert(kJdwpControlName.size() <= sizeof(reinterpret_cast<sockaddr_un*>(0)->sun_path));
}  // namespace

std::tuple<sockaddr_un, socklen_t> get_control_socket_addr() {
  sockaddr_un addr = {};
  addr.sun_family = AF_UNIX;
  memcpy(addr.sun_path, kJdwpControlName.data(), kJdwpControlName.size());
  socklen_t addrlen = offsetof(sockaddr_un, sun_path) + kJdwpControlName.size();

  return {addr, addrlen};
}

adb::proto::ProcessEntry ProcessInfo::toProtobuf() const {
  adb::proto::ProcessEntry process;
  process.set_pid(pid);
  process.set_user_id(user_id);
  process.set_debuggable(debuggable);
  process.set_profileable(profileable);
  process.set_architecture(architecture);
  process.set_process_name(process_name);
  for (std::string package_name : package_names) {
    process.add_package_names(package_name);
  }
  process.set_waiting_for_debugger(waiting_for_debugger);
  process.set_uid(uid);
  return process;
}

std::optional<ProcessInfo> ProcessInfo::parseProtobufString(const std::string& proto) {
  adb::proto::ProcessEntry process_entry_proto;
  if (!process_entry_proto.ParseFromString(proto)) {
    return {};
  }

  ProcessInfo process_info;
  process_info.pid = process_entry_proto.pid();
  process_info.user_id = process_entry_proto.user_id();
  process_info.debuggable = process_entry_proto.debuggable();
  process_info.profileable = process_entry_proto.profileable();
  process_info.architecture = process_entry_proto.architecture();
  process_info.process_name = process_entry_proto.process_name();
  for (int i = 0; i < process_entry_proto.package_names_size(); i++) {
    process_info.package_names.insert(process_entry_proto.package_names(i));
  }
  process_info.waiting_for_debugger = process_entry_proto.waiting_for_debugger();
  process_info.uid = process_entry_proto.uid();
  return process_info;
}