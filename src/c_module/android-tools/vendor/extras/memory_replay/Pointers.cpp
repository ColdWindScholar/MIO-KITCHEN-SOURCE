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

#include <err.h>
#include <inttypes.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#include "err.h"
#include "Pointers.h"

Pointers::Pointers(size_t max_allocs) {
  size_t pagesize = getpagesize();
  // Create a mmap that contains a 4:1 ratio of allocations to entries.
  // Align to a page.
  pointers_size_ = (max_allocs * 4 * sizeof(pointer_data) + pagesize - 1) & ~(pagesize - 1);
  max_pointers_ = pointers_size_ / sizeof(pointer_data);
  void* memory =
      mmap(nullptr, pointers_size_, PROT_READ | PROT_WRITE, MAP_ANON | MAP_PRIVATE, -1, 0);
  if (memory == MAP_FAILED) {
      err(1, "Unable to allocate data for pointer hash: %zu total_allocs", max_allocs);
  }
  // Set all of the pointers to be empty.
  memset(memory, 0, pointers_size_);
  pointers_ = reinterpret_cast<pointer_data*>(memory);
}

Pointers::~Pointers() {
  if (pointers_ != nullptr) {
    munmap(pointers_, pointers_size_);
    pointers_ = nullptr;
  }
}

void Pointers::Add(uintptr_t key_pointer, void* pointer) {
  pointer_data* data = FindEmpty(key_pointer);
  if (data == nullptr) {
    errx(1, "No empty entry found for 0x%" PRIxPTR, key_pointer);
  }
  atomic_store(&data->key_pointer, key_pointer);
  data->pointer = pointer;
}

void* Pointers::Remove(uintptr_t key_pointer) {
  if (key_pointer == 0) {
    errx(1, "Illegal zero value passed to Remove");
  }

  pointer_data* data = Find(key_pointer);
  if (data == nullptr) {
    errx(1, "No pointer value found for 0x%" PRIxPTR, key_pointer);
  }

  void* pointer = data->pointer;
  atomic_store(&data->key_pointer, uintptr_t(0));

  return pointer;
}

Pointers::pointer_data* Pointers::Find(uintptr_t key_pointer) {
  size_t index = GetHash(key_pointer);
  for (size_t entries = max_pointers_; entries != 0; entries--) {
    if (atomic_load(&pointers_[index].key_pointer) == key_pointer) {
      return pointers_ + index;
    }
    if (++index == max_pointers_) {
      index = 0;
    }
  }
  return nullptr;
}

Pointers::pointer_data* Pointers::FindEmpty(uintptr_t key_pointer) {
  size_t index = GetHash(key_pointer);
  for (size_t entries = 0; entries < max_pointers_; entries++) {
    uintptr_t empty = 0;
    if (atomic_compare_exchange_strong(&pointers_[index].key_pointer, &empty,
        uintptr_t(1))) {
      return pointers_ + index;
    }
    if (++index == max_pointers_) {
      index = 0;
    }
  }
  return nullptr;
}

size_t Pointers::GetHash(uintptr_t key_pointer) {
  return key_pointer % max_pointers_;
}

void Pointers::FreeAll() {
  for (size_t i = 0; i < max_pointers_; i++) {
    if (atomic_load(&pointers_[i].key_pointer) != 0) {
      free(pointers_[i].pointer);
    }
  }
}
