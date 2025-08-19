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
#include <stdint.h>
#include <selinux/android.h>
#include <string>

selabel_handle *GetHandle(FuzzedDataProvider &fdp) {
  switch (fdp.ConsumeIntegralInRange(0, 4)) {
  case 0: return selinux_android_file_context_handle();
  case 1: return selinux_android_service_context_handle();
  case 2: return selinux_android_hw_service_context_handle();
  case 3: return selinux_android_vendor_service_context_handle();
  case 4: return selinux_android_keystore2_key_context_handle();
  default: return selinux_android_file_context_handle();
  }
}

extern "C" int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
  FuzzedDataProvider fdp(data, size);

  std::string str = fdp.ConsumeRandomLengthString();
  static auto handle = GetHandle(fdp);
  char *conn = NULL;
  int type = fdp.ConsumeIntegral<int>();

  selabel_lookup(handle, &conn, str.data(), type);

  free(conn);

  return 0;
}
