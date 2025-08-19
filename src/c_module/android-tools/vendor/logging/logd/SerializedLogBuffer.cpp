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

#include "SerializedLogBuffer.h"

#include <sys/prctl.h>

#include <limits>

#include <android-base/logging.h>
#include <android-base/scopeguard.h>

#include "LogSize.h"
#include "LogStatistics.h"
#include "SerializedFlushToState.h"

static SerializedLogEntry* LogToLogBuffer(std::list<SerializedLogChunk>& log_buffer,
                                          size_t max_size, uint64_t sequence, log_time realtime,
                                          uid_t uid, pid_t pid, pid_t tid, const char* msg,
                                          uint16_t len) {
    if (log_buffer.empty()) {
        log_buffer.push_back(SerializedLogChunk(max_size / SerializedLogBuffer::kChunkSizeDivisor));
    }

    auto total_len = sizeof(SerializedLogEntry) + len;
    if (!log_buffer.back().CanLog(total_len)) {
        log_buffer.back().FinishWriting();
        log_buffer.push_back(SerializedLogChunk(max_size / SerializedLogBuffer::kChunkSizeDivisor));
    }

    return log_buffer.back().Log(sequence, realtime, uid, pid, tid, msg, len);
}

// Clear all logs from a particular UID by iterating through all existing logs for a log_id, and
// write all logs that don't match the UID into a new log buffer, then swapping the log buffers.
// There is an optimization that chunks are copied as-is until a log message from the UID is found,
// to ensure that back-to-back clears of the same UID do not require reflowing the entire buffer.
void ClearLogsByUid(std::list<SerializedLogChunk>& log_buffer, uid_t uid, size_t max_size,
                    log_id_t log_id, LogStatistics* stats) REQUIRES(logd_lock) {
    bool contains_uid_logs = false;
    std::list<SerializedLogChunk> new_logs;
    auto it = log_buffer.begin();
    while (it != log_buffer.end()) {
        auto chunk = it++;
        chunk->NotifyReadersOfPrune(log_id);
        chunk->IncReaderRefCount();

        if (!contains_uid_logs) {
            for (const auto& entry : *chunk) {
                if (entry.uid() == uid) {
                    contains_uid_logs = true;
                    break;
                }
            }
            if (!contains_uid_logs) {
                chunk->DecReaderRefCount();
                new_logs.splice(new_logs.end(), log_buffer, chunk);
                continue;
            }
            // We found a UID log, so push a writable chunk to prepare for the next loop.
            new_logs.push_back(
                    SerializedLogChunk(max_size / SerializedLogBuffer::kChunkSizeDivisor));
        }

        for (const auto& entry : *chunk) {
            if (entry.uid() == uid) {
                if (stats != nullptr) {
                    stats->Subtract(entry.ToLogStatisticsElement(log_id));
                }
            } else {
                LogToLogBuffer(new_logs, max_size, entry.sequence(), entry.realtime(), entry.uid(),
                               entry.pid(), entry.tid(), entry.msg(), entry.msg_len());
            }
        }
        chunk->DecReaderRefCount();
        log_buffer.erase(chunk);
    }
    std::swap(new_logs, log_buffer);
}

SerializedLogBuffer::SerializedLogBuffer(LogReaderList* reader_list, LogTags* tags,
                                         LogStatistics* stats)
    : reader_list_(reader_list), tags_(tags), stats_(stats) {
    Init();
}

void SerializedLogBuffer::Init() {
    log_id_for_each(i) {
        if (!SetSize(i, GetBufferSizeFromProperties(i))) {
            SetSize(i, kLogBufferMinSize);
        }
    }

    // Release any sleeping reader threads to dump their current content.
    auto lock = std::lock_guard{logd_lock};
    for (const auto& reader_thread : reader_list_->running_reader_threads()) {
        reader_thread->TriggerReader();
    }
}

