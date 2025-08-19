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

#include "SerializedLogChunk.h"

#include <limits>

#include <android-base/silent_death_test.h>
#include <android-base/stringprintf.h>
#include <android/log.h>
#include <gtest/gtest.h>

using SerializedLogChunk_DeathTest = SilentDeathTest;

using android::base::StringPrintf;

TEST(SerializedLogChunk, smoke) {
    size_t chunk_size = 10 * 4096;
    auto chunk = SerializedLogChunk{chunk_size};
    EXPECT_EQ(chunk_size + sizeof(SerializedLogChunk), chunk.PruneSize());

    static const char log_message[] = "log message";
    size_t expected_total_len = sizeof(SerializedLogEntry) + sizeof(log_message);
    ASSERT_TRUE(chunk.CanLog(expected_total_len));
    EXPECT_TRUE(chunk.CanLog(chunk_size));
    EXPECT_FALSE(chunk.CanLog(chunk_size + 1));

    log_time time(CLOCK_REALTIME);
    auto* entry = chunk.Log(1234, time, 0, 1, 2, log_message, sizeof(log_message));
    ASSERT_NE(nullptr, entry);

    EXPECT_EQ(1234U, entry->sequence());
    EXPECT_EQ(time, entry->realtime());
    EXPECT_EQ(0U, entry->uid());
    EXPECT_EQ(1, entry->pid());
    EXPECT_EQ(2, entry->tid());
    EXPECT_EQ(sizeof(log_message), entry->msg_len());
    EXPECT_STREQ(log_message, entry->msg());
    EXPECT_EQ(expected_total_len, entry->total_len());

    EXPECT_FALSE(chunk.CanLog(chunk_size));
    EXPECT_EQ(static_cast<int>(expected_total_len), chunk.write_offset());
    EXPECT_EQ(1234U, chunk.highest_sequence_number());
}

TEST(SerializedLogChunk, fill_log_exactly) {
    static const char log_message[] = "this is a log message";
    size_t individual_message_size = sizeof(SerializedLogEntry) + sizeof(log_message);
    size_t chunk_size = individual_message_size * 3;
    auto chunk = SerializedLogChunk{chunk_size};
    EXPECT_EQ(chunk_size + sizeof(SerializedLogChunk), chunk.PruneSize());

    ASSERT_TRUE(chunk.CanLog(individual_message_size));
    EXPECT_NE(nullptr, chunk.Log(1, log_time(), 1000, 1, 1, log_message, sizeof(log_message)));

    ASSERT_TRUE(chunk.CanLog(individual_message_size));
    EXPECT_NE(nullptr, chunk.Log(2, log_time(), 1000, 2, 1, log_message, sizeof(log_message)));

    ASSERT_TRUE(chunk.CanLog(individual_message_size));
    EXPECT_NE(nullptr, chunk.Log(3, log_time(), 1000, 3, 1, log_message, sizeof(log_message)));

    EXPECT_FALSE(chunk.CanLog(1));
}

TEST(SerializedLogChunk, three_logs) {
    size_t chunk_size = 10 * 4096;
    auto chunk = SerializedLogChunk{chunk_size};

    chunk.Log(2, log_time(0x1234, 0x5678), 0x111, 0x222, 0x333, "initial message",
              strlen("initial message"));
    chunk.Log(3, log_time(0x2345, 0x6789), 0x444, 0x555, 0x666, "second message",
              strlen("second message"));
    auto uint64_t_max = std::numeric_limits<uint64_t>::max();
    auto uint32_t_max = std::numeric_limits<uint32_t>::max();
    chunk.Log(uint64_t_max, log_time(uint32_t_max, uint32_t_max), uint32_t_max, uint32_t_max,
              uint32_t_max, "last message", strlen("last message"));

    static const char expected_buffer_data[] =
            "\x11\x01\x00\x00\x22\x02\x00\x00\x33\x03\x00\x00"  // UID PID TID
            "\x02\x00\x00\x00\x00\x00\x00\x00"                  // Sequence
            "\x34\x12\x00\x00\x78\x56\x00\x00"                  // Timestamp
            "\x0F\x00initial message"                           // msg_len + message
            "\x44\x04\x00\x00\x55\x05\x00\x00\x66\x06\x00\x00"  // UID PID TID
            "\x03\x00\x00\x00\x00\x00\x00\x00"                  // Sequence
            "\x45\x23\x00\x00\x89\x67\x00\x00"                  // Timestamp
            "\x0E\x00second message"                            // msg_len + message
            "\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF"  // UID PID TID
            "\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF"                  // Sequence
            "\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF"                  // Timestamp
            "\x0C\x00last message";                             // msg_len + message

    for (size_t i = 0; i < sizeof(expected_buffer_data) - 1; ++i) {
        EXPECT_EQ(static_cast<uint8_t>(expected_buffer_data[i]), chunk.data()[i])
                << "position: " << i;
    }
}

// Check that the CHECK() in DecReaderRefCount() if the ref count goes bad is caught.
TEST_F(SerializedLogChunk_DeathTest, catch_DecCompressedRef_CHECK) {
    size_t chunk_size = 10 * 4096;
    auto chunk = SerializedLogChunk{chunk_size};
    EXPECT_DEATH({ chunk.DecReaderRefCount(); }, "");
}

