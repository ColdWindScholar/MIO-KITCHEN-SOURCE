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

#include <gtest/gtest.h>

#include <filesystem>

#include <android-base/file.h>

#include "dso.h"
#include "environment.h"
#include "get_test_data.h"
#include "test_util.h"
#include "thread_tree.h"

namespace fs = std::filesystem;
using namespace simpleperf;

// @CddTest = 6.1/C-0-2
TEST(environment, PrepareVdsoFile) {
  std::string content;
  ASSERT_TRUE(android::base::ReadFileToString("/proc/self/maps", &content));
  if (content.find("[vdso]") == std::string::npos) {
    // Vdso isn't used, no need to test.
    return;
  }
  TemporaryDir tmpdir;
  auto scoped_temp_files = ScopedTempFiles::Create(tmpdir.path);
  ASSERT_TRUE(scoped_temp_files);
  PrepareVdsoFile();
  std::unique_ptr<Dso> dso =
      Dso::CreateDso(DSO_ELF_FILE, "[vdso]", sizeof(size_t) == sizeof(uint64_t));
  ASSERT_TRUE(dso != nullptr);
  ASSERT_NE(dso->GetDebugFilePath(), "[vdso]");
}

// @CddTest = 6.1/C-0-2
TEST(environment, GetHardwareFromCpuInfo) {
  std::string cpu_info =
      "CPU revision : 10\n\n"
      "Hardware : Symbol i.MX6 Freeport_Plat Quad/DualLite (Device Tree)\n";
  ASSERT_EQ("Symbol i.MX6 Freeport_Plat Quad/DualLite (Device Tree)",
            GetHardwareFromCpuInfo(cpu_info));
}

// @CddTest = 6.1/C-0-2
TEST(environment, MappedFileOnlyExistInMemory) {
  ASSERT_TRUE(MappedFileOnlyExistInMemory(""));
  ASSERT_TRUE(MappedFileOnlyExistInMemory("[stack]"));
  ASSERT_TRUE(MappedFileOnlyExistInMemory("[anon:.bss]"));
  ASSERT_FALSE(MappedFileOnlyExistInMemory("[vdso]"));
  ASSERT_TRUE(MappedFileOnlyExistInMemory("/dev/__properties__/u:object_r"));
  ASSERT_TRUE(MappedFileOnlyExistInMemory("//anon"));
  ASSERT_TRUE(MappedFileOnlyExistInMemory("/memfd:/jit-cache"));
  ASSERT_FALSE(MappedFileOnlyExistInMemory("./TemporaryFile-12345"));
  ASSERT_FALSE(MappedFileOnlyExistInMemory("/system/lib64/libc.so"));
}

// @CddTest = 6.1/C-0-2
TEST(environment, SetPerfEventLimits) {
#if defined(__ANDROID__)
  if (GetAndroidVersion() <= kAndroidVersionP) {
    return;
  }
  uint64_t orig_freq = 100000;
  size_t orig_percent = 25;
  uint64_t orig_mlock_kb = 516;
  bool has_freq = GetMaxSampleFrequency(&orig_freq);
  bool has_percent = GetCpuTimeMaxPercent(&orig_percent);
  bool has_mlock_kb = GetPerfEventMlockKb(&orig_mlock_kb);

  ASSERT_TRUE(SetPerfEventLimits(orig_freq + 1, orig_percent + 1, orig_mlock_kb + 1));
  if (has_freq) {
    uint64_t value;
    ASSERT_TRUE(GetMaxSampleFrequency(&value));
    ASSERT_EQ(value, orig_freq + 1);
  }
  if (has_percent) {
    size_t value;
    ASSERT_TRUE(GetCpuTimeMaxPercent(&value));
    ASSERT_EQ(value, orig_percent + 1);
  }
  if (has_mlock_kb) {
    uint64_t value;
    ASSERT_TRUE(GetPerfEventMlockKb(&value));
    ASSERT_EQ(value, orig_mlock_kb + 1);
  }
  // Restore the environment.
  ASSERT_TRUE(SetPerfEventLimits(orig_freq, orig_percent, orig_mlock_kb));
#else  // !defined(__ANDROID__)
  GTEST_LOG_(INFO) << "This test tests setting properties on Android.";
#endif
}

// @CddTest = 6.1/C-0-2
TEST(environment, GetKernelVersion) {
  ASSERT_TRUE(GetKernelVersion());
}

// @CddTest = 6.1/C-0-2
TEST(environment, GetModuleBuildId) {
  BuildId build_id;
  fs::path dir(GetTestData("sysfs/module/fake_kernel_module/notes"));
  ASSERT_TRUE(fs::copy_file(dir / "note.gnu.build-id", dir / ".note.gnu.build-id",
                            fs::copy_options::overwrite_existing));
  ASSERT_TRUE(GetModuleBuildId("fake_kernel_module", &build_id, GetTestData("sysfs")));
  ASSERT_EQ(build_id, BuildId("3e0ba155286f3454"));
}

// @CddTest = 6.1/C-0-2
TEST(environment, GetKernelAndModuleMmaps) {
  TEST_REQUIRE_ROOT();
  KernelMmap kernel_mmap;
  std::vector<KernelMmap> module_mmaps;
  GetKernelAndModuleMmaps(&kernel_mmap, &module_mmaps);
  // The kernel map should contain the kernel start address.
  ASSERT_EQ(kernel_mmap.name, std::string(DEFAULT_KERNEL_MMAP_NAME) + "_stext");
  ASSERT_GT(kernel_mmap.start_addr, 0);
}

// @CddTest = 6.1/C-0-2
TEST(environment, GetProcessUid) {
  std::optional<uid_t> uid = GetProcessUid(getpid());
  ASSERT_TRUE(uid.has_value());
  ASSERT_EQ(uid.value(), getuid());
}

// @CddTest = 6.1/C-0-2
TEST(environment, GetAppType) {
  TEST_REQUIRE_APPS();
  ASSERT_EQ(GetAppType("com.android.simpleperf.debuggable"), "debuggable");
  ASSERT_EQ(GetAppType("com.android.simpleperf.profileable"), "profileable");
  ASSERT_EQ(GetAppType("com.android.simpleperf.app_not_exist"), "not_exist");
}

// @CddTest = 6.1/C-0-2
TEST(environment, GetMemorySize) {
  auto value = GetMemorySize();
  ASSERT_GT(value, 0);
}

// @CddTest = 6.1/C-0-2
TEST(environment, GetARMCpuModels) {
#if defined(__aarch64__) && defined(__ANDROID__)
  auto models = GetARMCpuModels();
  ASSERT_FALSE(models.empty());
  ASSERT_FALSE(models[0].cpus.empty());
  ASSERT_EQ(models[0].cpus[0], 0);
#endif  // defined(__aarch64__) && defined(__ANDROID__)
}
