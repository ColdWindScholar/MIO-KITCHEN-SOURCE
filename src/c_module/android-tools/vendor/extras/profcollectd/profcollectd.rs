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

//! Daemon program to collect system traces.

use anyhow::{bail, Result};
use std::env;

const HELP_MSG: &str = r#"
profcollectd background daemon.
usage: profcollectd [command]
    nostart       Start daemon but do not schedule profile collection.
"#;

fn main() -> Result<()> {
    libprofcollectd::init_logging();

    let args: Vec<String> = env::args().collect();
    if args.len() > 2 {
        bail!("This program only takes one or no argument{}", &HELP_MSG);
    }
    if args.len() == 1 {
        libprofcollectd::init_service(true)?;
    }

    let action = &args[1];
    match action.as_str() {
        "nostart" => libprofcollectd::init_service(false)?,
        "help" => println!("{}", &HELP_MSG),
        arg => bail!("Unknown argument: {}\n{}", &arg, &HELP_MSG),
    }
    Ok(())
}
