/*
 * Copyright (C) 2020 The Android Open Source Project
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

#ifndef SIMPLE_PERF_KALLSYMS_H_
#define SIMPLE_PERF_KALLSYMS_H_

#include <string>

#include "environment.h"

namespace simpleperf {

struct KernelSymbol {
  uint64_t addr;
  char type;
  const char* name;
  const char* module;  // If nullptr, the symbol is not in a kernel module.
};

// Parses symbol_data as the content of /proc/kallsyms, calling the callback for
// each symbol that is found. Stops the parsing if the callback returns true.
bool ProcessKernelSymbols(std::string& symbol_data,
                          const std::function<bool(const KernelSymbol&)>& callback);

#if defined(__linux__)

// Returns the list of currently loaded kernel modules.
std::vector<KernelMmap> GetLoadedModules();

// Returns the start address of the kernel. It uses /proc/kallsyms to find this
// address. Returns 0 if unknown.
uint64_t GetKernelStartAddress();

// Loads the /proc/kallsyms file, requesting access if required. The value of
// kptr_restrict might be modified during the process. Its original value will
// be restored. This usually requires root privileges.
bool LoadKernelSymbols(std::string* kallsyms);

// only for testing
void ResetKernelAddressWarning();

#endif  // defined(__linux__)

}  // namespace simpleperf

#endif  // SIMPLE_PERF_KALLSYMS_H_
