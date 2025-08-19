/*
 * Copyright (C) 2015 The Android Open Source Project
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

#include "command.h"

#include <string.h>

#include <algorithm>
#include <map>
#include <string>
#include <vector>

#include <android-base/logging.h>
#include <android-base/parsedouble.h>
#include <android-base/parseint.h>

#include "utils.h"

namespace simpleperf {

bool Command::NextArgumentOrError(const std::vector<std::string>& args, size_t* pi) {
  if (*pi + 1 == args.size()) {
    LOG(ERROR) << "No argument following " << args[*pi] << " option. Try `simpleperf help " << name_
               << "`";
    return false;
  }
  ++*pi;
  return true;
}

bool ConvertArgsToOptions(const std::vector<std::string>& args,
                          const OptionFormatMap& option_formats, const std::string& help_msg,
                          OptionValueMap* options,
                          std::vector<std::pair<OptionName, OptionValue>>* ordered_options,
                          std::vector<std::string>* non_option_args) {
  options->values.clear();
  ordered_options->clear();
  size_t i;
  for (i = 0; i < args.size() && !args[i].empty() && args[i][0] == '-'; i++) {
    std::string value_after_equal;
    auto it = option_formats.find(args[i]);
    if (it == option_formats.end()) {
      if (auto pos = args[i].find("="); pos != std::string::npos) {
        value_after_equal = args[i].substr(pos + 1);
        it = option_formats.find(args[i].substr(0, pos));
      }
      if (it == option_formats.end()) {
        if (args[i] == "--") {
          i++;
          break;
        }
        LOG(ERROR) << "Unknown option " << args[i] << "." << help_msg;
        return false;
      }
    }
    const OptionName& name = it->first;
    const OptionFormat& format = it->second;
    OptionValue value;

    switch (format.value_type) {
      case OptionValueType::NONE:
        break;
      case OptionValueType::STRING:
        if (i + 1 == args.size()) {
          LOG(ERROR) << "No argument following " << name << " option." << help_msg;
          return false;
        }
        value.str_value = args[++i];
        break;
      case OptionValueType::OPT_STRING:
        if (i + 1 < args.size() && !args[i + 1].empty() && args[i + 1][0] != '-') {
          value.str_value = args[++i];
        }
        break;
      case OptionValueType::OPT_STRING_AFTER_EQUAL:
        value.str_value = value_after_equal;
        break;
      case OptionValueType::UINT:
        if (i + 1 == args.size()) {
          LOG(ERROR) << "No argument following " << name << " option." << help_msg;
          return false;
        }
        if (!android::base::ParseUint(args[++i], &value.uint_value,
                                      std::numeric_limits<uint64_t>::max(), true)) {
          LOG(ERROR) << "Invalid argument for option " << name << ": " << args[i] << "."
                     << help_msg;
          return false;
        }
        break;
      case OptionValueType::DOUBLE:
        if (i + 1 == args.size()) {
          LOG(ERROR) << "No argument following " << name << " option." << help_msg;
          return false;
        }
        if (!android::base::ParseDouble(args[++i], &value.double_value)) {
          LOG(ERROR) << "Invalid argument for option " << name << ": " << args[i] << "."
                     << help_msg;
          return false;
        }
        break;
    }

    switch (format.type) {
      case OptionType::SINGLE:
        if (auto it = options->values.find(name); it != options->values.end()) {
          it->second = value;
        } else {
          options->values.emplace(name, value);
        }
        break;
      case OptionType::MULTIPLE:
        options->values.emplace(name, value);
        break;
      case OptionType::ORDERED:
        ordered_options->emplace_back(name, value);
        break;
    }
  }
  if (i < args.size()) {
    if (non_option_args == nullptr) {
      LOG(ERROR) << "Invalid option " << args[i] << "." << help_msg;
      return false;
    }
    non_option_args->assign(args.begin() + i, args.end());
  }
  return true;
}

bool Command::PreprocessOptions(const std::vector<std::string>& args,
                                const OptionFormatMap& option_formats, OptionValueMap* options,
                                std::vector<std::pair<OptionName, OptionValue>>* ordered_options,
                                std::vector<std::string>* non_option_args) {
  const std::string help_msg = " Try `simpleperf help " + name_ + "`.";
  return ConvertArgsToOptions(args, option_formats, help_msg, options, ordered_options,
                              non_option_args);
}

bool Command::GetDoubleOption(const std::vector<std::string>& args, size_t* pi, double* value,
                              double min, double max) {
  if (!NextArgumentOrError(args, pi)) {
    return false;
  }
  if (!android::base::ParseDouble(args[*pi].c_str(), value, min, max)) {
    LOG(ERROR) << "Invalid argument for option " << args[*pi - 1] << ": " << args[*pi];
    return false;
  }
  return true;
}

void Command::ReportUnknownOption(const std::vector<std::string>& args, size_t i) {
  LOG(ERROR) << "Unknown option for " << name_ << " command: '" << args[i]
             << "'. Try `simpleperf help " << name_ << "`";
}

typedef std::function<std::unique_ptr<Command>(void)> callback_t;

static std::map<std::string, callback_t>& CommandMap() {
  // commands is used in the constructor of Command. Defining it as a static
  // variable in a function makes sure it is initialized before use.
  static std::map<std::string, callback_t> command_map;
  return command_map;
}

void RegisterCommand(const std::string& cmd_name,
                     const std::function<std::unique_ptr<Command>(void)>& callback) {
  CommandMap().insert(std::make_pair(cmd_name, callback));
}

void UnRegisterCommand(const std::string& cmd_name) {
  CommandMap().erase(cmd_name);
}

std::unique_ptr<Command> CreateCommandInstance(const std::string& cmd_name) {
  auto it = CommandMap().find(cmd_name);
  return (it == CommandMap().end()) ? nullptr : (it->second)();
}

const std::vector<std::string> GetAllCommandNames() {
  std::vector<std::string> names;
  for (const auto& pair : CommandMap()) {
    names.push_back(pair.first);
  }
  return names;
}

void RegisterAllCommands() {
  RegisterDumpRecordCommand();
  RegisterHelpCommand();
  RegisterInjectCommand();
  RegisterKmemCommand();
  RegisterMergeCommand();
  RegisterReportCommand();
  RegisterReportSampleCommand();
#if defined(__linux__)
  RegisterListCommand();
  RegisterRecordCommand();
  RegisterStatCommand();
  RegisterDebugUnwindCommand();
  RegisterTraceSchedCommand();
  RegisterMonitorCommand();
#if defined(__ANDROID__)
  RegisterAPICommands();
  RegisterBootRecordCommand();
#endif
#endif
}

static void StderrLogger(android::base::LogId, android::base::LogSeverity severity, const char*,
                         const char* file, unsigned int line, const char* message) {
  static const char log_characters[] = "VDIWEFF";
  char severity_char = log_characters[severity];
  fprintf(stderr, "simpleperf %c %s:%u] %s\n", severity_char, file, line, message);
}

bool log_to_android_buffer = false;

bool RunSimpleperfCmd(int argc, char** argv) {
  android::base::InitLogging(argv, StderrLogger);
  std::vector<std::string> args;
  android::base::LogSeverity log_severity = android::base::INFO;
  log_to_android_buffer = false;
  const OptionFormatMap& common_option_formats = GetCommonOptionFormatMap();

  int i;
  for (i = 1; i < argc && strcmp(argv[i], "--") != 0; ++i) {
    std::string option_name = argv[i];
    auto it = common_option_formats.find(option_name);
    if (it == common_option_formats.end()) {
      args.emplace_back(std::move(option_name));
      continue;
    }
    if (it->second.value_type != OptionValueType::NONE && i + 1 == argc) {
      LOG(ERROR) << "Missing argument for " << option_name;
      return false;
    }
    if (option_name == "-h" || option_name == "--help") {
      args.insert(args.begin(), "help");
    } else if (option_name == "--log") {
      if (!GetLogSeverity(argv[i + 1], &log_severity)) {
        LOG(ERROR) << "Unknown log severity: " << argv[i + 1];
      }
      ++i;
#if defined(__ANDROID__)
    } else if (option_name == "--log-to-android-buffer") {
      android::base::SetLogger(android::base::LogdLogger());
      log_to_android_buffer = true;
#endif
    } else if (option_name == "--version") {
      LOG(INFO) << "Simpleperf version " << GetSimpleperfVersion();
      return true;
    } else {
      CHECK(false) << "Unreachable code";
    }
  }
  while (i < argc) {
    args.emplace_back(argv[i++]);
  }

  android::base::ScopedLogSeverity severity(log_severity);

  if (args.empty()) {
    args.push_back("help");
  }
  std::unique_ptr<Command> command = CreateCommandInstance(args[0]);
  if (command == nullptr) {
    LOG(ERROR) << "malformed command line: unknown command " << args[0];
    return false;
  }
  std::string command_name = args[0];
  args.erase(args.begin());

  LOG(DEBUG) << "command '" << command_name << "' starts running";
  int exit_code;
  command->Run(args, &exit_code);
  LOG(DEBUG) << "command '" << command_name << "' "
             << (exit_code == 0 ? "finished successfully" : "failed");
  // Quick exit to avoid the cost of freeing memory and closing files.
  fflush(stdout);
  fflush(stderr);
  _Exit(exit_code);
  return exit_code == 0;
}

}  // namespace simpleperf
