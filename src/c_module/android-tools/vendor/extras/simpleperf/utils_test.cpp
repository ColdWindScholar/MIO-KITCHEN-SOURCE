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

#include "utils.h"

#include <gtest/gtest.h>

#include <android-base/file.h>

#include "environment.h"
#include "get_test_data.h"

using namespace simpleperf;

// @CddTest = 6.1/C-0-2
TEST(utils, ConvertBytesToValue) {
  char buf[8];
  for (int i = 0; i < 8; ++i) {
    buf[i] = i;
  }
  ASSERT_EQ(0x1ULL, ConvertBytesToValue(buf + 1, 1));
  ASSERT_EQ(0x201ULL, ConvertBytesToValue(buf + 1, 2));
  ASSERT_EQ(0x05040302ULL, ConvertBytesToValue(buf + 2, 4));
  ASSERT_EQ(0x0706050403020100ULL, ConvertBytesToValue(buf, 8));
}

// @CddTest = 6.1/C-0-2
TEST(utils, ArchiveHelper) {
  std::unique_ptr<ArchiveHelper> ahelper = ArchiveHelper::CreateInstance(GetTestData(APK_FILE));
  ASSERT_TRUE(ahelper);
  bool found = false;
  ZipEntry lib_entry;
  ASSERT_TRUE(ahelper->IterateEntries([&](ZipEntry& entry, const std::string& name) {
    if (name == NATIVELIB_IN_APK) {
      found = true;
      lib_entry = entry;
      return false;
    }
    return true;
  }));
  ASSERT_TRUE(found);
  ZipEntry entry;
  ASSERT_TRUE(ahelper->FindEntry(NATIVELIB_IN_APK, &entry));
  ASSERT_EQ(entry.offset, lib_entry.offset);
  std::vector<uint8_t> data;
  ASSERT_TRUE(ahelper->GetEntryData(entry, &data));

  // Check reading wrong file formats.
  ASSERT_FALSE(ArchiveHelper::CreateInstance(GetTestData(ELF_FILE)));
  ASSERT_FALSE(ArchiveHelper::CreateInstance("/dev/zero"));
}

// @CddTest = 6.1/C-0-2
TEST(utils, GetCpusFromString) {
  ASSERT_EQ(GetCpusFromString("0-2"), std::make_optional<std::set<int>>({0, 1, 2}));
  ASSERT_EQ(GetCpusFromString("0,2-3"), std::make_optional<std::set<int>>({0, 2, 3}));
  ASSERT_EQ(GetCpusFromString("1,0-3,3,4"), std::make_optional<std::set<int>>({0, 1, 2, 3, 4}));
  ASSERT_EQ(GetCpusFromString("0,1-3, 5, 7-8"),
            std::make_optional<std::set<int>>({0, 1, 2, 3, 5, 7, 8}));
  ASSERT_EQ(GetCpusFromString(""), std::nullopt);
  ASSERT_EQ(GetCpusFromString("-3"), std::nullopt);
  ASSERT_EQ(GetCpusFromString("3,2-1"), std::nullopt);
}

// @CddTest = 6.1/C-0-2
TEST(utils, GetTidsFromString) {
  ASSERT_EQ(GetTidsFromString("0,12,9", false), std::make_optional(std::set<pid_t>({0, 9, 12})));
  ASSERT_EQ(GetTidsFromString("-2", false), std::nullopt);
}

// @CddTest = 6.1/C-0-2
TEST(utils, GetPidsFromStrings) {
  ASSERT_EQ(GetPidsFromStrings({"0,12", "9"}, false, false),
            std::make_optional(std::set<pid_t>({0, 9, 12})));
  ASSERT_EQ(GetPidsFromStrings({"-2"}, false, false), std::nullopt);
#if defined(__linux__)
  pid_t pid = getpid();
  ASSERT_EQ(GetPidsFromStrings({std::to_string(pid)}, true, false),
            std::make_optional(std::set<pid_t>({pid})));
  std::string process_name = GetCompleteProcessName(pid);
  ASSERT_EQ(GetPidsFromStrings({process_name}, true, true),
            std::make_optional(std::set<pid_t>({pid})));
#endif  // defined(__linux__)
}

// @CddTest = 6.1/C-0-2
TEST(utils, LineReader) {
  TemporaryFile tmpfile;
  close(tmpfile.release());
  ASSERT_TRUE(android::base::WriteStringToFile("line1\nline2", tmpfile.path));
  LineReader reader(tmpfile.path);
  ASSERT_TRUE(reader.Ok());
  std::string* line = reader.ReadLine();
  ASSERT_TRUE(line != nullptr);
  ASSERT_EQ(*line, "line1");
  line = reader.ReadLine();
  ASSERT_TRUE(line != nullptr);
  ASSERT_EQ(*line, "line2");
  ASSERT_TRUE(reader.ReadLine() == nullptr);
}

// @CddTest = 6.1/C-0-2
TEST(utils, ReadableCount) {
  ASSERT_EQ(ReadableCount(0), "0");
  ASSERT_EQ(ReadableCount(204), "204");
  ASSERT_EQ(ReadableCount(1000), "1,000");
  ASSERT_EQ(ReadableCount(123456789), "123,456,789");
}
