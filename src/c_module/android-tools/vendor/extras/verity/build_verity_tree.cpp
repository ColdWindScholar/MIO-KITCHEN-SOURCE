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

#include "verity/build_verity_tree.h"

#include <android-base/logging.h>
#include <android-base/unique_fd.h>
#include <sparse/sparse.h>

#undef NDEBUG

bool generate_verity_tree(const std::string& data_filename,
                          const std::string& verity_filename,
                          HashTreeBuilder* builder,
                          const std::vector<unsigned char>& salt_content,
                          size_t block_size, bool sparse, bool verbose) {
  android::base::unique_fd data_fd(open(data_filename.c_str(), O_RDONLY));
  if (data_fd == -1) {
    PLOG(ERROR) << "failed to open " << data_filename;
    return false;
  }

  std::unique_ptr<sparse_file, decltype(&sparse_file_destroy)> file(nullptr, sparse_file_destroy);
  if (sparse) {
    file.reset(sparse_file_import(data_fd, false, false));
  } else {
    file.reset(sparse_file_import_auto(data_fd, false, verbose));
  }

  if (!file) {
    LOG(ERROR) << "failed to read file " << data_filename;
    return false;
  }

  int64_t len = sparse_file_len(file.get(), false, false);
  if (len % block_size != 0) {
    LOG(ERROR) << "file size " << len << " is not a multiple of " << block_size
               << " byte";
    return false;
  }

  // Initialize the builder to compute the hash tree.
  if (!builder->Initialize(len, salt_content)) {
    LOG(ERROR) << "Failed to initialize HashTreeBuilder";
    return false;
  }

  auto hash_callback = [](void* priv, const void* data, size_t len) {
    auto sparse_hasher = static_cast<HashTreeBuilder*>(priv);
    return sparse_hasher->Update(static_cast<const unsigned char*>(data), len)
               ? 0
               : 1;
  };
  sparse_file_callback(file.get(), false, false, hash_callback, builder);

  if (!builder->BuildHashTree()) {
    return false;
  }

  return builder->WriteHashTreeToFile(verity_filename);
}
