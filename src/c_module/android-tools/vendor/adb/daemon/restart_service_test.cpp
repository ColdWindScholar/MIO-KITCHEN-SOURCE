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

#include "restart_service.h"

#include <time.h>
#include <string>

#include <android-base/properties.h>
#include <android-base/stringprintf.h>
#include <android-base/strings.h>
#include <gtest/gtest.h>

#include "services.h"
#include "sysdeps.h"
#include "test_utils/test_utils.h"

using namespace test_utils;

// Test successful execution of tcp restart.
TEST(RestartServiceTest, RestartTcpServiceValidPortSuccess) {
    // Identify an available port from the system allocated pool.
    // The objective is to do a best guess attempt at randomizing the
    // specified port on which the restart service listens.
    unique_fd dontcare;
    const int assigned_port(test_utils::GetUnassignedPort(dontcare));

    unique_fd command_fd_ = create_service_thread(
            "tcp", std::bind(restart_tcp_service, std::placeholders::_1, assigned_port));
    EXPECT_GE(command_fd_.get(), 0);
    test_utils::ExpectLinesEqual(
            ReadRaw(command_fd_),
            {android::base::StringPrintf("restarting in TCP mode port: %d", assigned_port)});

    EXPECT_EQ(android::base::GetProperty("service.adb.tcp.port", ""),
              std::to_string(assigned_port));
}

// Test failure path of  tcp restart.
TEST(RestartServiceTest, RestartTcpServiceInvalidPortFailure) {
    const std::string port_str = android::base::GetProperty("service.adb.tcp.port", "");

    const int port = -5;
    unique_fd command_fd_ = create_service_thread(
            "tcp", std::bind(restart_tcp_service, std::placeholders::_1, port));
    EXPECT_GE(command_fd_, 0);
    test_utils::ExpectLinesEqual(ReadRaw(command_fd_),
                                 {android::base::StringPrintf("invalid port %d", port)});

    // Validate that there's no mutation.
    EXPECT_EQ(android::base::GetProperty("service.adb.tcp.port", ""), port_str);
}

// Test successful execution of usb restart.
TEST(RestartServiceTest, RestartUsbServiceSuccess) {
    unique_fd command_fd_ = create_service_thread("usb", restart_usb_service);
    EXPECT_GE(command_fd_, 0);

    test_utils::ExpectLinesEqual(ReadRaw(command_fd_),
                                 {android::base::StringPrintf("restarting in USB mode")});

    EXPECT_EQ(android::base::GetProperty("service.adb.tcp.port", ""), "0");
}
