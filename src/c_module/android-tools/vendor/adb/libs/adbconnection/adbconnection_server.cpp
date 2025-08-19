/*
 * Copyright (C) 2019 The Android Open Source Project
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

#include "adbconnection/server.h"

#include <sys/epoll.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

#include <algorithm>
#include <array>
#include <vector>

#include <android-base/logging.h>
#include <android-base/unique_fd.h>

#include "adbconnection/common.h"
#include "app_processes.pb.h"

using android::base::unique_fd;

std::optional<ProcessInfo> readProcessInfoFromSocket(int socket) {
  std::string proto;
  proto.resize(MAX_APP_MESSAGE_LENGTH);
  ssize_t rc = TEMP_FAILURE_RETRY(recv(socket, proto.data(), proto.length(), MSG_PEEK));

  if (rc == 0) {
    LOG(INFO) << "Remote process closed the socket (on MSG_PEEK)";
    return {};
  }

  if (rc == -1) {
    PLOG(ERROR) << "adbconnection_server: Unable to MSG_PEEK ProcessInfo recv";
    return {};
  }

  ssize_t message_size = rc;
  proto.resize(message_size);
  rc = TEMP_FAILURE_RETRY(recv(socket, proto.data(), message_size, 0));

  if (rc == 0) {
    LOG(INFO) << "Remote process closed the socket (on recv)";
    return {};
  }

  if (rc == -1) {
    PLOG(ERROR) << "adbconnection_server: Unable to recv ProcessInfo " << message_size << " bytes";
    return {};
  }

  if (rc != message_size) {
    LOG(ERROR) << "adbconnection_server: Unexpected ProcessInfo size " << message_size
               << " bytes but got " << rc;
    return {};
  }

  return ProcessInfo::parseProtobufString(proto);
}

// Listen for incoming jdwp clients forever.
void adbconnection_listen(void (*callback)(int fd, ProcessInfo process)) {
  unique_fd s(socket(AF_UNIX, SOCK_SEQPACKET | SOCK_NONBLOCK | SOCK_CLOEXEC, 0));
  if (s < 0) {
    PLOG(ERROR) << "failed to create JDWP control socket";
    return;
  }

  auto [addr, addr_len] = get_control_socket_addr();
  if (bind(s.get(), reinterpret_cast<sockaddr*>(&addr), addr_len) < 0) {
    PLOG(ERROR) << "failed to bind JDWP control socket";
    return;
  }

  if (listen(s.get(), 4) < 0) {
    PLOG(ERROR) << "failed to listen on JDWP control socket";
    return;
  }

  std::vector<unique_fd> pending_connections;

  unique_fd epfd(epoll_create1(EPOLL_CLOEXEC));
  std::array<epoll_event, 16> events;

  events[0].events = EPOLLIN;
  events[0].data.fd = -1;
  if (epoll_ctl(epfd.get(), EPOLL_CTL_ADD, s.get(), &events[0]) != 0) {
    PLOG(FATAL) << "failed to register socket " << s.get() << " with epoll fd";
  }

  while (true) {
    int epoll_rc = TEMP_FAILURE_RETRY(epoll_wait(epfd.get(), events.data(), events.size(), -1));
    if (epoll_rc == -1) {
      PLOG(FATAL) << "epoll_wait failed";
    }

    for (int i = 0; i < epoll_rc; ++i) {
      const epoll_event& event = events[i];
      if (event.data.fd == -1) {
        unique_fd client(
            TEMP_FAILURE_RETRY(accept4(s.get(), nullptr, nullptr, SOCK_NONBLOCK | SOCK_CLOEXEC)));

        if (client == -1) {
          PLOG(WARNING) << "failed to accept client on JDWP control socket";
          continue;
        }

        epoll_event register_event;
        register_event.events = EPOLLIN;
        register_event.data.fd = client.get();

        if (epoll_ctl(epfd.get(), EPOLL_CTL_ADD, client.get(), &register_event) != 0) {
          PLOG(FATAL) << "failed to register JDWP client " << client.get() << " with epoll";
        }

        pending_connections.emplace_back(std::move(client));
      } else {
        // n^2, but the backlog should be short.
        auto it = std::find_if(pending_connections.begin(), pending_connections.end(),
                               [&](const unique_fd& fd) { return fd.get() == event.data.fd; });

        if (it == pending_connections.end()) {
          LOG(FATAL) << "failed to find JDWP client (" << event.data.fd
                     << ") in pending connections";
        }

        auto process_info = readProcessInfoFromSocket(it->get());
        if (process_info) {
          callback(it->release(), *process_info);
        } else {
          LOG(ERROR) << "Unable to read ProcessInfo from app startup";
        }

        if (epoll_ctl(epfd.get(), EPOLL_CTL_DEL, event.data.fd, nullptr) != 0) {
          PLOG(FATAL) << "failed to delete fd " << event.data.fd << " from JDWP epoll fd";
        }

        pending_connections.erase(it);
      }
    }
  }
}
