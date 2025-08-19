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

//! Usage sample for libatrace_rust.

use std::thread::JoinHandle;

use atrace::AtraceTag;

fn spawn_async_event() -> JoinHandle<()> {
    // Unlike normal events, async events don't need to be nested.
    // You need to use the same name and cookie (the last arg) to close the event.
    // The cookie must be unique on the name level.
    let unique_cookie = 12345;
    atrace::atrace_async_begin(AtraceTag::App, "Async task", unique_cookie);
    std::thread::spawn(move || {
        std::thread::sleep(std::time::Duration::from_millis(500));
        atrace::atrace_async_end(AtraceTag::App, "Async task", unique_cookie);
    })
}

fn spawn_async_event_with_track() -> JoinHandle<()> {
    // Same as `atrace_async_begin` but per track.
    // Track name (not event name) and cookie are used to close the event.
    // The cookie must be unique on the track level.
    let unique_cookie = 12345;
    atrace::atrace_async_for_track_begin(
        AtraceTag::App,
        "Async track",
        "Task with track",
        unique_cookie,
    );
    std::thread::spawn(move || {
        std::thread::sleep(std::time::Duration::from_millis(600));
        atrace::atrace_async_for_track_end(AtraceTag::App, "Async track", unique_cookie);
    })
}

fn spawn_counter_thread() -> JoinHandle<()> {
    std::thread::spawn(|| {
        for i in 1..=10 {
            std::thread::sleep(std::time::Duration::from_millis(100));
            // Counter events are available for int and int64 to trace values.
            atrace::atrace_int(AtraceTag::App, "Count of i", i);
        }
    })
}

fn main() {
    // This macro will create a scoped event with the function name used as the event name.
    atrace::trace_method!(AtraceTag::App);

    // The scoped event will be ended when the returned guard is dropped.
    let _scoped_event = atrace::begin_scoped_event(AtraceTag::App, "Example main");

    // Methods starting with atrace_* are direct wrappers of libcutils methods.
    let enabled_tags = atrace::atrace_get_enabled_tags();
    println!("Enabled tags: {:?}", enabled_tags);

    println!("Spawning async trace events");
    let async_event_handler = spawn_async_event();
    let async_event_with_track_handler = spawn_async_event_with_track();
    let counter_thread_handler = spawn_counter_thread();

    // Instant events have no duration and don't need to be closed.
    atrace::atrace_instant(AtraceTag::App, "Instant event");

    println!("Calling atrace_begin and sleeping for 1 sec...");
    // If you begin an event you need to close it with the same tag. If you're calling begin
    // manually make sure you have a matching end. Or just use a scoped event.
    atrace::atrace_begin(AtraceTag::App, "Hello tracing!");
    std::thread::sleep(std::time::Duration::from_secs(1));
    atrace::atrace_end(AtraceTag::App);

    println!("Joining async events...");
    async_event_handler.join().unwrap();
    async_event_with_track_handler.join().unwrap();
    counter_thread_handler.join().unwrap();

    println!("Done!");
}
