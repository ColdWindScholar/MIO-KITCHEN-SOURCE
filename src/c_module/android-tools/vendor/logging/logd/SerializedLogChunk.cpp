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

#include <android-base/logging.h>

#include "CompressionEngine.h"
#include "SerializedFlushToState.h"

SerializedLogChunk::~SerializedLogChunk() {
    CHECK_EQ(reader_ref_count_, 0U);
}

void SerializedLogChunk::FinishWriting() {
    writer_active_ = false;
    CHECK_EQ(compressed_log_.size(), 0U);
    CompressionEngine::GetInstance().Compress(contents_, write_offset_, compressed_log_);
    LOG(VERBOSE) << "Compressed Log, buffer max size: " << contents_.size()
                 << " size used: " << write_offset_
                 << " compressed size: " << compressed_log_.size();
    if (reader_ref_count_ == 0) {
        contents_.Resize(0);
    }
}

// TODO: Develop a better reference counting strategy to guard against the case where the writer is
// much faster than the reader, and we needlessly compess / decompress the logs.
void SerializedLogChunk::IncReaderRefCount() {
    if (++reader_ref_count_ != 1 || writer_active_) {
        return;
    }
    contents_.Resize(write_offset_);
    CompressionEngine::GetInstance().Decompress(compressed_log_, contents_);
}

void SerializedLogChunk::DecReaderRefCount() {
    CHECK_NE(reader_ref_count_, 0U);
    if (--reader_ref_count_ != 0) {
        return;
    }
    if (!writer_active_) {
        contents_.Resize(0);
    }
}

void SerializedLogChunk::AttachReader(SerializedFlushToState* reader) {
    readers_.emplace_back(reader);
    IncReaderRefCount();
}

void SerializedLogChunk::DetachReader(SerializedFlushToState* reader) {
    auto it = std::find(readers_.begin(), readers_.end(), reader);
    CHECK(readers_.end() != it);
    readers_.erase(it);
    DecReaderRefCount();
}

void SerializedLogChunk::NotifyReadersOfPrune(log_id_t log_id) {
    // Readers will call DetachReader() in their Prune() call, so we make a copy of the list first.
    auto readers = readers_;
    for (auto& reader : readers) {
        reader->Prune(log_id);
    }
}

bool SerializedLogChunk::CanLog(size_t len) {
    return write_offset_ + len <= contents_.size();
}

SerializedLogEntry* SerializedLogChunk::Log(uint64_t sequence, log_time realtime, uid_t uid,
                                            pid_t pid, pid_t tid, const char* msg, uint16_t len) {
    auto new_log_address = contents_.data() + write_offset_;
    auto* entry = new (new_log_address) SerializedLogEntry(uid, pid, tid, sequence, realtime, len);
    memcpy(entry->msg(), msg, len);
    write_offset_ += entry->total_len();
    highest_sequence_number_ = sequence;
    return entry;
}
