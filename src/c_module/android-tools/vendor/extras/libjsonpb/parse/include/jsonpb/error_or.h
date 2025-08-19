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
#include <utility>
#include <variant>

#include <android-base/logging.h>

namespace android {
namespace jsonpb {

template <typename T>
struct ErrorOr {
  template <class... Args>
  explicit ErrorOr(Args&&... args) : data_(kIndex1, std::forward<Args>(args)...) {}
  T& operator*() {
    CHECK(ok());
    return *std::get_if<1u>(&data_);
  }
  const T& operator*() const {
    CHECK(ok());
    return *std::get_if<1u>(&data_);
  }
  T* operator->() {
    CHECK(ok());
    return std::get_if<1u>(&data_);
  }
  const T* operator->() const {
    CHECK(ok());
    return std::get_if<1u>(&data_);
  }
  const std::string& error() const {
    CHECK(!ok());
    return *std::get_if<0u>(&data_);
  }
  bool ok() const { return data_.index() != 0; }
  static ErrorOr<T> MakeError(std::string message) {
    return ErrorOr<T>(std::move(message), Tag::kDummy);
  }

 private:
  enum class Tag { kDummy };
  static constexpr std::in_place_index_t<0> kIndex0{};
  static constexpr std::in_place_index_t<1> kIndex1{};
  ErrorOr(std::string msg, Tag) : data_(kIndex0, std::move(msg)) {}

  std::variant<std::string, T> data_;
};

template <typename T>
inline ErrorOr<T> MakeError(std::string message) {
  return ErrorOr<T>::MakeError(std::move(message));
}

}  // namespace jsonpb
}  // namespace android
