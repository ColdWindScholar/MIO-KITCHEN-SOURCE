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

#pragma once

#include <list>
#include <memory>
#include <vector>

#include "LogBuffer.h"
#include "LogReaderThread.h"
#include "LogdLock.h"

class LogReaderList {
  public:
    void NotifyNewLog(LogMask log_mask) const REQUIRES(logd_lock);

    void AddAndRunThread(std::unique_ptr<LogReaderThread> thread) REQUIRES(logd_lock);
    void RemoveRunningThread(LogReaderThread* thread) REQUIRES(logd_lock);
    void AddPendingThread(std::unique_ptr<LogReaderThread> thread) REQUIRES(logd_lock);
    bool HandlePendingThread(uid_t uid, gid_t gid, pid_t pid, int32_t fd, bool approve);
    bool ReleaseThreadByName(const std::string& cli_name) REQUIRES(logd_lock);

    const std::list<std::unique_ptr<LogReaderThread>>& running_reader_threads() const
            REQUIRES(logd_lock) {
        return running_reader_threads_;
    }

  private:
    std::list<std::unique_ptr<LogReaderThread>> running_reader_threads_ GUARDED_BY(logd_lock);
    std::vector<std::unique_ptr<LogReaderThread>> pending_reader_threads_ GUARDED_BY(logd_lock);
};
