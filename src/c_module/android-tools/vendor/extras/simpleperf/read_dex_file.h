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

#ifndef SIMPLE_PERF_READ_DEX_FILE_H_
#define SIMPLE_PERF_READ_DEX_FILE_H_

#include <inttypes.h>

#include <functional>
#include <string>
#include <vector>

#ifndef NO_LIBDEXFILE_SUPPORT
#include <art_api/dex_file_support.h>
#endif

namespace simpleperf {

struct DexFileSymbol {
  std::string_view name;
  uint64_t addr;
  uint64_t size;
};

bool ReadSymbolsFromDexFileInMemory(void* addr, uint64_t size, const std::string& debug_filename,
                                    const std::vector<uint64_t>& dex_file_offsets,
                                    const std::function<void(DexFileSymbol*)>& symbol_callback);
bool ReadSymbolsFromDexFile(const std::string& file_path,
                            const std::vector<uint64_t>& dex_file_offsets,
                            const std::function<void(DexFileSymbol*)>& symbol_callback);

}  // namespace simpleperf

#endif  // SIMPLE_PERF_READ_DEX_FILE_H_
