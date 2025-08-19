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

#pragma once

#include "app_processes.pb.h"

#include <sys/socket.h>
#include <sys/un.h>

#include <optional>
#include <tuple>
#include <unordered_set>

struct ProcessInfo {
  uint64_t pid;
  bool debuggable;
  bool profileable;
  std::string architecture;
  bool waiting_for_debugger = false;
  uint64_t user_id = 0;
  std::string process_name = "";
  std::unordered_set<std::string> package_names;
  int uid;

  adb::proto::ProcessEntry toProtobuf() const;
  static std::optional<ProcessInfo> parseProtobufString(const std::string& proto);
};

#define MAX_APP_MESSAGE_LENGTH 4096

std::tuple<sockaddr_un, socklen_t> get_control_socket_addr();