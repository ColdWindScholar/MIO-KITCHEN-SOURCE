/*
 * Copyright (C) 2018 The Android Open Source Project
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

#include "read_dex_file.h"

#include <gtest/gtest.h>

#include <algorithm>

#include "dso.h"
#include "get_test_data.h"
#include "test_util.h"
#include "utils.h"

using namespace simpleperf;

// @CddTest = 6.1/C-0-2
TEST(read_dex_file, smoke) {
  std::vector<Symbol> symbols;
  auto symbol_callback = [&](DexFileSymbol* symbol) {
    symbols.emplace_back(symbol->name, symbol->addr, symbol->size);
  };
  ASSERT_TRUE(ReadSymbolsFromDexFile(GetTestData("base.vdex"), {0x28}, symbol_callback));
  ASSERT_EQ(12435u, symbols.size());
  auto it = std::find_if(symbols.begin(), symbols.end(),
                         [](const Symbol& symbol) { return symbol.addr == 0x6c77e; });
  ASSERT_NE(it, symbols.end());
  ASSERT_EQ(it->addr, 0x6c77e);
  ASSERT_EQ(it->len, 0x16);
  ASSERT_STREQ(it->Name(), "com.example.simpleperf.simpleperfexamplewithnative.MixActivity$1.run");
}
