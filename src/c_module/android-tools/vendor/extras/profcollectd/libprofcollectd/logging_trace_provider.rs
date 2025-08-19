//
// Copyright (C) 2021 The Android Open Source Project
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//

//! Logging trace provider for development and testing purposes.

use anyhow::Result;
use std::path::Path;
use std::time::Duration;
use trace_provider::TraceProvider;

use crate::trace_provider;

static LOGGING_TRACEFILE_EXTENSION: &str = "loggingtrace";

pub struct LoggingTraceProvider {}

impl TraceProvider for LoggingTraceProvider {
    fn get_name(&self) -> &'static str {
        "logging"
    }

    fn is_ready(&self) -> bool {
        true
    }

    fn trace_system(
        &self,
        trace_dir: &Path,
        tag: &str,
        sampling_period: &Duration,
        _binary_filter: &str,
    ) {
        let trace_file = trace_provider::get_path(trace_dir, tag, LOGGING_TRACEFILE_EXTENSION);

        log::info!(
            "Trace event triggered, tag {}, sampling for {}ms, saving to {}",
            tag,
            sampling_period.as_millis(),
            trace_file.display()
        );
    }

    fn trace_process(
        &self,
        trace_dir: &Path,
        tag: &str,
        sampling_period: &Duration,
        processes: &str,
    ) {
        let trace_file = trace_provider::get_path(trace_dir, tag, LOGGING_TRACEFILE_EXTENSION);

        log::info!(
            "Trace event triggered, tag {}, processes {}, sampling for {}ms, saving to {}",
            tag,
            processes,
            sampling_period.as_millis(),
            trace_file.display()
        );
    }

    fn process(&self, _trace_dir: &Path, _profile_dir: &Path, _binary_filter: &str) -> Result<()> {
        log::info!("Process event triggered");
        Ok(())
    }

    fn set_log_file(&self, _filename: &Path) {}
    fn reset_log_file(&self) {}
}

impl LoggingTraceProvider {
    pub fn supported() -> bool {
        true
    }
}
