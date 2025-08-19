// Copyright (C) 2023 The Android Open Source Project
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

//! Benchmark for ATrace bindings.

use atrace::AtraceTag;
use atrace_rust_benchmark_common::{new_criterion, turn_tracing_off, turn_tracing_on};
use criterion::{BenchmarkId, Criterion};

fn bench_tracing_off_begin(c: &mut Criterion, name_len: usize) {
    turn_tracing_off();
    let name = "0".repeat(name_len);
    c.bench_with_input(BenchmarkId::new("tracing_off_begin", name_len), &name, |b, name| {
        b.iter(|| atrace::atrace_begin(AtraceTag::App, name.as_str()))
    });
}

fn bench_tracing_off_end(c: &mut Criterion) {
    turn_tracing_off();
    c.bench_function("tracing_off_end", |b| b.iter(|| atrace::atrace_end(AtraceTag::App)));
}

fn bench_tracing_on_begin(c: &mut Criterion, name_len: usize) {
    turn_tracing_on();
    let name = "0".repeat(name_len);
    c.bench_with_input(BenchmarkId::new("tracing_on_begin", name_len), &name, |b, name| {
        b.iter(|| atrace::atrace_begin(AtraceTag::App, name.as_str()))
    });
    turn_tracing_off();
}

fn bench_tracing_on_end(c: &mut Criterion) {
    turn_tracing_on();
    c.bench_function("tracing_on_end", |b| b.iter(|| atrace::atrace_end(AtraceTag::App)));
    turn_tracing_off();
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut criterion = new_criterion();

    bench_tracing_off_begin(&mut criterion, 10);
    bench_tracing_off_begin(&mut criterion, 1000);
    bench_tracing_off_end(&mut criterion);

    bench_tracing_on_begin(&mut criterion, 10);
    bench_tracing_on_begin(&mut criterion, 1000);
    bench_tracing_on_end(&mut criterion);

    Ok(())
}
