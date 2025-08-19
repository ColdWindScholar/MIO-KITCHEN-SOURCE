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
#include "kallsyms.h"

#include <inttypes.h>

#include <string>

#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/properties.h>

#include "environment.h"
#include "read_elf.h"
#include "utils.h"

namespace simpleperf {

#if defined(__linux__)

namespace {

const char kKallsymsPath[] = "/proc/kallsyms";
const char kProcModulesPath[] = "/proc/modules";
const char kPtrRestrictPath[] = "/proc/sys/kernel/kptr_restrict";
const char kLowerPtrRestrictAndroidProp[] = "security.lower_kptr_restrict";
const unsigned int kMinLineTestNonNullSymbols = 10;

// Tries to read the kernel symbol file and ensure that at least some symbol
// addresses are non-null.
bool CanReadKernelSymbolAddresses() {
  LineReader reader(kKallsymsPath);
  if (!reader.Ok()) {
    LOG(DEBUG) << "Failed to read " << kKallsymsPath;
    return false;
  }
  auto symbol_callback = [&](const KernelSymbol& symbol) { return (symbol.addr != 0u); };
  for (unsigned int i = 0; i < kMinLineTestNonNullSymbols; i++) {
    std::string* line = reader.ReadLine();
    if (line == nullptr) {
      return false;
    }
    if (ProcessKernelSymbols(*line, symbol_callback)) {
      return true;
    }
  }
  return false;
}

// Define a scope in which access to kallsyms is possible.
// This is based on the Perfetto implementation.
class ScopedKptrUnrestrict {
 public:
  ScopedKptrUnrestrict();   // Lowers kptr_restrict if necessary.
  ~ScopedKptrUnrestrict();  // Restores the initial kptr_restrict.

  // Indicates if access to kallsyms should be successful.
  bool KallsymsAvailable() { return kallsyms_available_; }

  static void ResetWarning() { kernel_address_warning_printed_ = false; }

 private:
  bool WriteKptrRestrict(const std::string& value);
  void PrintWarning();

  bool restore_property_ = false;
  bool restore_restrict_value_ = false;
  std::string saved_restrict_value_;
  bool kallsyms_available_ = false;

