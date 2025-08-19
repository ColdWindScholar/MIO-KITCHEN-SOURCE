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

#include "tracing.h"

#include <gtest/gtest.h>

#include <android-base/strings.h>

using namespace simpleperf;

static void CheckAdjustFilter(const std::string& filter, bool use_quote,
                              const std::string& adjusted_filter,
                              const std::string used_field_str) {
  FieldNameSet used_fields;
  auto value = AdjustTracepointFilter(filter, use_quote, &used_fields);
  ASSERT_TRUE(value.has_value());
  ASSERT_EQ(value.value(), adjusted_filter);
  ASSERT_EQ(android::base::Join(used_fields, ","), used_field_str);
}

// @CddTest = 6.1/C-0-2
TEST(tracing, adjust_tracepoint_filter) {
  std::string filter = "((sig >= 1 && sig < 20) || sig == 32) && comm != \"bash\"";
  CheckAdjustFilter(filter, true, filter, "comm,sig");
  CheckAdjustFilter(filter, false, "((sig >= 1 && sig < 20) || sig == 32) && comm != bash",
                    "comm,sig");

  filter = "pid != 3 && !(comm ~ *bash)";
  CheckAdjustFilter(filter, true, "pid != 3 && !(comm ~ \"*bash\")", "comm,pid");
  CheckAdjustFilter(filter, false, filter, "comm,pid");

  filter = "mask & 3";
  CheckAdjustFilter(filter, true, filter, "mask");
  CheckAdjustFilter(filter, false, filter, "mask");

  filter = "addr > 0 && addr != 0xFFFFFFFFFFFFFFFF || value > -5";
  CheckAdjustFilter(filter, true, filter, "addr,value");
  CheckAdjustFilter(filter, false, filter, "addr,value");

  // unmatched paren
  FieldNameSet used_fields;
  ASSERT_FALSE(AdjustTracepointFilter("(pid > 3", true, &used_fields).has_value());
  ASSERT_FALSE(AdjustTracepointFilter("pid > 3)", true, &used_fields).has_value());
  // unknown operator
  ASSERT_FALSE(AdjustTracepointFilter("pid ^ 3", true, &used_fields).has_value());
}

namespace simpleperf {
std::ostream& operator<<(std::ostream& os, const TracingField& field) {
  os << "field (" << field.name << ", off " << field.offset << ", elem size " << field.elem_size
     << ", elem_count " << field.elem_count << ", is_signed " << field.is_signed << ", is_dynamic "
     << field.is_dynamic << ")";
  return os;
}
}  // namespace simpleperf

// @CddTest = 6.1/C-0-2
TEST(tracing, ParseTracingFormat) {
  std::string data =
      "name: sched_wakeup_new\n"
      "ID: 94\n"
      "format:\n"
      "\tfield:unsigned short common_type;	offset:0;	size:2;	signed:0;\n"
      "\tfield:unsigned char common_flags;	offset:2;	size:1;	signed:0;\n"
      "\tfield:unsigned char common_preempt_count;	offset:3;	size:1;	signed:0;\n"
      "\tfield:int common_pid;	offset:4;	size:4;	signed:1;\n"
      "\n"
      "\tfield:char comm[16];	offset:8;	size:16;	signed:1;\n"
      "\tfield:__data_loc char[] name;	offset:24;	size:4;	signed:1;\n";
  std::optional<TracingFormat> opt_format = ParseTracingFormat(data);
  ASSERT_TRUE(opt_format.has_value());
  const TracingFormat& format = opt_format.value();
  ASSERT_EQ(format.name, "sched_wakeup_new");
  ASSERT_EQ(format.id, 94);
  ASSERT_EQ(format.fields.size(), 6);
  ASSERT_EQ(format.fields[0], TracingField({.name = "common_type", .offset = 0, .elem_size = 2}));
  ASSERT_EQ(format.fields[1], TracingField({.name = "common_flags", .offset = 2, .elem_size = 1}));
  ASSERT_EQ(format.fields[2],
            TracingField({.name = "common_preempt_count", .offset = 3, .elem_size = 1}));
  ASSERT_EQ(format.fields[3],
            TracingField({.name = "common_pid", .offset = 4, .elem_size = 4, .is_signed = true}));
  ASSERT_EQ(
      format.fields[4],
      TracingField(
          {.name = "comm", .offset = 8, .elem_size = 1, .elem_count = 16, .is_signed = true}));
  ASSERT_EQ(format.fields[5], TracingField({.name = "name",
                                            .offset = 24,
                                            .elem_size = 4,
                                            .elem_count = 1,
                                            .is_signed = true,
                                            .is_dynamic = true}));
}
