/*
 * Copyright (C) 2020 The Android Open Source Project
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

#include "read_symbol_map.h"

#include <errno.h>
#include <stdlib.h>

#include <algorithm>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include "dso.h"

namespace simpleperf {
namespace {

std::optional<std::string_view> ConsumeWord(std::string_view& content_ref) {
  size_t begin = content_ref.find_first_not_of(" \t");
  if (begin == content_ref.npos) {
    return {};
  }

  size_t end = content_ref.find_first_of(" \t", begin + 1);
  if (end == content_ref.npos) {
    end = content_ref.size();
  }

  auto res = content_ref.substr(begin, end - begin);
  content_ref.remove_prefix(end);
  return res;
}

std::optional<uint64_t> ConsumeUInt(std::string_view& content_ref) {
  auto word = ConsumeWord(content_ref);
  if (!word) {
    return {};
  }

  errno = 0;
  const char* start = word.value().data();
  char* stop;
  auto res = strtoull(start, &stop, 0);
  if (errno != 0 || stop - start != word.value().size()) {
    return {};
  }

  return res;
}

void ReadSymbol(std::string_view content, std::vector<Symbol>* symbols) {
  auto addr = ConsumeUInt(content);
  if (!addr) {
    return;
  }

  auto size = ConsumeUInt(content);
  if (!size) {
    return;
  }

  // Interpret the rest of the line as the symbol name, after stripping leading
  // and trailing spaces.
  size_t symbol_begin = content.find_first_not_of(" \t");
  if (symbol_begin == content.npos) {
    return;
  }
  size_t symbol_end = content.find_last_not_of(" \t") + 1;

  auto name = content.substr(symbol_begin, symbol_end - symbol_begin);

  symbols->emplace_back(name, addr.value(), size.value());
}

}  // namespace

std::vector<Symbol> ReadSymbolMapFromString(const std::string& content) {
  std::vector<Symbol> symbols;

  for (size_t begin = 0;;) {
    size_t end = content.find_first_of("\n\r", begin);

    if (end == content.npos) {
      ReadSymbol({content.c_str() + begin, content.size() - begin}, &symbols);
      std::sort(symbols.begin(), symbols.end(), Symbol::CompareValueByAddr);
      return symbols;
    }

    ReadSymbol({content.c_str() + begin, end - begin}, &symbols);
    begin = end + 1;
  }
}

}  // namespace simpleperf
