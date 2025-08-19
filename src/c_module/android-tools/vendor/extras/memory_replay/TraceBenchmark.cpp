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

#include <err.h>
#include <inttypes.h>
#include <malloc.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#include <algorithm>
#include <stack>
#include <string>
#include <unordered_map>
#include <vector>

#include <android-base/file.h>
#include <android-base/strings.h>
#include <benchmark/benchmark.h>

#include "Alloc.h"
#include "File.h"
#include "Utils.h"

struct TraceDataType {
  AllocEntry* entries = nullptr;
  size_t num_entries = 0;
  void** ptrs = nullptr;
  size_t num_ptrs = 0;
};

static size_t GetIndex(std::stack<size_t>& free_indices, size_t* max_index) {
  if (free_indices.empty()) {
    return (*max_index)++;
  }
  size_t index = free_indices.top();
  free_indices.pop();
  return index;
}

static void FreePtrs(TraceDataType* trace_data) {
  for (size_t i = 0; i < trace_data->num_ptrs; i++) {
    void* ptr = trace_data->ptrs[i];
    if (ptr != nullptr) {
      free(ptr);
      trace_data->ptrs[i] = nullptr;
    }
  }
}

static void FreeTraceData(TraceDataType* trace_data) {
  if (trace_data->ptrs == nullptr) {
    return;
  }

  munmap(trace_data->ptrs, sizeof(void*) * trace_data->num_ptrs);
  FreeEntries(trace_data->entries, trace_data->num_entries);
}

static void GetTraceData(const std::string& filename, TraceDataType* trace_data) {
  // Only keep last trace encountered cached.
  static std::string cached_filename;
  static TraceDataType cached_trace_data;
  if (cached_filename == filename) {
    *trace_data = cached_trace_data;
    return;
  } else {
    FreeTraceData(&cached_trace_data);
  }

  cached_filename = filename;
  GetUnwindInfo(filename.c_str(), &trace_data->entries, &trace_data->num_entries);

  // This loop will convert the ptr field into an index into the ptrs array.
  // Creating this index allows the trace run to quickly store or retrieve the
  // allocation.
  // For free, the ptr field will be index + one, where a zero represents
  // a free(nullptr) call.
  // For realloc, the old_pointer field will be index + one, where a zero
  // represents a realloc(nullptr, XX).
  trace_data->num_ptrs = 0;
  std::stack<size_t> free_indices;
  std::unordered_map<uint64_t, size_t> ptr_to_index;
  for (size_t i = 0; i < trace_data->num_entries; i++) {
    AllocEntry* entry = &trace_data->entries[i];
    switch (entry->type) {
      case MALLOC:
      case CALLOC:
      case MEMALIGN: {
        size_t idx = GetIndex(free_indices, &trace_data->num_ptrs);
        ptr_to_index[entry->ptr] = idx;
        entry->ptr = idx;
        break;
      }
      case REALLOC: {
        if (entry->u.old_ptr != 0) {
          auto idx_entry = ptr_to_index.find(entry->u.old_ptr);
          if (idx_entry == ptr_to_index.end()) {
            errx(1, "File Error: Failed to find realloc pointer %" PRIx64, entry->u.old_ptr);
          }
          size_t old_pointer_idx = idx_entry->second;
          free_indices.push(old_pointer_idx);
          ptr_to_index.erase(idx_entry);
          entry->u.old_ptr = old_pointer_idx + 1;
        }
        size_t idx = GetIndex(free_indices, &trace_data->num_ptrs);
        ptr_to_index[entry->ptr] = idx;
        entry->ptr = idx;
        break;
      }
      case FREE:
        if (entry->ptr != 0) {
          auto idx_entry = ptr_to_index.find(entry->ptr);
          if (idx_entry == ptr_to_index.end()) {
            errx(1, "File Error: Unable to find free pointer %" PRIx64, entry->ptr);
          }
          free_indices.push(idx_entry->second);
          entry->ptr = idx_entry->second + 1;
          ptr_to_index.erase(idx_entry);
        }
        break;
      case THREAD_DONE:
        break;
    }
  }
  void* map = mmap(nullptr, sizeof(void*) * trace_data->num_ptrs, PROT_READ | PROT_WRITE, MAP_ANON | MAP_PRIVATE, -1, 0);
  if (map == MAP_FAILED) {
    err(1, "mmap failed");
  }
  trace_data->ptrs = reinterpret_cast<void**>(map);

  cached_trace_data = *trace_data;
}

