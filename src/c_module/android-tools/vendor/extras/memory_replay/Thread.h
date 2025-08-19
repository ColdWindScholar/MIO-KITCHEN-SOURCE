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

#pragma once

#include <pthread.h>
#include <stdint.h>
#include <sys/types.h>

// Forward Declarations.
struct AllocEntry;
class Pointers;

class Thread {
 public:
  Thread();
  virtual ~Thread();

  void WaitForReady();
  void WaitForPending();
  void SetPending();
  void ClearPending();

  void AddTimeNsecs(uint64_t nsecs) { total_time_nsecs_ += nsecs; }

  void set_pointers(Pointers* pointers) { pointers_ = pointers; }
  Pointers* pointers() { return pointers_; }

  void SetAllocEntry(const AllocEntry* entry) { entry_ = entry; }
  const AllocEntry& GetAllocEntry() { return *entry_; }

 private:
  pthread_mutex_t mutex_ = PTHREAD_MUTEX_INITIALIZER;
  pthread_cond_t cond_;
  bool pending_ = false;

  pthread_t thread_id_;
  pid_t tid_ = 0;
  uint64_t total_time_nsecs_ = 0;

  Pointers* pointers_ = nullptr;

  const AllocEntry* entry_;

  friend class Threads;
};
