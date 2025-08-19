/*
 * Copyright (C) 2019 The Android Open Source Project
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

#include <unistd.h>

#include <memory>
#include <string>

#include <android-base/file.h>
#include <android-base/strings.h>
#include <gtest/gtest.h>
#include <json/reader.h>
#include <json/writer.h>
#include <jsonpb/jsonpb.h>
#include <jsonpb/verify.h>

// JsonSchemaTest test that a given JSON file conforms to a given schema.
// This includes:
// - libprotobuf can parse the given JSON file using the given Prototype class
// - Additional checks on field names of the JSON file, and types of values.

namespace android {
namespace jsonpb {

class JsonSchemaTestConfig {
 public:
  virtual ~JsonSchemaTestConfig() = default;
  virtual std::unique_ptr<google::protobuf::Message> CreateMessage() const = 0;
  virtual std::string file_path() const = 0;
  /**
   * If it returns true, tests are skipped when the file is not found.
   */
  virtual bool optional() const { return false; }
};
using JsonSchemaTestConfigFactory = std::function<std::unique_ptr<JsonSchemaTestConfig>()>;

template <typename T>
class AbstractJsonSchemaTestConfig : public JsonSchemaTestConfig {
 public:
  AbstractJsonSchemaTestConfig(const std::string& path) : file_path_(path){};
  std::unique_ptr<google::protobuf::Message> CreateMessage() const override {
    return std::make_unique<T>();
  }
  std::string file_path() const override { return file_path_; }

 private:
  std::string file_path_;
};

template <typename T>
JsonSchemaTestConfigFactory MakeTestParam(const std::string& path) {
  return [path]() { return std::make_unique<AbstractJsonSchemaTestConfig<T>>(path); };
}

class JsonSchemaTest : public ::testing::TestWithParam<JsonSchemaTestConfigFactory> {
 public:
  void SetUp() override {
    auto&& config = ::testing::TestWithParam<JsonSchemaTestConfigFactory>::GetParam()();
    file_path_ = config->file_path();

    if (access(file_path_.c_str(), F_OK) == -1) {
      ASSERT_EQ(ENOENT, errno) << "File '" << file_path_
                               << "' is not accessible: " << strerror(errno);
      ASSERT_TRUE(config->optional()) << "Missing mandatory file " << file_path_;
      GTEST_SKIP();
    }
    ASSERT_TRUE(android::base::ReadFileToString(file_path_, &json_));
    ASSERT_FALSE(json_.empty()) << "File '" << file_path_ << "' exists but is empty";

    object_ = config->CreateMessage();
    auto res = internal::JsonStringToMessage(json_, object_.get());
    ASSERT_TRUE(res.ok()) << "Invalid format of file " << file_path_ << ": " << res.error();
  }
  google::protobuf::Message* message() const { return object_.get(); }
  std::string file_path_;
  std::string json_;
  std::unique_ptr<google::protobuf::Message> object_;
};

// Test that the JSON file has no fields unknown by the schema. See
// AllFieldsAreKnown() for more details.
TEST_P(JsonSchemaTest, NoUnknownFields) {
  std::string error;
  EXPECT_TRUE(AllFieldsAreKnown(*object_, json_, &error))
      << "File: " << file_path_ << ": " << error;
}

TEST_P(JsonSchemaTest, EqReformattedJson) {
  std::string error;
  EXPECT_TRUE(EqReformattedJson(json_, object_.get(), &error))
      << "File: " << file_path_ << ": " << error;
}

}  // namespace jsonpb
}  // namespace android
