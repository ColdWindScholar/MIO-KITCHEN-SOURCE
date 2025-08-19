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

//! ProfCollect configurations.

use anyhow::Result;
use macaddr::MacAddr6;
use once_cell::sync::Lazy;
use rand::Rng;
use serde::{Deserialize, Serialize};
use std::error::Error;
use std::fs::{read_dir, remove_file};
use std::path::Path;
use std::process::Command;
use std::str::FromStr;
use std::time::Duration;

const PROFCOLLECT_CONFIG_NAMESPACE: &str = "aconfig_flags.profcollect_native_boot";
const PROFCOLLECT_NODE_ID_PROPERTY: &str = "persist.profcollectd.node_id";

const DEFAULT_BINARY_FILTER: &str = "(^/(system|apex/.+|vendor)/(bin|lib64)/.+)|\
    (^/data/app/.+\\.so$)|kernel.kallsyms";
pub const REPORT_RETENTION_SECS: u64 = 14 * 24 * 60 * 60; // 14 days.

// Static configs that cannot be changed.
pub static TRACE_OUTPUT_DIR: Lazy<&'static Path> =
    Lazy::new(|| Path::new("/data/misc/profcollectd/trace/"));
pub static PROFILE_OUTPUT_DIR: Lazy<&'static Path> =
    Lazy::new(|| Path::new("/data/misc/profcollectd/output/"));
pub static REPORT_OUTPUT_DIR: Lazy<&'static Path> =
    Lazy::new(|| Path::new("/data/misc/profcollectd/report/"));
pub static CONFIG_FILE: Lazy<&'static Path> =
    Lazy::new(|| Path::new("/data/misc/profcollectd/output/config.json"));
pub static LOG_FILE: Lazy<&'static Path> =
    Lazy::new(|| Path::new("/data/misc/profcollectd/output/trace.log"));

/// Dynamic configs, stored in config.json.
#[derive(Clone, PartialEq, Eq, Serialize, Deserialize, Debug)]
pub struct Config {
    /// Version of config file scheme, always equals to 1.
    version: u32,
    /// Application specific node ID.
    pub node_id: MacAddr6,
    /// Device build fingerprint.
    pub build_fingerprint: String,
    /// Interval between collections.
    pub collection_interval: Duration,
    /// An optional filter to limit which binaries to or not to profile.
    pub binary_filter: String,
    /// Maximum size of the trace directory.
    pub max_trace_limit_mb: u64,
    /// The kernel release version
    pub kernel_release: String,
}

impl Config {
    pub fn from_env() -> Result<Self> {
        Ok(Config {
            version: 1,
            node_id: get_or_initialise_node_id()?,
            build_fingerprint: get_build_fingerprint()?,
            collection_interval: Duration::from_secs(get_device_config(
                "collection_interval",
                600,
            )?),
            binary_filter: get_device_config("binary_filter", DEFAULT_BINARY_FILTER.to_string())?,
            max_trace_limit_mb: get_device_config("max_trace_limit_mb", 768)?,
            kernel_release: get_kernel_release(),
        })
    }
}

impl std::fmt::Display for Config {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", serde_json::to_string(self).expect("Failed to deserialise configuration."))
    }
}

impl FromStr for Config {
    type Err = serde_json::Error;
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        serde_json::from_str::<Config>(s)
    }
}

fn get_or_initialise_node_id() -> Result<MacAddr6> {
    let mut node_id = get_property(PROFCOLLECT_NODE_ID_PROPERTY, MacAddr6::nil())?;
    if node_id.is_nil() {
        node_id = generate_random_node_id();
        set_property(PROFCOLLECT_NODE_ID_PROPERTY, node_id)?;
    }

    Ok(node_id)
}

fn get_build_fingerprint() -> Result<String> {
    get_property("ro.build.fingerprint", "unknown".to_string())
}

fn get_device_config<T>(key: &str, default_value: T) -> Result<T>
where
    T: FromStr + ToString,
    T::Err: Error + Send + Sync + 'static,
{
    let default_value = default_value.to_string();
    let config =
        flags_rust::GetServerConfigurableFlag(PROFCOLLECT_CONFIG_NAMESPACE, key, &default_value);
    Ok(T::from_str(&config)?)
}

pub fn get_sampling_period() -> Duration {
    let default_period = 1500;
    Duration::from_millis(
        get_device_config("sampling_period", default_period).unwrap_or(default_period),
    )
}

fn get_property<T>(key: &str, default_value: T) -> Result<T>
where
    T: FromStr + ToString,
    T::Err: Error + Send + Sync + 'static,
{
    let default_value = default_value.to_string();
    let value = rustutils::system_properties::read(key).unwrap_or(None).unwrap_or(default_value);
    Ok(T::from_str(&value)?)
}

fn set_property<T>(key: &str, value: T) -> Result<()>
where
    T: ToString,
{
    let value = value.to_string();
    Ok(rustutils::system_properties::write(key, &value)?)
}

fn generate_random_node_id() -> MacAddr6 {
    let mut node_id = rand::thread_rng().gen::<[u8; 6]>();
    node_id[0] |= 0x1;
    MacAddr6::from(node_id)
}

fn get_kernel_release() -> String {
    match Command::new("uname").args(["-r"]).output() {
        Ok(output) if output.status.success() => {
            String::from_utf8_lossy(&output.stdout).trim().to_string()
        }
        _ => String::new(),
    }
}

pub fn clear_data() -> Result<()> {
    fn remove_files(path: &Path) -> Result<()> {
        read_dir(path)?
            .filter_map(|e| e.ok())
            .map(|e| e.path())
            .filter(|e| e.is_file() && e != *LOG_FILE)
            .try_for_each(remove_file)?;
        Ok(())
    }

    remove_files(&TRACE_OUTPUT_DIR)?;
    remove_files(&PROFILE_OUTPUT_DIR)?;
    remove_files(&REPORT_OUTPUT_DIR)?;
    Ok(())
}
pub fn clear_processed_files() -> Result<()> {
    read_dir(&PROFILE_OUTPUT_DIR as &Path)?
        .filter_map(|e| e.ok())
        .map(|e| e.path())
        .filter(|e| e.is_file() && e != (&CONFIG_FILE as &Path))
        .try_for_each(remove_file)?;
    Ok(())
}
