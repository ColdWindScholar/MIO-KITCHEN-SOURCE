/*
 * Copyright (C) 2021 The Android Open Source Project
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

#pragma once

namespace simpleperf {
// Config bits from include/linux/coresight-pmu.h in the kernel
// For etm_event_config:
static constexpr int ETM_OPT_CYCACC = 12;
static constexpr int ETM_OPT_CTXTID = 14;
static constexpr int ETM_OPT_CTXTID2 = 15;
static constexpr int ETM_OPT_TS = 28;
// For etm_config_reg:
static constexpr int ETM4_CFG_BIT_CCI = 4;
static constexpr int ETM4_CFG_BIT_CTXTID = 6;
static constexpr int ETM4_CFG_BIT_VMID = 7;
static constexpr int ETM4_CFG_BIT_TS = 11;
static constexpr int ETM4_CFG_BIT_VMID_OPT = 15;
}  // namespace simpleperf
