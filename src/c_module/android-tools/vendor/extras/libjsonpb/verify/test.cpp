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

#include <limits>

#include <sstream>

#include <gmock/gmock.h>
#include <gtest/gtest.h>
#include <json/writer.h>
#include <jsonpb/jsonpb.h>
#include <jsonpb/verify.h>

#include "test.pb.h"

using ::android::jsonpb::internal::FormatJson;
using ::testing::ElementsAre;
using ::testing::HasSubstr;

namespace android {
namespace jsonpb {

// Unit tests for libjsonpbverify.

class LibJsonpbVerifyTest : public ::testing::Test {};

class JsonKeyTest : public LibJsonpbVerifyTest {
 public:
  template <typename T>
  std::string GetFieldJsonName(const std::string& field_name) {
    return T{}.GetDescriptor()->FindFieldByName(field_name)->json_name();
  }

  template <typename T>
  void TestParseOkWithUnknownKey(const std::string& field_name, const std::string& json_key) {
    std::string json = "{\"" + json_key + "\": \"test\"}";
    auto object = JsonStringToMessage<T>(json);
    ASSERT_TRUE(object.ok()) << object.error();
    EXPECT_EQ("test", object->GetReflection()->GetString(
                          *object, object->GetDescriptor()->FindFieldByName(field_name)));
    std::string error;
    ASSERT_FALSE(AllFieldsAreKnown(*object, json, &error))
        << "AllFieldsAreKnown should return false";
    EXPECT_THAT(error, HasSubstr("unknown keys"));
    EXPECT_THAT(error, HasSubstr(json_key));
  }
};

TEST_F(JsonKeyTest, WithJsonNameOk) {
  std::string json =
      "{\n"
      "    \"FOOBAR\": \"foo_bar\",\n"
      "    \"BarBaz\": \"barBaz\",\n"
      "    \"baz_qux\": \"BazQux\",\n"
      "    \"quxQuux\": \"QUX_QUUX\"\n"
      "\n}";
  auto object = JsonStringToMessage<WithJsonName>(json);
  ASSERT_TRUE(object.ok()) << object.error();

  EXPECT_EQ("foo_bar", object->foo_bar());
  EXPECT_EQ("barBaz", object->barbaz());
  EXPECT_EQ("BazQux", object->bazqux());
  EXPECT_EQ("QUX_QUUX", object->qux_quux());

  std::string error;
  EXPECT_TRUE(AllFieldsAreKnown(*object, json, &error)) << error;
}

// If Prototype field name as keys while json_name is present, AllFieldsAreKnown
// should return false.
TEST_F(JsonKeyTest, WithJsonNameFooBar) {
  TestParseOkWithUnknownKey<WithJsonName>("foo_bar", "foo_bar");
}

TEST_F(JsonKeyTest, WithJsonNameBarBaz) {
  TestParseOkWithUnknownKey<WithJsonName>("barBaz", "barBaz");
}

TEST_F(JsonKeyTest, WithJsonNameBazQux) {
  TestParseOkWithUnknownKey<WithJsonName>("BazQux", "BazQux");
}

TEST_F(JsonKeyTest, WithJsonNameQuxQuux) {
  TestParseOkWithUnknownKey<WithJsonName>("QUX_QUUX", "QUX_QUUX");
}

// JSON field name matches Proto field name
TEST_F(JsonKeyTest, NoJsonNameOk) {
  std::string json =
      "{\n"
      "    \"foo_bar\": \"foo_bar\",\n"
      "    \"barBaz\": \"barBaz\",\n"
      "    \"BazQux\": \"BazQux\",\n"
      "    \"QUX_QUUX\": \"QUX_QUUX\"\n"
      "\n}";
  auto object = JsonStringToMessage<NoJsonName>(json);
  ASSERT_TRUE(object.ok()) << object.error();

  EXPECT_EQ("foo_bar", object->foo_bar());
  EXPECT_EQ("barBaz", object->barbaz());
  EXPECT_EQ("BazQux", object->bazqux());
  EXPECT_EQ("QUX_QUUX", object->qux_quux());

  std::string error;
  EXPECT_TRUE(AllFieldsAreKnown(*object, json, &error)) << error;
}

// JSON field name is lower/UpperCamelCase of Proto field name;
// AllFieldsAreKnown should return false. Although the lower/UpperCamelCase name
// is a valid key accepted by Protobuf's JSON parser, we explicitly disallow the
// behavior.
TEST_F(JsonKeyTest, NoJsonNameFooBar) {
  EXPECT_EQ("fooBar", GetFieldJsonName<NoJsonName>("foo_bar"));
  TestParseOkWithUnknownKey<NoJsonName>("foo_bar", "fooBar");
}

TEST_F(JsonKeyTest, NoJsonNameBarBaz) {
  EXPECT_EQ("barBaz", GetFieldJsonName<NoJsonName>("barBaz"));
  // No test for barBaz because its JSON name is the same as field_name
}

TEST_F(JsonKeyTest, NoJsonNameBazQux) {
  EXPECT_EQ("BazQux", GetFieldJsonName<NoJsonName>("BazQux"));
  // No test for BazQux because its JSON name is the same as field_name
}

TEST_F(JsonKeyTest, NoJsonNameQuxQuux) {
  EXPECT_EQ("QUXQUUX", GetFieldJsonName<NoJsonName>("QUX_QUUX"));
  TestParseOkWithUnknownKey<NoJsonName>("QUX_QUUX", "QUXQUUX");
}

class EmbeddedJsonKeyTest : public LibJsonpbVerifyTest {
 public:
  ErrorOr<Parent> TestEmbeddedError(const std::string& json, const std::string& unknown_key) {
    auto object = JsonStringToMessage<Parent>(json);
    if (!object.ok()) return object;
    std::string error;
    EXPECT_FALSE(AllFieldsAreKnown(*object, json, &error))
        << "AllFieldsAreKnown should return false";
    EXPECT_THAT(error, HasSubstr("unknown keys"));
    EXPECT_THAT(error, HasSubstr(unknown_key));
    return object;
  }
};

TEST_F(EmbeddedJsonKeyTest, Ok) {
  std::string json =
      "{"
      "    \"with_json_name\": {\"FOOBAR\": \"foo_bar\"},\n"
      "    \"repeated_with_json_name\": [{\"BarBaz\": \"barBaz\"}],\n"
      "    \"no_json_name\": {\"BazQux\": \"BazQux\"},\n"
      "    \"repeated_no_json_name\": [{\"QUX_QUUX\": \"QUX_QUUX\"}]\n"
      "}";
  auto object = JsonStringToMessage<Parent>(json);
  ASSERT_TRUE(object.ok()) << object.error();

  EXPECT_EQ("foo_bar", object->with_json_name().foo_bar());
  ASSERT_EQ(1u, object->repeated_with_json_name().size());
  EXPECT_EQ("barBaz", object->repeated_with_json_name().begin()->barbaz());
  EXPECT_EQ("BazQux", object->no_json_name().bazqux());
  ASSERT_EQ(1u, object->repeated_no_json_name().size());
  EXPECT_EQ("QUX_QUUX", object->repeated_no_json_name().begin()->qux_quux());

  std::string error;
  EXPECT_TRUE(AllFieldsAreKnown(*object, json, &error)) << error;
}

TEST_F(EmbeddedJsonKeyTest, FooBar) {
  auto object = TestEmbeddedError("{\"with_json_name\": {\"foo_bar\": \"test\"}}", "foo_bar");
  ASSERT_TRUE(object.ok()) << object.error();
  EXPECT_EQ("test", object->with_json_name().foo_bar());
}

TEST_F(EmbeddedJsonKeyTest, BarBaz) {
  auto object =
      TestEmbeddedError("{\"repeated_with_json_name\": [{\"barBaz\": \"test\"}]}", "barBaz");
  ASSERT_TRUE(object.ok()) << object.error();
  ASSERT_EQ(1u, object->repeated_with_json_name().size());
  EXPECT_EQ("test", object->repeated_with_json_name().begin()->barbaz());
}

TEST_F(EmbeddedJsonKeyTest, NoJsonName) {
  auto object = TestEmbeddedError("{\"no_json_name\": {\"QUXQUUX\": \"test\"}}", "QUXQUUX");
  ASSERT_TRUE(object.ok()) << object.error();
  EXPECT_EQ("test", object->no_json_name().qux_quux());
}

TEST_F(EmbeddedJsonKeyTest, QuxQuux) {
  auto object =
      TestEmbeddedError("{\"repeated_no_json_name\": [{\"QUXQUUX\": \"test\"}]}", "QUXQUUX");
  ASSERT_TRUE(object.ok()) << object.error();
  ASSERT_EQ(1u, object->repeated_no_json_name().size());
  EXPECT_EQ("test", object->repeated_no_json_name().begin()->qux_quux());
}

class ScalarTest : public LibJsonpbVerifyTest {
 public:
  ::testing::AssertionResult IsJsonEq(const std::string& l, const std::string& r) {
    Json::CharReaderBuilder builder;
    std::unique_ptr<Json::CharReader> reader(builder.newCharReader());
    Json::Value lvalue;
    std::string errorMessage;
    if (!reader->parse(&*l.begin(), &*l.end(), &lvalue, &errorMessage))
      return ::testing::AssertionFailure() << errorMessage;
    Json::Value rvalue;
    if (!reader->parse(&*r.begin(), &*r.end(), &rvalue, &errorMessage))
      return ::testing::AssertionFailure() << errorMessage;
    Json::StreamWriterBuilder factory;
    return lvalue == rvalue
               ? (::testing::AssertionSuccess() << "Both are \n"
                                                << Json::writeString(factory, lvalue))
               : (::testing::AssertionFailure() << Json::writeString(factory, lvalue)
                                                << "\n does not equal \n"
                                                << Json::writeString(factory, rvalue));
  }

