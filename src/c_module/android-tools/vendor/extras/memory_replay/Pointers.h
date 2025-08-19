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

#pragma once

#include <stdatomic.h>
#include <stdint.h>

class Pointers {
 public:
  struct pointer_data {
    std::atomic_uintptr_t key_pointer;
    void* pointer;
  };

  explicit Pointers(size_t max_allocs);
  virtual ~Pointers();

  void Add(uintptr_t key_pointer, void* pointer);

  void* Remove(uintptr_t key_pointer);

  size_t max_pointers() { return max_pointers_; }

  void FreeAll();

 private:
  pointer_data* FindEmpty(uintptr_t key_pointer);
  pointer_data* Find(uintptr_t key_pointer);
  size_t GetHash(uintptr_t key_pointer);

  pointer_data* pointers_ = nullptr;
  size_t pointers_size_ = 0;
  size_t max_pointers_ = 0;
};
