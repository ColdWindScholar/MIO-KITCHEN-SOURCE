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

#include "shell_service.h"

#include <gtest/gtest.h>

#include <signal.h>

#include <string>
#include <vector>

#include <android-base/strings.h>

#include "adb.h"
#include "adb_io.h"
#include "shell_protocol.h"
#include "sysdeps.h"
#include "test_utils/test_utils.h"

using namespace test_utils;

class ShellServiceTest : public ::testing::Test {
  public:
    static void SetUpTestCase() {
        // This is normally done in main.cpp.
        saved_sigpipe_handler_ = signal(SIGPIPE, SIG_IGN);
    }

    static void TearDownTestCase() {
        signal(SIGPIPE, saved_sigpipe_handler_);
    }

    // Helpers to start and cleanup a subprocess. Cleanup normally does not
    // need to be called manually unless multiple subprocesses are run from
    // a single test.
    void StartTestSubprocess(const char* command, SubprocessType type,
                             SubprocessProtocol protocol);
    void CleanupTestSubprocess();

    void StartTestCommandInProcess(std::string name, Command command, SubprocessProtocol protocol);

    virtual void TearDown() override { CleanupTestSubprocess(); }

    static sighandler_t saved_sigpipe_handler_;

    unique_fd command_fd_;
};

sighandler_t ShellServiceTest::saved_sigpipe_handler_ = nullptr;

void ShellServiceTest::StartTestSubprocess(
        const char* command, SubprocessType type, SubprocessProtocol protocol) {
    command_fd_ = StartSubprocess(command, nullptr, type, protocol);
    ASSERT_TRUE(command_fd_ >= 0);
}

void ShellServiceTest::CleanupTestSubprocess() {
}

void ShellServiceTest::StartTestCommandInProcess(std::string name, Command command,
                                                 SubprocessProtocol protocol) {
    command_fd_ = StartCommandInProcess(std::move(name), std::move(command), protocol);
    ASSERT_TRUE(command_fd_ >= 0);
}

// Tests a raw subprocess with no protocol.
TEST_F(ShellServiceTest, RawNoProtocolSubprocess) {
    // [ -t 0 ] checks if stdin is connected to a terminal.
    ASSERT_NO_FATAL_FAILURE(StartTestSubprocess(
            "echo foo; echo bar >&2; [ -t 0 ]; echo $?",
            SubprocessType::kRaw, SubprocessProtocol::kNone));

    // [ -t 0 ] == 0 means we have a terminal (PTY). Even when requesting a raw subprocess, without
    // the shell protocol we should always force a PTY to ensure proper cleanup.
    ExpectLinesEqual(ReadRaw(command_fd_), {"foo", "bar", "0"});
}

// Tests a PTY subprocess with no protocol.
TEST_F(ShellServiceTest, PtyNoProtocolSubprocess) {
    // [ -t 0 ] checks if stdin is connected to a terminal.
    ASSERT_NO_FATAL_FAILURE(StartTestSubprocess(
            "echo foo; echo bar >&2; [ -t 0 ]; echo $?",
            SubprocessType::kPty, SubprocessProtocol::kNone));

    // [ -t 0 ] == 0 means we have a terminal (PTY).
    ExpectLinesEqual(ReadRaw(command_fd_), {"foo", "bar", "0"});
}

// Tests a raw subprocess with the shell protocol.
TEST_F(ShellServiceTest, RawShellProtocolSubprocess) {
    ASSERT_NO_FATAL_FAILURE(StartTestSubprocess(
            "echo foo; echo bar >&2; echo baz; exit 24",
            SubprocessType::kRaw, SubprocessProtocol::kShell));

    std::string stdout, stderr;
    EXPECT_EQ(24, ReadShellProtocol(command_fd_, &stdout, &stderr));
    ExpectLinesEqual(stdout, {"foo", "baz"});
    ExpectLinesEqual(stderr, {"bar"});
}

// Tests a PTY subprocess with the shell protocol.
TEST_F(ShellServiceTest, PtyShellProtocolSubprocess) {
    ASSERT_NO_FATAL_FAILURE(StartTestSubprocess(
            "echo foo; echo bar >&2; echo baz; exit 50",
            SubprocessType::kPty, SubprocessProtocol::kShell));

    // PTY always combines stdout and stderr but the shell protocol should
    // still give us an exit code.
    std::string stdout, stderr;
    EXPECT_EQ(50, ReadShellProtocol(command_fd_, &stdout, &stderr));
    ExpectLinesEqual(stdout, {"foo", "bar", "baz"});
    ExpectLinesEqual(stderr, {});
}

