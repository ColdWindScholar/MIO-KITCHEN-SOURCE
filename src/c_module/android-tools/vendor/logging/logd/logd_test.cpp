/*
 * Copyright (C) 2014 The Android Open Source Project
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

#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#include <string>

#include <android-base/file.h>
#include <android-base/macros.h>
#include <android-base/stringprintf.h>
#include <android-base/unique_fd.h>
#include <cutils/sockets.h>
#include <gtest/gtest-death-test.h>
#include <gtest/gtest.h>
#include <log/log_read.h>
#include <private/android_filesystem_config.h>
#include <private/android_logger.h>
#ifdef __ANDROID__
#include <selinux/selinux.h>
#endif

#include "LogUtils.h"  // For LOGD_SNDTIMEO.

using android::base::unique_fd;

#ifdef __ANDROID__
static bool write_command(int sock, const char* command) {
    // The command sent to logd must include the '\0' character at the end.
    size_t command_length = strlen(command) + 1;
    ssize_t bytes_written = TEMP_FAILURE_RETRY(write(sock, command, command_length));
    if (bytes_written != static_cast<ssize_t>(command_length)) {
        if (bytes_written == -1) {
            printf("Failed to send '%s' command: %s\n", command, strerror(errno));
        } else {
            printf("Failed to send '%s' command: bytes written %zd, expected written %zu\n",
                   command, bytes_written, command_length);
        }
        return false;
    }
    return true;
}

static bool write_command(int sock, const std::string& command) {
    return write_command(sock, command.c_str());
}

static void send_to_control(const char* command, std::string& result) {
    unique_fd sock(socket_local_client("logd", ANDROID_SOCKET_NAMESPACE_RESERVED, SOCK_STREAM));
    ASSERT_LT(0, sock) << "Failed to open logd: " << strerror(errno);
    ASSERT_TRUE(write_command(sock, command));
    result.clear();
    while (true) {
        struct pollfd p = {.fd = sock, .events = POLLIN, .revents = 0};
        // Timeout after 20 seconds.
        int ret = TEMP_FAILURE_RETRY(poll(&p, 1, 20000));
        ASSERT_TRUE(ret != -1) << "Poll call failed for command '" << command
                               << "': " << strerror(errno);
        ASSERT_NE(0, ret) << "Timeout sending command '" << command << "'";
        ASSERT_TRUE(p.revents & POLLIN)
                << "Command socket not readable for command '" << command << "'";

        char buffer[256];
        ssize_t bytes_read = TEMP_FAILURE_RETRY(read(sock, buffer, sizeof(buffer)));
        ASSERT_GE(bytes_read, 0) << "Read failed for command '" << command
                                 << "': " << strerror(errno);
        result += std::string(buffer, bytes_read);
        if (bytes_read == 0 || static_cast<size_t>(bytes_read) < sizeof(buffer)) {
            return;
        }
    }
}
#endif

#ifdef LOGD_ENABLE_FLAKY_TESTS
TEST(logd, statistics) {
#ifdef __ANDROID__
    // Drop cache so that any access problems can be discovered.
    if (!android::base::WriteStringToFile("3\n", "/proc/sys/vm/drop_caches")) {
        GTEST_LOG_(INFO) << "Could not open trigger dropping inode cache";
    }

    std::string result;
    send_to_control("getStatistics 0 1 2 3 4", result);
    ASSERT_FALSE(result.empty());

    EXPECT_NE(std::string::npos, result.find("\nChattiest UIDs in main "));

    EXPECT_NE(std::string::npos, result.find("\nChattiest UIDs in radio "));

    EXPECT_NE(std::string::npos, result.find("\nChattiest UIDs in system "));

    EXPECT_NE(std::string::npos, result.find("\nChattiest UIDs in events "));

    // Look for any u0_a or u0_a[0-9]+ values. If found, it indicates the
    // libpackagelistparser failed.
    static const char getpwuid_prefix[] = " u0_a";
    size_t pos = 0;
    while ((pos = result.find(getpwuid_prefix, pos)) != std::string::npos) {
        // Check to see if the value following u0_a is all digits, or empty.
        size_t uid_name_pos = pos + strlen(getpwuid_prefix);
        size_t i = 0;
        while (isdigit(result[uid_name_pos + i])) {
            i++;
        }
        ASSERT_FALSE(isspace(result[uid_name_pos + i]))
                << "libpackagelistparser failed to pick up " << result.substr(uid_name_pos, i);

        pos = uid_name_pos + i;
    }
#else
    GTEST_LOG_(INFO) << "This test does nothing.\n";
#endif
}
#endif

#ifdef __ANDROID__
static void caught_signal(int /* signum */) {
}

