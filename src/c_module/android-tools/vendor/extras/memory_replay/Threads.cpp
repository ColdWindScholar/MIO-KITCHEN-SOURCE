/*
 * Copyright (C) 2015 The Android Open Source Project
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

#include <err.h>
#include <errno.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#include <new>

#include "Alloc.h"
#include "Pointers.h"
#include "Thread.h"
#include "Threads.h"

void* ThreadRunner(void* data) {
  Thread* thread = reinterpret_cast<Thread*>(data);
  while (true) {
    thread->WaitForPending();
    const AllocEntry& entry = thread->GetAllocEntry();
    thread->AddTimeNsecs(AllocExecute(entry, thread->pointers()));
    bool thread_done = entry.type == THREAD_DONE;
    thread->ClearPending();
    if (thread_done) {
      break;
    }
  }
  return nullptr;
}

Threads::Threads(Pointers* pointers, size_t max_threads)
    : pointers_(pointers), max_threads_(max_threads) {
  size_t pagesize = getpagesize();
  data_size_ = (max_threads_ * sizeof(Thread) + pagesize - 1) & ~(pagesize - 1);
  max_threads_ = data_size_ / sizeof(Thread);

  void* memory = mmap(nullptr, data_size_, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANON, -1, 0);
  if (memory == MAP_FAILED) {
    err(1, "Failed to map in memory for Threads: map size %zu, max threads %zu", data_size_,
        max_threads_);
  }

  threads_ = new (memory) Thread[max_threads_];
}

Threads::~Threads() {
  if (threads_) {
    munmap(threads_, data_size_);
    threads_ = nullptr;
    data_size_ = 0;
  }
}

Thread* Threads::CreateThread(pid_t tid) {
  if (num_threads_ == max_threads_) {
    errx(1, "Too many threads created, current max %zu", num_threads_);
  }
  Thread* thread = FindEmptyEntry(tid);
  if (thread == nullptr) {
    errx(1, "No empty entries found, current max %zu, num threads %zu", max_threads_, num_threads_);
  }
  thread->tid_ = tid;
  thread->pointers_ = pointers_;
  thread->total_time_nsecs_ = 0;
  if ((errno = pthread_create(&thread->thread_id_, nullptr, ThreadRunner, thread)) != 0) {
    err(1, "Failed to create thread %d", tid);
  }

  num_threads_++;
  return thread;
}

Thread* Threads::FindThread(pid_t tid) {
  size_t index = GetHashEntry(tid);
  for (size_t entries = num_threads_; entries != 0; ) {
    pid_t cur_tid = threads_[index].tid_;
    if (cur_tid == tid) {
      return threads_ + index;
    }
    if (cur_tid != 0) {
      entries--;
    }
    if (++index == max_threads_) {
      index = 0;
    }
  }
  return nullptr;
}

void Threads::WaitForAllToQuiesce() {
  for (size_t i = 0, threads = 0; threads < num_threads_; i++) {
    pid_t cur_tid = threads_[i].tid_;
    if (cur_tid != 0) {
      threads++;
      threads_[i].WaitForReady();
    }
  }
}

size_t Threads::GetHashEntry(pid_t tid) {
  return tid % max_threads_;
}

Thread* Threads::FindEmptyEntry(pid_t tid) {
  size_t index = GetHashEntry(tid);
  for (size_t entries = 0; entries < max_threads_; entries++) {
    if (threads_[index].tid_ == 0) {
      return threads_ + index;
    }
    if (++index == max_threads_) {
      index = 0;
    }
  }
  return nullptr;
}

void Threads::Finish(Thread* thread) {
  int ret = pthread_join(thread->thread_id_, nullptr);
  if (ret != 0) {
    err(1, "pthread_join failed");
  }
  total_time_nsecs_ += thread->total_time_nsecs_;
  thread->tid_ = 0;
  num_threads_--;
}

void Threads::FinishAll() {
  AllocEntry thread_done = {.type = THREAD_DONE};
  for (size_t i = 0; i < max_threads_; i++) {
    if (threads_[i].tid_ != 0) {
      threads_[i].SetAllocEntry(&thread_done);
      threads_[i].SetPending();
      Finish(threads_ + i);
    }
  }
}
