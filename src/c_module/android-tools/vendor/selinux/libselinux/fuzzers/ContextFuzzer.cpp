/*
 * Copyright 2020 The Android Open Source Project
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

#include <fuzzer/FuzzedDataProvider.h>
#include <stddef.h>
#include <stdint.h>
#include <string>

#include <selinux/context.h>

extern "C" int LLVMFuzzerTestOneInput(const uint8_t *data, [[maybe_unused]] size_t size) {
  FuzzedDataProvider fdp(data, size);
  std::string contextName = fdp.ConsumeRemainingBytesAsString();

  context_t context = context_new(contextName.c_str());
  // According to docs, this should be safe to call with null pointer
  // (meaning even if previous call fails).
  context_free(context);

  return 0;
}
