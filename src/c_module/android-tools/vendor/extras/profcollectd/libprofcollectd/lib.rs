//
// Copyright (C) 2020 The Android Open Source Project
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

//! ProfCollect Binder client interface.

mod config;
mod report;
mod scheduler;
mod service;
mod simpleperf_etm_trace_provider;
mod simpleperf_lbr_trace_provider;
mod trace_provider;

#[cfg(feature = "test")]
mod logging_trace_provider;

use anyhow::{Context, Result};
use profcollectd_aidl_interface::aidl::com::android::server::profcollect::IProfCollectd::{
    self, BnProfCollectd,
};
use profcollectd_aidl_interface::aidl::com::android::server::profcollect::IProviderStatusCallback::{IProviderStatusCallback, BnProviderStatusCallback};
use profcollectd_aidl_interface::binder::{self, BinderFeatures};
use service::{err_to_binder_status, ProfcollectdBinderService};
use std::time::{Duration, Instant};

const PROFCOLLECTD_SERVICE_NAME: &str = "profcollectd";

struct ProviderStatusCallback {
    service_start_time: Instant,
}

impl binder::Interface for ProviderStatusCallback {}

impl IProviderStatusCallback for ProviderStatusCallback {
    fn onProviderReady(&self) -> binder::Result<()> {
        // If we have waited too long for the provider to be ready, then we have passed
        // boot phase, and no need to collect boot profile.
        // TODO: should we check boottime instead?
        const TIMEOUT_TO_COLLECT_BOOT_PROFILE: Duration = Duration::from_secs(3);
        let elapsed = Instant::now().duration_since(self.service_start_time);
        if elapsed < TIMEOUT_TO_COLLECT_BOOT_PROFILE {
            trace_system("boot").map_err(err_to_binder_status)?;
        }
        schedule().map_err(err_to_binder_status)?;
        Ok(())
    }
}

/// Initialise profcollectd service.
/// * `schedule_now` - Immediately schedule collection after service is initialised.
pub fn init_service(schedule_now: bool) -> Result<()> {
    binder::ProcessState::start_thread_pool();

    let profcollect_binder_service = ProfcollectdBinderService::new()?;
    binder::add_service(
        PROFCOLLECTD_SERVICE_NAME,
        BnProfCollectd::new_binder(profcollect_binder_service, BinderFeatures::default())
            .as_binder(),
    )
    .context("Failed to register service.")?;

    if schedule_now {
        let cb = BnProviderStatusCallback::new_binder(
            ProviderStatusCallback { service_start_time: Instant::now() },
            BinderFeatures::default(),
        );
        get_profcollectd_service()?.registerProviderStatusCallback(&cb)?;
    }

    binder::ProcessState::join_thread_pool();
    Ok(())
}

fn get_profcollectd_service() -> Result<binder::Strong<dyn IProfCollectd::IProfCollectd>> {
    binder::wait_for_interface(PROFCOLLECTD_SERVICE_NAME)
        .context("Failed to get profcollectd binder service, is profcollectd running?")
}

/// Schedule periodic profile collection.
pub fn schedule() -> Result<()> {
    get_profcollectd_service()?.schedule()?;
    Ok(())
}

/// Terminate periodic profile collection.
pub fn terminate() -> Result<()> {
    get_profcollectd_service()?.terminate()?;
    Ok(())
}

/// Immediately schedule a one-off trace.
pub fn trace_system(tag: &str) -> Result<()> {
    get_profcollectd_service()?.trace_system(tag)?;
    Ok(())
}

/// Process traces.
pub fn process() -> Result<()> {
    get_profcollectd_service()?.process()?;
    Ok(())
}

/// Process traces and report profile.
pub fn report() -> Result<String> {
    Ok(get_profcollectd_service()?.report(report::NO_USAGE_SETTING)?)
}

/// Clear all local data.
pub fn reset() -> Result<()> {
    config::clear_data()?;
    Ok(())
}

/// Inits logging for Android
pub fn init_logging() {
    let max_log_level =
        if cfg!(feature = "test") { log::LevelFilter::Info } else { log::LevelFilter::Error };
    android_logger::init_once(
        android_logger::Config::default()
            .with_tag("profcollectd")
            .with_max_level(max_log_level)
            .with_log_buffer(android_logger::LogId::System),
    );
}
