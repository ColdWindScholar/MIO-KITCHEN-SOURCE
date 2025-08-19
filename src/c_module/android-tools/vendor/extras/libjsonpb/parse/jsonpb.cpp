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

#include <jsonpb/jsonpb.h>

#include <android-base/logging.h>
#include <google/protobuf/descriptor.h>
#include <google/protobuf/message.h>
#include <google/protobuf/util/json_util.h>
#include <google/protobuf/util/type_resolver_util.h>

namespace android {
namespace jsonpb {

using google::protobuf::DescriptorPool;
using google::protobuf::Message;
using google::protobuf::util::NewTypeResolverForDescriptorPool;
using google::protobuf::util::TypeResolver;

static constexpr char kTypeUrlPrefix[] = "type.googleapis.com";

std::string GetTypeUrl(const Message& message) {
  return std::string(kTypeUrlPrefix) + "/" + message.GetDescriptor()->full_name();
}

ErrorOr<std::string> MessageToJsonString(const Message& message) {
  std::unique_ptr<TypeResolver> resolver(
      NewTypeResolverForDescriptorPool(kTypeUrlPrefix, DescriptorPool::generated_pool()));

  google::protobuf::util::JsonPrintOptions options;
  options.add_whitespace = true;

  std::string json;
  auto status = BinaryToJsonString(resolver.get(), GetTypeUrl(message), message.SerializeAsString(),
                                   &json, options);

  if (!status.ok()) {
#if GOOGLE_PROTOBUF_VERSION < 3016000
    return MakeError<std::string>(status.error_message().as_string());
#elif GOOGLE_PROTOBUF_VERSION < 4022000
    return MakeError<std::string>(status.message().as_string());
#else
    return MakeError<std::string>(std::string(status.message()));
#endif
  }
  return ErrorOr<std::string>(std::move(json));
}

namespace internal {
ErrorOr<std::monostate> JsonStringToMessage(const std::string& content, Message* message) {
  std::unique_ptr<TypeResolver> resolver(
      NewTypeResolverForDescriptorPool(kTypeUrlPrefix, DescriptorPool::generated_pool()));

  std::string binary;
  auto status = JsonToBinaryString(resolver.get(), GetTypeUrl(*message), content, &binary);
  if (!status.ok()) {
#if GOOGLE_PROTOBUF_VERSION < 3016000
    return MakeError<std::monostate>(status.error_message().as_string());
#elif GOOGLE_PROTOBUF_VERSION < 4022000
    return MakeError<std::monostate>(status.message().as_string());
#else
    return MakeError<std::monostate>(std::string(status.message()));
#endif
  }
  if (!message->ParseFromString(binary)) {
    return MakeError<std::monostate>("Fail to parse.");
  }
  return ErrorOr<std::monostate>();
}
}  // namespace internal

}  // namespace jsonpb
}  // namespace android
