/*
 * Copyright (C) 2015 The Android Open Source Project
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

#ifndef SIMPLE_PERF_BUILD_ID_H_
#define SIMPLE_PERF_BUILD_ID_H_

#include <android-base/stringprintf.h>
#include <string.h>
#include <algorithm>
#include <string>
#include <string_view>

namespace simpleperf {

constexpr size_t BUILD_ID_SIZE = 20;

// Shared libraries can have a section called .note.gnu.build-id, containing
// a ~20 bytes unique id. Build id is used to compare if two shared libraries
// are actually the same. BuildId class is the representation of build id in
// memory.
class BuildId {
 public:
  static size_t Size() { return BUILD_ID_SIZE; }

  BuildId() { memset(data_, '\0', BUILD_ID_SIZE); }

  // Copy build id from a byte array, like {0x76, 0x00, 0x32,...}.
  BuildId(const void* data, size_t len) : BuildId() {
    memcpy(data_, data, std::min(len, BUILD_ID_SIZE));
  }

  // Read build id from a hex string, like "7600329e31058e12b145d153ef27cd40e1a5f7b9".
  explicit BuildId(const std::string& s) : BuildId() {
    for (size_t i = 0; i < s.size() && i < BUILD_ID_SIZE * 2; i += 2) {
      unsigned char ch = 0;
      for (size_t j = i; j < i + 2; ++j) {
        ch <<= 4;
        if (s[j] >= '0' && s[j] <= '9') {
          ch |= s[j] - '0';
        } else if (s[j] >= 'a' && s[j] <= 'f') {
          ch |= s[j] - 'a' + 10;
        } else if (s[j] >= 'A' && s[j] <= 'F') {
          ch |= s[j] - 'A' + 10;
        }
      }
      data_[i / 2] = ch;
    }
  }

  const unsigned char* Data() const { return data_; }

  std::string ToString() const {
    std::string s = "0x";
    for (size_t i = 0; i < BUILD_ID_SIZE; ++i) {
      s += android::base::StringPrintf("%02x", data_[i]);
    }
    return s;
  }

  bool operator==(const BuildId& build_id) const {
    return memcmp(data_, build_id.data_, BUILD_ID_SIZE) == 0;
  }

  bool operator!=(const BuildId& build_id) const { return !(*this == build_id); }

  bool IsEmpty() const {
    static BuildId empty_build_id;
    return *this == empty_build_id;
  }

 private:
  unsigned char data_[BUILD_ID_SIZE];
};

inline std::ostream& operator<<(std::ostream& os, const BuildId& build_id) {
  os << build_id.ToString();
  return os;
}

}  // namespace simpleperf

namespace std {

template <>
struct hash<simpleperf::BuildId> {
  size_t operator()(const simpleperf::BuildId& build_id) const noexcept {
    return std::hash<std::string_view>()(
        std::string_view(reinterpret_cast<const char*>(build_id.Data()), build_id.Size()));
  }
};

}  // namespace std

#endif  // SIMPLE_PERF_BUILD_ID_H_
