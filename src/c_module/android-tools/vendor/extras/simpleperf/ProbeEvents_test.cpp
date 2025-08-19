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

#include "ProbeEvents.h"

#include <gtest/gtest.h>

#include "get_test_data.h"
#include "test_util.h"

using namespace simpleperf;

// @CddTest = 6.1/C-0-2
TEST(probe_events, ParseKprobeEventName) {
  ProbeEvent event;
  ASSERT_TRUE(ProbeEvents::ParseKprobeEventName("p:myprobe do_sys_open", &event));
  ASSERT_EQ(event.group_name, "kprobes");
  ASSERT_EQ(event.event_name, "myprobe");

  ASSERT_TRUE(ProbeEvents::ParseKprobeEventName("p:mygroup/myprobe do_sys_open", &event));
  ASSERT_EQ(event.group_name, "mygroup");
  ASSERT_EQ(event.event_name, "myprobe");

  ASSERT_TRUE(ProbeEvents::ParseKprobeEventName("p do_sys_open", &event));
  ASSERT_EQ(event.group_name, "kprobes");
  ASSERT_EQ(event.event_name, "p_do_sys_open_0");

  ASSERT_TRUE(ProbeEvents::ParseKprobeEventName("r do_sys_open+138", &event));
  ASSERT_EQ(event.group_name, "kprobes");
  ASSERT_EQ(event.event_name, "r_do_sys_open_138");

  ASSERT_TRUE(ProbeEvents::ParseKprobeEventName("r module:do_sys_open+138", &event));
  ASSERT_EQ(event.group_name, "kprobes");
  ASSERT_EQ(event.event_name, "r_module_do_sys_open_138");

  ASSERT_TRUE(ProbeEvents::ParseKprobeEventName("p 0x12345678", &event));
  ASSERT_EQ(event.group_name, "kprobes");
  ASSERT_EQ(event.event_name, "p_0x12345678");
}
