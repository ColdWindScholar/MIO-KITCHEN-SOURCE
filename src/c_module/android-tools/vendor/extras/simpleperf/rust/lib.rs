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

//! This module implements safe wrappers for simpleperf operations required
//! by profcollect.

use std::ffi::{c_char, CString};
use std::path::Path;

fn path_to_cstr(path: &Path) -> CString {
    CString::new(path.to_str().unwrap()).unwrap()
}

/// Returns whether the system has etm driver. ETM driver should be available immediately
/// after boot.
pub fn is_etm_driver_available() -> bool {
    // SAFETY: This is always safe to call.
    unsafe { simpleperf_profcollect_bindgen::IsETMDriverAvailable() }
}

/// Returns whether the system has etm device. ETM device may not be available immediately
/// after boot.
pub fn is_etm_device_available() -> bool {
    // SAFETY: This is always safe to call.
    unsafe { simpleperf_profcollect_bindgen::IsETMDeviceAvailable() }
}

/// Returns whether the system support LBR recording.
pub fn is_lbr_available() -> bool {
    // SAFETY: This is always safe to call.
    unsafe { simpleperf_profcollect_bindgen::IsLBRAvailable() }
}

/// Run the record command to record ETM/LBR data.
pub fn run_record_cmd(args: &[&str]) -> bool {
    let c_args: Vec<CString> = args.iter().map(|s| CString::new(s.as_bytes()).unwrap()).collect();
    let mut pointer_args: Vec<*const c_char> = c_args.iter().map(|s| s.as_ptr()).collect();
    let arg_count: i32 = pointer_args.len().try_into().unwrap();
    // SAFETY: pointer_args is an array of valid C strings. Its length is defined by arg_count.
    unsafe { simpleperf_profcollect_bindgen::RunRecordCmd(pointer_args.as_mut_ptr(), arg_count) }
}

/// Run the inject command to process ETM/LBR data.
pub fn run_inject_cmd(args: &[&str]) -> bool {
    let c_args: Vec<CString> = args.iter().map(|s| CString::new(s.as_bytes()).unwrap()).collect();
    let mut pointer_args: Vec<*const c_char> = c_args.iter().map(|s| s.as_ptr()).collect();
    let arg_count: i32 = pointer_args.len().try_into().unwrap();
    // SAFETY: pointer_args is an array of valid C strings. Its length is defined by arg_count.
    unsafe { simpleperf_profcollect_bindgen::RunInjectCmd(pointer_args.as_mut_ptr(), arg_count) }
}

/// Save logs in file.
pub fn set_log_file(filename: &Path) {
    let log_file = path_to_cstr(filename);
    // SAFETY: The pointer is a valid C string, and isn't retained after the function call returns.
    unsafe {
        simpleperf_profcollect_bindgen::SetLogFile(log_file.as_ptr());
    }
}

/// Stop using log file.
pub fn reset_log_file() {
    // SAFETY: This is always safe to call.
    unsafe {
        simpleperf_profcollect_bindgen::ResetLogFile();
    }
}
