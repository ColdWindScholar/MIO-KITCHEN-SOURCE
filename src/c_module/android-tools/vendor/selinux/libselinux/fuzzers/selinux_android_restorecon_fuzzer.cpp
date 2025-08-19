/******************************************************************************
 *
 * Copyright (C) 2020 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at:
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 *****************************************************************************
 */

#include <fuzzer/FuzzedDataProvider.h>
#include <selinux/android.h>
#include <string>

unsigned int GetFlags(FuzzedDataProvider &fdp) {
  unsigned int flags = 0;
  if (fdp.ConsumeBool()) {
    flags |= SELINUX_ANDROID_RESTORECON_NOCHANGE;
  }
  if (fdp.ConsumeBool()) {
    flags |= SELINUX_ANDROID_RESTORECON_VERBOSE;
  }
  if (fdp.ConsumeBool()) {
    flags |= SELINUX_ANDROID_RESTORECON_RECURSE;
  }
  if (fdp.ConsumeBool()) {
    flags |= SELINUX_ANDROID_RESTORECON_FORCE;
  }
  if (fdp.ConsumeBool()) {
    flags |= SELINUX_ANDROID_RESTORECON_DATADATA;
  }
  if (fdp.ConsumeBool()) {
    flags |= SELINUX_ANDROID_RESTORECON_SKIPCE;
  }
  if (fdp.ConsumeBool()) {
    flags |= SELINUX_ANDROID_RESTORECON_CROSS_FILESYSTEMS;
  }
  if (fdp.ConsumeBool()) {
    flags |= SELINUX_ANDROID_RESTORECON_SKIP_SEHASH;
  }
  // Try adding random noise (which likely isn't a real flag).
  if (fdp.ConsumeBool()) {
    flags |= fdp.ConsumeIntegral<unsigned int>();
  }
  return flags;
}

extern "C" int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
  FuzzedDataProvider fdp(data, size);

  std::string file = fdp.ConsumeRandomLengthString();
  unsigned int flags = GetFlags(fdp);

  selinux_android_restorecon(file.c_str(), flags);

  return 0;
}
