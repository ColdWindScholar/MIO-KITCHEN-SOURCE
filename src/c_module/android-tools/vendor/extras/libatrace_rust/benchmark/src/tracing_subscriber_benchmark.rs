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

//! Benchmark for ATrace tracing subscriber.

use atrace_rust_benchmark_common::{new_criterion, turn_tracing_off, turn_tracing_on};
use atrace_tracing_subscriber::AtraceSubscriber;
use criterion::Criterion;
use tracing_subscriber::prelude::__tracing_subscriber_SubscriberExt;

fn make_example_vec() -> Vec<i32> {
    Vec::from([1, 2, 3, 4])
}

fn bench_with_subscriber<F>(c: &mut Criterion, name: &str, mut f: F)
where
    F: FnMut(),
{
    let subscriber = tracing_subscriber::registry().with(AtraceSubscriber::default());
    tracing::subscriber::with_default(subscriber, || {
        c.bench_function(name, |b| b.iter(&mut f));
    });
}

fn bench_with_filtering_subscriber<F>(c: &mut Criterion, name: &str, mut f: F)
where
    F: FnMut(),
{
    let subscriber = tracing_subscriber::registry().with(AtraceSubscriber::default().with_filter());
    tracing::subscriber::with_default(subscriber, || {
        c.bench_function(name, |b| b.iter(&mut f));
    });
}

fn bench_tracing_off_event(c: &mut Criterion) {
    turn_tracing_off();
    bench_with_subscriber(c, "tracing_off_event", || tracing::info!("bench info event"));
}

fn bench_filtered_event(c: &mut Criterion) {
    turn_tracing_off();
    bench_with_filtering_subscriber(c, "filtered_event", || tracing::info!("bench info event"));
}

fn bench_tracing_off_event_args(c: &mut Criterion) {
    turn_tracing_off();
    let v = make_example_vec();
    bench_with_subscriber(c, "tracing_off_event_args", || {
        tracing::info!(debug_arg1 = 123,
            debug_arg2 = "argument",
            debug_arg3 = ?v,
            debug_arg4 = "last",
            "bench info event")
    });
}

fn bench_filtered_event_args(c: &mut Criterion) {
    turn_tracing_off();
    let v = make_example_vec();
    bench_with_filtering_subscriber(c, "filtered_event_args", || {
        tracing::info!(debug_arg1 = 123,
            debug_arg2 = "argument",
            debug_arg3 = ?v,
            debug_arg4 = "last",
            "bench info event")
    });
}

fn bench_tracing_off_span(c: &mut Criterion) {
    turn_tracing_off();
    bench_with_subscriber(c, "tracing_off_span", || {
        let _entered = tracing::info_span!("bench info span").entered();
    });
}

fn bench_filtered_span(c: &mut Criterion) {
    turn_tracing_off();
    bench_with_filtering_subscriber(c, "filtered_span", || {
        let _entered = tracing::info_span!("bench info span").entered();
    });
}

fn bench_tracing_off_span_args(c: &mut Criterion) {
    turn_tracing_off();
    let v = make_example_vec();
    bench_with_subscriber(c, "tracing_off_span_args", || {
        let _entered = tracing::info_span!("bench info span", debug_arg1 = 123,
            debug_arg2 = "argument",
            debug_arg3 = ?v,
            debug_arg4 = "last")
        .entered();
    });
}

fn bench_filtered_span_args(c: &mut Criterion) {
    turn_tracing_off();
    let v = make_example_vec();
    bench_with_filtering_subscriber(c, "filtered_span_args", || {
        let _entered = tracing::info_span!("bench info span", debug_arg1 = 123,
            debug_arg2 = "argument",
            debug_arg3 = ?v,
            debug_arg4 = "last")
        .entered();
    });
}

fn bench_tracing_on_event(c: &mut Criterion) {
    turn_tracing_on();
    bench_with_subscriber(c, "tracing_on_event", || tracing::info!("bench info event"));
    turn_tracing_off();
}

fn bench_tracing_on_event_args(c: &mut Criterion) {
    turn_tracing_on();
    let v = make_example_vec();
    bench_with_subscriber(c, "tracing_on_event_args", || {
        tracing::info!(debug_arg1 = 123,
            debug_arg2 = "argument",
            debug_arg3 = ?v,
            debug_arg4 = "last",
            "bench info event")
    });
    turn_tracing_off();
}

fn bench_tracing_on_span(c: &mut Criterion) {
    turn_tracing_on();
    bench_with_subscriber(c, "tracing_on_span", || {
        let _entered = tracing::info_span!("bench info span").entered();
    });
    turn_tracing_off();
}

fn bench_tracing_on_span_args(c: &mut Criterion) {
    turn_tracing_on();
    let v = make_example_vec();
    bench_with_subscriber(c, "tracing_on_span_args", || {
        let _entered = tracing::info_span!("bench info span", debug_arg1 = 123,
            debug_arg2 = "argument",
            debug_arg3 = ?v,
            debug_arg4 = "last")
        .entered();
    });
    turn_tracing_off();
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut criterion = new_criterion();

    bench_tracing_off_event(&mut criterion);
    bench_filtered_event(&mut criterion);
    bench_tracing_off_event_args(&mut criterion);
    bench_filtered_event_args(&mut criterion);
    bench_tracing_off_span(&mut criterion);
    bench_filtered_span(&mut criterion);
    bench_tracing_off_span_args(&mut criterion);
    bench_filtered_span_args(&mut criterion);

    bench_tracing_on_event(&mut criterion);
    bench_tracing_on_event_args(&mut criterion);
    bench_tracing_on_span(&mut criterion);
    bench_tracing_on_span_args(&mut criterion);

    Ok(())
}
