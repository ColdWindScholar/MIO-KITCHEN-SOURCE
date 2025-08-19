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

//! Usage sample for a tracing subscriber in libatrace_rust.

use tracing::{debug, error, event, info, span, trace, warn, Level};

use atrace_tracing_subscriber::AtraceSubscriber;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

#[tracing::instrument]
fn mul_by_100_instrumented(num: i32) -> i32 {
    let result = num * 100;
    std::thread::sleep(std::time::Duration::from_millis(300));
    event!(Level::INFO, num, result);
    result
}

fn events_and_spans_demo() {
    let power_level = 8999;

    event!(Level::INFO, foo = "bar", power_level, "This is a {} message", "formattable");
    std::thread::sleep(std::time::Duration::from_millis(100));

    let span = span!(Level::TRACE, "Span name", baz = "quux");
    std::thread::sleep(std::time::Duration::from_millis(300));

    let _span_guard = span.enter();

    let _entered_span = span!(Level::TRACE, "Entered span").entered();
    std::thread::sleep(std::time::Duration::from_millis(300));

    trace!("test {} log {}", "VERBOSE", mul_by_100_instrumented(42));
    debug!("test {} log", "DEBUG");
    info!("test {} log", "INFO");
    warn!("test {} log", "WARNING");
    error!("test {} log", "ERROR");
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::registry()
        .with(AtraceSubscriber::default().with_filter())
        .with(tracing_subscriber::fmt::layer())
        .init();

    events_and_spans_demo();

    Ok(())
}
