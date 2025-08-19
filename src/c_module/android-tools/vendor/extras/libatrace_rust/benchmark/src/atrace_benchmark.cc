/*
 * Copyright (C) 2023 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include <benchmark/benchmark.h>
#include <cutils/trace.h>
#include <string>

#include "trace_enabler.h"

static void BM_TracingOffAtraceBegin(benchmark::State& state) {
    disable_app_atrace();
    std::string name(state.range(0), '0');
    for (auto _ : state) {
        atrace_begin(ATRACE_TAG_APP, name.c_str());
    }
}

static void BM_TracingOffAtraceEnd(benchmark::State& state) {
    disable_app_atrace();
    for (auto _ : state) {
        atrace_end(ATRACE_TAG_APP);
    }
}

static void BM_TracingOnAtraceBegin(benchmark::State& state) {
    enable_atrace_for_single_app("*libatrace_rust_benchmark_cc");
    std::string name(state.range(0), '0');
    for (auto _ : state) {
        atrace_begin(ATRACE_TAG_APP, name.c_str());
    }
    disable_app_atrace();
}

static void BM_TracingOnAtraceEnd(benchmark::State& state) {
    enable_atrace_for_single_app("*libatrace_rust_benchmark_cc");
    for (auto _ : state) {
        atrace_end(ATRACE_TAG_APP);
    }
    disable_app_atrace();
}

// Register the function as a benchmark
BENCHMARK(BM_TracingOffAtraceBegin)->Arg(10)->Arg(1000);
BENCHMARK(BM_TracingOffAtraceEnd);
BENCHMARK(BM_TracingOnAtraceBegin)->Arg(10)->Arg(1000);
BENCHMARK(BM_TracingOnAtraceEnd);

BENCHMARK_MAIN();