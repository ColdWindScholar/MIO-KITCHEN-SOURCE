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

#include <sstream>
#include <string>
#include <vector>

#include <google/protobuf/message.h>
#include <json/reader.h>
#include <json/value.h>
#include <jsonpb/jsonpb.h>

namespace android {
namespace jsonpb {

// Ensure that the JSON file has no unknown fields that is not defined in proto.
// Because we want forwards compatibility, the parser of JSON files must ignore
// unknown fields. This is achievable with libprotobuf version > 3.0-beta.
// - <= 3.0-beta: we have to check unknown fields manually, and parser cannot
// use libprotobuf
//   to parse JSON files.
// - < 3.5: libprotobuf discards all unknown fields. We can still check unknown
// fields manually, but
//   an easier way to check is `json == FormatJson(json)` (schematically)
// - >= 3.5: Unknown fields are preserved, so FormatJson() may contain these
// unknown fields. We can
//   still check fields manually, or use reflection mechanism.
//
// For example, if a new field "foo" is added to cgroups.json but not to
// cgroups.proto, libprocessgroup could technically read the value of "foo" by
// using other libraries that parse JSON strings, effectively working around the
// schema.
//
// This test also ensures that the parser does not use alternative key names.
// For example, if the proto file states: message Foo { string foo_bar = 1;
// string bar_baz = 2 [json_name = "BarBaz"]; } Then the parser accepts
// "foo_bar" "fooBar", "bar_baz", "BarBaz" as valid key names. Here, we enforce
// that the JSON file must use "foo_bar" and "BarBaz".
//
// Requiring this avoids surprises like:
//     message Foo { string FooBar = 1; }
//     { "fooBar" : "s" }
// conforms with the schema, because libprotobuf accept "fooBar" as a valid key.
// The correct schema should be:
//     message Foo { string foo_bar = 1 [json_name="fooBar"]; }
//
// Params:
//    path: path to navigate inside JSON tree. For example, {"foo", "bar"} for
//    the value "string" in
//          {"foo": {"bar" : "string"}}
bool AllFieldsAreKnown(const google::protobuf::Message& message, const std::string& json,
                       std::string* error);

// Format the given JSON string according to Prototype T. This will serialize
// the JSON string to a Prototype message, then re-print the message as JSON. By
// reformatting the JSON string, we effectively enforces that the JSON source
// file uses conventions of Protobuf's JSON writer; e.g. 64-bit integers /
// special floating point numbers (inf, NaN, etc.) in strings, enum values in
// names, etc.
//
// Params:
//   scratch_space: The scratch space to use to store the Protobuf message. It
//   must be a pointer
//                  to the schema that the JSON string conforms to.
bool EqReformattedJson(const std::string& json, google::protobuf::Message* scratch_space,
                       std::string* error);

namespace internal {
// See EqReformattedJson().
ErrorOr<std::string> FormatJson(const std::string& json, google::protobuf::Message* scratch_space);

}  // namespace internal

}  // namespace jsonpb
}  // namespace android
