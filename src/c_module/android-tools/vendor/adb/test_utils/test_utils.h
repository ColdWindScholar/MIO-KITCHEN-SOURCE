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

#include <string>
#include <vector>

#include <android-base/file.h>
#include <android-base/unique_fd.h>

namespace test_utils {

// Reads raw data from |fd| until it closes or errors.
std::string ReadRaw(android::base::borrowed_fd fd);

// / Reads shell protocol data from |fd| until it closes or errors. Fills
// |stdout| and |stderr| with their respective data, and returns the exit code
// read from the protocol or -1 if an exit code packet was not received.
int ReadShellProtocol(android::base::borrowed_fd fd, std::string* std_out, std::string* std_err);

// Checks if each line in |lines| exists in the same order in |output|. Blank
// lines in |output| are ignored for simplicity.
bool ExpectLinesEqual(const std::string& output, const std::vector<std::string>& lines);

// Allows the device to allocate a port, which is returned to the caller.
// Also returns the associated fd.
int GetUnassignedPort(android::base::unique_fd& fd);

}  // namespace test_utils
