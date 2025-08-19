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

#include <gtest/gtest.h>

#include "command.h"

using namespace simpleperf;

class MockCommand : public Command {
 public:
  MockCommand() : Command("mock", "mock_short_help", "mock_long_help") {}

  bool Run(const std::vector<std::string>&) override { return true; }
};

// @CddTest = 6.1/C-0-2
TEST(command, CreateCommandInstance) {
  ASSERT_TRUE(CreateCommandInstance("mock1") == nullptr);
  RegisterCommand("mock1", [] { return std::unique_ptr<Command>(new MockCommand); });
  ASSERT_TRUE(CreateCommandInstance("mock1") != nullptr);
  UnRegisterCommand("mock1");
  ASSERT_TRUE(CreateCommandInstance("mock1") == nullptr);
}

// @CddTest = 6.1/C-0-2
TEST(command, GetAllCommands) {
  size_t command_count = GetAllCommandNames().size();
  RegisterCommand("mock1", [] { return std::unique_ptr<Command>(new MockCommand); });
  ASSERT_EQ(command_count + 1, GetAllCommandNames().size());
  UnRegisterCommand("mock1");
  ASSERT_EQ(command_count, GetAllCommandNames().size());
}

// @CddTest = 6.1/C-0-2
TEST(command, GetValueForOption) {
  MockCommand command;
  uint64_t value;
  size_t i;
  for (bool allow_suffixes : {true, false}) {
    i = 0;
    ASSERT_TRUE(command.GetUintOption({"-s", "156"}, &i, &value, 0,
                                      std::numeric_limits<uint64_t>::max(), allow_suffixes));
    ASSERT_EQ(i, 1u);
    ASSERT_EQ(value, 156u);
  }
  i = 0;
  ASSERT_TRUE(command.GetUintOption({"-s", "156k"}, &i, &value, 0,
                                    std::numeric_limits<uint64_t>::max(), true));
  ASSERT_EQ(value, 156 * (1ULL << 10));
  i = 0;
  ASSERT_FALSE(command.GetUintOption({"-s"}, &i, &value));
  i = 0;
  ASSERT_FALSE(command.GetUintOption({"-s", "0"}, &i, &value, 1));
  i = 0;
  ASSERT_FALSE(command.GetUintOption({"-s", "156"}, &i, &value, 0, 155));
  i = 0;
  double double_value;
  ASSERT_TRUE(command.GetDoubleOption({"-s", "3.2"}, &i, &double_value, 0, 4));
  ASSERT_DOUBLE_EQ(double_value, 3.2);
}

