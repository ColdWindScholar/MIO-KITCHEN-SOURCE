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

#include <stdio.h>

#include <gmock/gmock.h>
#include <gtest/gtest.h>

#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/properties.h>
#include <bootloader_message/bootloader_message.h>
#include <string_view>

namespace {
using ::testing::StartsWith;

int mtectrl(std::string_view arg) {
  std::string cmd = "mtectrl -t /data/local/tmp/misc_memtag ";
  cmd += arg;
  return system(cmd.c_str());
}

int RunMteCtrl() {
  CHECK(android::base::GetIntProperty("arm64.memtag.test_bootctl_loaded", 0) == 1);
  std::string arg = android::base::GetProperty("arm64.memtag.test_bootctl", "none");
  arg += " ";
  arg += android::base::GetProperty("arm64.memtag.test_bootctl_override", "default");
  return mtectrl(arg);
}

void Boot(misc_memtag_message m) {
  std::string m_str(reinterpret_cast<char*>(&m), sizeof(m));
  android::base::WriteStringToFile(m_str, "/data/local/tmp/misc_memtag");
  mtectrl("-s arm64.memtag.test_bootctl -f arm64.memtag.test_bootctl_loaded");
  // arm64.memtag.test_bootctl got updated, so we trigger ourselves.
  RunMteCtrl();
}

void Reboot() {
  android::base::SetProperty("arm64.memtag.test_bootctl", "INVALID");
  android::base::SetProperty("arm64.memtag.test_bootctl_loaded", "0");
  std::string m_str;
  ASSERT_TRUE(android::base::ReadFileToString("/data/local/tmp/misc_memtag", &m_str));
  misc_memtag_message m;
  ASSERT_EQ(m_str.size(), sizeof(m));
  memcpy(&m, m_str.c_str(), sizeof(m));
  m.memtag_mode &= ~MISC_MEMTAG_MODE_MEMTAG_ONCE;
  Boot(m);
}

void SetMemtagProp(const std::string& s) {
  android::base::SetProperty("arm64.memtag.test_bootctl", s);
  RunMteCtrl();
}

void SetOverrideProp(const std::string& s) {
  android::base::SetProperty("arm64.memtag.test_bootctl_override", s);
  RunMteCtrl();
}

std::string GetMisc() {
  std::string data;
  CHECK(android::base::ReadFileToString("/data/local/tmp/misc_memtag", &data, false));
  return data;
}

std::string TestProperty() {
  return android::base::GetProperty("arm64.memtag.test_bootctl", "");
}
std::string TestFlag() {
  return android::base::GetProperty("arm64.memtag.test_bootctl_loaded", "");
}
}  // namespace

class MteCtrlTest : public ::testing::Test {
  void SetUp() override {
    // Empty fake misc partition.
    int fd = creat("/data/local/tmp/misc_memtag", 0600);
    CHECK(fd != -1);
    CHECK(ftruncate(fd, sizeof(misc_memtag_message)) != -1);
    close(fd);
    android::base::SetProperty("arm64.memtag.test_bootctl", "INVALID");
    android::base::SetProperty("arm64.memtag.test_bootctl_override", "");
    android::base::SetProperty("arm64.memtag.test_bootctl_loaded", "0");
  }
  void TearDown() override {
    CHECK(unlink("/data/local/tmp/misc_memtag") == 0);
  }
};

TEST_F(MteCtrlTest, invalid) {
  EXPECT_NE(mtectrl("memtag-invalid"), 0);
  EXPECT_NE(mtectrl("memtag override-invalid"), 0);
}

TEST_F(MteCtrlTest, set_once) {
  Boot({});
  SetMemtagProp("memtag-once");
  EXPECT_THAT(GetMisc(), StartsWith("\x01\x5a\xfe\xfe\x5a\x02"));
}

TEST_F(MteCtrlTest, set_once_kernel) {
  Boot({});
  SetMemtagProp("memtag-once,memtag-kernel");
  EXPECT_THAT(GetMisc(), StartsWith("\x01\x5a\xfe\xfe\x5a\x06"));
}

TEST_F(MteCtrlTest, read_memtag) {
  Boot({});
  SetMemtagProp("memtag");
  Reboot();
  EXPECT_EQ(TestProperty(), "memtag");
  EXPECT_EQ(TestFlag(), "1");
}

TEST_F(MteCtrlTest, read_invalid_memtag_message) {
  misc_memtag_message m = {.version = 1, .magic = 0xffff, .memtag_mode = MISC_MEMTAG_MODE_MEMTAG};
  Boot(m);
  EXPECT_EQ(TestProperty(), "none");
  EXPECT_EQ(TestFlag(), "1");
}

TEST_F(MteCtrlTest, read_invalid_memtag_mode) {
  misc_memtag_message m = {.version = MISC_MEMTAG_MESSAGE_VERSION,
                           .magic = MISC_MEMTAG_MAGIC_HEADER,
                           .memtag_mode = MISC_MEMTAG_MODE_MEMTAG | 1u << 31};
  Boot(m);
  EXPECT_EQ(TestProperty(), "memtag");
  EXPECT_EQ(TestFlag(), "1");
}

TEST_F(MteCtrlTest, set_read_force_off) {
  Boot({});
  SetMemtagProp("memtag,memtag-once");
  SetOverrideProp("force_off");
  Reboot();
  EXPECT_EQ(TestProperty(), "memtag-off,forced");
  SetOverrideProp("default");
  Reboot();
  EXPECT_EQ(TestProperty(), "none");
}

