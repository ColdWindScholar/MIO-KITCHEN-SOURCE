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

#include "build_verity_tree_utils.h"

#include <limits>

#include <android-base/logging.h>

size_t verity_tree_blocks(uint64_t data_size, size_t block_size,
                          size_t hash_size, size_t level) {
  uint64_t level_blocks = div_round_up(data_size, block_size);
  uint64_t hashes_per_block = div_round_up(block_size, hash_size);

  do {
    level_blocks = div_round_up(level_blocks, hashes_per_block);
  } while (level--);

  CHECK_LE(level_blocks, std::numeric_limits<size_t>::max());
  return level_blocks;
}