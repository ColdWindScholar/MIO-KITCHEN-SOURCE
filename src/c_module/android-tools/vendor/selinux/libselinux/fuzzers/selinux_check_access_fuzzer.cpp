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
#include <selinux/selinux.h>
#include <string>

std::string GetClass(FuzzedDataProvider &fdp) {
  switch (fdp.ConsumeIntegralInRange(0, 9)) {
  case 0: return "filesystem";
  case 1: return "dir";
  case 2: return "file";
  case 3: return "lnk_file";
  case 4: return "chr_file";
  case 5: return "blk_file";
  case 6: return "sock_file";
  case 7: return "fifo_file";
  case 8: return "fd";
  default: return fdp.ConsumeRandomLengthString();
  }
}

// This is not an exhaustive list.
std::string GetPermission(FuzzedDataProvider &fdp) {
  switch (fdp.ConsumeIntegralInRange(0, 7)) {
  case 0: return "create";
  case 1: return "execute";
  case 2: return "getattr";
  case 3: return "ioctl";
  case 4: return "read";
  case 5: return "setattr";
  case 6: return "write";
  default: return fdp.ConsumeRandomLengthString();
  }
}

extern "C" int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
  FuzzedDataProvider fdp(data, size);

  std::string tclass = GetClass(fdp);
  std::string perm = GetPermission(fdp);
  std::string scon = fdp.ConsumeRandomLengthString();
  std::string tcon = fdp.ConsumeRandomLengthString();

  selinux_check_access(scon.data(), tcon.data(), tclass.data(), perm.data(), NULL);

  return 0;
}