static void dump_log_msg(const char* prefix, log_msg* msg, int lid) {
    std::cout << std::flush;
    std::cerr << std::flush;
    fflush(stdout);
    fflush(stderr);
    EXPECT_GE(msg->entry.hdr_size, sizeof(logger_entry));

    fprintf(stderr, "%s: [%u] ", prefix, msg->len());
    fprintf(stderr, "hdr_size=%u ", msg->entry.hdr_size);
    fprintf(stderr, "pid=%u tid=%u %u.%09u ", msg->entry.pid, msg->entry.tid, msg->entry.sec,
            msg->entry.nsec);
    lid = msg->entry.lid;

    switch (lid) {
        case 0:
            fprintf(stderr, "lid=main ");
            break;
        case 1:
            fprintf(stderr, "lid=radio ");
            break;
        case 2:
            fprintf(stderr, "lid=events ");
            break;
        case 3:
            fprintf(stderr, "lid=system ");
            break;
        case 4:
            fprintf(stderr, "lid=crash ");
            break;
        case 5:
            fprintf(stderr, "lid=security ");
            break;
        case 6:
            fprintf(stderr, "lid=kernel ");
            break;
        default:
            if (lid >= 0) {
                fprintf(stderr, "lid=%d ", lid);
            }
    }

    unsigned int len = msg->entry.len;
    fprintf(stderr, "msg[%u]={", len);
    unsigned char* cp = reinterpret_cast<unsigned char*>(msg->msg());
    if (!cp) {
        static const unsigned char garbage[] = "<INVALID>";
        cp = const_cast<unsigned char*>(garbage);
        len = strlen(reinterpret_cast<const char*>(garbage));
    }
    while (len) {
        unsigned char* p = cp;
        while (*p && (((' ' <= *p) && (*p < 0x7F)) || (*p == '\n'))) {
            ++p;
        }
        if (((p - cp) > 3) && !*p && ((unsigned int)(p - cp) < len)) {
            fprintf(stderr, "\"");
            while (*cp) {
                if (*cp != '\n') {
                    fprintf(stderr, "%c", *cp);
                } else {
                    fprintf(stderr, "\\n");
                }
                ++cp;
                --len;
            }
            fprintf(stderr, "\"");
        } else {
            fprintf(stderr, "%02x", *cp);
        }
        ++cp;
        if (--len) {
            fprintf(stderr, ", ");
        }
    }
    fprintf(stderr, "}\n");
    fflush(stderr);
}
#endif

// b/26447386 confirm fixed
void timeout_negative([[maybe_unused]] const char* command) {
#ifdef __ANDROID__
    log_msg msg_wrap, msg_timeout;
    bool content_wrap = false, content_timeout = false, written = false;
    unsigned int alarm_wrap = 0, alarm_timeout = 0;
    // A few tries to get it right just in case wrap kicks in due to
    // content providers being active during the test.
    int i = 3;

    while (--i) {
        unique_fd fd(
                socket_local_client("logdr", ANDROID_SOCKET_NAMESPACE_RESERVED, SOCK_SEQPACKET));
        ASSERT_LT(0, fd) << "Failed to open logdr: " << strerror(errno);

        struct sigaction ignore = {.sa_handler = caught_signal};
        sigemptyset(&ignore.sa_mask);
        struct sigaction old_sigaction;
        sigaction(SIGALRM, &ignore, &old_sigaction);
        unsigned int old_alarm = alarm(3);

        written = write_command(fd, command);
        if (!written) {
            alarm(old_alarm);
            sigaction(SIGALRM, &old_sigaction, nullptr);
            continue;
        }

        // alarm triggers at 50% of the --wrap time out
        content_wrap = TEMP_FAILURE_RETRY(recv(fd, msg_wrap.buf, sizeof(msg_wrap), 0)) > 0;

        alarm_wrap = alarm(5);

        // alarm triggers at 133% of the --wrap time out
        content_timeout = TEMP_FAILURE_RETRY(recv(fd, msg_timeout.buf, sizeof(msg_timeout), 0)) > 0;
        if (!content_timeout) {  // make sure we hit dumpAndClose
            content_timeout =
                    TEMP_FAILURE_RETRY(recv(fd, msg_timeout.buf, sizeof(msg_timeout), 0)) > 0;
        }

        if (old_alarm > 0) {
            unsigned int time_spent = 3 - alarm_wrap;
            if (old_alarm > time_spent + 1) {
                old_alarm -= time_spent;
            } else {
                old_alarm = 2;
            }
        }
        alarm_timeout = alarm(old_alarm);
        sigaction(SIGALRM, &old_sigaction, nullptr);

        if (content_wrap && alarm_wrap && content_timeout && alarm_timeout) {
            break;
        }
    }

    if (content_wrap) {
        dump_log_msg("wrap", &msg_wrap, -1);
    }

    if (content_timeout) {
        dump_log_msg("timeout", &msg_timeout, -1);
    }

    EXPECT_TRUE(written);
    EXPECT_TRUE(content_wrap);
    EXPECT_NE(0U, alarm_wrap);
    EXPECT_TRUE(content_timeout);
    EXPECT_NE(0U, alarm_timeout);
#else
    command = nullptr;
    GTEST_LOG_(INFO) << "This test does nothing.\n";
#endif
}

