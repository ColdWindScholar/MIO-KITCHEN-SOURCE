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

#include "adbconnection/client.h"

#include <pwd.h>
#include <stddef.h>
#include <stdint.h>
#include <sys/socket.h>
#include <sys/un.h>

#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <vector>

#include <android-base/cmsg.h>
#include <android-base/logging.h>
#include <android-base/properties.h>
#include <android-base/thread_annotations.h>
#include <android-base/unique_fd.h>

#include "adbconnection/common.h"

using android::base::unique_fd;

struct AppInfo {
  std::mutex mutex;

  // The state of the app process
  ProcessInfo process GUARDED_BY(mutex);

  // True if any of the ProcessInfo fields have been modified since we last sent an update to the
  // server.
  bool has_pending_update GUARDED_BY(mutex) = false;
};

static auto& app_info = *new AppInfo();

struct AdbConnectionClientContext {
  unique_fd control_socket_;
};

bool SocketPeerIsTrusted(int fd) {
  // Allow unit tests to pass on Linux host
#if !defined(__ANDROID__)
  return true;
#endif
  ucred cr;
  socklen_t cr_length = sizeof(cr);
  if (getsockopt(fd, SOL_SOCKET, SO_PEERCRED, &cr, &cr_length) != 0) {
    PLOG(ERROR) << "couldn't get socket credentials";
    return false;
  }

  passwd* shell = getpwnam("shell");
  if (cr.uid != 0 && cr.uid != shell->pw_uid) {
    LOG(ERROR) << "untrusted uid " << cr.uid << " on other end of socket";
    return false;
  }

  return true;
}

static void send_app_info(const AdbConnectionClientContext* ctx) {
  std::lock_guard<std::mutex> lock(app_info.mutex);
  if (!ctx) {
    LOG(WARNING) << "Can't send app_info: No connection to adbd";
    return;
  }

  if (!app_info.has_pending_update) {
    LOG(WARNING) << "adbconnection_client: No pending updates";
    return;
  }

  auto protobufProcess = app_info.process.toProtobuf();
  std::string serialized_message;
  if (!protobufProcess.SerializeToString(&serialized_message)) {
    LOG(ERROR) << "Unable to build ART -> adbd message";
    return;
  }

  if (serialized_message.size() > MAX_APP_MESSAGE_LENGTH) {
    LOG(ERROR) << "adbd appinfo message too big (> " << MAX_APP_MESSAGE_LENGTH << ")";
    return;
  }

  ssize_t message_size = serialized_message.size();
  ssize_t rc = TEMP_FAILURE_RETRY(
      write(ctx->control_socket_.get(), serialized_message.data(), serialized_message.size()));
  if (rc != message_size) {
    PLOG(ERROR) << "failed to send app info to adbd";
    return;
  }
  app_info.has_pending_update = false;
}