TEST_F(MteCtrlTest, set_read_force_off_none) {
  Boot({});
  SetMemtagProp("none");
  SetOverrideProp("force_off");
  Reboot();
  EXPECT_EQ(TestProperty(), "memtag-off,forced");
  SetOverrideProp("default");
  Reboot();
  EXPECT_EQ(TestProperty(), "none");
}

TEST_F(MteCtrlTest, set_read_force_off_and_on) {
  Boot({});
  SetMemtagProp("memtag,memtag-once");
  SetOverrideProp("force_off");
  Reboot();
  EXPECT_EQ(TestProperty(), "memtag-off,forced");
  SetOverrideProp("default");
  Reboot();
  EXPECT_EQ(TestProperty(), "none");
  SetOverrideProp("force_on");
  Reboot();
  EXPECT_EQ(TestProperty(), "memtag,forced");
}

TEST_F(MteCtrlTest, set_read_force_off_already) {
  Boot({});
  SetMemtagProp("memtag-off,memtag-once");
  SetOverrideProp("force_off");
  Reboot();
  EXPECT_EQ(TestProperty(), "memtag-off");
  SetOverrideProp("default");
  Reboot();
  EXPECT_EQ(TestProperty(), "memtag-off");
}

TEST_F(MteCtrlTest, set_read_force_off_and_on_already) {
  Boot({});
  SetMemtagProp("memtag-off,memtag-once");
  SetOverrideProp("force_off");
  Reboot();
  EXPECT_EQ(TestProperty(), "memtag-off");
  SetOverrideProp("default");
  Reboot();
  EXPECT_EQ(TestProperty(), "memtag-off");
  SetOverrideProp("force_on");
  Reboot();
  EXPECT_EQ(TestProperty(), "memtag,forced");
}

TEST_F(MteCtrlTest, set_read_force_on) {
  Boot({});
  SetMemtagProp("memtag-once");
  SetOverrideProp("force_on");
  Reboot();
  EXPECT_EQ(TestProperty(), "memtag,forced");
  SetOverrideProp("default");
  Reboot();
  EXPECT_EQ(TestProperty(), "none");
}

TEST_F(MteCtrlTest, set_read_force_on_none) {
  Boot({});
  SetMemtagProp("none");
  SetOverrideProp("force_on");
  Reboot();
  EXPECT_EQ(TestProperty(), "memtag,forced");
  SetOverrideProp("default");
  Reboot();
  EXPECT_EQ(TestProperty(), "none");
}

TEST_F(MteCtrlTest, set_read_force_on_and_off) {
  Boot({});
  SetMemtagProp("memtag-once");
  SetOverrideProp("force_on");
  Reboot();
  EXPECT_EQ(TestProperty(), "memtag,forced");
  SetOverrideProp("default");
  Reboot();
  EXPECT_EQ(TestProperty(), "none");
  SetOverrideProp("force_off");
  Reboot();
  EXPECT_EQ(TestProperty(), "memtag-off,forced");
}

TEST_F(MteCtrlTest, set_read_force_on_already) {
  Boot({});
  SetMemtagProp("memtag,memtag-once");
  SetOverrideProp("force_on");
  Reboot();
  EXPECT_EQ(TestProperty(), "memtag");
  SetOverrideProp("default");
  Reboot();
  EXPECT_EQ(TestProperty(), "memtag");
}

TEST_F(MteCtrlTest, set_read_force_on_and_off_already) {
  Boot({});
  SetMemtagProp("memtag,memtag-once");
  SetOverrideProp("force_on");
  Reboot();
  EXPECT_EQ(TestProperty(), "memtag");
  SetOverrideProp("default");
  Reboot();
  EXPECT_EQ(TestProperty(), "memtag");
  SetOverrideProp("force_off");
  Reboot();
  EXPECT_EQ(TestProperty(), "memtag-off,forced");
}

TEST_F(MteCtrlTest, override) {
  Boot({});
  SetMemtagProp(("memtag"));
  SetMemtagProp(("memtag-once"));
  EXPECT_THAT(GetMisc(), StartsWith("\x01\x5a\xfe\xfe\x5a\x02"));
}

TEST_F(MteCtrlTest, read_empty) {
  Boot({});
  EXPECT_EQ(TestProperty(), "none");
  EXPECT_EQ(TestFlag(), "1");
}

TEST_F(MteCtrlTest, force_off_invalid_mode) {
  Boot({});
  SetMemtagProp("memtag-invalid");
  SetOverrideProp("force_off");
  EXPECT_THAT(GetMisc(), StartsWith("\x01\x5a\xfe\xfe\x5a\x30"));
  Reboot();
  EXPECT_EQ(TestProperty(), "memtag-off,forced");
  SetOverrideProp("default");
  Reboot();
  EXPECT_EQ(TestProperty(), "none");
}

TEST_F(MteCtrlTest, force_on_invalid_mode) {
  Boot({});
  SetMemtagProp("memtag-invalid");
  SetOverrideProp("force_on");
  EXPECT_THAT(GetMisc(), StartsWith("\x01\x5a\xfe\xfe\x5a\x21"));
  Reboot();
  EXPECT_EQ(TestProperty(), "memtag,forced");
  SetOverrideProp("default");
  Reboot();
  EXPECT_EQ(TestProperty(), "none");
}

TEST_F(MteCtrlTest, mode_invalid_override) {
  Boot({});
  SetMemtagProp("memtag");
  SetOverrideProp("force_invalid");
  EXPECT_THAT(GetMisc(), StartsWith("\x01\x5a\xfe\xfe\x5a\x01"));
  Reboot();
  EXPECT_EQ(TestProperty(), "memtag");
  SetOverrideProp("default");
  Reboot();
  EXPECT_EQ(TestProperty(), "memtag");
}
