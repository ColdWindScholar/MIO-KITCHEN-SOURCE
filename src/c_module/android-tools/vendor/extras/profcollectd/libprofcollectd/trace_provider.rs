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

//! ProfCollect trace provider trait and helper functions.

use anyhow::{anyhow, Result};
use chrono::Utc;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use crate::simpleperf_etm_trace_provider::SimpleperfEtmTraceProvider;
use crate::simpleperf_lbr_trace_provider::SimpleperfLbrTraceProvider;

#[cfg(feature = "test")]
use crate::logging_trace_provider::LoggingTraceProvider;

pub trait TraceProvider {
    fn get_name(&self) -> &'static str;
    fn is_ready(&self) -> bool;
    fn trace_system(
        &self,
        trace_dir: &Path,
        tag: &str,
        sampling_period: &Duration,
        binary_filter: &str,
    );
    fn trace_process(
        &self,
        trace_dir: &Path,
        tag: &str,
        sampling_period: &Duration,
        processes: &str,
    );
    fn process(&self, trace_dir: &Path, profile_dir: &Path, binary_filter: &str) -> Result<()>;
    fn set_log_file(&self, filename: &Path);
    fn reset_log_file(&self);
}

pub fn get_trace_provider() -> Result<Arc<Mutex<dyn TraceProvider + Send>>> {
    if SimpleperfEtmTraceProvider::supported() {
        log::info!("simpleperf_etm trace provider registered.");
        return Ok(Arc::new(Mutex::new(SimpleperfEtmTraceProvider {})));
    }
    if SimpleperfLbrTraceProvider::supported() {
        log::info!("simpleperf_lbr trace provider registered.");
        return Ok(Arc::new(Mutex::new(SimpleperfLbrTraceProvider {})));
    }

    #[cfg(feature = "test")]
    if LoggingTraceProvider::supported() {
        log::info!("logging trace provider registered.");
        return Ok(Arc::new(Mutex::new(LoggingTraceProvider {})));
    }

    Err(anyhow!("No trace provider found for this device."))
}

pub fn get_path(dir: &Path, tag: &str, ext: &str) -> Box<Path> {
    let filename = format!("{}_{}", Utc::now().format("%Y%m%d-%H%M%S"), tag);
    let mut trace_file = PathBuf::from(dir);
    trace_file.push(filename);
    trace_file.set_extension(ext);
    trace_file.into_boxed_path()
}