TEST(logd, timeout_no_start) {
    timeout_negative("dumpAndClose lids=0,1,2,3,4,5 timeout=6");
}

TEST(logd, timeout_start_epoch) {
    timeout_negative(
        "dumpAndClose lids=0,1,2,3,4,5 timeout=6 start=0.000000000");
}

#ifdef LOGD_ENABLE_FLAKY_TESTS
// b/26447386 refined behavior
TEST(logd, timeout) {
#ifdef __ANDROID__
    // b/33962045 This test interferes with other log reader tests that
    // follow because of file descriptor socket persistence in the same
    // process.  So let's fork it to isolate it from giving us pain.

    pid_t pid = fork();

    if (pid) {
        siginfo_t info = {};
        ASSERT_EQ(0, TEMP_FAILURE_RETRY(waitid(P_PID, pid, &info, WEXITED)));
        ASSERT_EQ(0, info.si_status);
        return;
    }

    log_msg msg_wrap, msg_timeout;
    bool content_wrap = false, content_timeout = false, written = false;
    unsigned int alarm_wrap = 0, alarm_timeout = 0;
    // A few tries to get it right just in case wrap kicks in due to
    // content providers being active during the test.
    int i = 5;
    log_time start(CLOCK_REALTIME);
    start.tv_sec -= 30;  // reach back a moderate period of time

    while (--i) {
        unique_fd fd(
                socket_local_client("logdr", ANDROID_SOCKET_NAMESPACE_RESERVED, SOCK_SEQPACKET));
        ASSERT_LT(0, fd) << "Failed to open logdr: " << strerror(errno);

        std::string ask = android::base::StringPrintf(
            "dumpAndClose lids=0,1,2,3,4,5 timeout=6 start=%" PRIu32
            ".%09" PRIu32,
            start.tv_sec, start.tv_nsec);

        struct sigaction ignore = {.sa_handler = caught_signal};
        sigemptyset(&ignore.sa_mask);
        struct sigaction old_sigaction;
        sigaction(SIGALRM, &ignore, &old_sigaction);
        unsigned int old_alarm = alarm(3);

        written = write_command(fd, ask);
        if (!written) {
            alarm(old_alarm);
            sigaction(SIGALRM, &old_sigaction, nullptr);
            continue;
        }

        // alarm triggers at 50% of the --wrap time out
        content_wrap = TEMP_FAILURE_RETRY(recv(fd, msg_wrap.buf, sizeof(msg_wrap), 0)) > 0;

        alarm_wrap = alarm(5);

        // alarm triggers at 133% of the --wrap time out
        content_timeout = TEMP_FAILURE_RETRY(recv(fd, msg_timeout.buf, sizeof(msg_timeout), 0)) > 0;
        if (!content_timeout) {  // make sure we hit dumpAndClose
            content_timeout =
                    TEMP_FAILURE_RETRY(recv(fd, msg_timeout.buf, sizeof(msg_timeout), 0)) > 0;
        }

        if (old_alarm > 0) {
            unsigned int time_spent = 3 - alarm_wrap;
            if (old_alarm > time_spent + 1) {
                old_alarm -= time_spent;
            } else {
                old_alarm = 2;
            }
        }
        alarm_timeout = alarm(old_alarm);
        sigaction(SIGALRM, &old_sigaction, nullptr);

        if (!content_wrap && !alarm_wrap && content_timeout && alarm_timeout) {
            break;
        }

        // modify start time in case content providers are relatively
        // active _or_ inactive during the test.
        if (content_timeout) {
            log_time msg(msg_timeout.entry.sec, msg_timeout.entry.nsec);
            if (msg < start) {
                fprintf(stderr, "%u.%09u < %u.%09u\n", msg_timeout.entry.sec,
                        msg_timeout.entry.nsec, (unsigned)start.tv_sec,
                        (unsigned)start.tv_nsec);
                _exit(-1);
            }
            if (msg > start) {
                start = msg;
                start.tv_sec += 30;
                log_time now = log_time(CLOCK_REALTIME);
                if (start > now) {
                    start = now;
                    --start.tv_sec;
                }
            }
        } else {
            start.tv_sec -= 120;  // inactive, reach further back!
        }
    }

    if (content_wrap) {
        dump_log_msg("wrap", &msg_wrap, -1);
    }

    if (content_timeout) {
        dump_log_msg("timeout", &msg_timeout, -1);
    }

    if (content_wrap || !content_timeout) {
        fprintf(stderr, "start=%" PRIu32 ".%09" PRIu32 "\n", start.tv_sec,
                start.tv_nsec);
    }

    EXPECT_TRUE(written);
    EXPECT_FALSE(content_wrap);
    EXPECT_EQ(0U, alarm_wrap);
    EXPECT_TRUE(content_timeout);
    EXPECT_NE(0U, alarm_timeout);

    _exit(!written + content_wrap + alarm_wrap + !content_timeout +
          !alarm_timeout);
#else
    GTEST_LOG_(INFO) << "This test does nothing.\n";
#endif
}
#endif

