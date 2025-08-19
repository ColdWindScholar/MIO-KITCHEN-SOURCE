/*
 * Copyright (C) 2023 The Android Open Source Project
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
#include <getopt.h>
#include <stdint.h>
#include <stdio.h>

#include <limits>
#include <string_view>
#include <unordered_map>

#include <android-base/file.h>
#include <android-base/parseint.h>
#include <android-base/strings.h>

#include "AllocParser.h"
#include "File.h"

static std::string GetBaseExec() {
  return android::base::Basename(android::base::GetExecutablePath());
}

static void Usage() {
  fprintf(
      stderr,
      "Usage: %s [--min_size SIZE] [--max_size SIZE] [--print_trace_format] [--help] TRACE_FILE\n",
      GetBaseExec().c_str());
  fprintf(stderr, "  --min_size SIZE\n");
  fprintf(stderr, "      Display all allocations that are greater than or equal to SIZE\n");
  fprintf(stderr, "  --max_size SIZE\n");
  fprintf(stderr, "      Display all allocations that are less than or equal to SIZE\n");
  fprintf(stderr, "  --print_trace_format\n");
  fprintf(stderr, "      Display all allocations from the trace in the trace format\n");
  fprintf(stderr, "  --help\n");
  fprintf(stderr, "      Display this usage message\n");
  fprintf(stderr, "  TRACE_FILE\n");
  fprintf(stderr, "      The name of the trace file to filter\n");
  fprintf(stderr, "\n  Display all of the allocations from the trace file that meet the filter\n");
  fprintf(stderr, "  criteria. By default, without changing the min size or max size, all\n");
  fprintf(stderr, "  allocations in the trace will be printed.\n");
}

static bool ParseOptions(int argc, char** argv, size_t& min_size, size_t& max_size,
                         bool& print_trace_format, std::string_view& trace_file) {
  while (true) {
    option options[] = {
        {"min_size", required_argument, nullptr, 'i'},
        {"max_size", required_argument, nullptr, 'x'},
        {"print_trace_format", no_argument, nullptr, 'p'},
        {"help", no_argument, nullptr, 'h'},
        {nullptr, 0, nullptr, 0},
    };
    int option_index = 0;
    int opt = getopt_long(argc, argv, "", options, &option_index);
    if (opt == -1) {
      break;
    }

    switch (opt) {
      case 'i':
      case 'x':
        size_t value;
        if (!android::base::ParseUint<size_t>(optarg, &value)) {
          fprintf(stderr, "%s: option '--%s' is not valid: %s\n", GetBaseExec().c_str(),
                  options[option_index].name, optarg);
          return false;
        }
        if (opt == 'i') {
          min_size = value;
        } else {
          max_size = value;
        }
        break;
      case 'p':
        print_trace_format = true;
        break;
      case 'h':
      default:
        return false;
    }
  }
  if (optind + 1 != argc) {
    fprintf(stderr, "%s: only allows one argument.\n", GetBaseExec().c_str());
    return false;
  }
  if (min_size > max_size) {
    fprintf(stderr, "%s: min size(%zu) must be less than max size(%zu)\n", GetBaseExec().c_str(),
            min_size, max_size);
    return false;
  }

  trace_file = argv[optind];
  return true;
}

static void PrintEntry(const AllocEntry& entry, size_t size, bool print_trace_format) {
  if (print_trace_format) {
    switch (entry.type) {
      case REALLOC:
        if (entry.u.old_ptr == 0) {
          // Convert to a malloc since it is functionally the same.
          printf("%d: malloc %p %zu\n", entry.tid, reinterpret_cast<void*>(entry.ptr), entry.size);
        } else {
          printf("%d: realloc %p %p %zu\n", entry.tid, reinterpret_cast<void*>(entry.ptr),
                 reinterpret_cast<void*>(entry.u.old_ptr), entry.size);
        }
        break;
      case MALLOC:
        printf("%d: malloc %p %zu\n", entry.tid, reinterpret_cast<void*>(entry.ptr), entry.size);
        break;
      case MEMALIGN:
        printf("%d: memalign %p %zu %zu\n", entry.tid, reinterpret_cast<void*>(entry.ptr),
               entry.u.align, entry.size);
        break;
      case CALLOC:
        printf("%d: calloc %p %zu %zu\n", entry.tid, reinterpret_cast<void*>(entry.ptr),
               entry.u.n_elements, entry.size);
        break;
      default:
        errx(1, "Invalid entry type found %d\n", entry.type);
        break;
    }
  } else {
    printf("%s size %zu\n", entry.type == REALLOC && entry.u.old_ptr != 0 ? "realloc" : "alloc",
           size);
  }
}

static void ProcessTrace(const std::string_view& trace, size_t min_size, size_t max_size,
                         bool print_trace_format) {
  AllocEntry* entries;
  size_t num_entries;
  GetUnwindInfo(trace.data(), &entries, &num_entries);

  if (!print_trace_format) {
    if (max_size != std::numeric_limits<size_t>::max()) {
      printf("Scanning for allocations between %zu and %zu\n", min_size, max_size);
    } else if (min_size != 0) {
      printf("Scanning for allocations >= %zu\n", min_size);
    } else {
      printf("Scanning for all allocations\n");
    }
  }
  size_t total_allocs = 0;
  size_t total_reallocs = 0;
  for (size_t i = 0; i < num_entries; i++) {
    const AllocEntry& entry = entries[i];
    switch (entry.type) {
      case MALLOC:
      case MEMALIGN:
      case REALLOC:
        if (entry.size >= min_size && entry.size <= max_size) {
          PrintEntry(entry, entry.size, print_trace_format);
          if (entry.type == REALLOC) {
            total_reallocs++;
          } else {
            total_allocs++;
          }
        }
        break;

      case CALLOC:
        if (size_t size = entry.u.n_elements * entry.size;
            size >= min_size && entry.size <= max_size) {
          PrintEntry(entry, size, print_trace_format);
        }
        break;

      case FREE:
      case THREAD_DONE:
      default:
        break;
    }
  }
  if (!print_trace_format) {
    printf("Total allocs:   %zu\n", total_allocs);
    printf("Total reallocs: %zu\n", total_reallocs);
  }

  FreeEntries(entries, num_entries);
}

int main(int argc, char** argv) {
  size_t min_size = 0;
  size_t max_size = std::numeric_limits<size_t>::max();
  bool print_trace_format = false;
  std::string_view trace_file;
  if (!ParseOptions(argc, argv, min_size, max_size, print_trace_format, trace_file)) {
    Usage();
    return 1;
  }

  ProcessTrace(trace_file, min_size, max_size, print_trace_format);
  return 0;
}
