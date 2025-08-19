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

#include <chrono>
#include <iostream>
#include <mutex>
#include <thread>

#include "adbconnection/client.h"
#include "adbconnection/common.h"
#include "adbconnection/server.h"

#include <gtest/gtest.h>

// How this test works. Normally, the client lives in ART process and the server live in adbd.
// They communicate over UDS "@jdwp-control", each using a poll system (we don't have here).
//
// We spawn the client and the server in the same process. They still use the same UDS to
// communicate. The fdevent from adbd system is mocked with a single loop (server_callback). The
// conditional variable is used to pace the test (send then assert).

ProcessInfo info = {};

// The client synchronize with the server with mx and cv
std::mutex mx;
std::condition_variable cv;
void onUpdateReceived() {
  std::lock_guard<std::mutex> lock(mx);
  cv.notify_one();
}
void waitForUpdateReceived() {
  std::unique_lock<std::mutex> lock(mx);
  cv.wait(lock);
}

void server_callback(int fd, ProcessInfo process) {
  info = process;
  onUpdateReceived();
  // After the first processinfo update is received, jdwp_service in adbd takes over reading
  // from the fd leveraging fdevent system. We emulate it by reading on a regular basis.
  while (true) {
    auto optional = readProcessInfoFromSocket(fd);
    if (optional) {
      info = *optional;
      onUpdateReceived();
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }
}

// This test mimics an app starting up and sending data as zygote is specializing
TEST(LibAdbConnectionTest, TestComm) {
  // Start a fake server
  std::thread([]() { adbconnection_listen(server_callback); }).detach();
  // Let the server start
  sleep(1);

  const char* isa = "arch_foo";
  const AdbConnectionClientInfo infos[] = {
      {.type = AdbConnectionClientInfoType::pid, .data.pid = 666},
      {.type = AdbConnectionClientInfoType::debuggable, .data.debuggable = true},
      {.type = AdbConnectionClientInfoType::profileable, .data.profileable = true},
      {.type = AdbConnectionClientInfoType::architecture,
       .data.architecture.name = isa,
       .data.architecture.size = strlen(isa)},
  };

  //   Send the first batch of data (mimic the app starting up)
  const AdbConnectionClientInfo* info_ptrs[] = {&infos[0], &infos[1], &infos[2], &infos[3]};
  auto ctx = adbconnection_client_new(info_ptrs, std::size(infos));
  EXPECT_TRUE(ctx != nullptr);
  EXPECT_FALSE(adbconnection_client_has_pending_update());

  waitForUpdateReceived();
  EXPECT_EQ(info.pid, infos[0].data.pid);
  EXPECT_TRUE(info.debuggable);
  EXPECT_TRUE(info.profileable);
  EXPECT_EQ(info.architecture, isa);
  EXPECT_FALSE(adbconnection_client_has_pending_update());

  adbconnection_client_set_current_process_name("my_process_name");
  adbconnection_client_add_application("my_package_name");
  adbconnection_client_add_application("my_package_name2");
  adbconnection_client_remove_application("my_package_name2");
  adbconnection_client_set_user_id(888);
  adbconnection_client_set_waiting_for_debugger(true);

  EXPECT_TRUE(adbconnection_client_has_pending_update());

  // Send an update
  adbconnection_client_send_update(ctx);
  EXPECT_FALSE(adbconnection_client_has_pending_update());

  waitForUpdateReceived();
  EXPECT_EQ(info.package_names.size(), 1);
  EXPECT_EQ(info.package_names.count("my_package_name"), 1);
  EXPECT_EQ(info.process_name, "my_process_name");
  EXPECT_EQ(info.user_id, 888);
  EXPECT_TRUE(info.waiting_for_debugger);
}