/*
 * Copyright (C) 2012-2014 The Android Open Source Project
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

#include "LogBufferElement.h"

#include <ctype.h>
#include <endian.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#include <log/log_read.h>
#include <private/android_logger.h>

#include "LogStatistics.h"
#include "LogUtils.h"

LogBufferElement::LogBufferElement(log_id_t log_id, log_time realtime, uid_t uid, pid_t pid,
                                   pid_t tid, uint64_t sequence, const char* msg, uint16_t len)
    : uid_(uid),
      pid_(pid),
      tid_(tid),
      sequence_(sequence),
      realtime_(realtime),
      msg_len_(len),
      log_id_(log_id) {
    msg_ = new char[len];
    memcpy(msg_, msg, len);
}

LogBufferElement::LogBufferElement(const LogBufferElement& elem)
    : uid_(elem.uid_),
      pid_(elem.pid_),
      tid_(elem.tid_),
      sequence_(elem.sequence_),
      realtime_(elem.realtime_),
      msg_len_(elem.msg_len_),
      log_id_(elem.log_id_) {
    msg_ = new char[msg_len_];
    memcpy(msg_, elem.msg_, msg_len_);
}

LogBufferElement::LogBufferElement(LogBufferElement&& elem) noexcept
    : uid_(elem.uid_),
      pid_(elem.pid_),
      tid_(elem.tid_),
      sequence_(elem.sequence_),
      realtime_(elem.realtime_),
      msg_len_(elem.msg_len_),
      log_id_(elem.log_id_) {
    msg_ = elem.msg_;
    elem.msg_ = nullptr;
}

LogBufferElement::~LogBufferElement() {
    delete[] msg_;
}

uint32_t LogBufferElement::GetTag() const {
    // Binary buffers have no tag.
    if (!IsBinary(log_id())) {
        return 0;
    }
    return MsgToTag(msg(), msg_len());
}

LogStatisticsElement LogBufferElement::ToLogStatisticsElement() const {
    // Estimate the size of this element in the parent std::list<> by adding two void*'s
    // corresponding to the next/prev pointers and aligning to 64 bit.
    uint16_t element_in_list_size =
            (sizeof(*this) + 2 * sizeof(void*) + sizeof(uint64_t) - 1) & -sizeof(uint64_t);
    return LogStatisticsElement{
            .uid = uid(),
            .pid = pid(),
            .tid = tid(),
            .tag = GetTag(),
            .realtime = realtime(),
            .msg = msg(),
            .msg_len = msg_len(),
            .log_id = log_id(),
            .total_len = static_cast<uint16_t>(element_in_list_size + msg_len()),
    };
}

// caller must own and free character string
char* android::tidToName(pid_t tid) {
    char* retval = nullptr;
    char buffer[256];
    snprintf(buffer, sizeof(buffer), "/proc/%u/comm", tid);
    int fd = open(buffer, O_RDONLY | O_CLOEXEC);
    if (fd >= 0) {
        ssize_t ret = read(fd, buffer, sizeof(buffer));
        if (ret >= (ssize_t)sizeof(buffer)) {
            ret = sizeof(buffer) - 1;
        }
        while ((ret > 0) && isspace(buffer[ret - 1])) {
            --ret;
        }
        if (ret > 0) {
            buffer[ret] = '\0';
            retval = strdup(buffer);
        }
        close(fd);
    }

    // if nothing for comm, check out cmdline
    char* name = android::pidToName(tid);
    if (!retval) {
        retval = name;
        name = nullptr;
    }

    // check if comm is truncated, see if cmdline has full representation
    if (name) {
        // impossible for retval to be NULL if name not NULL
        size_t retval_len = strlen(retval);
        size_t name_len = strlen(name);
        // KISS: ToDo: Only checks prefix truncated, not suffix, or both
        if ((retval_len < name_len) &&
            !fastcmp<strcmp>(retval, name + name_len - retval_len)) {
            free(retval);
            retval = name;
        } else {
            free(name);
        }
    }
    return retval;
}

bool LogBufferElement::FlushTo(LogWriter* writer) {
    struct logger_entry entry = {};

    entry.hdr_size = sizeof(struct logger_entry);
    entry.lid = log_id_;
    entry.pid = pid_;
    entry.tid = tid_;
    entry.uid = uid_;
    entry.sec = realtime_.tv_sec;
    entry.nsec = realtime_.tv_nsec;
    entry.len = msg_len_;

    return writer->Write(entry, msg_);
}