  static bool kernel_address_warning_printed_;
};

bool ScopedKptrUnrestrict::kernel_address_warning_printed_ = false;

ScopedKptrUnrestrict::ScopedKptrUnrestrict() {
  if (CanReadKernelSymbolAddresses()) {
    // Everything seems to work (e.g., we are running as root and kptr_restrict
    // is < 2). Don't touching anything.
    kallsyms_available_ = true;
    return;
  }

  if (GetAndroidVersion() >= 12 && IsRoot()) {
    // Enable kernel addresses by setting property.
    if (!android::base::SetProperty(kLowerPtrRestrictAndroidProp, "1")) {
      LOG(DEBUG) << "Unable to set " << kLowerPtrRestrictAndroidProp << " to 1.";
      PrintWarning();
      return;
    }
    restore_property_ = true;
    // Init takes some time to react to the property change.
    // Unfortunately, we cannot read kptr_restrict because of SELinux. Instead,
    // we detect this by reading the initial lines of kallsyms and checking
    // that they are non-zero. This loop waits for at most 250ms (50 * 5ms).
    for (int attempt = 1; attempt <= 50; ++attempt) {
      usleep(5000);
      if (CanReadKernelSymbolAddresses()) {
        kallsyms_available_ = true;
        return;
      }
    }
    LOG(DEBUG) << "kallsyms addresses are still masked after setting "
               << kLowerPtrRestrictAndroidProp;
    PrintWarning();
    return;
  }

  // Otherwise, read the kptr_restrict value and lower it if needed.
  if (!android::base::ReadFileToString(kPtrRestrictPath, &saved_restrict_value_)) {
    LOG(DEBUG) << "Failed to read " << kPtrRestrictPath;
    PrintWarning();
    return;
  }

  // Progressively lower kptr_restrict until we can read kallsyms.
  for (int value = atoi(saved_restrict_value_.c_str()); value > 0; --value) {
    if (!WriteKptrRestrict(std::to_string(value))) {
      break;
    }
    restore_restrict_value_ = true;
    if (CanReadKernelSymbolAddresses()) {
      kallsyms_available_ = true;
      return;
    }
  }
  PrintWarning();
}

ScopedKptrUnrestrict::~ScopedKptrUnrestrict() {
  if (restore_property_) {
    android::base::SetProperty(kLowerPtrRestrictAndroidProp, "0");
  }
  if (restore_restrict_value_) {
    WriteKptrRestrict(saved_restrict_value_);
  }
}

bool ScopedKptrUnrestrict::WriteKptrRestrict(const std::string& value) {
  if (!android::base::WriteStringToFile(value, kPtrRestrictPath)) {
    LOG(DEBUG) << "Failed to set " << kPtrRestrictPath << " to " << value;
    return false;
  }
  return true;
}

void ScopedKptrUnrestrict::PrintWarning() {
  if (!kernel_address_warning_printed_) {
    kernel_address_warning_printed_ = true;
    LOG(WARNING) << "Access to kernel symbol addresses is restricted. If "
                 << "possible, please do `echo 0 >/proc/sys/kernel/kptr_restrict` "
                 << "to fix this.";
  }
}

}  // namespace

std::vector<KernelMmap> GetLoadedModules() {
  ScopedKptrUnrestrict kptr_unrestrict;
  if (!kptr_unrestrict.KallsymsAvailable()) return {};
  std::vector<KernelMmap> result;
  LineReader reader(kProcModulesPath);
  if (!reader.Ok()) {
    // There is no /proc/modules on Android devices, so we don't print error if failed to open it.
    PLOG(DEBUG) << "failed to open file /proc/modules";
    return result;
  }
  std::string* line;
  std::string name_buf;
  while ((line = reader.ReadLine()) != nullptr) {
    // Parse line like: nf_defrag_ipv6 34768 1 nf_conntrack_ipv6, Live 0xffffffffa0fe5000
    name_buf.resize(line->size());
    char* name = name_buf.data();
    uint64_t addr;
    uint64_t len;
    if (sscanf(line->data(), "%s%" PRIu64 "%*u%*s%*s 0x%" PRIx64, name, &len, &addr) == 3) {
      KernelMmap map;
      map.name = name;
      map.start_addr = addr;
      map.len = len;
      result.push_back(map);
    }
  }
  bool all_zero = true;
  for (const auto& map : result) {
    if (map.start_addr != 0) {
      all_zero = false;
    }
  }
  if (all_zero) {
    LOG(DEBUG) << "addresses in /proc/modules are all zero, so ignore kernel modules";
    return std::vector<KernelMmap>();
  }
  return result;
}

uint64_t GetKernelStartAddress() {
  ScopedKptrUnrestrict kptr_unrestrict;
  if (!kptr_unrestrict.KallsymsAvailable()) return 0;
  LineReader reader(kKallsymsPath);
  if (!reader.Ok()) {
    return 0;
  }
  std::string* line;
  while ((line = reader.ReadLine()) != nullptr) {
    if (strstr(line->data(), "_stext") != nullptr) {
      uint64_t addr;
      if (sscanf(line->data(), "%" PRIx64, &addr) == 1) {
        return addr;
      }
    }
  }
  return 0;
}

bool LoadKernelSymbols(std::string* kallsyms) {
  ScopedKptrUnrestrict kptr_unrestrict;
  if (kptr_unrestrict.KallsymsAvailable()) {
    return android::base::ReadFileToString(kKallsymsPath, kallsyms);
  }
  return false;
}

void ResetKernelAddressWarning() {
  ScopedKptrUnrestrict::ResetWarning();
}

#endif  // defined(__linux__)

bool ProcessKernelSymbols(std::string& symbol_data,
                          const std::function<bool(const KernelSymbol&)>& callback) {
  char* p = &symbol_data[0];
  char* data_end = p + symbol_data.size();
  while (p < data_end) {
    char* line_end = strchr(p, '\n');
    if (line_end != nullptr) {
      *line_end = '\0';
    }
    size_t line_size = (line_end != nullptr) ? (line_end - p) : (data_end - p);
    // Parse line like: ffffffffa005c4e4 d __warned.41698       [libsas]
    char name[line_size];
    char module[line_size];
    strcpy(module, "");

    KernelSymbol symbol;
    int ret = sscanf(p, "%" PRIx64 " %c %s%s", &symbol.addr, &symbol.type, name, module);
    if (line_end != nullptr) {
      *line_end = '\n';
      p = line_end + 1;
    } else {
      p = data_end;
    }
    if (ret >= 3) {
      if (IsArmMappingSymbol(name)) {
        continue;
      }

      symbol.name = name;
      size_t module_len = strlen(module);
      if (module_len > 2 && module[0] == '[' && module[module_len - 1] == ']') {
        module[module_len - 1] = '\0';
        symbol.module = &module[1];
      } else {
        symbol.module = nullptr;
      }

      if (callback(symbol)) {
        return true;
      }
    }
  }
  return false;
}

}  // namespace simpleperf