  bool EqReformattedJson(const std::string& json, std::string* error) {
    return android::jsonpb::EqReformattedJson(json, &scalar_, error);
  }

  Scalar scalar_;
  std::string error_;
};

TEST_F(ScalarTest, Ok) {
  std::string json =
      "{\n"
      "    \"i32\": 1,\n"
      "    \"si32\": 1,\n"
      "    \"i64\": \"1\",\n"
      "    \"si64\": \"1\",\n"
      "    \"f\": 1.5,\n"
      "    \"d\": 1.5,\n"
      "    \"e\": \"FOO\"\n"
      "}";
  auto formatted = FormatJson(json, &scalar_);
  ASSERT_TRUE(formatted.ok()) << formatted.error();
  EXPECT_TRUE(IsJsonEq(json, *formatted));

  EXPECT_TRUE(EqReformattedJson(json, &error_)) << error_;
}

using ScalarTestErrorParam = std::tuple<const char*, const char*>;
class ScalarTestError : public ScalarTest,
                        public ::testing::WithParamInterface<ScalarTestErrorParam> {};

TEST_P(ScalarTestError, Test) {
  std::string json;
  std::string message;
  std::tie(json, message) = GetParam();
  auto formatted = FormatJson(json, &scalar_);
  ASSERT_TRUE(formatted.ok()) << formatted.error();
  EXPECT_FALSE(IsJsonEq(json, *formatted)) << message;
  EXPECT_FALSE(EqReformattedJson(json, &error_)) << "EqReformattedJson should return false";
}

static const std::vector<ScalarTestErrorParam> gScalarTestErrorParams = {
    {"{\"i32\": \"1\"}", "Should not allow int32 values to be quoted"},
    {"{\"si32\": \"1\"}", "Should not allow sint32 values to be quoted"},
    {"{\"i64\": 1}", "Should require int64 values to be quoted"},
    {"{\"si64\": 1}", "Should require sint64 values to be quoted"},
    {"{\"f\": \"1.5\"}", "Should not allow float values to be quoted"},
    {"{\"d\": \"1.5\"}", "Should not allow double values to be quoted"},
    {"{\"e\": 1}", "Should not allow integers for enums"},
};

INSTANTIATE_TEST_SUITE_P(Jsonpb, ScalarTestError, ::testing::ValuesIn(gScalarTestErrorParams));

int main(int argc, char** argv) {
  using ::testing::AddGlobalTestEnvironment;
  using ::testing::InitGoogleTest;

  InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}

}  // namespace jsonpb
}  // namespace android
