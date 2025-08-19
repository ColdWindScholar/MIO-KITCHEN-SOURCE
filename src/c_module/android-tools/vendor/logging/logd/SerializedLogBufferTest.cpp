/*
 * Copyright (C) 2021 The Android Open Source Project
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

#include "SerializedLogBuffer.h"

#include <gtest/gtest.h>
#include <log/log.h>

#include "LogReaderList.h"
#include "LogSize.h"
#include "LogStatistics.h"
#include "LogTags.h"
#include "SerializedLogChunk.h"
#include "SerializedLogEntry.h"

// b/188858988 - Previously, if clearing UID logs erased the back-most chunk, then a chunk that has
// previously been closed for writing will be the back-most chunk in the list. Subsequent calls to
// SerializedLogBuffer::Log() will call SerializedLogChunk::FinishWriting(), which triggered a
// CHECK().
TEST(SerializedLogBuffer, uid_prune_deletes_last_chunk) {
    LogReaderList reader_list;
    LogTags tags;
    LogStatistics stats(false, true);
    SerializedLogBuffer log_buffer(&reader_list, &tags, &stats);

    log_buffer.SetSize(LOG_ID_MAIN, kLogBufferMinSize);
    log_buffer.Clear(LOG_ID_MAIN, 0);

    const uid_t kNonClearUid = 123;
    const std::string kDontClearMessage = "this message is not cleared";
    log_buffer.Log(LOG_ID_MAIN, log_time(0, 1), kNonClearUid, 1, 1, kDontClearMessage.data(),
                   kDontClearMessage.size());

    // Fill at least one chunk with a message with the UID that we'll clear
    const uid_t kClearUid = 555;
    const std::string kClearMessage(1024, 'c');
    size_t size_written = 0;
    while (size_written < kLogBufferMinSize / 2) {
        log_buffer.Log(LOG_ID_MAIN, log_time(1, size_written), kClearUid, 1, 1,
                       kClearMessage.data(), kClearMessage.size());
        size_written += kClearMessage.size();
    }

    log_buffer.Clear(LOG_ID_MAIN, kClearUid);

    // This previously would trigger a CHECK() in SerializedLogChunk::FinishWriting().
    log_buffer.Log(LOG_ID_MAIN, log_time(0, 2), kNonClearUid, 1, 1, kDontClearMessage.data(),
                   kDontClearMessage.size());
}

struct TestEntry {
    uint32_t uid;
    uint32_t pid;
    uint32_t tid;
    uint64_t sequence;
    log_time realtime;
    std::string msg;
};

SerializedLogChunk CreateChunk(size_t max_size, const std::vector<TestEntry>& entries,
                               bool finish_writing) {
    SerializedLogChunk chunk(max_size / SerializedLogBuffer::kChunkSizeDivisor);

    for (const auto& entry : entries) {
        if (!chunk.CanLog(sizeof(SerializedLogEntry) + entry.msg.size())) {
            EXPECT_TRUE(false) << "Test set up failure, entries don't fit in chunks";
            return chunk;
        }
        chunk.Log(entry.sequence, entry.realtime, entry.uid, entry.pid, entry.tid, entry.msg.data(),
                  entry.msg.size());
    }
    if (finish_writing) {
        chunk.FinishWriting();
    }
    return chunk;
}

void VerifyChunks(const std::list<SerializedLogChunk>& expected,
                  const std::list<SerializedLogChunk>& chunks) {
    int chunk = 0;
    auto expected_it = expected.begin();
    auto it = chunks.begin();
    for (; expected_it != expected.end() && it != chunks.end(); ++expected_it, ++it, ++chunk) {
        EXPECT_EQ(expected_it->reader_ref_count_, it->reader_ref_count_) << "chunk #" << chunk;
        EXPECT_EQ(expected_it->writer_active_, it->writer_active_) << "chunk #" << chunk;
        EXPECT_EQ(expected_it->highest_sequence_number_, it->highest_sequence_number_)
                << "chunk #" << chunk;
        EXPECT_EQ(expected_it->readers_, it->readers_) << "chunk #" << chunk;

        ASSERT_EQ(expected_it->contents_.size(), it->contents_.size()) << "chunk #" << chunk;
        ASSERT_EQ(expected_it->write_offset_, it->write_offset_) << "chunk #" << chunk;
        if (expected_it->contents_.size() > 0) {
            for (int i = 0; i < it->write_offset_; ++i) {
                EXPECT_EQ(expected_it->contents_.data()[i], it->contents_.data()[i])
                        << "chunk #" << chunk;
            }
        }

        ASSERT_EQ(expected_it->compressed_log_.size(), it->compressed_log_.size())
                << "chunk #" << chunk;
        if (expected_it->compressed_log_.size() > 0) {
            for (size_t i = 0; i < it->compressed_log_.size(); ++i) {
                EXPECT_EQ(expected_it->compressed_log_.data()[i], it->compressed_log_.data()[i])
                        << "chunk #" << chunk;
            }
        }
    }
    EXPECT_EQ(expected.end(), expected_it);
    EXPECT_EQ(chunks.end(), it);
}

// If no blocks are present before ClearLogsByUid() then no blocks should be output.
TEST(SerializedLogBuffer, uid_prune_no_blocks) {
    const uid_t kClearUid = 555;
    const size_t kMaxSize = kLogBufferMinSize;

    std::list<SerializedLogChunk> chunks;
    std::list<SerializedLogChunk> expected_chunks;

    ClearLogsByUid(chunks, kClearUid, kMaxSize, LOG_ID_MAIN, nullptr);
    VerifyChunks(expected_chunks, chunks);

    ClearLogsByUid(chunks, kClearUid, kMaxSize, LOG_ID_MAIN, nullptr);
    VerifyChunks(expected_chunks, chunks);
}

// If no UIDs to be cleared are found, then the _same exact_ block is returned.
TEST(SerializedLogBuffer, uid_prune_one_block_no_uid) {
    const uid_t kNonClearUid = 123;
    const uid_t kClearUid = 555;
    const size_t kMaxSize = kLogBufferMinSize;

    std::vector<TestEntry> entries = {
            {.uid = kNonClearUid,
             .pid = 10,
             .tid = 10,
             .sequence = 1,
             .realtime = log_time(0, 1),
             .msg = "some message"},
    };

    std::list<SerializedLogChunk> chunks;
    chunks.emplace_back(CreateChunk(kMaxSize, entries, false));
    void* original_chunk_address = reinterpret_cast<void*>(&chunks.front());

    std::list<SerializedLogChunk> expected_chunks;
    expected_chunks.push_back(CreateChunk(kMaxSize, entries, false));

    ClearLogsByUid(chunks, kClearUid, kMaxSize, LOG_ID_MAIN, nullptr);
    VerifyChunks(expected_chunks, chunks);
    void* after_clear_chunk_address = reinterpret_cast<void*>(&chunks.front());
    EXPECT_EQ(original_chunk_address, after_clear_chunk_address);

    ClearLogsByUid(chunks, kClearUid, kMaxSize, LOG_ID_MAIN, nullptr);
    VerifyChunks(expected_chunks, chunks);
    after_clear_chunk_address = reinterpret_cast<void*>(&chunks.front());
    EXPECT_EQ(original_chunk_address, after_clear_chunk_address);
}

std::vector<TestEntry> FilterEntries(const std::vector<TestEntry>& entries, uid_t uid_to_remove) {
    std::vector<TestEntry> filtered_entries;
    for (const auto& entry : entries) {
        if (entry.uid == uid_to_remove) {
            continue;
        }
        filtered_entries.emplace_back(entry);
    }
    return filtered_entries;
}

TEST(SerializedLogBuffer, uid_prune_one_block_some_uid) {
    const uid_t kNonClearUid = 123;
    const uid_t kClearUid = 555;
    const size_t kMaxSize = kLogBufferMinSize;

    std::list<SerializedLogChunk> chunks;
    std::vector<TestEntry> entries = {
            {.uid = kNonClearUid,
             .pid = 10,
             .tid = 10,
             .sequence = 1,
             .realtime = log_time(0, 1),
             .msg = "some message"},
            {.uid = kClearUid,
             .pid = 10,
             .tid = 10,
             .sequence = 2,
             .realtime = log_time(0, 1),
             .msg = "some cleared message"},
    };
    chunks.emplace_back(CreateChunk(kMaxSize, entries, false));

    std::list<SerializedLogChunk> expected_chunks;
    expected_chunks.emplace_back(CreateChunk(kMaxSize, FilterEntries(entries, kClearUid), false));

    ClearLogsByUid(chunks, kClearUid, kMaxSize, LOG_ID_MAIN, nullptr);
    VerifyChunks(expected_chunks, chunks);

    ClearLogsByUid(chunks, kClearUid, kMaxSize, LOG_ID_MAIN, nullptr);
    VerifyChunks(expected_chunks, chunks);
}

TEST(SerializedLogBuffer, uid_prune_one_block_all_uid) {
    const uid_t kClearUid = 555;
    const size_t kMaxSize = kLogBufferMinSize;

    std::list<SerializedLogChunk> chunks;
    std::vector<TestEntry> entries = {
            {.uid = kClearUid,
             .pid = 10,
             .tid = 10,
             .sequence = 1,
             .realtime = log_time(0, 1),
             .msg = "some message"},
            {.uid = kClearUid,
             .pid = 10,
             .tid = 10,
             .sequence = 2,
             .realtime = log_time(0, 1),
             .msg = "some cleared message"},
    };
    chunks.emplace_back(CreateChunk(kMaxSize, entries, false));

    std::list<SerializedLogChunk> expected_chunks;
    expected_chunks.emplace_back(CreateChunk(kMaxSize, {}, false));

    ClearLogsByUid(chunks, kClearUid, kMaxSize, LOG_ID_MAIN, nullptr);
    VerifyChunks(expected_chunks, chunks);

    ClearLogsByUid(chunks, kClearUid, kMaxSize, LOG_ID_MAIN, nullptr);
    VerifyChunks(expected_chunks, chunks);
}

TEST(SerializedLogBuffer, uid_prune_first_middle_last_chunks) {
    const uid_t kNonClearUid = 123;
    const uid_t kClearUid = 555;
    const std::string kMsg = "constant log message";
    const size_t kMaxSize =
            (sizeof(SerializedLogEntry) + kMsg.size()) * SerializedLogBuffer::kChunkSizeDivisor;

    std::list<SerializedLogChunk> chunks;
    std::vector<TestEntry> entries0 = {
            {.uid = kClearUid,
             .pid = 10,
             .tid = 10,
             .sequence = 1,
             .realtime = log_time(0, 1),
             .msg = kMsg},
    };
    chunks.emplace_back(CreateChunk(kMaxSize, entries0, true));
    std::vector<TestEntry> entries1 = {
            {.uid = kNonClearUid,
             .pid = 10,
             .tid = 10,
             .sequence = 2,
             .realtime = log_time(0, 1),
             .msg = kMsg},
    };
    chunks.emplace_back(CreateChunk(kMaxSize, entries1, true));
    std::vector<TestEntry> entries2 = {
            {.uid = kClearUid,
             .pid = 10,
             .tid = 10,
             .sequence = 3,
             .realtime = log_time(0, 1),
             .msg = kMsg},
    };
    chunks.emplace_back(CreateChunk(kMaxSize, entries2, true));
    std::vector<TestEntry> entries3 = {
            {.uid = kNonClearUid,
             .pid = 10,
             .tid = 10,
             .sequence = 4,
             .realtime = log_time(0, 1),
             .msg = kMsg},
    };
    chunks.emplace_back(CreateChunk(kMaxSize, entries3, true));
    std::vector<TestEntry> entries4 = {
            {.uid = kClearUid,
             .pid = 10,
             .tid = 10,
             .sequence = 5,
             .realtime = log_time(0, 1),
             .msg = kMsg},
    };
    chunks.emplace_back(CreateChunk(kMaxSize, entries4, false));

    std::list<SerializedLogChunk> expected_chunks;
    expected_chunks.emplace_back(CreateChunk(kMaxSize, entries1, true));
    expected_chunks.emplace_back(CreateChunk(kMaxSize, entries3, false));

    ClearLogsByUid(chunks, kClearUid, kMaxSize, LOG_ID_MAIN, nullptr);
    VerifyChunks(expected_chunks, chunks);

    ClearLogsByUid(chunks, kClearUid, kMaxSize, LOG_ID_MAIN, nullptr);
    VerifyChunks(expected_chunks, chunks);
}

TEST(SerializedLogBuffer, uid_prune_coalesce) {
    const uid_t kNonClearUid = 123;
    const uid_t kClearUid = 555;
    const std::string kMsg = "constant log message";
    const size_t kMaxSize =
            (sizeof(SerializedLogEntry) + kMsg.size()) * SerializedLogBuffer::kChunkSizeDivisor * 2;

    std::list<SerializedLogChunk> chunks;
    std::vector<TestEntry> entries0 = {
            {.uid = kNonClearUid,
             .pid = 10,
             .tid = 10,
             .sequence = 1,
             .realtime = log_time(0, 1),
             .msg = kMsg},
            {.uid = kNonClearUid,
             .pid = 10,
             .tid = 10,
             .sequence = 2,
             .realtime = log_time(0, 1),
             .msg = kMsg},
    };
    chunks.emplace_back(CreateChunk(kMaxSize, entries0, true));
    std::vector<TestEntry> entries1 = {
            {.uid = kNonClearUid,
             .pid = 10,
             .tid = 10,
             .sequence = 3,
             .realtime = log_time(0, 1),
             .msg = kMsg},
            {.uid = kClearUid,
             .pid = 10,
             .tid = 10,
             .sequence = 4,
             .realtime = log_time(0, 1),
             .msg = kMsg},
    };
    chunks.emplace_back(CreateChunk(kMaxSize, entries1, true));
    std::vector<TestEntry> entries2 = {
            {.uid = kClearUid,
             .pid = 10,
             .tid = 10,
             .sequence = 5,
             .realtime = log_time(0, 1),
             .msg = kMsg},
            {.uid = kClearUid,
             .pid = 10,
             .tid = 10,
             .sequence = 6,
             .realtime = log_time(0, 1),
             .msg = kMsg},
    };
    chunks.emplace_back(CreateChunk(kMaxSize, entries2, true));
    std::vector<TestEntry> entries3 = {
            {.uid = kNonClearUid,
             .pid = 10,
             .tid = 10,
             .sequence = 7,
             .realtime = log_time(0, 1),
             .msg = kMsg},
            {.uid = kNonClearUid,
             .pid = 10,
             .tid = 10,
             .sequence = 8,
             .realtime = log_time(0, 1),
             .msg = kMsg},
    };
    chunks.emplace_back(CreateChunk(kMaxSize, entries3, false));

    std::list<SerializedLogChunk> expected_chunks;
    expected_chunks.emplace_back(CreateChunk(kMaxSize, entries0, true));

    std::vector<TestEntry> expected_entries_1;
    expected_entries_1.emplace_back(entries1[0]);
    expected_entries_1.emplace_back(entries3[0]);
    expected_chunks.emplace_back(CreateChunk(kMaxSize, expected_entries_1, true));

    std::vector<TestEntry> expected_entries_2;
    expected_entries_2.emplace_back(entries3[1]);
    expected_chunks.emplace_back(CreateChunk(kMaxSize, expected_entries_2, false));

    ClearLogsByUid(chunks, kClearUid, kMaxSize, LOG_ID_MAIN, nullptr);
    VerifyChunks(expected_chunks, chunks);

    ClearLogsByUid(chunks, kClearUid, kMaxSize, LOG_ID_MAIN, nullptr);
    VerifyChunks(expected_chunks, chunks);
}
