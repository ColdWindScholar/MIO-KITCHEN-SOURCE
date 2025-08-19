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

#ifndef __BUILD_VERITY_TREE_UTILS_H__
#define __BUILD_VERITY_TREE_UTILS_H__

#include <inttypes.h>
#include <stddef.h>

inline uint64_t div_round_up(uint64_t x, uint64_t y) { return (x + y - 1) / y; }

size_t verity_tree_blocks(uint64_t data_size, size_t block_size,
                          size_t hash_size, size_t level);

#endif  // __BUILD_VERITY_TREE_UTILS_H__
