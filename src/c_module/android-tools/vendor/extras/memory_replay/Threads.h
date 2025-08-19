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

#include <stdint.h>
#include <sys/types.h>

// Forward Declarations.
class Pointers;
class Thread;

class Threads {
 public:
  Threads(Pointers* pointers, size_t max_threads);
  virtual ~Threads();

  Thread* CreateThread(pid_t tid);
  Thread* FindThread(pid_t tid);
  void WaitForAllToQuiesce();
  void Finish(Thread* thread);
  void FinishAll();

  size_t num_threads() { return num_threads_; }
  size_t max_threads() { return max_threads_; }
  uint64_t total_time_nsecs() { return total_time_nsecs_; }

 private:
  Pointers* pointers_ = nullptr;
  Thread* threads_ = nullptr;
  size_t data_size_ = 0;
  size_t max_threads_ = 0;
  size_t num_threads_= 0;
  uint64_t total_time_nsecs_ = 0;

  Thread* FindEmptyEntry(pid_t tid);
  size_t GetHashEntry(pid_t tid);

  void ClearData();

  friend Thread;
};
