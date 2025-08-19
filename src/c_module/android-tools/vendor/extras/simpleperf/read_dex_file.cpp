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

#include <fcntl.h>

#include <algorithm>
#include <functional>
#include <iterator>
#include <string>
#include <utility>
#include <vector>

#include <android-base/logging.h>
#include <android-base/mapped_file.h>
#include <android-base/unique_fd.h>
#include <art_api/dex_file_support.h>

#include "utils.h"

namespace simpleperf {

static void ReadSymbols(art_api::dex::DexFile& dex_file, uint64_t file_offset,
                        const std::function<void(DexFileSymbol*)>& symbol_cb) {
  auto callback = [&](const art_api::dex::DexFile::Method& method) {
    size_t name_size, code_size;
    const char* name = method.GetQualifiedName(/*with_params=*/false, &name_size);
    size_t offset = method.GetCodeOffset(&code_size);
    DexFileSymbol symbol{std::string_view(name, name_size), file_offset + offset, code_size};
    symbol_cb(&symbol);
  };
  dex_file.ForEachMethod(callback);
}

bool ReadSymbolsFromDexFileInMemory(void* addr, uint64_t size, const std::string& debug_filename,
                                    const std::vector<uint64_t>& dex_file_offsets,
                                    const std::function<void(DexFileSymbol*)>& symbol_callback) {
  for (uint64_t file_offset : dex_file_offsets) {
    size_t max_file_size;
    if (__builtin_sub_overflow(size, file_offset, &max_file_size)) {
      LOG(WARNING) << "failed to read dex file symbols from " << debug_filename << "(offset "
                   << file_offset << ")";
      return false;
    }
    uint8_t* file_addr = static_cast<uint8_t*>(addr) + file_offset;
    std::unique_ptr<art_api::dex::DexFile> dex_file;
    art_api::dex::DexFile::Error error_msg =
        art_api::dex::DexFile::Create(file_addr, max_file_size, nullptr, "", &dex_file);
    if (dex_file == nullptr) {
      LOG(WARNING) << "failed to read dex file symbols from " << debug_filename << "(offset "
                   << file_offset << "): " << error_msg.ToString();
      return false;
    }
    ReadSymbols(*dex_file, file_offset, symbol_callback);
  }
  return true;
}

bool ReadSymbolsFromDexFile(const std::string& file_path,
                            const std::vector<uint64_t>& dex_file_offsets,
                            const std::function<void(DexFileSymbol*)>& symbol_callback) {
  android::base::unique_fd fd(TEMP_FAILURE_RETRY(open(file_path.c_str(), O_RDONLY | O_CLOEXEC)));
  if (fd == -1) {
    return false;
  }
  size_t file_size = GetFileSize(file_path);
  if (file_size == 0) {
    return false;
  }
  std::unique_ptr<android::base::MappedFile> map;
  map = android::base::MappedFile::FromFd(fd, 0, file_size, PROT_READ);
  if (map == nullptr) {
    return false;
  }
  return ReadSymbolsFromDexFileInMemory(map->data(), file_size, file_path, dex_file_offsets,
                                        symbol_callback);
}

}  // namespace simpleperf
