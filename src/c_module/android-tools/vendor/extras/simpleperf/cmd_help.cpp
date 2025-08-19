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

#include <stdio.h>
#include <string>
#include <vector>

#include <android-base/logging.h>

#include "command.h"

namespace simpleperf {
namespace {

class HelpCommand : public Command {
 public:
  HelpCommand()
      : Command("help", "print help information for simpleperf",
                // clang-format off
"Usage: simpleperf help [subcommand]\n"
"    Without subcommand, print short help string for every subcommand.\n"
"    With subcommand, print long help string for the subcommand.\n\n"
                // clang-format on
        ) {}

  bool Run(const std::vector<std::string>& args) override;

 private:
  void PrintShortHelp();
  void PrintLongHelpForOneCommand(const Command& cmd);
};

bool HelpCommand::Run(const std::vector<std::string>& args) {
  if (args.empty()) {
    PrintShortHelp();
  } else {
    std::unique_ptr<Command> cmd = CreateCommandInstance(args[0]);
    if (cmd == nullptr) {
      LOG(ERROR) << "malformed command line: can't find help string for "
                    "unknown command "
                 << args[0];
      LOG(ERROR) << "try using \"--help\"";
      return false;
    } else {
      PrintLongHelpForOneCommand(*cmd);
    }
  }
  return true;
}

void HelpCommand::PrintShortHelp() {
  printf(
      // clang-format off
"Usage: simpleperf [common options] subcommand [args_for_subcommand]\n"
"common options:\n"
"    -h/--help     Print this help information.\n"
"    --log <severity> Set the minimum severity of logging. Possible severities\n"
"                     include verbose, debug, warning, info, error, fatal.\n"
"                     Default is info.\n"
#if defined(__ANDROID__)
"    --log-to-android-buffer  Write log to android log buffer instead of stderr.\n"
#endif
"    --version     Print version of simpleperf.\n"
      "subcommands:\n"
      // clang-format on
  );
  for (auto& cmd_name : GetAllCommandNames()) {
    std::unique_ptr<Command> cmd = CreateCommandInstance(cmd_name);
    printf("    %-20s%s\n", cmd_name.c_str(), cmd->ShortHelpString().c_str());
  }
}

void HelpCommand::PrintLongHelpForOneCommand(const Command& command) {
  printf("%s\n", command.LongHelpString().c_str());
}

}  // namespace

void RegisterHelpCommand() {
  RegisterCommand("help", [] { return std::unique_ptr<Command>(new HelpCommand); });
}

}  // namespace simpleperf
