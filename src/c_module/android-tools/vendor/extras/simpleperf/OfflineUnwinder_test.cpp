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

#include "OfflineUnwinder.h"
#include "OfflineUnwinder_impl.h"

#include <android-base/parseint.h>
#include <unwindstack/RegsArm64.h>

#include <gtest/gtest.h>

using namespace simpleperf;

bool CheckUnwindMaps(UnwindMaps& maps, const MapSet& map_set) {
  if (maps.Total() != map_set.maps.size()) {
    return false;
  }
  std::shared_ptr<unwindstack::MapInfo> prev_real_map;
  for (auto& info : maps) {
    if (info == nullptr || map_set.maps.find(info->start()) == map_set.maps.end()) {
      return false;
    }
    if (prev_real_map != nullptr && prev_real_map->name() == info->name() &&
        prev_real_map != info->GetPrevRealMap()) {
      return false;
    }
    if (!info->IsBlank()) {
      prev_real_map = info;
    }
  }
  return true;
}

// @CddTest = 6.1/C-0-2
TEST(OfflineUnwinder, UnwindMaps) {
  // 1. Create fake map entries.
  std::unique_ptr<Dso> fake_dso = Dso::CreateDso(DSO_UNKNOWN_FILE, "unknown");
  std::vector<MapEntry> map_entries;
  for (size_t i = 0; i < 10; i++) {
    map_entries.emplace_back(i, 1, i, fake_dso.get(), false);
  }

  // 2. Init with empty maps.
  MapSet map_set;
  UnwindMaps maps;
  maps.UpdateMaps(map_set);
  ASSERT_TRUE(CheckUnwindMaps(maps, map_set));

  // 3. Add maps starting from even addr.
  map_set.version = 1;
  for (size_t i = 0; i < map_entries.size(); i += 2) {
    map_set.maps.insert(std::make_pair(map_entries[i].start_addr, &map_entries[i]));
  }

  maps.UpdateMaps(map_set);
  ASSERT_TRUE(CheckUnwindMaps(maps, map_set));

  // 4. Add maps starting from odd addr.
  map_set.version = 2;
  for (size_t i = 1; i < 10; i += 2) {
    map_set.maps.insert(std::make_pair(map_entries[i].start_addr, &map_entries[i]));
  }
  maps.UpdateMaps(map_set);
  ASSERT_TRUE(CheckUnwindMaps(maps, map_set));

  // 5. Remove maps starting from even addr.
  map_set.version = 3;
  for (size_t i = 0; i < 10; i += 2) {
    map_set.maps.erase(map_entries[i].start_addr);
  }
  maps.UpdateMaps(map_set);
  ASSERT_TRUE(CheckUnwindMaps(maps, map_set));

  // 6. Remove all maps.
  map_set.version = 4;
  map_set.maps.clear();
  maps.UpdateMaps(map_set);
  ASSERT_TRUE(CheckUnwindMaps(maps, map_set));
}

// @CddTest = 6.1/C-0-2
TEST(OfflineUnwinder, CollectMetaInfo) {
  std::unordered_map<std::string, std::string> info_map;
  OfflineUnwinder::CollectMetaInfo(&info_map);
  if (auto it = info_map.find(OfflineUnwinder::META_KEY_ARM64_PAC_MASK); it != info_map.end()) {
    uint64_t arm64_pack_mask;
    ASSERT_TRUE(android::base::ParseUint(it->second, &arm64_pack_mask));
    ASSERT_NE(arm64_pack_mask, 0);
  }
}

// @CddTest = 6.1/C-0-2
TEST(OfflineUnwinder, ARM64PackMask) {
  std::unordered_map<std::string, std::string> info_map;
  info_map[OfflineUnwinder::META_KEY_ARM64_PAC_MASK] = "0xff00000000";
  std::unique_ptr<OfflineUnwinderImpl> unwinder(new OfflineUnwinderImpl(false));
  unwinder->LoadMetaInfo(info_map);

  RegSet fake_regs(0, 0, nullptr);
  fake_regs.arch = ARCH_ARM64;
  unwindstack::Regs* regs = unwinder->GetBacktraceRegs(fake_regs);
  ASSERT_TRUE(regs != nullptr);
  auto& arm64 = *static_cast<unwindstack::RegsArm64*>(regs);
  arm64.SetPseudoRegister(unwindstack::Arm64Reg::ARM64_PREG_RA_SIGN_STATE, 1);
  arm64.set_pc(0xffccccccccULL);
  ASSERT_EQ(arm64.pc(), 0xccccccccULL);
}
