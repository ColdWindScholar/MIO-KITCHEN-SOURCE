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

#include "command.h"

namespace simpleperf {

inline const OptionFormatMap& GetApiCollectCmdOptionFormats() {
  static const OptionFormatMap option_formats = {
      {"--app", {OptionValueType::STRING, OptionType::SINGLE, AppRunnerType::NOT_ALLOWED}},
      {"--in-app", {OptionValueType::NONE, OptionType::SINGLE, AppRunnerType::ALLOWED}},
      {"-o", {OptionValueType::STRING, OptionType::SINGLE, AppRunnerType::NOT_ALLOWED}},
      {"--out-fd", {OptionValueType::UINT, OptionType::SINGLE, AppRunnerType::CHECK_FD}},
      {"--stop-signal-fd", {OptionValueType::UINT, OptionType::SINGLE, AppRunnerType::CHECK_FD}},
  };
  return option_formats;
}

}  // namespace simpleperf
