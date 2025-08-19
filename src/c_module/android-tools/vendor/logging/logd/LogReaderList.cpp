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

#include "LogReaderList.h"

#include <android-base/logging.h>
#include <android/os/logcat/ILogcatManagerService.h>
#include <binder/IServiceManager.h>

using android::defaultServiceManager;
using android::sp;
using android::String16;
using android::os::logcat::ILogcatManagerService;

static sp<ILogcatManagerService> InitLogcatService() {
    return android::interface_cast<ILogcatManagerService>(
            defaultServiceManager()->waitForService(String16("logcat")));
}

static sp<ILogcatManagerService> GetLogcatService() {
    static sp<ILogcatManagerService> logcat_service = InitLogcatService();

    if (logcat_service == nullptr) {
        LOG(ERROR) << "Permission problem or fatal error occurs to get logcat service";
    }
    return logcat_service;
}

// When we are notified a new log entry is available, inform
// listening sockets who are watching this entry's log id.
void LogReaderList::NotifyNewLog(LogMask log_mask) const {
    for (const auto& entry : running_reader_threads_) {
        if (!entry->IsWatchingMultiple(log_mask)) {
            continue;
        }
        if (entry->deadline().time_since_epoch().count() != 0) {
            continue;
        }
        entry->TriggerReader();
    }
}

bool LogReaderList::HandlePendingThread(uid_t uid, gid_t gid, pid_t pid, int32_t fd, bool approve) {
    auto lock = std::lock_guard{logd_lock};
    PendingReaderThreadKey key = {
            .uid = uid,
            .gid = gid,
            .pid = pid,
            .fd = fd,
    };
    auto iter = std::find_if(pending_reader_threads_.begin(), pending_reader_threads_.end(),
                             [&key](const auto& other) REQUIRES(logd_lock) {
                                 return other->pending_reader_thread_key() == key;
                             });
    if (iter == pending_reader_threads_.end()) {
        return false;
    }

    auto entry = std::move(*iter);
    pending_reader_threads_.erase(iter);
    if (!approve) {
        entry->Revoke();
    } else {
        entry->set_track_flag();
    }
    AddAndRunThread(std::move(entry));
    return true;
}

void LogReaderList::AddAndRunThread(std::unique_ptr<LogReaderThread> thread) {
    thread->Run();
    running_reader_threads_.emplace_front(std::move(thread));
}

void LogReaderList::RemoveRunningThread(LogReaderThread* thread) {
    auto iter = std::find_if(running_reader_threads_.begin(), running_reader_threads_.end(),
                             [thread](const auto& other)
                                     REQUIRES(logd_lock) { return other.get() == thread; });
    if (iter == running_reader_threads_.end()) {
        return;
    }

    // If the track_flag is false, we don't need to notify LogcatManagerService.
    // All the native processes are in this category, so we can remove the
    // dependency on system_server for the native processes.
    if (!thread->track_flag()) {
        running_reader_threads_.erase(iter);
        return;
    }

    auto service = GetLogcatService();
    if (service != nullptr) {
        const PendingReaderThreadKey key = thread->pending_reader_thread_key();
        service->finishThread(key.uid, key.gid, key.pid, key.fd);
    }
    running_reader_threads_.erase(iter);
}

void LogReaderList::AddPendingThread(std::unique_ptr<LogReaderThread> thread) {
    auto service = GetLogcatService();

    // If the logcat binder service is not available, we will be not able to
    // check the user consent. So we revoke the privileges.
    if (service == nullptr) {
        thread->Revoke();
        AddAndRunThread(std::move(thread));
        return;
    }

    const PendingReaderThreadKey key = thread->pending_reader_thread_key();
    service->startThread(key.uid, key.gid, key.pid, key.fd);
    pending_reader_threads_.emplace_back(std::move(thread));
}

bool LogReaderList::ReleaseThreadByName(const std::string& cli_name) REQUIRES(logd_lock) {
    for (const auto& reader : running_reader_threads_) {
        if (reader->name() == cli_name) {
            reader->Release();
            return true;
        }
    }

    for (const auto& reader : pending_reader_threads_) {
        if (reader->name() == cli_name) {
            reader->Release();
            return true;
        }
    }
    return false;
}
