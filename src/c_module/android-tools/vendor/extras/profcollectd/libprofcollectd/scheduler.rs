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

//! ProfCollect tracing scheduler.

use std::fs;
use std::mem;
use std::path::Path;
use std::sync::mpsc::{sync_channel, SyncSender};
use std::sync::Arc;
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

use crate::config::{get_sampling_period, Config, LOG_FILE, PROFILE_OUTPUT_DIR, TRACE_OUTPUT_DIR};
use crate::trace_provider::{self, TraceProvider};
use anyhow::{anyhow, ensure, Context, Result};

pub struct Scheduler {
    /// Signal to terminate the periodic collection worker thread, None if periodic collection is
    /// not scheduled.
    termination_ch: Option<SyncSender<()>>,
    /// The preferred trace provider for the system.
    trace_provider: Arc<Mutex<dyn TraceProvider + Send>>,
    provider_ready_callbacks: Arc<Mutex<Vec<Box<dyn FnOnce() + Send>>>>,
}

impl Scheduler {
    pub fn new() -> Result<Self> {
        let p = trace_provider::get_trace_provider()?;
        p.lock().map_err(|e| anyhow!(e.to_string()))?.set_log_file(&LOG_FILE);
        Ok(Scheduler {
            termination_ch: None,
            trace_provider: p,
            provider_ready_callbacks: Arc::new(Mutex::new(Vec::new())),
        })
    }

    fn is_scheduled(&self) -> bool {
        self.termination_ch.is_some()
    }

    pub fn schedule_periodic(&mut self, config: &Config) -> Result<()> {
        ensure!(!self.is_scheduled(), "Already scheduled.");

        let (sender, receiver) = sync_channel(1);
        self.termination_ch = Some(sender);

        // Clone config and trace_provider ARC for the worker thread.
        let config = config.clone();
        let trace_provider = self.trace_provider.clone();

        thread::spawn(move || {
            loop {
                match receiver.recv_timeout(config.collection_interval) {
                    Ok(_) => break,
                    Err(_) => {
                        // Did not receive a termination signal, initiate trace event.
                        if check_space_limit(&TRACE_OUTPUT_DIR, &config).unwrap() {
                            trace_provider.lock().unwrap().trace_system(
                                &TRACE_OUTPUT_DIR,
                                "periodic",
                                &get_sampling_period(),
                                &config.binary_filter,
                            );
                        }
                    }
                }
            }
        });
        Ok(())
    }

    pub fn terminate_periodic(&mut self) -> Result<()> {
        self.termination_ch
            .as_ref()
            .ok_or_else(|| anyhow!("Not scheduled"))?
            .send(())
            .context("Scheduler worker disappeared.")?;
        self.termination_ch = None;
        Ok(())
    }

    pub fn trace_system(&self, config: &Config, tag: &str) -> Result<()> {
        let trace_provider = self.trace_provider.clone();
        if check_space_limit(&TRACE_OUTPUT_DIR, config)? {
            trace_provider.lock().unwrap().trace_system(
                &TRACE_OUTPUT_DIR,
                tag,
                &get_sampling_period(),
                &config.binary_filter,
            );
        }
        Ok(())
    }

    pub fn trace_process(
        &self,
        config: &Config,
        tag: &str,
        processes: &str,
        samplng_period: f32,
    ) -> Result<()> {
        let trace_provider = self.trace_provider.clone();
        let duration = match samplng_period {
            0.0 => get_sampling_period(),
            _ => Duration::from_millis(samplng_period as u64),
        };
        if check_space_limit(&TRACE_OUTPUT_DIR, config)? {
            trace_provider.lock().unwrap().trace_process(
                &TRACE_OUTPUT_DIR,
                tag,
                &duration,
                processes,
            );
        }
        Ok(())
    }

    pub fn process(&self, config: &Config) -> Result<()> {
        let trace_provider = self.trace_provider.clone();
        trace_provider
            .lock()
            .unwrap()
            .process(&TRACE_OUTPUT_DIR, &PROFILE_OUTPUT_DIR, &config.binary_filter)
            .context("Failed to process profiles.")?;
        Ok(())
    }

    pub fn get_trace_provider_name(&self) -> &'static str {
        self.trace_provider.lock().unwrap().get_name()
    }

    pub fn is_provider_ready(&self) -> bool {
        self.trace_provider.lock().unwrap().is_ready()
    }

    pub fn register_provider_ready_callback(&self, cb: Box<dyn FnOnce() + Send>) {
        let mut locked_callbacks = self.provider_ready_callbacks.lock().unwrap();
        locked_callbacks.push(cb);
        if locked_callbacks.len() == 1 {
            self.start_thread_waiting_for_provider_ready();
        }
    }

    fn start_thread_waiting_for_provider_ready(&self) {
        let provider = self.trace_provider.clone();
        let callbacks = self.provider_ready_callbacks.clone();

        thread::spawn(move || {
            let start_time = Instant::now();
            loop {
                let elapsed = Instant::now().duration_since(start_time);
                if provider.lock().unwrap().is_ready() {
                    break;
                }
                // Decide check period based on how long we have waited:
                // For the first 10s waiting, check every 100ms (likely to work on EVT devices).
                // For the first 10m waiting, check every 10s (likely to work on DVT devices).
                // For others, check every 10m.
                let sleep_duration = if elapsed < Duration::from_secs(10) {
                    Duration::from_millis(100)
                } else if elapsed < Duration::from_secs(60 * 10) {
                    Duration::from_secs(10)
                } else {
                    Duration::from_secs(60 * 10)
                };
                thread::sleep(sleep_duration);
            }

            let mut locked_callbacks = callbacks.lock().unwrap();
            let v = mem::take(&mut *locked_callbacks);
            for cb in v {
                cb();
            }
        });
    }

    pub fn clear_trace_log(&self) -> Result<()> {
        let provider = self.trace_provider.lock().map_err(|e| anyhow!(e.to_string()))?;
        provider.reset_log_file();
        let mut result = Ok(());
        if LOG_FILE.exists() {
            result = fs::remove_file(*LOG_FILE).map_err(|e| anyhow!(e));
        }
        provider.set_log_file(&LOG_FILE);
        result
    }
}

/// Run if space usage is under limit.
fn check_space_limit(path: &Path, config: &Config) -> Result<bool> {
    // Returns the size of a directory, non-recursive.
    let dir_size = |path| -> Result<u64> {
        fs::read_dir(path)?.try_fold(0, |acc, file| {
            let metadata = file?.metadata()?;
            let size = if metadata.is_file() { metadata.len() } else { 0 };
            Ok(acc + size)
        })
    };

    if dir_size(path)? > config.max_trace_limit_mb * 1024 * 1024 {
        log::error!("trace storage exhausted.");
        return Ok(false);
    }
    Ok(true)
}
