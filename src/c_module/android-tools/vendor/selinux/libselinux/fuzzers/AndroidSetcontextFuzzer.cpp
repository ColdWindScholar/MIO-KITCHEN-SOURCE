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

#include <selinux/android.h>

extern "C" int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
  FuzzedDataProvider fdp(data, size);
  uid_t uid = fdp.ConsumeIntegral<int>();
  bool isSystemServer = fdp.ConsumeBool();
  std::string pkgname = fdp.ConsumeRandomLengthString();
  std::string seinfo = fdp.ConsumeRemainingBytesAsString();

  selinux_android_setcontext(uid, isSystemServer, seinfo.c_str(), pkgname.c_str());

  return 0;
}
