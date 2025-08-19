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

#include "RegEx.h"

#include <regex>

#include <android-base/logging.h>

namespace simpleperf {

RegExMatch::~RegExMatch() {}

class RegExMatchImpl : public RegExMatch {
 public:
  RegExMatchImpl(std::string_view s, const std::regex& re)
      : match_it_(s.data(), s.data() + s.size(), re) {}

  bool IsValid() const override { return match_it_ != std::cregex_iterator(); }

  std::string GetField(size_t index) const override { return match_it_->str(index); }

  void MoveToNextMatch() override { ++match_it_; }

 private:
  std::cregex_iterator match_it_;
};

class RegExImpl : public RegEx {
 public:
  RegExImpl(std::string_view pattern)
      : RegEx(pattern), re_(pattern_, std::regex::ECMAScript | std::regex::optimize) {}

  bool Match(std::string_view s) const override {
    return std::regex_match(s.begin(), s.end(), re_);
  }
  bool Search(std::string_view s) const override {
    return std::regex_search(s.begin(), s.end(), re_);
  }
  std::unique_ptr<RegExMatch> SearchAll(std::string_view s) const override {
    return std::unique_ptr<RegExMatch>(new RegExMatchImpl(s, re_));
  }
  std::optional<std::string> Replace(const std::string& s,
                                     const std::string& format) const override {
    try {
      return {std::regex_replace(s, re_, format)};
    } catch (std::regex_error& e) {
      LOG(ERROR) << "regex_error: " << e.what() << ", pattern " << pattern_ << ", format "
                 << format;
      return std::nullopt;
    }
  }

 private:
  std::regex re_;
};

std::unique_ptr<RegEx> RegEx::Create(std::string_view pattern) {
  try {
    return std::make_unique<RegExImpl>(pattern);
  } catch (std::regex_error& e) {
    LOG(ERROR) << "regex_error: " << e.what() << ", pattern " << pattern;
    return nullptr;
  }
}

bool SearchInRegs(std::string_view s, const std::vector<std::unique_ptr<RegEx>>& regs) {
  for (auto& reg : regs) {
    if (reg->Search(s)) {
      return true;
    }
  }
  return false;
}

}  // namespace simpleperf