bool SerializedLogBuffer::ShouldLog(log_id_t log_id, const char* msg, uint16_t len) {
    if (log_id == LOG_ID_SECURITY) {
        return true;
    }

    int prio = ANDROID_LOG_INFO;
    const char* tag = nullptr;
    size_t tag_len = 0;
    if (IsBinary(log_id)) {
        int32_t tag_int = MsgToTag(msg, len);
        tag = tags_->tagToName(tag_int);
        if (tag) {
            tag_len = strlen(tag);
        }
    } else {
        prio = *msg;
        tag = msg + 1;
        tag_len = strnlen(tag, len - 1);
    }
    return __android_log_is_loggable_len(prio, tag, tag_len, ANDROID_LOG_VERBOSE);
}

int SerializedLogBuffer::Log(log_id_t log_id, log_time realtime, uid_t uid, pid_t pid, pid_t tid,
                             const char* msg, uint16_t len) {
    if (log_id >= LOG_ID_MAX || len == 0) {
        return -EINVAL;
    }

    if (len > LOGGER_ENTRY_MAX_PAYLOAD) {
        len = LOGGER_ENTRY_MAX_PAYLOAD;
    }

    if (!ShouldLog(log_id, msg, len)) {
        stats_->AddTotal(log_id, len);
        return -EACCES;
    }

    auto sequence = sequence_.fetch_add(1, std::memory_order_relaxed);

    auto lock = std::lock_guard{logd_lock};
    auto entry = LogToLogBuffer(logs_[log_id], max_size_[log_id], sequence, realtime, uid, pid, tid,
                                msg, len);
    stats_->Add(entry->ToLogStatisticsElement(log_id));

    MaybePrune(log_id);

    reader_list_->NotifyNewLog(1 << log_id);
    return len;
}

void SerializedLogBuffer::MaybePrune(log_id_t log_id) {
    size_t total_size = GetSizeUsed(log_id);
    size_t after_size = total_size;
    if (total_size > max_size_[log_id]) {
        Prune(log_id, total_size - max_size_[log_id]);
        after_size = GetSizeUsed(log_id);
        LOG(VERBOSE) << "Pruned Logs from log_id: " << log_id << ", previous size: " << total_size
                     << " after size: " << after_size;
    }

    stats_->set_overhead(log_id, after_size);
}

void SerializedLogBuffer::RemoveChunkFromStats(log_id_t log_id, SerializedLogChunk& chunk) {
    chunk.IncReaderRefCount();
    for (const auto& entry : chunk) {
        stats_->Subtract(entry.ToLogStatisticsElement(log_id));
    }
    chunk.DecReaderRefCount();
}

void SerializedLogBuffer::Prune(log_id_t log_id, size_t bytes_to_free) {
    auto& log_buffer = logs_[log_id];
    auto it = log_buffer.begin();
    while (it != log_buffer.end()) {
        for (const auto& reader_thread : reader_list_->running_reader_threads()) {
            if (!reader_thread->IsWatching(log_id)) {
                continue;
            }

            if (reader_thread->deadline().time_since_epoch().count() != 0) {
                // Always wake up wrapped readers when pruning.  'Wrapped' readers are an
                // optimization that allows the reader to wait until logs starting at a specified
                // time stamp are about to be pruned.  This is error-prone however, since if that
                // timestamp is about to be pruned, the reader is not likely to read the messages
                // fast enough to not back-up logd.  Instead, we can achieve an nearly-as-efficient
                // but not error-prune batching effect by waking the reader whenever any chunk is
                // about to be pruned.
                reader_thread->TriggerReader();
            }

            // Some readers may be still reading from this log chunk, log a warning that they are
            // about to lose logs.
            // TODO: We should forcefully disconnect the reader instead, such that the reader itself
            // has an indication that they've lost logs.
            if (reader_thread->start() <= it->highest_sequence_number()) {
                LOG(WARNING) << "Skipping entries from slow reader, " << reader_thread->name()
                             << ", from LogBuffer::Prune()";
            }
        }

        // Increment ahead of time since we're going to erase this iterator from the list.
        auto it_to_prune = it++;

        // Readers may have a reference to the chunk to track their last read log_position.
        // Notify them to delete the reference.
        it_to_prune->NotifyReadersOfPrune(log_id);

        size_t buffer_size = it_to_prune->PruneSize();
        RemoveChunkFromStats(log_id, *it_to_prune);
        log_buffer.erase(it_to_prune);
        if (buffer_size >= bytes_to_free) {
            return;
        }
        bytes_to_free -= buffer_size;
    }
}