AdbConnectionClientContext* adbconnection_client_new(
    const AdbConnectionClientInfo* const* info_elems, size_t info_count) {
  auto ctx = std::make_unique<AdbConnectionClientContext>();

  std::optional<uint64_t> pid;
  std::optional<bool> debuggable;
  std::optional<bool> profileable;
  std::optional<std::string> architecture;

  for (size_t i = 0; i < info_count; ++i) {
    auto info = info_elems[i];
    switch (info->type) {
      case AdbConnectionClientInfoType::pid:
        if (pid) {
          LOG(ERROR) << "multiple pid entries in AdbConnectionClientInfo, ignoring";
          continue;
        }
        pid = info->data.pid;
        break;

      case AdbConnectionClientInfoType::debuggable:
        if (debuggable) {
          LOG(ERROR) << "multiple debuggable entries in AdbConnectionClientInfo, ignoring";
          continue;
        }
        debuggable = info->data.debuggable;
        break;

      case AdbConnectionClientInfoType::profileable:
        if (profileable) {
          LOG(ERROR) << "multiple profileable entries in AdbConnectionClientInfo, ignoring";
          continue;
        }
        profileable = info->data.profileable;
        break;

      case AdbConnectionClientInfoType::architecture:
        if (architecture) {
          LOG(ERROR) << "multiple architecture entries in AdbConnectionClientInfo, ignoring";
          continue;
        }
        architecture = std::string(info->data.architecture.name, info->data.architecture.size);
        break;
    }
  }

  if (!pid) {
    LOG(ERROR) << "AdbConnectionClientInfo missing required field pid";
    return nullptr;
  }

  if (!debuggable) {
    LOG(ERROR) << "AdbConnectionClientInfo missing required field debuggable";
    return nullptr;
  }

  bool expectProfileableAndArch = false;
#if defined(__BIONIC__)
  expectProfileableAndArch = android_get_device_api_level() >= __ANDROID_API_S__;
#endif
  if (expectProfileableAndArch) {
    if (!profileable) {
      LOG(ERROR) << "AdbConnectionClientInfo missing required field profileable";
      return nullptr;
    }

    if (!architecture) {
      LOG(ERROR) << "AdbConnectionClientInfo missing required field architecture";
      return nullptr;
    }
  }

  ctx->control_socket_.reset(socket(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC, 0));
  if (ctx->control_socket_ < 0) {
    PLOG(ERROR) << "failed to create Unix domain socket";
    return nullptr;
  }

#if defined(__ANDROID__)
  // It's possible that adbd isn't running at this point.
  // We don't want to just blindly connect, because if there's nothing listening, we'll end up
  // waking up every second and preventing the CPU from going to sleep.
  if (!android::base::WaitForProperty("init.svc.adbd", "running")) {
    LOG(ERROR) << "adbd isn't running";
    return nullptr;
  }
#endif

  struct timeval timeout;
  timeout.tv_sec = 1;
  timeout.tv_usec = 0;
  setsockopt(ctx->control_socket_.get(), SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));

  auto [addr, addr_len] = get_control_socket_addr();
  int rc = connect(ctx->control_socket_.get(), reinterpret_cast<sockaddr*>(&addr), addr_len);
  if (rc != 0) {
    if (errno == ECONNREFUSED) {
      // On userdebug devices, every Java process is debuggable, so if adbd is explicitly turned
      // off, this would spew enormous amounts of red-herring errors.
      LOG(DEBUG) << "failed to connect to jdwp control socket, adbd not running?";
    } else {
      PLOG(ERROR) << "failed to connect to jdwp control socket";
    }
    return nullptr;
  }

  bool trusted = SocketPeerIsTrusted(ctx->control_socket_.get());
  if (!trusted) {
    LOG(ERROR) << "adb socket is not trusted, aborting connection";
    return nullptr;
  }

  {
    std::lock_guard<std::mutex> lock(app_info.mutex);
    app_info.process.pid = *pid;
    app_info.process.debuggable = *debuggable;
    if (profileable) {
      app_info.process.profileable = *profileable;
    }
    if (architecture) {
      app_info.process.architecture = *architecture;
    }
    app_info.process.uid = getuid();
    app_info.has_pending_update = true;
  }
  send_app_info(ctx.get());

  return ctx.release();
}

void adbconnection_client_set_current_process_name(const char* process_name) {
  std::lock_guard<std::mutex> lock(app_info.mutex);
  app_info.process.process_name = process_name;
  app_info.has_pending_update = true;
}

void adbconnection_client_add_application(const char* package_name) {
  std::lock_guard<std::mutex> lock(app_info.mutex);
  app_info.process.package_names.insert(package_name);
  app_info.has_pending_update = true;
}

void adbconnection_client_remove_application(const char* package_name) {
  std::lock_guard<std::mutex> lock(app_info.mutex);
  app_info.process.package_names.erase(package_name);
  app_info.has_pending_update = true;
}

void adbconnection_client_set_waiting_for_debugger(bool waiting) {
  std::lock_guard<std::mutex> lock(app_info.mutex);
  app_info.process.waiting_for_debugger = waiting;
  app_info.has_pending_update = true;
}

bool adbconnection_client_has_pending_update() {
  std::lock_guard<std::mutex> lock(app_info.mutex);
  return app_info.has_pending_update;
}

void adbconnection_client_set_user_id(int user_id) {
  std::lock_guard<std::mutex> lock(app_info.mutex);
  app_info.process.user_id = user_id;
  app_info.has_pending_update = true;
}

void adbconnection_client_send_update(const AdbConnectionClientContext* ctx) {
  send_app_info(ctx);
}

void adbconnection_client_destroy(AdbConnectionClientContext* ctx) {
  delete ctx;
}

int adbconnection_client_pollfd(AdbConnectionClientContext* ctx) {
  return ctx->control_socket_.get();
}

int adbconnection_client_receive_jdwp_fd(AdbConnectionClientContext* ctx) {
  char dummy;
  unique_fd jdwp_fd;
  ssize_t rc = android::base::ReceiveFileDescriptors(ctx->control_socket_, &dummy, 1, &jdwp_fd);
  if (rc != 1) {
    return rc;
  }
  return jdwp_fd.release();
}