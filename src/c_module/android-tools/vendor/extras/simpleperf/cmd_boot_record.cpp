/*
 * Copyright (C) 2022 The Android Open Source Project
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

#include <sys/stat.h>

#include <android-base/properties.h>
#include <android-base/stringprintf.h>
#include <android-base/strings.h>

#include "cmd_record_impl.h"
#include "command.h"
#include "utils.h"
#include "workload.h"

namespace simpleperf {
namespace {

enum class Action {
  NONE,
  ENABLE,
  DISABLE,
  RECORD,
};

const std::string RECORD_OUT_DIR = "/data/simpleperf_boot_data";

class BootRecordCommand : public Command {
 public:
  BootRecordCommand()
      : Command(
            "boot-record", "record at boot time",
            // clang-format off
"Usage: simpleperf boot-record [options]\n"
"    Record boot-time profiles. Only supported on userdebug/eng build. The record file will be\n"
"    stored in /data/simpleperf_boot_data.\n"
"--enable <record_options>  Enable boot time recording. Record options are options passed\n"
"                           to simpleperf record cmd, like \"-a -g --duration 10\".\n"
"--disable                  Disable record at boot time.\n"
#if 0
// The following option is only used internally.
"--record <record_options>  Record with record options.\n"
#endif
            // clang-format on
        ) {
  }

  bool Run(const std::vector<std::string>& args);

 private:
  bool ParseOptions(const std::vector<std::string>& args);
  bool SetRecordOptions(const std::string& record_options);
  bool CheckRecordOptions(const std::string& record_options);
  bool CreateOutDir();
  bool Record();
  std::string GetDefaultOutputFilename();

  Action action_ = Action::NONE;
  std::string record_options_;
};

bool BootRecordCommand::Run(const std::vector<std::string>& args) {
  if (!ParseOptions(args)) {
    return false;
  }
  if (action_ == Action::ENABLE) {
    if (!CheckRecordOptions(record_options_) || !SetRecordOptions(record_options_) ||
        !CreateOutDir()) {
      return false;
    }
    LOG(INFO) << "After boot, boot profile will be stored in " << RECORD_OUT_DIR;
    return true;
  }
  if (action_ == Action::DISABLE) {
    return SetRecordOptions("");
  }
  if (action_ == Action::RECORD) {
    return Record();
  }
  return true;
}

bool BootRecordCommand::ParseOptions(const std::vector<std::string>& args) {
  const OptionFormatMap option_formats = {
      {"--enable", {OptionValueType::STRING, OptionType::SINGLE}},
      {"--disable", {OptionValueType::NONE, OptionType::SINGLE}},
      {"--record", {OptionValueType::STRING, OptionType::SINGLE}},
  };
  OptionValueMap options;
  std::vector<std::pair<OptionName, OptionValue>> ordered_options;
  std::vector<std::string> non_option_args;
  if (!PreprocessOptions(args, option_formats, &options, &ordered_options, &non_option_args)) {
    return false;
  }
  if (auto value = options.PullValue("--enable"); value) {
    action_ = Action::ENABLE;
    record_options_ = value->str_value;
  } else if (options.PullBoolValue("--disable")) {
    action_ = Action::DISABLE;
  } else if (auto value = options.PullValue("--record"); value) {
    action_ = Action::RECORD;
    record_options_ = value->str_value;
  }
  return true;
}

bool BootRecordCommand::SetRecordOptions(const std::string& record_options) {
  const std::string prop_name = "persist.simpleperf.boot_record";
  if (!android::base::SetProperty(prop_name, record_options)) {
    LOG(ERROR) << "Failed to SetProperty " << prop_name << " to \"" << record_options << "\"";
    return false;
  }
  return true;
}

bool BootRecordCommand::CheckRecordOptions(const std::string& record_options) {
  std::vector<std::string> args = android::base::Split(record_options, " ");

  OptionValueMap options;
  std::vector<std::pair<OptionName, OptionValue>> ordered_options;
  std::vector<std::string> non_option_args;
  if (!PreprocessOptions(args, GetRecordCmdOptionFormats(), &options, &ordered_options,
                         &non_option_args)) {
    LOG(ERROR) << "Invalid record options.";
    return false;
  }
  if (!non_option_args.empty()) {
    LOG(ERROR) << "Running child command isn't allowed";
    return false;
  }
  if (auto value = options.PullValue("-o"); value) {
    LOG(ERROR) << "-o option isn't allowed. The output file is stored in " << RECORD_OUT_DIR;
    return false;
  }
  return true;
}

bool BootRecordCommand::CreateOutDir() {
  if (!IsDir(RECORD_OUT_DIR)) {
    if (mkdir(RECORD_OUT_DIR.c_str(), 0775) != 0) {
      PLOG(ERROR) << "failed to create dir " << RECORD_OUT_DIR;
      return false;
    }
    return Workload::RunCmd(
        {"chcon", "u:object_r:simpleperf_boot_data_file:s0", "/data/simpleperf_boot_data"});
  }
  return true;
}

bool BootRecordCommand::Record() {
  if (!CheckRecordOptions(record_options_)) {
    return false;
  }

  std::vector<std::string> args = android::base::Split(record_options_, " ");
  std::string output_file = RECORD_OUT_DIR + "/" + GetDefaultOutputFilename();
  args.emplace_back("-o");
  args.emplace_back(output_file);
  std::unique_ptr<Command> record_cmd = CreateCommandInstance("record");
  CHECK(record_cmd != nullptr);
  return record_cmd->Run(args);
}

std::string BootRecordCommand::GetDefaultOutputFilename() {
  time_t t = time(nullptr);
  struct tm tm;
  if (localtime_r(&t, &tm) != &tm) {
    return "perf.data";
  }
  return android::base::StringPrintf("perf-%04d%02d%02d-%02d-%02d-%02d.data", tm.tm_year + 1900,
                                     tm.tm_mon + 1, tm.tm_mday, tm.tm_hour, tm.tm_min, tm.tm_sec);
}

}  // namespace

void RegisterBootRecordCommand() {
  RegisterCommand("boot-record", [] { return std::unique_ptr<Command>(new BootRecordCommand); });
}

}  // namespace simpleperf
