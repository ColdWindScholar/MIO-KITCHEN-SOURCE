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

//! ProfCollect Binder service implementation.

use anyhow::{anyhow, Context, Error, Result};
use binder::Result as BinderResult;
use binder::{SpIBinder, Status};
use profcollectd_aidl_interface::aidl::com::android::server::profcollect::IProfCollectd::IProfCollectd;
use profcollectd_aidl_interface::aidl::com::android::server::profcollect::IProviderStatusCallback::IProviderStatusCallback;
use std::ffi::CString;
use std::fs::{read_dir, read_to_string, remove_file, write};
use std::str::FromStr;
use std::sync::{Mutex, MutexGuard};
use std::time::Duration;

use crate::config::{
    clear_data, Config, CONFIG_FILE, PROFILE_OUTPUT_DIR, REPORT_OUTPUT_DIR, REPORT_RETENTION_SECS,
};
use crate::report::{get_report_ts, pack_report};
use crate::scheduler::Scheduler;

pub fn err_to_binder_status(msg: Error) -> Status {
    let msg = format!("{:#?}", msg);
    let msg = CString::new(msg).expect("Failed to convert to CString");
    Status::new_service_specific_error(1, Some(&msg))
}

pub struct ProfcollectdBinderService {
    lock: Mutex<Lock>,
}

struct Lock {
    config: Config,
    scheduler: Scheduler,
}

impl binder::Interface for ProfcollectdBinderService {}

impl IProfCollectd for ProfcollectdBinderService {
    fn schedule(&self) -> BinderResult<()> {
        let lock = &mut *self.lock();
        lock.scheduler
            .schedule_periodic(&lock.config)
            .context("Failed to schedule collection.")
            .map_err(err_to_binder_status)
    }
    fn terminate(&self) -> BinderResult<()> {
        self.lock()
            .scheduler
            .terminate_periodic()
            .context("Failed to terminate collection.")
            .map_err(err_to_binder_status)
    }
    fn trace_system(&self, tag: &str) -> BinderResult<()> {
        let lock = &mut *self.lock();
        lock.scheduler
            .trace_system(&lock.config, tag)
            .context("Failed to perform system-wide trace.")
            .map_err(err_to_binder_status)
    }
    fn trace_process(&self, tag: &str, process: &str, duration: f32) -> BinderResult<()> {
        let lock = &mut *self.lock();
        lock.scheduler
            .trace_process(&lock.config, tag, process, duration)
            .context("Failed to perform process trace.")
            .map_err(err_to_binder_status)
    }
    fn process(&self) -> BinderResult<()> {
        let lock = &mut *self.lock();
        lock.scheduler
            .process(&lock.config)
            .context("Failed to process profiles.")
            .map_err(err_to_binder_status)
    }
    fn report(&self, usage_setting: i32) -> BinderResult<String> {
        self.process()?;

        let lock = &mut *self.lock();
        pack_report(&PROFILE_OUTPUT_DIR, &REPORT_OUTPUT_DIR, &lock.config, usage_setting)
            .context("Failed to create profile report.")
            .map_err(err_to_binder_status)
    }
    fn get_supported_provider(&self) -> BinderResult<String> {
        Ok(self.lock().scheduler.get_trace_provider_name().to_string())
    }

    fn registerProviderStatusCallback(
        &self,
        cb: &binder::Strong<(dyn IProviderStatusCallback)>,
    ) -> BinderResult<()> {
        if self.lock().scheduler.is_provider_ready() {
            if let Err(e) = cb.onProviderReady() {
                log::error!("Failed to call ProviderStatusCallback {:?}", e);
            }
            return Ok(());
        }

        let cb_binder: SpIBinder = cb.as_binder();
        self.lock().scheduler.register_provider_ready_callback(Box::new(move || {
            if let Ok(cb) = cb_binder.into_interface::<dyn IProviderStatusCallback>() {
                if let Err(e) = cb.onProviderReady() {
                    log::error!("Failed to call ProviderStatusCallback {:?}", e)
                }
            } else {
                log::error!("SpIBinder is not a IProviderStatusCallback.");
            }
        }));
        Ok(())
    }
}

impl ProfcollectdBinderService {
    pub fn new() -> Result<Self> {
        let new_scheduler = Scheduler::new()?;
        let new_config = Config::from_env()?;

        let config_changed = read_to_string(*CONFIG_FILE)
            .ok()
            .and_then(|s| Config::from_str(&s).ok())
            .filter(|c| new_config == *c)
            .is_none();

        if config_changed {
            log::info!("Config change detected, resetting profcollect.");
            clear_data()?;

            write(*CONFIG_FILE, new_config.to_string())?;
            new_scheduler.clear_trace_log()?;
        }

        // Clear profile reports out of rentention period.
        for report in read_dir(*REPORT_OUTPUT_DIR)? {
            let report = report?.path();
            let report_name = report
                .file_stem()
                .and_then(|f| f.to_str())
                .ok_or_else(|| anyhow!("Malformed path {}", report.display()))?;
            let report_ts = get_report_ts(report_name);
            if let Err(e) = report_ts {
                log::error!(
                    "Cannot decode creation timestamp for report {}, caused by {}, deleting",
                    report_name,
                    e
                );
                remove_file(report)?;
                continue;
            }
            let report_age = report_ts.unwrap().elapsed()?;
            if report_age > Duration::from_secs(REPORT_RETENTION_SECS) {
                log::info!("Report {} past rentention period, deleting", report_name);
                remove_file(report)?;
            }
        }

        Ok(ProfcollectdBinderService {
            lock: Mutex::new(Lock { scheduler: new_scheduler, config: new_config }),
        })
    }

    fn lock(&self) -> MutexGuard<Lock> {
        self.lock.lock().unwrap()
    }
}