// Tests an interactive PTY session.
TEST_F(ShellServiceTest, InteractivePtySubprocess) {
    ASSERT_NO_FATAL_FAILURE(StartTestSubprocess(
            "", SubprocessType::kPty, SubprocessProtocol::kShell));

    // Use variable substitution so echoed input is different from output.
    const char* commands[] = {"TEST_STR=abc123",
                              "echo --${TEST_STR}--",
                              "exit"};

    ShellProtocol* protocol = new ShellProtocol(command_fd_);
    for (std::string command : commands) {
        // Interactive shell requires a newline to complete each command.
        command.push_back('\n');
        memcpy(protocol->data(), command.data(), command.length());
        ASSERT_TRUE(protocol->Write(ShellProtocol::kIdStdin, command.length()));
    }
    delete protocol;

    std::string stdout, stderr;
    EXPECT_EQ(0, ReadShellProtocol(command_fd_, &stdout, &stderr));
    // An unpredictable command prompt makes parsing exact output difficult but
    // it should at least contain echoed input and the expected output.
    for (const char* command : commands) {
        EXPECT_FALSE(stdout.find(command) == std::string::npos);
    }
    EXPECT_FALSE(stdout.find("--abc123--") == std::string::npos);
}

// Tests closing raw subprocess stdin.
TEST_F(ShellServiceTest, CloseClientStdin) {
    ASSERT_NO_FATAL_FAILURE(StartTestSubprocess(
            "cat; echo TEST_DONE",
            SubprocessType::kRaw, SubprocessProtocol::kShell));

    std::string input = "foo\nbar";
    ShellProtocol* protocol = new ShellProtocol(command_fd_);
    memcpy(protocol->data(), input.data(), input.length());
    ASSERT_TRUE(protocol->Write(ShellProtocol::kIdStdin, input.length()));
    ASSERT_TRUE(protocol->Write(ShellProtocol::kIdCloseStdin, 0));
    delete protocol;

    std::string stdout, stderr;
    EXPECT_EQ(0, ReadShellProtocol(command_fd_, &stdout, &stderr));
    ExpectLinesEqual(stdout, {"foo", "barTEST_DONE"});
    ExpectLinesEqual(stderr, {});
}

// Tests that nothing breaks when the stdin/stdout pipe closes.
TEST_F(ShellServiceTest, CloseStdinStdoutSubprocess) {
    ASSERT_NO_FATAL_FAILURE(StartTestSubprocess(
            "exec 0<&-; exec 1>&-; echo bar >&2",
            SubprocessType::kRaw, SubprocessProtocol::kShell));

    std::string stdout, stderr;
    EXPECT_EQ(0, ReadShellProtocol(command_fd_, &stdout, &stderr));
    ExpectLinesEqual(stdout, {});
    ExpectLinesEqual(stderr, {"bar"});
}

// Tests that nothing breaks when the stderr pipe closes.
TEST_F(ShellServiceTest, CloseStderrSubprocess) {
    ASSERT_NO_FATAL_FAILURE(StartTestSubprocess(
            "exec 2>&-; echo foo",
            SubprocessType::kRaw, SubprocessProtocol::kShell));

    std::string stdout, stderr;
    EXPECT_EQ(0, ReadShellProtocol(command_fd_, &stdout, &stderr));
    ExpectLinesEqual(stdout, {"foo"});
    ExpectLinesEqual(stderr, {});
}

// Tests an inprocess command with no protocol.
TEST_F(ShellServiceTest, RawNoProtocolInprocess) {
    ASSERT_NO_FATAL_FAILURE(
            StartTestCommandInProcess("123",
                                      [](auto args, auto in, auto out, auto err) -> int {
                                          EXPECT_EQ("123", args);
                                          char input[10];
                                          EXPECT_TRUE(ReadFdExactly(in, input, 2));
                                          input[2] = 0;
                                          EXPECT_STREQ("in", input);
                                          WriteFdExactly(out, "out\n");
                                          WriteFdExactly(err, "err\n");
                                          return 0;
                                      },
                                      SubprocessProtocol::kNone));

    WriteFdExactly(command_fd_, "in");
    ExpectLinesEqual(ReadRaw(command_fd_), {"out", "err"});
}

// Tests an inprocess command with the shell protocol.
TEST_F(ShellServiceTest, RawShellProtocolInprocess) {
    ASSERT_NO_FATAL_FAILURE(
            StartTestCommandInProcess("321",
                                      [](auto args, auto in, auto out, auto err) -> int {
                                          EXPECT_EQ("321", args);
                                          char input[10];
                                          EXPECT_TRUE(ReadFdExactly(in, input, 2));
                                          input[2] = 0;
                                          EXPECT_STREQ("in", input);
                                          WriteFdExactly(out, "out\n");
                                          WriteFdExactly(err, "err\n");
                                          return 0;
                                      },
                                      SubprocessProtocol::kShell));

    {
        auto write_protocol = std::make_unique<ShellProtocol>(command_fd_);
        memcpy(write_protocol->data(), "in", 2);
        write_protocol->Write(ShellProtocol::kIdStdin, 2);
    }

    std::string stdout, stderr;
    // For in-process commands the exit code is always the default (1).
    EXPECT_EQ(1, ReadShellProtocol(command_fd_, &stdout, &stderr));
    ExpectLinesEqual(stdout, {"out"});
    ExpectLinesEqual(stderr, {"err"});
}