#ifdef LOGD_ENABLE_FLAKY_TESTS
// b/27242723 confirmed fixed
TEST(logd, SNDTIMEO) {
#ifdef __ANDROID__
    static const unsigned sndtimeo =
        LOGD_SNDTIMEO;  // <sigh> it has to be done!
    static const unsigned sleep_time = sndtimeo + 3;
    static const unsigned alarm_time = sleep_time + 5;

    unique_fd fd(socket_local_client("logdr", ANDROID_SOCKET_NAMESPACE_RESERVED, SOCK_SEQPACKET));
    ASSERT_LT(0, fd) << "Failed to open logdr: " << strerror(errno);

    struct sigaction ignore = {.sa_handler = caught_signal};
    sigemptyset(&ignore.sa_mask);
    struct sigaction old_sigaction;
    sigaction(SIGALRM, &ignore, &old_sigaction);
    unsigned int old_alarm = alarm(alarm_time);

    // Stream all sources.
    ASSERT_TRUE(write_command(fd, "stream lids=0,1,2,3,4,5,6"));

    log_msg msg;
    bool read_one = TEMP_FAILURE_RETRY(recv(fd, msg.buf, sizeof(msg), 0)) > 0;
    EXPECT_TRUE(read_one);
    if (read_one) {
        dump_log_msg("user", &msg, -1);
    }

    fprintf(stderr, "Sleep for >%d seconds logd SO_SNDTIMEO ...\n", sndtimeo);
    sleep(sleep_time);

    // flush will block if we did not trigger. if it did, last entry returns 0
    int recv_ret;
    do {
        recv_ret = TEMP_FAILURE_RETRY(recv(fd, msg.buf, sizeof(msg), 0));
    } while (recv_ret > 0);
    int save_errno = (recv_ret < 0) ? errno : 0;

    EXPECT_NE(0U, alarm(old_alarm));
    sigaction(SIGALRM, &old_sigaction, nullptr);

    EXPECT_EQ(0, recv_ret);
    if (recv_ret > 0) {
        dump_log_msg("user", &msg, -1);
    }
    EXPECT_EQ(0, save_errno);
#else
    GTEST_LOG_(INFO) << "This test does nothing.\n";
#endif
}
#endif

TEST(logd, getEventTag_list) {
#ifdef __ANDROID__
    std::string result;
    send_to_control("getEventTag name=*", result);
    ASSERT_FALSE(result.empty());

    char* cp;
    long ret = strtol(result.c_str(), &cp, 10);
    EXPECT_GT(ret, 4096) << "Command result: " << result;
#else
    GTEST_LOG_(INFO) << "This test does nothing.\n";
#endif
}

