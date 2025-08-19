/*
 * Copyright (C) 2016 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

// The bootio tool provides options to collect I/O stats for processes during boot.

#include <vector>
#include <getopt.h>
#include <unistd.h>
#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/strings.h>
#include <log/log.h>

#include "bootio_collector.h"

namespace android {

#define LOG_ROOT           "/data/misc/bootio"
#define LOG_START_FILE      LOG_ROOT"/start"
#define SELF_IO            "/proc/self/io"

static const int LOG_TIMEOUT_INDEX = 0;
static const int LOG_SAMPLES_INDEX = 1;
static const int LOG_MAX_TIMEOUT = 120;
static const int LOG_MAX_SAMPLES = 30;

void ShowHelp(const char *cmd) {
    fprintf(stderr, "Usage: %s [options]\n", cmd);
    fprintf(stderr,
            "options include:\n"
                    "  -h, --help            Show this help\n"
                    "  -p, --print           Dump the boot io data to the console\n"
                    "\nNo options will start data collection process.\n");
}

void PrintBootIo() {
    printf("Boot I/O:\n");
    printf("------------\n");
    std::unique_ptr <BootioCollector> collector(new BootioCollector(LOG_ROOT));
    if (collector.get() == NULL) {
        LOG(ERROR) << "Failed to create data collector";
        return;
    }
    collector->Print();
}

void StartDataCollection() {
    if (access(SELF_IO, F_OK) == -1) {
        LOG(ERROR) << "Kernel doesn't support I/O profiling.";
        printf("Kernel doesn't support I/O profiling.");
        return;
    }

    int timeout = 0;
    int samples = 0;

    std::string start;
    android::base::ReadFileToString(LOG_START_FILE, &start);

    if (!start.empty()) {
        std::vector <std::string> components = android::base::Split(start, " ");
        if (components.size() != 2) {
            LOG(ERROR) << "Invalid value in start file." << start;
            return;
        }
        timeout = atoi(components.at(LOG_TIMEOUT_INDEX).c_str());
        samples = atoi(components.at(LOG_SAMPLES_INDEX).c_str());
    } else {
        LOG(INFO) << "No profiling requested. Exiting";
        printf("Boot I/O: no profiling requested. Exiting.\n");
        return;
    }
    if (timeout <= 0 || samples <= 0) {
        LOG(ERROR) << "Boot I/O: failed to parse string:" << start;
        printf("Boot I/O: failed to parse string: %s\n", start.c_str());
        return;
    }
    if (samples > timeout || samples > LOG_MAX_SAMPLES || timeout > LOG_MAX_TIMEOUT) {
        LOG(ERROR) << "Bad values for bootio. timeout=" << timeout <<
        " samples=" << samples << " Max timeout=" << LOG_MAX_TIMEOUT <<
        " Max samples=" << LOG_MAX_SAMPLES;
        return;
    }
    LOG(INFO) << "Boot I/O: collecting data. samples=" << samples << "timeout=" << timeout;
    printf("Boot I/O: collecting data\ntimeout=%d, samples=%d\n",
           timeout, samples);
    std::unique_ptr <BootioCollector> collector(new BootioCollector(LOG_ROOT));
    if (collector.get() == NULL) {
        LOG(ERROR) << "Failed to create data collector";
        return;
    }
    collector->StartDataCollection(timeout, samples);
}

}

int main(int argc, char **argv) {
    android::base::InitLogging(argv);

    LOG(INFO) << "Bootio started";

    int optionIndex = 0;
    static const struct option longOptions[] = {
            {"help",  no_argument, NULL, 'h'},
            {"print", no_argument, NULL, 'p'},
            {NULL,    0,           NULL, 0}
    };

    int opt = 0;
    bool startCollection = true;
    while ((opt = getopt_long(argc, argv, "hlpr:", longOptions, &optionIndex)) != -1) {
        switch (opt) {
            case 0: {
                const std::string option_name = longOptions[optionIndex].name;
                LOG(ERROR) << "Invalid option: " << option_name;
                break;
            }

            case 'h': {
                android::ShowHelp(argv[0]);
                startCollection = false;
                break;
            }

            case 'p': {
                android::PrintBootIo();
                startCollection = false;
                break;
            }

            default: {
                DCHECK_EQ(opt, '?');

                // |optopt| is an external variable set by getopt representing
                // the value of the invalid option.
                LOG(ERROR) << "Invalid option: " << optopt;
                android::ShowHelp(argv[0]);
                return EXIT_FAILURE;
            }
        }
    }

    if (startCollection) {
        android::StartDataCollection();
    }

    return 0;
}

