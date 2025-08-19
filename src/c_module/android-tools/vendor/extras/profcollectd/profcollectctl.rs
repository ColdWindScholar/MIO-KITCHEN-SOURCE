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

//! Command to control profcollectd behaviour.

use anyhow::{bail, Context, Result};
use std::env;

const HELP_MSG: &str = r#"
usage: profcollectctl [command]

Command to control profcollectd behaviour.

command:
    start       Schedule periodic collection.
    stop        Terminate periodic collection.
    trace       Request an one-off system-wide trace.
    process     Convert traces to perf profiles.
    reconfig    Refresh configuration.
    report      Create a report containing all profiles.
    reset       Clear all local data.
    help        Print this message.
"#;

fn main() -> Result<()> {
    libprofcollectd::init_logging();

    let args: Vec<String> = env::args().collect();
    if args.len() != 2 {
        bail!("This program only takes one argument{}", &HELP_MSG);
    }

    let action = &args[1];
    match action.as_str() {
        "start" => {
            println!("Scheduling profile collection");
            libprofcollectd::schedule().context("Failed to schedule collection.")?;
        }
        "stop" => {
            println!("Terminating profile collection");
            libprofcollectd::terminate().context("Failed to terminate collection.")?;
        }
        "trace" => {
            println!("Performing system-wide trace");
            libprofcollectd::trace_system("manual").context("Failed to trace.")?;
        }
        "process" => {
            println!("Processing traces");
            libprofcollectd::process().context("Failed to process traces.")?;
        }
        "report" => {
            println!("Creating profile report");
            let path = libprofcollectd::report().context("Failed to create profile report.")?;
            println!("Report created at: {}", &path);
        }
        "reset" => {
            libprofcollectd::reset().context("Failed to reset.")?;
            println!("Reset done.");
        }
        "help" => println!("{}", &HELP_MSG),
        arg => bail!("Unknown argument: {}\n{}", &arg, &HELP_MSG),
    }
    Ok(())
}
