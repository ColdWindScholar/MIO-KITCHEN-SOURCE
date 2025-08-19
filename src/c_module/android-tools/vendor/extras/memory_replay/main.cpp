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
#include <fcntl.h>
#include <inttypes.h>
#include <malloc.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#include "Alloc.h"
#include "File.h"
#include "NativeInfo.h"
#include "Pointers.h"
#include "Thread.h"
#include "Threads.h"

#include <log/log.h>
#include <log/log_read.h>

constexpr size_t kDefaultMaxThreads = 512;

static size_t GetMaxAllocs(const AllocEntry* entries, size_t num_entries) {
  size_t max_allocs = 0;
  size_t num_allocs = 0;
  for (size_t i = 0; i < num_entries; i++) {
    switch (entries[i].type) {
      case THREAD_DONE:
        break;
      case MALLOC:
      case CALLOC:
      case MEMALIGN:
        if (entries[i].ptr != 0) {
          num_allocs++;
        }
        break;
      case REALLOC:
        if (entries[i].ptr == 0 && entries[i].u.old_ptr != 0) {
          num_allocs--;
        } else if (entries[i].ptr != 0 && entries[i].u.old_ptr == 0) {
          num_allocs++;
        }
        break;
      case FREE:
        if (entries[i].ptr != 0) {
          num_allocs--;
        }
        break;
    }
    if (num_allocs > max_allocs) {
      max_allocs = num_allocs;
    }
  }
  return max_allocs;
}

static void PrintLogStats(const char* log_name) {
  logger_list* list =
      android_logger_list_open(android_name_to_log_id(log_name), ANDROID_LOG_NONBLOCK, 0, getpid());
  if (list == nullptr) {
    printf("Failed to open log for %s\n", log_name);
    return;
  }
  while (true) {
    log_msg entry;
    ssize_t retval = android_logger_list_read(list, &entry);
    if (retval == 0) {
      break;
    }
    if (retval < 0) {
      if (retval == -EINTR) {
        continue;
      }
      // EAGAIN means there is nothing left to read when ANDROID_LOG_NONBLOCK is set.
      if (retval != -EAGAIN) {
        printf("Failed to read log entry: %s\n", strerrordesc_np(retval));
      }
      break;
    }
    if (entry.msg() == nullptr) {
      continue;
    }
    // Only print allocator tagged log entries.
    std::string_view tag(entry.msg() + 1);
    if (tag != "scudo" && tag != "jemalloc") {
      continue;
    }
    printf("%s\n", &tag.back() + 2);
  }
  android_logger_list_close(list);
}

static void ProcessDump(const AllocEntry* entries, size_t num_entries, size_t max_threads) {
  // Do a pass to get the maximum number of allocations used at one
  // time to allow a single mmap that can hold the maximum number of
  // pointers needed at once.
  size_t max_allocs = GetMaxAllocs(entries, num_entries);
  Pointers pointers(max_allocs);
  Threads threads(&pointers, max_threads);

  dprintf(STDOUT_FILENO, "Maximum threads available:   %zu\n", threads.max_threads());
  dprintf(STDOUT_FILENO, "Maximum allocations in dump: %zu\n", max_allocs);
  dprintf(STDOUT_FILENO, "Total pointers available:    %zu\n\n", pointers.max_pointers());

  NativePrintInfo("Initial ");

  for (size_t i = 0; i < num_entries; i++) {
    if (((i + 1) % 100000) == 0) {
      dprintf(STDOUT_FILENO, "  At line %zu:\n", i + 1);
      NativePrintInfo("    ");
    }
    const AllocEntry& entry = entries[i];
    Thread* thread = threads.FindThread(entry.tid);
    if (thread == nullptr) {
      thread = threads.CreateThread(entry.tid);
    }

    // Wait for the thread to complete any previous actions before handling
    // the next action.
    thread->WaitForReady();

    thread->SetAllocEntry(&entry);

    bool does_free = AllocDoesFree(entry);
    if (does_free) {
      // Make sure that any other threads doing allocations are complete
      // before triggering the action. Otherwise, another thread could
      // be creating the allocation we are going to free.
      threads.WaitForAllToQuiesce();
    }

    // Tell the thread to execute the action.
    thread->SetPending();

    if (entries[i].type == THREAD_DONE) {
      // Wait for the thread to finish and clear the thread entry.
      threads.Finish(thread);
    }

    // Wait for this action to complete. This avoids a race where
    // another thread could be creating the same allocation where are
    // trying to free.
    if (does_free) {
      thread->WaitForReady();
    }
  }
  // Wait for all threads to stop processing actions.
  threads.WaitForAllToQuiesce();

  NativePrintInfo("Final ");

  // Free any outstanding pointers.
  // This allows us to run a tool like valgrind to verify that no memory
  // is leaked and everything is accounted for during a run.
  threads.FinishAll();
  pointers.FreeAll();

  // Print out the total time making all allocation calls.
  char buffer[256];
  uint64_t total_nsecs = threads.total_time_nsecs();
  NativeFormatFloat(buffer, sizeof(buffer), total_nsecs, 1000000000);
  dprintf(STDOUT_FILENO, "Total Allocation/Free Time: %" PRIu64 "ns %ss\n", total_nsecs, buffer);

  // Send native allocator stats to the log
  mallopt(M_LOG_STATS, 0);

  // No need to avoid allocations at this point since all stats have been sent to the log.
  printf("Native Allocator Stats:\n");
  PrintLogStats("system");
  PrintLogStats("main");
}

int main(int argc, char** argv) {
  if (argc != 2 && argc != 3) {
    if (argc > 3) {
      fprintf(stderr, "Only two arguments are expected.\n");
    } else {
      fprintf(stderr, "Requires at least one argument.\n");
    }
    fprintf(stderr, "Usage: %s MEMORY_LOG_FILE [MAX_THREADS]\n", basename(argv[0]));
    fprintf(stderr, "  MEMORY_LOG_FILE\n");
    fprintf(stderr, "    This can either be a text file or a zipped text file.\n");
    fprintf(stderr, "  MAX_THREADs\n");
    fprintf(stderr, "    The maximum number of threads in the trace. The default is %zu.\n",
            kDefaultMaxThreads);
    fprintf(stderr, "    This pre-allocates the memory for thread data to avoid allocating\n");
    fprintf(stderr, "    while the trace is being replayed.\n");
    return 1;
  }

#if defined(__LP64__)
  dprintf(STDOUT_FILENO, "64 bit environment.\n");
#else
  dprintf(STDOUT_FILENO, "32 bit environment.\n");
#endif

#if defined(__BIONIC__)
  dprintf(STDOUT_FILENO, "Setting decay time to 1\n");
  mallopt(M_DECAY_TIME, 1);
#endif

  size_t max_threads = kDefaultMaxThreads;
  if (argc == 3) {
    max_threads = atoi(argv[2]);
  }

  AllocEntry* entries;
  size_t num_entries;
  GetUnwindInfo(argv[1], &entries, &num_entries);

  dprintf(STDOUT_FILENO, "Processing: %s\n", argv[1]);

  ProcessDump(entries, num_entries, max_threads);

  FreeEntries(entries, num_entries);

  return 0;
}
