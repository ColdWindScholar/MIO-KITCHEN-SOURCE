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

#pragma once

#include <private/android_logger.h>
#include <sysutils/SocketListener.h>

#include "LogBuffer.h"
#include "LogStatistics.h"

/* Use SocketListener because it provides reader thread management and
 * works well with the Trusty log device due to using poll() and not
 * relying on blocking reads, which the Trusty log device does not support.
 */
class TrustyLog : public SocketListener {
    LogBuffer* logbuf;
    void LogMsg(const char* msg, size_t len);

  public:
    static void create(LogBuffer* buf);

  protected:
    virtual bool onDataAvailable(SocketClient* cli);
    TrustyLog(LogBuffer* buf, int fdRead);
};
