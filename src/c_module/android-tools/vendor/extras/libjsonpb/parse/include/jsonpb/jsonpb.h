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

#include <string>

#include <jsonpb/error_or.h>

#include <google/protobuf/message.h>

namespace android {
namespace jsonpb {

namespace internal {
ErrorOr<std::monostate> JsonStringToMessage(const std::string& content,
                                            google::protobuf::Message* message);
}  // namespace internal

// TODO: JsonStringToMessage is a newly added function in protobuf
// and is not yet available in the android tree. Replace this function with
// https://developers.google.com/protocol-buffers/docs/reference/cpp/google.protobuf.util.json_util#JsonStringToMessage.details
// when the android tree gets updated
template <typename T>
ErrorOr<T> JsonStringToMessage(const std::string& content) {
  ErrorOr<T> ret;
  auto error = internal::JsonStringToMessage(content, &*ret);
  if (!error.ok()) {
    return MakeError<T>(error.error());
  }
  return ret;
}

// TODO: MessageToJsonString is a newly added function in protobuf
// and is not yet available in the android tree. Replace this function with
// https://developers.google.com/protocol-buffers/docs/reference/cpp/google.protobuf.util.json_util#MessageToJsonString.details
// when the android tree gets updated.
//
// The new MessageToJsonString also allows preserving proto field names. However,
// the function here can't. Hence, a field name "foo_bar" without json_name option
// will be "fooBar" in the final output. Additional checks are needed to ensure
// that doesn't happen.
ErrorOr<std::string> MessageToJsonString(const google::protobuf::Message& message);

}  // namespace jsonpb
}  // namespace android
