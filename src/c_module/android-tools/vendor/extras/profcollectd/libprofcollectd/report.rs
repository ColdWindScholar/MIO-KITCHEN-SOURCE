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

//! Pack profiles into reports.

use anyhow::{anyhow, Result};
use macaddr::MacAddr6;
use std::fs::{self, File, Permissions};
use std::io::{Read, Write};
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};
use std::time::{Duration, SystemTime};
use uuid::v1::{Context, Timestamp};
use uuid::Uuid;
use zip::write::FileOptions;
use zip::CompressionMethod::Deflated;
use zip::ZipWriter;

use crate::config::{clear_processed_files, Config};

pub const NO_USAGE_SETTING: i32 = -1;

pub static UUID_CONTEXT: Context = Context::new(0);

pub fn pack_report(
    profile: &Path,
    report: &Path,
    config: &Config,
    usage_setting: i32,
) -> Result<String> {
    let mut report = PathBuf::from(report);
    let report_filename = get_report_filename(&config.node_id)?;
    report.push(&report_filename);
    report.set_extension("zip");

    // Remove the current report file if exists.
    fs::remove_file(&report).ok();

    let report_file = fs::OpenOptions::new().create_new(true).write(true).open(&report)?;

    // Set report file ACL bits to 644, so that this can be shared to uploaders.
    // Who has permission to actually read the file is protected by SELinux policy.
    fs::set_permissions(&report, Permissions::from_mode(0o644))?;

    let options = FileOptions::default().compression_method(Deflated);
    let mut zip = ZipWriter::new(report_file);

    fs::read_dir(profile)?
        .filter_map(|e| e.ok())
        .map(|e| e.path())
        .filter(|e| e.is_file())
        .try_for_each(|e| -> Result<()> {
            let filename = e
                .file_name()
                .and_then(|f| f.to_str())
                .ok_or_else(|| anyhow!("Malformed profile path: {}", e.display()))?;
            zip.start_file(filename, options)?;
            let mut f = File::open(e)?;
            let mut buffer = Vec::new();
            f.read_to_end(&mut buffer)?;
            zip.write_all(&buffer)?;
            Ok(())
        })?;

    if usage_setting != NO_USAGE_SETTING {
        zip.start_file("usage_setting", options)?;
        zip.write_all(usage_setting.to_string().as_bytes())?;
    }
    zip.finish()?;
    clear_processed_files()?;

    Ok(report_filename)
}

fn get_report_filename(node_id: &MacAddr6) -> Result<String> {
    let since_epoch = SystemTime::now().duration_since(SystemTime::UNIX_EPOCH)?;
    let ts = Timestamp::from_unix(&UUID_CONTEXT, since_epoch.as_secs(), since_epoch.subsec_nanos());
    let uuid = Uuid::new_v1(
        ts,
        node_id.as_bytes().try_into().expect("Invalid number of bytes in V1 UUID"),
    );
    Ok(uuid.to_string())
}

/// Get report creation timestamp through its filename (version 1 UUID).
pub fn get_report_ts(filename: &str) -> Result<SystemTime> {
    let uuid_ts = Uuid::parse_str(filename)?
        .get_timestamp()
        .ok_or_else(|| anyhow!("filename is not a valid V1 UUID."))?
        .to_unix();
    Ok(SystemTime::UNIX_EPOCH + Duration::new(uuid_ts.0, uuid_ts.1))
}
