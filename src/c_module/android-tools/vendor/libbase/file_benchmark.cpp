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

#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>

#include <benchmark/benchmark.h>

#include "android-base/file.h"
#include "android-base/logging.h"

static void BenchmarkReadFdToString(benchmark::State& state) {
  android::base::unique_fd fd(memfd_create("memfile", 0));
  CHECK(fd.get() > 0);
  CHECK_EQ(ftruncate(fd, state.range(0)), 0);
  for (auto _ : state) {
    CHECK_EQ(lseek(fd, 0, SEEK_SET), 0);
    std::string str;
    benchmark::DoNotOptimize(android::base::ReadFdToString(fd, &str));
  }
  state.SetBytesProcessed(state.iterations() * state.range(0));
}

BENCHMARK_RANGE(BenchmarkReadFdToString, 0, 1024 * 1024);