TEST(logd, getEventTag_42) {
#ifdef __ANDROID__
    std::string result;
    send_to_control("getEventTag id=42", result);
    ASSERT_FALSE(result.empty());

    char* cp;
    long ret = strtol(result.c_str(), &cp, 10);
    EXPECT_GT(ret, 16) << "Command result: " << result;
    EXPECT_NE(std::string::npos, result.find("\t(to life the universe etc|3)"))
            << "Command result: " << result;
    EXPECT_NE(std::string::npos, result.find("answer")) << "Command result: " << result;
#else
    GTEST_LOG_(INFO) << "This test does nothing.\n";
#endif
}

TEST(logd, getEventTag_newentry) {
#ifdef __ANDROID__
    log_time now(CLOCK_MONOTONIC);
    std::string name;
    name = android::base::StringPrintf("a%" PRIu64, now.nsec());

    std::string command;
    command = android::base::StringPrintf("getEventTag name=%s format=\"(new|1)\"", name.c_str());

    std::string result;
    send_to_control(command.c_str(), result);
    ASSERT_FALSE(result.empty());

    char* cp;
    long ret = strtol(result.c_str(), &cp, 10);
    EXPECT_GT(ret, 16) << "Command result: " << result;
    EXPECT_NE(std::string::npos, result.find("\t(new|1)")) << "Command result: " << result;
    EXPECT_NE(std::string::npos, result.find(name)) << "Command result: " << result;
// ToDo: also look for this in /data/misc/logd/event-log-tags and
// /dev/event-log-tags.
#else
    GTEST_LOG_(INFO) << "This test does nothing.\n";
#endif
}

TEST(logd, no_epipe) {
#ifdef __ANDROID__
    // Actually generating SIGPIPE in logd is racy, since we need to close the socket quicker than
    // logd finishes writing the data to it, so we try 5 times, which should be enough to trigger
    // SIGPIPE if logd isn't ignoring SIGPIPE
    for (int i = 0; i < 5; ++i) {
        unique_fd sock1(
                socket_local_client("logd", ANDROID_SOCKET_NAMESPACE_RESERVED, SOCK_STREAM));
        ASSERT_LT(0, sock1) << "Failed to open logd: " << strerror(errno);
        unique_fd sock2(
                socket_local_client("logd", ANDROID_SOCKET_NAMESPACE_RESERVED, SOCK_STREAM));
        ASSERT_LT(0, sock2) << "Failed to open logd: " << strerror(errno);

        std::string message = "getStatistics 0 1 2 3 4 5 6 7";
        ASSERT_TRUE(write_command(sock1, message));
        sock1.reset();
        ASSERT_TRUE(write_command(sock2, message));

        struct pollfd p = {.fd = sock2, .events = POLLIN, .revents = 0};

        int ret = TEMP_FAILURE_RETRY(poll(&p, 1, 1000));
        EXPECT_EQ(ret, 1);
        EXPECT_TRUE(p.revents & POLLIN);
        EXPECT_FALSE(p.revents & POLL_ERR);
    }
#else
    GTEST_LOG_(INFO) << "This test does nothing.\n";
#endif
}

// Only AID_ROOT, AID_SYSTEM, and AID_LOG can set log sizes.  Ensure that a different user, AID_BIN,
// cannot set the log size.
TEST(logd, logging_permissions) {
#ifdef __ANDROID__
    if (getuid() != 0) {
        GTEST_SKIP() << "This test requires root";
    }

    auto child_main = [] {
        setgroups(0, nullptr);
        setgid(AID_BIN);
        setuid(AID_BIN);

        std::unique_ptr<logger_list, decltype(&android_logger_list_free)> logger_list{
                android_logger_list_alloc(0, 0, 0), &android_logger_list_free};
        if (!logger_list) {
            _exit(1);
        }
        auto logger = android_logger_open(logger_list.get(), LOG_ID_MAIN);
        if (!logger) {
            _exit(2);
        }
        // This line should fail, so if it returns 0, we exit with an error.
        if (android_logger_set_log_size(logger, 2 * 1024 * 1024) == 0) {
            _exit(3);
        }
        _exit(EXIT_SUCCESS);
    };

    ASSERT_EXIT(child_main(), testing::ExitedWithCode(0), "");
#else
    GTEST_LOG_(INFO) << "This test does nothing.\n";
#endif
}
