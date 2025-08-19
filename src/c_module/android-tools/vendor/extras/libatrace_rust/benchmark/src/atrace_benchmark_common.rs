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

//! Utilities to benchmark ATrace in Rust.

use criterion::Criterion;

// We could use bindgen to generate these bindings automatically but the signatures are simple and
// we don't expect them to change much (if at all). So we specify them manually and skip having an
// intermediate target.
extern "C" {
    fn disable_app_atrace();
    fn enable_atrace_for_single_app(name: *const std::os::raw::c_char);
}

/// Disables ATrace for all apps (ATRACE_TAG_APP).
pub fn turn_tracing_off() {
    // SAFETY: This call is always safe.
    unsafe {
        disable_app_atrace();
    }
}

/// Enables ATrace for this app.
pub fn turn_tracing_on() {
    // ATrace uses command line for per-process tracing control, so env::current_exe won't work.
    let procname = std::ffi::CString::new(std::env::args().next().unwrap()).unwrap();
    // SAFETY: `procname` is a valid C string and the function doesn't store it after it returns.
    unsafe {
        enable_atrace_for_single_app(procname.as_ptr());
    }
}

/// Creates a new configured instance of Criterion for benchmarking.
pub fn new_criterion() -> Criterion {
    let path = "/data/local/tmp/criterion/benchmarks";
    std::fs::create_dir_all(path).unwrap_or_else(|e| {
        panic!("The criterion folder should be possible to create at {}: {}", path, e)
    });
    std::env::set_var("CRITERION_HOME", path);
    Criterion::default()
}
