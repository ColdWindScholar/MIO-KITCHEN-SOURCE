/*
 * Copyright (C) 2020 The Android Open Source Project
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

#pragma once

#include <string>
#include <vector>

#include "RecordFilter.h"
#include "command.h"

namespace simpleperf {

struct AddrFilter;

std::vector<AddrFilter> ParseAddrFilterOption(const std::string& s);

inline const OptionFormatMap& GetRecordCmdOptionFormats() {
  static OptionFormatMap option_formats;
  if (option_formats.empty()) {
    option_formats = {
        {"-a", {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::NOT_ALLOWED}},
        {"--add-counter", {OptionValueType::STRING, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--add-meta-info",
         {OptionValueType::STRING, OptionType::MULTIPLE, AppRunnerType::ALLOWED}},
        {"--addr-filter", {OptionValueType::STRING, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--app", {OptionValueType::STRING, OptionType::SINGLE, AppRunnerType::NOT_ALLOWED}},
        {"--aux-buffer-size", {OptionValueType::UINT, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"-b", {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--binary", {OptionValueType::STRING, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"-c", {OptionValueType::UINT, OptionType::ORDERED, AppRunnerType::ALLOWED}},
        {"--call-graph", {OptionValueType::STRING, OptionType::ORDERED, AppRunnerType::ALLOWED}},
        {"--callchain-joiner-min-matching-nodes",
         {OptionValueType::UINT, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--clockid", {OptionValueType::STRING, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--cpu", {OptionValueType::STRING, OptionType::ORDERED, AppRunnerType::ALLOWED}},
        {"--cpu-percent", {OptionValueType::UINT, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--cycle-threshold", {OptionValueType::UINT, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--decode-etm", {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--delay", {OptionValueType::UINT, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--etm-flush-interval",
         {OptionValueType::UINT, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--record-timestamp", {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--record-cycles", {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--duration", {OptionValueType::DOUBLE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"-e", {OptionValueType::STRING, OptionType::ORDERED, AppRunnerType::ALLOWED}},
        {"--exclude-perf", {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--exit-with-parent", {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"-f", {OptionValueType::UINT, OptionType::ORDERED, AppRunnerType::ALLOWED}},
        {"-g", {OptionValueType::NONE, OptionType::ORDERED, AppRunnerType::ALLOWED}},
        {"--group", {OptionValueType::STRING, OptionType::ORDERED, AppRunnerType::ALLOWED}},
        {"--in-app", {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"-j", {OptionValueType::STRING, OptionType::MULTIPLE, AppRunnerType::ALLOWED}},
        {"--keep-failed-unwinding-result",
         {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--keep-failed-unwinding-debug-info",
         {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::NOT_ALLOWED}},
        {"--kprobe", {OptionValueType::STRING, OptionType::MULTIPLE, AppRunnerType::NOT_ALLOWED}},
        {"-m", {OptionValueType::UINT, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--no-callchain-joiner",
         {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--no-cut-samples", {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--no-dump-kernel-symbols",
         {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--no-dump-symbols", {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--no-inherit", {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--no-unwind", {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::NOT_ALLOWED}},
        {"-o", {OptionValueType::STRING, OptionType::SINGLE, AppRunnerType::NOT_ALLOWED}},
        {"--out-fd", {OptionValueType::UINT, OptionType::SINGLE, AppRunnerType::CHECK_FD}},
        {"-p", {OptionValueType::STRING, OptionType::MULTIPLE, AppRunnerType::ALLOWED}},
        {"--post-unwind", {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--post-unwind=no", {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--post-unwind=yes", {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--user-buffer-size", {OptionValueType::UINT, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--size-limit", {OptionValueType::UINT, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--start_profiling_fd",
         {OptionValueType::UINT, OptionType::SINGLE, AppRunnerType::CHECK_FD}},
        {"--stdio-controls-profiling",
         {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--stop-signal-fd", {OptionValueType::UINT, OptionType::SINGLE, AppRunnerType::CHECK_FD}},
        {"--symfs", {OptionValueType::STRING, OptionType::SINGLE, AppRunnerType::CHECK_PATH}},
        {"-t", {OptionValueType::STRING, OptionType::MULTIPLE, AppRunnerType::ALLOWED}},
        {"--tp-filter", {OptionValueType::STRING, OptionType::ORDERED, AppRunnerType::ALLOWED}},
        {"--trace-offcpu", {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
        {"--tracepoint-events",
         {OptionValueType::STRING, OptionType::SINGLE, AppRunnerType::CHECK_PATH}},
        {"--use-cmd-exit-code",
         {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::NOT_ALLOWED}},
        {"-z",
         {OptionValueType::OPT_STRING_AFTER_EQUAL, OptionType::SINGLE, AppRunnerType::ALLOWED}},
    };
    OptionFormatMap record_filter_options = GetRecordFilterOptionFormats(true);
    option_formats.insert(record_filter_options.begin(), record_filter_options.end());
  }
  return option_formats;
}

}  // namespace simpleperf
