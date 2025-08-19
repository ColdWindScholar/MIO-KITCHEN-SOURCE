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

#ifndef __BUILD_VERITY_TREE_H__
#define __BUILD_VERITY_TREE_H__

#include <inttypes.h>

#include <string>
#include <vector>

#include "hash_tree_builder.h"

bool generate_verity_tree(const std::string& data_filename,
                          const std::string& verity_filename,
                          HashTreeBuilder* hasher,
                          const std::vector<unsigned char>& salt_content,
                          size_t block_size, bool sparse, bool verbose);

#endif  // __BUILD_VERITY_TREE_H__