static void RunTrace(benchmark::State& state, TraceDataType* trace_data) {
  int pagesize = getpagesize();
  uint64_t total_ns = 0;
  uint64_t start_ns;
  void** ptrs = trace_data->ptrs;
  for (size_t i = 0; i < trace_data->num_entries; i++) {
    void* ptr;
    const AllocEntry& entry = trace_data->entries[i];
    switch (entry.type) {
      case MALLOC:
        start_ns = Nanotime();
        ptr = malloc(entry.size);
        if (ptr == nullptr) {
          errx(1, "malloc returned nullptr");
        }
        MakeAllocationResident(ptr, entry.size, pagesize);
        total_ns += Nanotime() - start_ns;

        if (ptrs[entry.ptr] != nullptr) {
          errx(1, "Internal Error: malloc pointer being replaced is not nullptr");
        }
        ptrs[entry.ptr] = ptr;
        break;

      case CALLOC:
        start_ns = Nanotime();
        ptr = calloc(entry.u.n_elements, entry.size);
        if (ptr == nullptr) {
          errx(1, "calloc returned nullptr");
        }
        MakeAllocationResident(ptr, entry.size, pagesize);
        total_ns += Nanotime() - start_ns;

        if (ptrs[entry.ptr] != nullptr) {
          errx(1, "Internal Error: calloc pointer being replaced is not nullptr");
        }
        ptrs[entry.ptr] = ptr;
        break;

      case MEMALIGN:
        start_ns = Nanotime();
        ptr = memalign(entry.u.align, entry.size);
        if (ptr == nullptr) {
          errx(1, "memalign returned nullptr");
        }
        MakeAllocationResident(ptr, entry.size, pagesize);
        total_ns += Nanotime() - start_ns;

        if (ptrs[entry.ptr] != nullptr) {
          errx(1, "Internal Error: memalign pointer being replaced is not nullptr");
        }
        ptrs[entry.ptr] = ptr;
        break;

      case REALLOC:
        start_ns = Nanotime();
        if (entry.u.old_ptr == 0) {
          ptr = realloc(nullptr, entry.size);
        } else {
          ptr = realloc(ptrs[entry.u.old_ptr - 1], entry.size);
          ptrs[entry.u.old_ptr - 1] = nullptr;
        }
        if (entry.size > 0) {
          if (ptr == nullptr) {
            errx(1, "realloc returned nullptr");
          }
          MakeAllocationResident(ptr, entry.size, pagesize);
        }
        total_ns += Nanotime() - start_ns;

        if (ptrs[entry.ptr] != nullptr) {
          errx(1, "Internal Error: realloc pointer being replaced is not nullptr");
        }
        ptrs[entry.ptr] = ptr;
        break;

      case FREE:
        if (entry.ptr != 0) {
          ptr = ptrs[entry.ptr - 1];
          ptrs[entry.ptr - 1] = nullptr;
        } else {
          ptr = nullptr;
        }
        start_ns = Nanotime();
        free(ptr);
        total_ns += Nanotime() - start_ns;
        break;

      case THREAD_DONE:
        break;
    }
  }
  state.SetIterationTime(total_ns / double(1000000000.0));

  FreePtrs(trace_data);
}

// Run a trace as if all of the allocations occurred in a single thread.
// This is not completely realistic, but it is a possible worst case that
// could happen in an app.
static void BenchmarkTrace(benchmark::State& state, const char* filename, bool enable_decay_time) {
#if defined(__BIONIC__)
  if (enable_decay_time) {
    mallopt(M_DECAY_TIME, 1);
  } else {
    mallopt(M_DECAY_TIME, 0);
  }
#endif
  std::string full_filename(android::base::GetExecutableDirectory() + "/traces/" + filename);

  TraceDataType trace_data;
  GetTraceData(full_filename, &trace_data);

  for (auto _ : state) {
    RunTrace(state, &trace_data);
  }

  // Don't free the trace_data, it is cached. The last set of trace data
  // will be leaked away.
}

#define BENCH_OPTIONS                 \
  UseManualTime()                     \
      ->Unit(benchmark::kMicrosecond) \
      ->MinTime(15.0)                 \
      ->Repetitions(4)                \
      ->ReportAggregatesOnly(true)

static void BM_angry_birds2_default(benchmark::State& state) {
  BenchmarkTrace(state, "angry_birds2.zip", true);
}
BENCHMARK(BM_angry_birds2_default)->BENCH_OPTIONS;

#if defined(__BIONIC__)
static void BM_angry_birds2_no_decay(benchmark::State& state) {
  BenchmarkTrace(state, "angry_birds2.zip", false);
}
BENCHMARK(BM_angry_birds2_no_decay)->BENCH_OPTIONS;
#endif

static void BM_camera_default(benchmark::State& state) {
  BenchmarkTrace(state, "camera.zip", true);
}
BENCHMARK(BM_camera_default)->BENCH_OPTIONS;

#if defined(__BIONIC__)
static void BM_camera_no_decay(benchmark::State& state) {
  BenchmarkTrace(state, "camera.zip", false);
}
BENCHMARK(BM_camera_no_decay)->BENCH_OPTIONS;
#endif

static void BM_candy_crush_saga_default(benchmark::State& state) {
  BenchmarkTrace(state, "candy_crush_saga.zip", true);
}
BENCHMARK(BM_candy_crush_saga_default)->BENCH_OPTIONS;

#if defined(__BIONIC__)
static void BM_candy_crush_saga_no_decay(benchmark::State& state) {
  BenchmarkTrace(state, "candy_crush_saga.zip", false);
}
BENCHMARK(BM_candy_crush_saga_no_decay)->BENCH_OPTIONS;
#endif

