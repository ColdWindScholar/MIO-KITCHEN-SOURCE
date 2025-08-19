/*
 * Copyright (C) 2016 The Android Open Source Project
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

#include "IOEventLoop.h"

#include <event2/event.h>
#include <fcntl.h>

#include <android-base/logging.h>

namespace simpleperf {

struct IOEvent {
  IOEventLoop* loop;
  event* e;
  timeval timeout;
  std::function<bool()> callback;
  bool enabled;

  IOEvent(IOEventLoop* loop, const std::function<bool()>& callback)
      : loop(loop), e(nullptr), timeout({}), callback(callback), enabled(false) {}

  ~IOEvent() {
    if (e != nullptr) {
      event_free(e);
    }
  }
};

IOEventLoop::IOEventLoop() : ebase_(nullptr), has_error_(false), in_loop_(false) {}

IOEventLoop::~IOEventLoop() {
  events_.clear();
  if (ebase_ != nullptr) {
    event_base_free(ebase_);
  }
}

bool IOEventLoop::EnsureInit() {
  if (ebase_ == nullptr) {
    event_config* cfg = event_config_new();
    if (cfg != nullptr) {
      event_config_set_flag(cfg, EVENT_BASE_FLAG_PRECISE_TIMER);
      if (event_config_avoid_method(cfg, "epoll") != 0) {
        LOG(ERROR) << "event_config_avoid_method";
        return false;
      }
      ebase_ = event_base_new_with_config(cfg);
      // perf event files support reporting available data via poll methods. However, it doesn't
      // work well with epoll. Because perf_poll() in kernel/events/core.c uses a report and reset
      // way to report poll events. If perf_poll() is called twice, it may return POLLIN for the
      // first time, and no events for the second time. And epoll may call perf_poll() more than
      // once to confirm events. A failed situation is below:
      // When profiling SimpleperfExampleOfKotlin on Pixel device with `-g --duration 10`, the
      // kernel fills up the buffer before we call epoll_ctl(EPOLL_CTL_ADD). Then the POLLIN event
      // is returned when calling epoll_ctl(), while no events are returned when calling
      // epoll_wait(). As a result, simpleperf doesn't receive any poll wakeup events.
      if (strcmp(event_base_get_method(ebase_), "poll") != 0) {
        LOG(ERROR) << "event_base_get_method isn't poll: " << event_base_get_method(ebase_);
        return false;
      }
      event_config_free(cfg);
      if (event_base_priority_init(ebase_, 2) != 0) {
        LOG(ERROR) << "event_base_priority_init failed";
        return false;
      }
    }
    if (ebase_ == nullptr) {
      LOG(ERROR) << "failed to create event_base";
      return false;
    }
  }
  return true;
}

void IOEventLoop::EventCallbackFn(int, int16_t, void* arg) {
  IOEvent* e = static_cast<IOEvent*>(arg);
  if (!e->callback()) {
    e->loop->has_error_ = true;
    e->loop->ExitLoop();
  }
}

static bool MakeFdNonBlocking(int fd) {
  int flags = fcntl(fd, F_GETFL, 0);
  if (flags == -1 || fcntl(fd, F_SETFL, flags | O_NONBLOCK) == -1) {
    PLOG(ERROR) << "fcntl() failed";
    return false;
  }
  return true;
}

IOEventRef IOEventLoop::AddReadEvent(int fd, const std::function<bool()>& callback,
                                     IOEventPriority priority) {
  if (!MakeFdNonBlocking(fd)) {
    return nullptr;
  }
  return AddEvent(fd, EV_READ | EV_PERSIST, nullptr, callback, priority);
}

IOEventRef IOEventLoop::AddWriteEvent(int fd, const std::function<bool()>& callback,
                                      IOEventPriority priority) {
  if (!MakeFdNonBlocking(fd)) {
    return nullptr;
  }
  return AddEvent(fd, EV_WRITE | EV_PERSIST, nullptr, callback, priority);
}

bool IOEventLoop::AddSignalEvent(int sig, const std::function<bool()>& callback,
                                 IOEventPriority priority) {
  return AddEvent(sig, EV_SIGNAL | EV_PERSIST, nullptr, callback, priority) != nullptr;
}

bool IOEventLoop::AddSignalEvents(std::vector<int> sigs, const std::function<bool()>& callback,
                                  IOEventPriority priority) {
  for (auto sig : sigs) {
    if (!AddSignalEvent(sig, callback, priority)) {
      return false;
    }
  }
  return true;
}

IOEventRef IOEventLoop::AddPeriodicEvent(timeval duration, const std::function<bool()>& callback,
                                         IOEventPriority priority) {
  return AddEvent(-1, EV_PERSIST, &duration, callback, priority);
}

IOEventRef IOEventLoop::AddOneTimeEvent(timeval duration, const std::function<bool()>& callback,
                                        IOEventPriority priority) {
  return AddEvent(-1, 0, &duration, callback, priority);
}

IOEventRef IOEventLoop::AddEvent(int fd_or_sig, int16_t events, timeval* timeout,
                                 const std::function<bool()>& callback, IOEventPriority priority) {
  if (!EnsureInit()) {
    return nullptr;
  }
  std::unique_ptr<IOEvent> e(new IOEvent(this, callback));
  e->e = event_new(ebase_, fd_or_sig, events, EventCallbackFn, e.get());
  if (e->e == nullptr) {
    LOG(ERROR) << "event_new() failed";
    return nullptr;
  }
  event_priority_set(e->e, priority);
  if (event_add(e->e, timeout) != 0) {
    LOG(ERROR) << "event_add() failed";
    return nullptr;
  }
  if (timeout != nullptr) {
    e->timeout = *timeout;
  }
  e->enabled = true;
  events_.push_back(std::move(e));
  return events_.back().get();
}

bool IOEventLoop::RunLoop() {
  in_loop_ = true;
  if (event_base_dispatch(ebase_) == -1) {
    LOG(ERROR) << "event_base_dispatch() failed";
    in_loop_ = false;
    return false;
  }
  if (has_error_) {
    return false;
  }
  return true;
}

bool IOEventLoop::ExitLoop() {
  if (in_loop_) {
    if (event_base_loopbreak(ebase_) == -1) {
      LOG(ERROR) << "event_base_loopbreak() failed";
      return false;
    }
    in_loop_ = false;
  }
  return true;
}

bool IOEventLoop::DisableEvent(IOEventRef ref) {
  if (ref->enabled) {
    if (event_del(ref->e) != 0) {
      LOG(ERROR) << "event_del() failed";
      return false;
    }
    ref->enabled = false;
  }
  return true;
}

bool IOEventLoop::EnableEvent(IOEventRef ref) {
  if (!ref->enabled) {
    timeval* timeout =
        (ref->timeout.tv_sec != 0 || ref->timeout.tv_usec != 0) ? &ref->timeout : nullptr;
    if (event_add(ref->e, timeout) != 0) {
      LOG(ERROR) << "event_add() failed";
      return false;
    }
    ref->enabled = true;
  }
  return true;
}

bool IOEventLoop::DelEvent(IOEventRef ref) {
  DisableEvent(ref);
  IOEventLoop* loop = ref->loop;
  for (auto it = loop->events_.begin(); it != loop->events_.end(); ++it) {
    if (it->get() == ref) {
      loop->events_.erase(it);
      break;
    }
  }
  return true;
}

}  // namespace simpleperf