void SerializedLogBuffer::UidClear(log_id_t log_id, uid_t uid) {
    // Wake all readers; see comment in Prune().
    for (const auto& reader_thread : reader_list_->running_reader_threads()) {
        if (!reader_thread->IsWatching(log_id)) {
            continue;
        }

        if (reader_thread->deadline().time_since_epoch().count() != 0) {
            reader_thread->TriggerReader();
        }
    }
    ClearLogsByUid(logs_[log_id], uid, max_size_[log_id], log_id, stats_);
}

std::unique_ptr<FlushToState> SerializedLogBuffer::CreateFlushToState(uint64_t start,
                                                                      LogMask log_mask) {
    return std::make_unique<SerializedFlushToState>(start, log_mask, logs_);
}

bool SerializedLogBuffer::FlushTo(
        LogWriter* writer, FlushToState& abstract_state,
        const std::function<FilterResult(log_id_t log_id, pid_t pid, uint64_t sequence,
                                         log_time realtime)>& filter) {
    auto& state = reinterpret_cast<SerializedFlushToState&>(abstract_state);

    while (state.HasUnreadLogs()) {
        LogWithId top = state.PopNextUnreadLog();
        auto* entry = top.entry;
        auto log_id = top.log_id;

        if (entry->sequence() < state.start()) {
            continue;
        }
        state.set_start(entry->sequence());

        if (!writer->privileged() && entry->uid() != writer->uid()) {
            continue;
        }

        if (filter) {
            auto ret = filter(log_id, entry->pid(), entry->sequence(), entry->realtime());
            if (ret == FilterResult::kSkip) {
                continue;
            }
            if (ret == FilterResult::kStop) {
                break;
            }
        }

        // We copy the log entry such that we can flush it without the lock.  We never block pruning
        // waiting for this Flush() to complete.
        constexpr size_t kMaxEntrySize = sizeof(*entry) + LOGGER_ENTRY_MAX_PAYLOAD + 1;
        unsigned char entry_copy[kMaxEntrySize] __attribute__((uninitialized));
        CHECK_LT(entry->msg_len(), LOGGER_ENTRY_MAX_PAYLOAD + 1);
        memcpy(entry_copy, entry, sizeof(*entry) + entry->msg_len());
        logd_lock.unlock();

        if (!reinterpret_cast<SerializedLogEntry*>(entry_copy)->Flush(writer, log_id)) {
            logd_lock.lock();
            return false;
        }

        logd_lock.lock();
    }

    state.set_start(state.start() + 1);
    return true;
}

bool SerializedLogBuffer::Clear(log_id_t id, uid_t uid) {
    auto lock = std::lock_guard{logd_lock};
    if (uid == 0) {
        Prune(id, ULONG_MAX);
    } else {
        UidClear(id, uid);
    }

    // Clearing SerializedLogBuffer never waits for readers and therefore is always successful.
    return true;
}

size_t SerializedLogBuffer::GetSizeUsed(log_id_t id) {
    size_t total_size = 0;
    for (const auto& chunk : logs_[id]) {
        total_size += chunk.PruneSize();
    }
    return total_size;
}

size_t SerializedLogBuffer::GetSize(log_id_t id) {
    auto lock = std::lock_guard{logd_lock};
    return max_size_[id];
}

// New SerializedLogChunk objects will be allocated according to the new size, but older one are
// unchanged.  MaybePrune() is called on the log buffer to reduce it to an appropriate size if the
// new size is lower.
bool SerializedLogBuffer::SetSize(log_id_t id, size_t size) {
    // Reasonable limits ...
    if (!IsValidBufferSize(size)) {
        return false;
    }

    auto lock = std::lock_guard{logd_lock};
    max_size_[id] = size;

    MaybePrune(id);

    return true;
}
