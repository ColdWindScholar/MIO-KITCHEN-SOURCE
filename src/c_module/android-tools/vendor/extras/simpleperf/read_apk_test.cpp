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

#include "read_apk.h"

#include <gtest/gtest.h>
#include "get_test_data.h"
#include "test_util.h"

using namespace simpleperf;

// @CddTest = 6.1/C-0-2
TEST(read_apk, FindElfInApkByOffset) {
  ApkInspector inspector;
  ASSERT_TRUE(inspector.FindElfInApkByOffset("/dev/null", 0) == nullptr);
  ASSERT_TRUE(inspector.FindElfInApkByOffset(GetTestData(APK_FILE), 0) == nullptr);
  // Test if we can read the EmbeddedElf using an offset inside its [offset, offset+size] range
  // in the apk file.
  EmbeddedElf* ee = inspector.FindElfInApkByOffset(
      GetTestData(APK_FILE), NATIVELIB_OFFSET_IN_APK + NATIVELIB_SIZE_IN_APK / 2);
  ASSERT_TRUE(ee != nullptr);
  ASSERT_EQ(NATIVELIB_IN_APK, ee->entry_name());
  ASSERT_EQ(NATIVELIB_OFFSET_IN_APK, ee->entry_offset());
  ASSERT_EQ(NATIVELIB_SIZE_IN_APK, ee->entry_size());
}

// @CddTest = 6.1/C-0-2
TEST(read_apk, FindElfInApkByName) {
  ASSERT_TRUE(ApkInspector::FindElfInApkByName("/dev/null", "") == nullptr);
  ASSERT_TRUE(ApkInspector::FindElfInApkByName(GetTestData(APK_FILE), "") == nullptr);
  auto ee = ApkInspector::FindElfInApkByName(GetTestData(APK_FILE), NATIVELIB_IN_APK);
  ASSERT_TRUE(ee != nullptr);
  ASSERT_EQ(NATIVELIB_OFFSET_IN_APK, ee->entry_offset());
  ASSERT_EQ(NATIVELIB_SIZE_IN_APK, ee->entry_size());
}

// @CddTest = 6.1/C-0-2
TEST(read_apk, ParseExtractedInMemoryPath) {
  std::string zip_path;
  std::string entry_name;
  ASSERT_TRUE(ParseExtractedInMemoryPath(
      "[anon:dalvik-classes.dex extracted in memory from "
      "/data/app/com.example.simpleperf.simpleperfexamplepurejava-HZK6bPs3Z9SDT3a-tqmasA==/"
      "base.apk]",
      &zip_path, &entry_name));
  ASSERT_EQ(zip_path,
            "/data/app/com.example.simpleperf.simpleperfexamplepurejava"
            "-HZK6bPs3Z9SDT3a-tqmasA==/base.apk");
  ASSERT_EQ(entry_name, "classes.dex");
  ASSERT_FALSE(
      ParseExtractedInMemoryPath("[anon:dalvik-thread local mark stack]", &zip_path, &entry_name));
  ASSERT_TRUE(ParseExtractedInMemoryPath(
      "/dev/ashmem/dalvik-classes.dex extracted in memory from "
      "/data/app/com.example.simpleperf.simpleperfexamplepurejava-HZK6bPs3Z9SDT3a-tqmasA==/base.apk"
      " (deleted)",
      &zip_path, &entry_name));
  ASSERT_EQ(zip_path,
            "/data/app/com.example.simpleperf.simpleperfexamplepurejava"
            "-HZK6bPs3Z9SDT3a-tqmasA==/base.apk");
  ASSERT_EQ(entry_name, "classes.dex");
  ASSERT_FALSE(ParseExtractedInMemoryPath("/dev/ashmem/dalvik-thread local mark stack (deleted)",
                                          &zip_path, &entry_name));

  // Parse multidex file.
  ASSERT_TRUE(ParseExtractedInMemoryPath(
      "/dev/ashmem/dalvik-classes2.dex extracted in memory from "
      "/data/app/getxml.test.com.testgetxml-knxI11ZXLT-OVBs9X9bSkw==/base.apk!classes2.dex "
      "(deleted)",
      &zip_path, &entry_name));
  ASSERT_EQ(zip_path, "/data/app/getxml.test.com.testgetxml-knxI11ZXLT-OVBs9X9bSkw==/base.apk");
  ASSERT_EQ(entry_name, "classes2.dex");
}
