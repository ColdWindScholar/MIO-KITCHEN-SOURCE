/*
 * Copyright (C) 2019 The Android Open Source Project
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

#include <malloc.h>
#include <stdint.h>
#include <stdio.h>
#include <unistd.h>

#include "Alloc.h"
#include "AllocParser.h"
#include "Pointers.h"
#include "Utils.h"

bool AllocDoesFree(const AllocEntry& entry) {
  switch (entry.type) {
    case MALLOC:
    case CALLOC:
    case MEMALIGN:
    case THREAD_DONE:
      return false;

    case FREE:
      return entry.ptr != 0;

    case REALLOC:
      return entry.u.old_ptr != 0;
  }
}

static uint64_t MallocExecute(const AllocEntry& entry, Pointers* pointers) {
  int pagesize = getpagesize();
  uint64_t time_nsecs = Nanotime();
  void* memory = malloc(entry.size);
  MakeAllocationResident(memory, entry.size, pagesize);
  time_nsecs = Nanotime() - time_nsecs;

  pointers->Add(entry.ptr, memory);

  return time_nsecs;
}

static uint64_t CallocExecute(const AllocEntry& entry, Pointers* pointers) {
  int pagesize = getpagesize();
  uint64_t time_nsecs = Nanotime();
  void* memory = calloc(entry.u.n_elements, entry.size);
  MakeAllocationResident(memory, entry.u.n_elements * entry.size, pagesize);
  time_nsecs = Nanotime() - time_nsecs;

  pointers->Add(entry.ptr, memory);

  return time_nsecs;
}

static uint64_t ReallocExecute(const AllocEntry& entry, Pointers* pointers) {
  void* old_memory = nullptr;
  if (entry.u.old_ptr != 0) {
    old_memory = pointers->Remove(entry.u.old_ptr);
  }

  int pagesize = getpagesize();
  uint64_t time_nsecs = Nanotime();
  void* memory = realloc(old_memory, entry.size);
  MakeAllocationResident(memory, entry.size, pagesize);
  time_nsecs = Nanotime() - time_nsecs;

  pointers->Add(entry.ptr, memory);

  return time_nsecs;
}

static uint64_t MemalignExecute(const AllocEntry& entry, Pointers* pointers) {
  int pagesize = getpagesize();
  uint64_t time_nsecs = Nanotime();
  void* memory = memalign(entry.u.align, entry.size);
  MakeAllocationResident(memory, entry.size, pagesize);
  time_nsecs = Nanotime() - time_nsecs;

  pointers->Add(entry.ptr, memory);

  return time_nsecs;
}

static uint64_t FreeExecute(const AllocEntry& entry, Pointers* pointers) {
  if (entry.ptr == 0) {
    return 0;
  }

  void* memory = pointers->Remove(entry.ptr);
  uint64_t time_nsecs = Nanotime();
  free(memory);
  return Nanotime() - time_nsecs;
}

uint64_t AllocExecute(const AllocEntry& entry, Pointers* pointers) {
  switch (entry.type) {
    case MALLOC:
      return MallocExecute(entry, pointers);
    case CALLOC:
      return CallocExecute(entry, pointers);
    case REALLOC:
      return ReallocExecute(entry, pointers);
    case MEMALIGN:
      return MemalignExecute(entry, pointers);
    case FREE:
      return FreeExecute(entry, pointers);
    default:
      return 0;
  }
}
