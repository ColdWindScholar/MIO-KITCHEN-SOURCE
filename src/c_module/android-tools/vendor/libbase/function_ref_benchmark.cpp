/*
 * Copyright (C) 2022 The Android Open Source Project
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

#include "android-base/function_ref.h"

#include <benchmark/benchmark.h>

#include <functional>
#include <utility>

#include <time.h>

using android::base::function_ref;

template <class Callable, class... Args>
[[clang::noinline]] auto call(Callable&& c, Args&&... args) {
  return c(std::forward<Args>(args)...);
}

[[clang::noinline]] static int testFunc(int, const char*, char) {
  return time(nullptr);
}

using Func = decltype(testFunc);

static void BenchmarkFuncRaw(benchmark::State& state) {
  for (auto _ : state) {
    benchmark::DoNotOptimize(call(testFunc, 1, "1", '1'));
  }
}
BENCHMARK(BenchmarkFuncRaw);

static void BenchmarkFuncPtr(benchmark::State& state) {
  auto ptr = &testFunc;
  for (auto _ : state) {
    benchmark::DoNotOptimize(call(ptr, 1, "1", '1'));
  }
}
BENCHMARK(BenchmarkFuncPtr);

static void BenchmarkStdFunction(benchmark::State& state) {
  std::function<Func> f(testFunc);
  for (auto _ : state) {
    benchmark::DoNotOptimize(call(f, 1, "1", '1'));
  }
}
BENCHMARK(BenchmarkStdFunction);

static void BenchmarkFunctionRef(benchmark::State& state) {
  function_ref<Func> f(testFunc);
  for (auto _ : state) {
    benchmark::DoNotOptimize(call(f, 1, "1", '1'));
  }
}
BENCHMARK(BenchmarkFunctionRef);

namespace {
struct BigFunc {
  char big[128];
  [[clang::noinline]] int operator()(int, const char*, char) const { return time(nullptr); }
};

static BigFunc bigFunc;
}  // namespace

static void BenchmarkBigRaw(benchmark::State& state) {
  for (auto _ : state) {
    benchmark::DoNotOptimize(call(bigFunc, 1, "1", '1'));
  }
}
BENCHMARK(BenchmarkBigRaw);

static void BenchmarkBigStdFunction(benchmark::State& state) {
  std::function<Func> f(bigFunc);
  for (auto _ : state) {
    benchmark::DoNotOptimize(call(f, 1, "1", '1'));
  }
}
BENCHMARK(BenchmarkBigStdFunction);

static void BenchmarkBigFunctionRef(benchmark::State& state) {
  function_ref<Func> f(bigFunc);
  for (auto _ : state) {
    benchmark::DoNotOptimize(call(f, 1, "1", '1'));
  }
}
BENCHMARK(BenchmarkBigFunctionRef);

static void BenchmarkMakeFunctionRef(benchmark::State& state) {
  for (auto _ : state) {
    benchmark::DoNotOptimize(call<function_ref<Func>>(bigFunc, 1, "1", '1'));
  }
}
BENCHMARK(BenchmarkMakeFunctionRef);

static void BenchmarkMakeStdFunction(benchmark::State& state) {
  for (auto _ : state) {
    benchmark::DoNotOptimize(call<std::function<Func>>(bigFunc, 1, "1", '1'));
  }
}
BENCHMARK(BenchmarkMakeStdFunction);
