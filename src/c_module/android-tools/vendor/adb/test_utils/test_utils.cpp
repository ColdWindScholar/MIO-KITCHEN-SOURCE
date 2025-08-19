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

#include "test_utils.h"

#include <android-base/strings.h>
#include <android-base/test_utils.h>

#include <cutils/sockets.h>
#include <gtest/gtest.h>

#include "shell_protocol.h"
#include "sysdeps.h"

namespace test_utils {

// Reads raw data from |fd| until it closes or errors.
std::string ReadRaw(android::base::borrowed_fd fd) {
    char buffer[1024];
    char *cur_ptr = buffer, *end_ptr = buffer + sizeof(buffer);

    while (1) {
        int bytes = adb_read(fd, cur_ptr, end_ptr - cur_ptr);
        if (bytes <= 0) {
            return std::string(buffer, cur_ptr);
        }
        cur_ptr += bytes;
    }
}

// Reads shell protocol data from |fd| until it closes or errors. Fills
// |stdout| and |stderr| with their respective data, and returns the exit code
// read from the protocol or -1 if an exit code packet was not received.
int ReadShellProtocol(android::base::borrowed_fd fd, std::string* std_out, std::string* std_err) {
    int exit_code = -1;
    std_out->clear();
    std_err->clear();

    auto protocol = std::make_unique<ShellProtocol>(fd.get());
    while (protocol->Read()) {
        switch (protocol->id()) {
            case ShellProtocol::kIdStdout:
                std_out->append(protocol->data(), protocol->data_length());
                break;
            case ShellProtocol::kIdStderr:
                std_err->append(protocol->data(), protocol->data_length());
                break;
            case ShellProtocol::kIdExit:
                EXPECT_EQ(-1, exit_code) << "Multiple exit packets received";
                EXPECT_EQ(1u, protocol->data_length());
                exit_code = protocol->data()[0];
                break;
            default:
                ADD_FAILURE() << "Unidentified packet ID: " << protocol->id();
        }
    }

    return exit_code;
}

// Checks if each line in |lines| exists in the same order in |output|. Blank
// lines in |output| are ignored for simplicity.
bool ExpectLinesEqual(const std::string& output, const std::vector<std::string>& lines) {
    auto output_lines = android::base::Split(output, "\r\n");
    size_t i = 0;

    for (const std::string& line : lines) {
        // Skip empty lines in output.
        while (i < output_lines.size() && output_lines[i].empty()) {
            ++i;
        }
        if (i >= output_lines.size()) {
            ADD_FAILURE() << "Ran out of output lines";
            return false;
        }
        EXPECT_EQ(output_lines[i], line);
        ++i;
    }

    while (i < output_lines.size() && output_lines[i].empty()) {
        ++i;
    }
    EXPECT_EQ(i, output_lines.size()) << "Found unmatched output lines";
    return true;
}

// Relies on the device to allocate an available port, and
// returns it to the caller. Also returns the associated fd.
// Existing client (LocalSocketTest) of this interface is
// implemented only on Linux, hence using cutils.
int GetUnassignedPort(android::base::unique_fd& fd) {
    fd.reset(socket_inaddr_any_server(0, SOCK_STREAM));
    EXPECT_NE(static_cast<cutils_socket_t>(fd.get()), INVALID_SOCKET);

    const int port = socket_get_local_port(fd.get());
    EXPECT_GT(port, 0);

    return port;
}

}  // namespace test_utils
