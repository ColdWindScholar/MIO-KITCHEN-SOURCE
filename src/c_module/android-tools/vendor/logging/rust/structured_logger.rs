// Copyright 2024, The Android Open Source Project
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

//! # Structed Logger API for Android

use log_event_list::__private_api::{LogContext, LogContextError};

/// Add functionality to a type to log to a LogContext
pub trait Value {
    /// Apend value to provided context
    fn add_to_context(&self, ctx: LogContext) -> Result<LogContext, LogContextError>;
}

impl Value for f32 {
    fn add_to_context(&self, ctx: LogContext) -> Result<LogContext, LogContextError> {
        ctx.append_f32(*self)
    }
}

impl Value for i32 {
    fn add_to_context(&self, ctx: LogContext) -> Result<LogContext, LogContextError> {
        ctx.append_i32(*self)
    }
}

impl Value for i64 {
    fn add_to_context(&self, ctx: LogContext) -> Result<LogContext, LogContextError> {
        ctx.append_i64(*self)
    }
}

impl Value for &str {
    fn add_to_context(&self, ctx: LogContext) -> Result<LogContext, LogContextError> {
        ctx.append_str(self)
    }
}

impl Value for String {
    fn add_to_context(&self, ctx: LogContext) -> Result<LogContext, LogContextError> {
        ctx.append_str(self.as_str())
    }
}

/// Enum provides values to control sections.
#[derive(PartialEq)]
pub enum StructuredLogSection {
    /// Start a new section
    SubsectionStart,
    /// End a section
    SubsectionEnd,
}

impl Value for StructuredLogSection {
    fn add_to_context(&self, ctx: LogContext) -> Result<LogContext, LogContextError> {
        match *self {
            StructuredLogSection::SubsectionStart => ctx.begin_list(),
            StructuredLogSection::SubsectionEnd => ctx.end_list(),
        }
    }
}

// The following uses global crate names to make the usage of the macro
// as simple as possible as the using code does not need to use the
// dependencies explicitly.
// Using imported crate names would require using code to import all our
// internal dependencies without using them manually.

/// Events log buffer.
/// C++ implementation always logs to events, and used by default for consistent behavior between Rust and C++.
pub const LOG_ID_EVENTS: u32 = log_event_list_bindgen::log_id_LOG_ID_EVENTS;
/// Security log buffer.
pub const LOG_ID_SECURITY: u32 = log_event_list_bindgen::log_id_LOG_ID_SECURITY;
/// Statistics log buffer.
pub const LOG_ID_STATS: u32 = log_event_list_bindgen::log_id_LOG_ID_STATS;

/// Add a structured log entry to buffer $log_id.
/// Should not be used directly, but the macros below.
/// Warning: Since this macro is internal, it may change any time.
/// Usage: __structured_log_internal!(LOG_ID, TAG, value1, value2, ...)
/// Returns Result:
///   Ok if entry was written successfully
///   Err(str) with an error description
#[doc(hidden)]
#[macro_export]
macro_rules! __structured_log_internal {
    ($log_id:expr, $tag:expr, $($entry:expr),+) => (
        {
            let mut ctx =
                log_event_list::__private_api::LogContext::new($log_id, $tag)
                    .ok_or(log_event_list::__private_api::LogContextError).map_err(|_|
                "Unable to create a log context");
            $(ctx = ctx.and_then(|c| $crate::Value::add_to_context(&$entry, c)
                .map_err(|_| "unable to log value"));)+;
            ctx.and_then(|c| c.write()
                .map_err(|_| "unable to write log message"))
        }
    )
}

/// Add a structured log entry to events.
/// Usage: structured_log!(TAG, value1, value2, ...)
/// To use a different log buffer, you can specify it with log_id.
/// Usage: structured_log!(log_id: LOG_ID, TAG, value1, value2, ...)
/// Returns Result:
///   Ok if entry was written successfully
///   Err(str) with an error description
#[macro_export]
macro_rules! structured_log {
    (log_id: $log_id:expr, $tag:expr, $($entry:expr),+) => (
        {
            $crate::__structured_log_internal!($log_id, $tag, $($entry),+)
        }
    );
    ($tag:expr, $($entry:expr),+) => (
        {
            $crate::__structured_log_internal!($crate::LOG_ID_EVENTS, $tag, $($entry),+)
        }
    )
}