// @CddTest = 6.1/C-0-2
TEST(command, PreprocessOptions) {
  MockCommand cmd;
  OptionValueMap options;
  std::vector<std::pair<OptionName, OptionValue>> ordered_options;
  std::vector<std::string> non_option_args;

  OptionFormatMap option_formats = {
      {"--bool-option", {OptionValueType::NONE, OptionType::SINGLE}},
      {"--str-option", {OptionValueType::STRING, OptionType::MULTIPLE}},
      {"--str2-option", {OptionValueType::STRING, OptionType::SINGLE}},
      {"--opt-str-option", {OptionValueType::OPT_STRING, OptionType::MULTIPLE}},
      {"--opt-str-after-equal-option",
       {OptionValueType::OPT_STRING_AFTER_EQUAL, OptionType::MULTIPLE}},
      {"--uint-option", {OptionValueType::UINT, OptionType::SINGLE}},
      {"--double-option", {OptionValueType::DOUBLE, OptionType::SINGLE}},

      // ordered options
      {"--ord-str-option", {OptionValueType::STRING, OptionType::ORDERED}},
      {"--ord-uint-option", {OptionValueType::UINT, OptionType::ORDERED}},
  };

  // Check options.
  std::vector<std::string> args = {"--bool-option",
                                   "--str-option",
                                   "str1",
                                   "--str-option",
                                   "str1_2",
                                   "--str2-option",
                                   "str2_value",
                                   "--opt-str-option",
                                   "--opt-str-option",
                                   "opt_str",
                                   "--opt-str-after-equal-option",
                                   "--opt-str-after-equal-option=str3",
                                   "--uint-option",
                                   "34",
                                   "--double-option",
                                   "-32.75"};
  ASSERT_TRUE(cmd.PreprocessOptions(args, option_formats, &options, &ordered_options, nullptr));
  ASSERT_TRUE(options.PullBoolValue("--bool-option"));
  auto values = options.PullValues("--str-option");
  ASSERT_EQ(values.size(), 2);
  ASSERT_EQ(values[0].str_value, "str1");
  ASSERT_EQ(values[1].str_value, "str1_2");
  std::string str2_value;
  options.PullStringValue("--str2-option", &str2_value);
  ASSERT_EQ(str2_value, "str2_value");
  values = options.PullValues("--opt-str-option");
  ASSERT_EQ(values.size(), 2);
  ASSERT_TRUE(values[0].str_value.empty());
  ASSERT_EQ(values[1].str_value, "opt_str");
  values = options.PullValues("--opt-str-after-equal-option");
  ASSERT_EQ(values.size(), 2);
  ASSERT_TRUE(values[0].str_value.empty());
  ASSERT_EQ(values[1].str_value, "str3");
  size_t uint_value;
  ASSERT_TRUE(options.PullUintValue("--uint-option", &uint_value));
  ASSERT_EQ(uint_value, 34);
  double double_value;
  ASSERT_TRUE(options.PullDoubleValue("--double-option", &double_value));
  ASSERT_DOUBLE_EQ(double_value, -32.75);
  ASSERT_TRUE(options.values.empty());

  // Check ordered options.
  args = {"--ord-str-option", "str1", "--ord-uint-option", "32", "--ord-str-option", "str2"};
  ASSERT_TRUE(cmd.PreprocessOptions(args, option_formats, &options, &ordered_options, nullptr));
  ASSERT_EQ(ordered_options.size(), 3);
  ASSERT_EQ(ordered_options[0].first, "--ord-str-option");
  ASSERT_EQ(ordered_options[0].second.str_value, "str1");
  ASSERT_EQ(ordered_options[1].first, "--ord-uint-option");
  ASSERT_EQ(ordered_options[1].second.uint_value, 32);
  ASSERT_EQ(ordered_options[2].first, "--ord-str-option");
  ASSERT_EQ(ordered_options[2].second.str_value, "str2");

  // Check non_option_args.
  ASSERT_TRUE(cmd.PreprocessOptions({"arg1", "--arg2"}, option_formats, &options, &ordered_options,
                                    &non_option_args));
  ASSERT_EQ(non_option_args, std::vector<std::string>({"arg1", "--arg2"}));
  // "--" can force following args to be non_option_args.
  ASSERT_TRUE(cmd.PreprocessOptions({"--", "--bool-option"}, option_formats, &options,
                                    &ordered_options, &non_option_args));
  ASSERT_EQ(non_option_args, std::vector<std::string>({"--bool-option"}));
  // Pass nullptr to not accept non option args.
  ASSERT_FALSE(cmd.PreprocessOptions({"non_option_arg"}, option_formats, &options, &ordered_options,
                                     nullptr));

  // Check different errors.
  // unknown option
  ASSERT_FALSE(cmd.PreprocessOptions({"--unknown-option"}, option_formats, &options,
                                     &ordered_options, nullptr));
  // no option value
  ASSERT_FALSE(
      cmd.PreprocessOptions({"--str-option"}, option_formats, &options, &ordered_options, nullptr));
  // wrong option value format
  ASSERT_FALSE(cmd.PreprocessOptions({"--uint-option", "-2"}, option_formats, &options,
                                     &ordered_options, nullptr));
  ASSERT_FALSE(cmd.PreprocessOptions({"--double-option", "str"}, option_formats, &options,
                                     &ordered_options, nullptr));
  // unexpected non_option_args
  ASSERT_FALSE(cmd.PreprocessOptions({"non_option_args"}, option_formats, &options,
                                     &ordered_options, nullptr));

  auto parse_args = [&](const std::vector<std::string>& args) {
    return cmd.PreprocessOptions(args, option_formats, &options, &ordered_options, nullptr);
  };

  ASSERT_TRUE(parse_args({"--opt-str-after-equal-option"}));
  std::string s;
  options.PullStringValue("--opt-str-after-equal-option", &s);
  ASSERT_EQ(s, "");
  ASSERT_TRUE(parse_args({"--opt-str-after-equal-option=str_value"}));
  options.PullStringValue("--opt-str-after-equal-option", &s);
  ASSERT_EQ(s, "str_value");
}

// @CddTest = 6.1/C-0-2
TEST(command, OptionValueMap) {
  OptionValue value;
  value.uint_value = 10;

  OptionValueMap options;
  uint64_t uint_value;
  options.values.emplace("--uint-option", value);
  ASSERT_FALSE(options.PullUintValue("--uint-option", &uint_value, 11));
  options.values.emplace("--uint-option", value);
  ASSERT_FALSE(options.PullUintValue("--uint-option", &uint_value, 0, 9));
  options.values.emplace("--uint-option", value);
  ASSERT_TRUE(options.PullUintValue("--uint-option", &uint_value, 10, 10));

  double double_value;
  value.double_value = 0.0;
  options.values.emplace("--double-option", value);
  ASSERT_FALSE(options.PullDoubleValue("--double-option", &double_value, 1.0));
  options.values.emplace("--double-option", value);
  ASSERT_FALSE(options.PullDoubleValue("--double-option", &double_value, -2.0, -1.0));
  options.values.emplace("--double-option", value);
  ASSERT_TRUE(options.PullDoubleValue("--double-option", &double_value, 0.0, 0.0));
}
