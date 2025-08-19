/*
 * Copyright (C) 2017 The Android Open Source Project
 *
 * Permission is hereby granted, free of charge, to any person
 * obtaining a copy of this software and associated documentation
 * files (the "Software"), to deal in the Software without
 * restriction, including without limitation the rights to use, copy,
 * modify, merge, publish, distribute, sublicense, and/or sell copies
 * of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be
 * included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 * EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
 * NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
 * BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
 * ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

#include <endian.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <map>

#include <base/debug/stack_trace.h>

#include <libavb/libavb.h>

int avb_memcmp(const void* src1, const void* src2, size_t n) {
  return memcmp(src1, src2, n);
}

void* avb_memcpy(void* dest, const void* src, size_t n) {
  return memcpy(dest, src, n);
}

void* avb_memset(void* dest, const int c, size_t n) {
  return memset(dest, c, n);
}

int avb_strcmp(const char* s1, const char* s2) {
  return strcmp(s1, s2);
}

int avb_strncmp(const char* s1, const char* s2, size_t n) {
  return strncmp(s1, s2, n);
}

size_t avb_strlen(const char* str) {
  return strlen(str);
}

void avb_abort(void) {
  abort();
}

void avb_print(const char* message) {
  fprintf(stderr, "%s", message);
}

void avb_printv(const char* message, ...) {
  va_list ap;
  const char* m;

  va_start(ap, message);
  for (m = message; m != NULL; m = va_arg(ap, const char*)) {
    fprintf(stderr, "%s", m);
  }
  va_end(ap);
}

void avb_printf(const char* fmt, ...) {
  va_list ap;
  va_start(ap, fmt);
  vfprintf(stderr, fmt, ap);
  va_end(ap);
}

typedef struct {
  size_t size;
  base::debug::StackTrace stack_trace;
} AvbAllocatedBlock;

static std::map<void*, AvbAllocatedBlock> allocated_blocks;

void* avb_malloc_(size_t size) {
  void* ptr = malloc(size);
  avb_assert(ptr != nullptr);
  AvbAllocatedBlock block;
  block.size = size;
  allocated_blocks[ptr] = block;
  return ptr;
}

void avb_free(void* ptr) {
  auto block_it = allocated_blocks.find(ptr);
  if (block_it == allocated_blocks.end()) {
    avb_fatal("Tried to free pointer to non-allocated block.\n");
    return;
  }
  allocated_blocks.erase(block_it);
  free(ptr);
}

uint32_t avb_div_by_10(uint64_t* dividend) {
  uint32_t rem = (uint32_t)(*dividend % 10);
  *dividend /= 10;
  return rem;
}

namespace avb {

void testing_memory_reset() {
  allocated_blocks.clear();
}

bool testing_memory_all_freed() {
  if (allocated_blocks.size() == 0) {
    return true;
  }

  size_t sum = 0;
  for (const auto& block_it : allocated_blocks) {
    sum += block_it.second.size;
  }
  fprintf(stderr,
          "%zd bytes still allocated in %zd blocks:\n",
          sum,
          allocated_blocks.size());
  size_t n = 0;
  for (const auto& block_it : allocated_blocks) {
    fprintf(stderr,
            "--\nAllocation %zd/%zd of %zd bytes:\n",
            1 + n++,
            allocated_blocks.size(),
            block_it.second.size);
    block_it.second.stack_trace.Print();
  }
  return false;
}

// Also check leaks at process exit.
__attribute__((destructor)) static void ensure_all_memory_freed_at_exit() {
  if (!testing_memory_all_freed()) {
    avb_fatal("libavb memory leaks at process exit.\n");
  }
}

}  // namespace avb