void BM_gmail_default(benchmark::State& state) {
  BenchmarkTrace(state, "gmail.zip", true);
}
BENCHMARK(BM_gmail_default)->BENCH_OPTIONS;

#if defined(__BIONIC__)
void BM_gmail_no_decay(benchmark::State& state) {
  BenchmarkTrace(state, "gmail.zip", false);
}
BENCHMARK(BM_gmail_no_decay)->BENCH_OPTIONS;
#endif

void BM_maps_default(benchmark::State& state) {
  BenchmarkTrace(state, "maps.zip", true);
}
BENCHMARK(BM_maps_default)->BENCH_OPTIONS;

#if defined(__BIONIC__)
void BM_maps_no_decay(benchmark::State& state) {
  BenchmarkTrace(state, "maps.zip", false);
}
BENCHMARK(BM_maps_no_decay)->BENCH_OPTIONS;
#endif

void BM_photos_default(benchmark::State& state) {
  BenchmarkTrace(state, "photos.zip", true);
}
BENCHMARK(BM_photos_default)->BENCH_OPTIONS;

#if defined(__BIONIC__)
void BM_photos_no_decay(benchmark::State& state) {
  BenchmarkTrace(state, "photos.zip", false);
}
BENCHMARK(BM_photos_no_decay)->BENCH_OPTIONS;
#endif

void BM_pubg_default(benchmark::State& state) {
  BenchmarkTrace(state, "pubg.zip", true);
}
BENCHMARK(BM_pubg_default)->BENCH_OPTIONS;

#if defined(__BIONIC__)
void BM_pubg_no_decay(benchmark::State& state) {
  BenchmarkTrace(state, "pubg.zip", false);
}
BENCHMARK(BM_pubg_no_decay)->BENCH_OPTIONS;
#endif

void BM_surfaceflinger_default(benchmark::State& state) {
  BenchmarkTrace(state, "surfaceflinger.zip", true);
}
BENCHMARK(BM_surfaceflinger_default)->BENCH_OPTIONS;

#if defined(__BIONIC__)
void BM_surfaceflinger_no_decay(benchmark::State& state) {
  BenchmarkTrace(state, "surfaceflinger.zip", false);
}
BENCHMARK(BM_surfaceflinger_no_decay)->BENCH_OPTIONS;
#endif

void BM_system_server_default(benchmark::State& state) {
  BenchmarkTrace(state, "system_server.zip", true);
}
BENCHMARK(BM_system_server_default)->BENCH_OPTIONS;

#if defined(__BIONIC__)
void BM_system_server_no_decay(benchmark::State& state) {
  BenchmarkTrace(state, "system_server.zip", false);
}
BENCHMARK(BM_system_server_no_decay)->BENCH_OPTIONS;
#endif

void BM_systemui_default(benchmark::State& state) {
  BenchmarkTrace(state, "systemui.zip", true);
}
BENCHMARK(BM_systemui_default)->BENCH_OPTIONS;

#if defined(__BIONIC__)
void BM_systemui_no_decay(benchmark::State& state) {
  BenchmarkTrace(state, "systemui.zip", false);
}
BENCHMARK(BM_systemui_no_decay)->BENCH_OPTIONS;
#endif

void BM_youtube_default(benchmark::State& state) {
  BenchmarkTrace(state, "youtube.zip", true);
}
BENCHMARK(BM_youtube_default)->BENCH_OPTIONS;

#if defined(__BIONIC__)
void BM_youtube_no_decay(benchmark::State& state) {
  BenchmarkTrace(state, "youtube.zip", false);
}
BENCHMARK(BM_youtube_no_decay)->BENCH_OPTIONS;
#endif

int main(int argc, char** argv) {
  std::vector<char*> args;
  args.push_back(argv[0]);

  // Look for the --cpu=XX option.
  for (int i = 1; i < argc; i++) {
    if (strncmp(argv[i], "--cpu=", 6) == 0) {
      char* endptr;
      int cpu = strtol(&argv[i][6], &endptr, 10);
      if (argv[i][0] == '\0' || endptr == nullptr || *endptr != '\0') {
        printf("Invalid format of --cpu option, '%s' must be an integer value.\n", argv[i] + 6);
        return 1;
      }
      cpu_set_t cpuset;
      CPU_ZERO(&cpuset);
      CPU_SET(cpu, &cpuset);
      if (sched_setaffinity(0, sizeof(cpuset), &cpuset) != 0) {
        if (errno == EINVAL) {
          printf("Invalid cpu %d\n", cpu);
          return 1;
        }
        perror("sched_setaffinity failed");
        return 1;
      }
      printf("Locking to cpu %d\n", cpu);
    } else {
      args.push_back(argv[i]);
    }
  }

  argc = args.size();
  ::benchmark::Initialize(&argc, args.data());
  if (::benchmark::ReportUnrecognizedArguments(argc, args.data())) return 1;
  ::benchmark::RunSpecifiedBenchmarks();
}
