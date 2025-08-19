// Copyright 2021, The Android Open Source Project
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

//! Provides a universal logger interface that allows logging both on-device (using android_logger)
//! and on-host (using env_logger).
//! On-host, this allows the use of the RUST_LOG environment variable as documented in
//! https://docs.rs/env_logger.
use std::ffi::CString;
use std::sync::atomic::{AtomicBool, Ordering};

static LOGGER_INITIALIZED: AtomicBool = AtomicBool::new(false);

type FormatFn = Box<dyn Fn(&log::Record) -> String + Sync + Send>;

/// Logger configuration, opportunistically mapped to configuration parameters for android_logger
/// or env_logger where available.
#[derive(Default)]
pub struct Config<'a> {
    log_level: Option<log::LevelFilter>,
    custom_format: Option<FormatFn>,
    filter: Option<&'a str>,
    #[allow(dead_code)] // Field is only used on device, and ignored on host.
    tag: Option<CString>,
}

/// Based on android_logger::Config
impl<'a> Config<'a> {
    /// Changes the maximum log level.
    ///
    /// Note, that `Trace` is the maximum level, because it provides the
    /// maximum amount of detail in the emitted logs.
    ///
    /// If `Off` level is provided, then nothing is logged at all.
    ///
    /// [`log::max_level()`] is considered as the default level.
    pub fn with_max_level(mut self, level: log::LevelFilter) -> Self {
        self.log_level = Some(level);
        self
    }

    /// Set a log tag. Only used on device.
    pub fn with_tag_on_device<S: Into<Vec<u8>>>(mut self, tag: S) -> Self {
        self.tag = Some(CString::new(tag).expect("Can't convert tag to CString"));
        self
    }

    /// Set the format function for formatting the log output.
    /// ```
    /// # use universal_logger::Config;
    /// universal_logger::init(
    ///     Config::default()
    ///         .with_max_level(log::LevelFilter::Trace)
    ///         .format(|record| format!("my_app: {}", record.args()))
    /// )
    /// ```
    pub fn format<F>(mut self, format: F) -> Self
    where
        F: Fn(&log::Record) -> String + Sync + Send + 'static,
    {
        self.custom_format = Some(Box::new(format));
        self
    }

    /// Set a filter, using the format specified in https://docs.rs/env_logger.
    pub fn with_filter(mut self, filter: &'a str) -> Self {
        self.filter = Some(filter);
        self
    }
}

/// Initializes logging on host. Returns false if logging is already initialized.
/// Config values take precedence over environment variables for host logging.
#[cfg(not(target_os = "android"))]
pub fn init(config: Config) -> bool {
    // Return immediately if the logger is already initialized.
    if LOGGER_INITIALIZED.fetch_or(true, Ordering::SeqCst) {
        return false;
    }

    let mut builder = env_logger::Builder::from_default_env();
    if let Some(log_level) = config.log_level {
        builder.filter_level(log_level);
    }
    if let Some(custom_format) = config.custom_format {
        use std::io::Write; // Trait used by write!() macro, but not in Android code

        builder.format(move |f, r| {
            let formatted = custom_format(r);
            writeln!(f, "{}", formatted)
        });
    }
    if let Some(filter_str) = config.filter {
        builder.parse_filters(filter_str);
    }

    builder.init();
    true
}

/// Initializes logging on device. Returns false if logging is already initialized.
#[cfg(target_os = "android")]
pub fn init(config: Config) -> bool {
    // Return immediately if the logger is already initialized.
    if LOGGER_INITIALIZED.fetch_or(true, Ordering::SeqCst) {
        return false;
    }

    // We do not have access to the private variables in android_logger::Config, so we have to use
    // the builder instead.
    let mut builder = android_logger::Config::default();
    if let Some(log_level) = config.log_level {
        builder = builder.with_max_level(log_level);
    }
    if let Some(custom_format) = config.custom_format {
        builder = builder.format(move |f, r| {
            let formatted = custom_format(r);
            write!(f, "{}", formatted)
        });
    }
    if let Some(filter_str) = config.filter {
        let filter = env_logger::filter::Builder::new().parse(filter_str).build();
        builder = builder.with_filter(filter);
    }
    if let Some(tag) = config.tag {
        builder = builder.with_tag(tag);
    }

    android_logger::init_once(builder);
    true
}

/// Note that the majority of tests checking behavior are under the tests/ folder, as they all
/// require independent initialization steps. The local test module just performs some basic crash
/// testing without performing initialization.
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_with_max_level() {
        let config = Config::default()
            .with_max_level(log::LevelFilter::Trace)
            .with_max_level(log::LevelFilter::Error);

        assert_eq!(config.log_level, Some(log::LevelFilter::Error));
    }

    #[test]
    fn test_with_filter() {
        let filter = "debug,hello::crate=trace";
        let config = Config::default().with_filter(filter);

        assert_eq!(config.filter.unwrap(), filter)
    }

    #[test]
    fn test_with_tag_on_device() {
        let config = Config::default().with_tag_on_device("my_app");

        assert_eq!(config.tag.unwrap(), CString::new("my_app").unwrap());
    }

    #[test]
    fn test_format() {
        let config = Config::default().format(|record| format!("my_app: {}", record.args()));

        assert!(config.custom_format.is_some());
    }
}
