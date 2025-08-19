/*
 * Copyright (C) 2019 The Android Open Source Project
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

#include "ETMRecorder.h"

#include <stdio.h>
#include <sys/sysinfo.h>

#include <limits>
#include <memory>
#include <string>

#include <android-base/expected.h>
#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/parseint.h>
#include <android-base/properties.h>
#include <android-base/strings.h>

#include "ETMConstants.h"
#include "environment.h"
#include "utils.h"

namespace simpleperf {

using android::base::expected;
using android::base::unexpected;

static const std::string ETM_DIR = "/sys/bus/event_source/devices/cs_etm/";

// from coresight_get_trace_id(int cpu) in include/linux/coresight-pmu.h
static int GetTraceId(int cpu) {
  return 0x10 + cpu * 2;
}

template <typename T>
static bool ReadValueInEtmDir(const std::string& file, T* value, bool report_error = true,
                              const std::string& prefix = "") {
  std::string s;
  uint64_t v;
  if (!android::base::ReadFileToString(ETM_DIR + file, &s) ||
      !android::base::StartsWith(s, prefix) ||
      !android::base::ParseUint(&android::base::Trim(s)[prefix.size()], &v)) {
    if (report_error) {
      LOG(ERROR) << "failed to read " << ETM_DIR << file;
    }
    return false;
  }
  *value = static_cast<T>(v);
  return true;
}

static uint32_t GetBits(uint32_t value, int start, int end) {
  return (value >> start) & ((1U << (end - start + 1)) - 1);
}

int ETMPerCpu::GetMajorVersion() const {
  return GetBits(trcidr1, 8, 11);
}

bool ETMPerCpu::IsContextIDSupported() const {
  return GetBits(trcidr2, 5, 9) >= 4;
}

bool ETMPerCpu::IsTimestampSupported() const {
  return GetBits(trcidr0, 24, 28) > 0;
}

bool ETMPerCpu::IsCycAccSupported() const {
  return GetBits(trcidr0, 7, 7);
}

bool ETMPerCpu::IsEnabled() const {
  return GetBits(trcauthstatus, 0, 3) == 0xc;
}

ETMRecorder& ETMRecorder::GetInstance() {
  static ETMRecorder etm;
  return etm;
}

int ETMRecorder::GetEtmEventType() {
  if (event_type_ == 0) {
    if (!IsDir(ETM_DIR) || !ReadValueInEtmDir("type", &event_type_, false)) {
      event_type_ = -1;
    }
  }
  return event_type_;
}

std::unique_ptr<EventType> ETMRecorder::BuildEventType() {
  int etm_event_type = GetEtmEventType();
  if (etm_event_type == -1) {
    return nullptr;
  }
  return std::make_unique<EventType>("cs-etm", etm_event_type, 0,
                                     "CoreSight ETM instruction tracing", "arm");
}

bool ETMRecorder::IsETMDriverAvailable() {
  return IsDir(ETM_DIR);
}

expected<bool, std::string> ETMRecorder::CheckEtmSupport() {
  if (GetEtmEventType() == -1) {
    return unexpected("etm event type isn't supported on device");
  }
  if (!ReadEtmInfo()) {
    return unexpected("etm devices are not available");
  }
  for (const auto& p : etm_info_) {
    if (p.second.GetMajorVersion() < 4) {
      return unexpected("etm device version is less than 4.0");
    }
    if (!p.second.IsContextIDSupported()) {
      return unexpected("etm device doesn't support contextID");
    }
    if (!p.second.IsEnabled()) {
      return unexpected("etm device isn't enabled by the bootloader");
    }
  }
  if (!FindSinkConfig()) {
    // Trigger a manual probe of etr. Then wait and recheck.
    std::string prop_name = "profcollectd.etr.probe";
    bool res = android::base::SetProperty(prop_name, "1");
    if (!res) {
      LOG(ERROR) << "fails to setprop" << prop_name;
    }
    usleep(200000);  // Wait for 200ms.
    if (!FindSinkConfig()) {
      return unexpected("can't find etr device, which moves etm data to memory");
    }
  }
  etm_supported_ = true;
  return true;
}

bool ETMRecorder::ReadEtmInfo() {
  int contextid_value;
  use_contextid2_ = ReadValueInEtmDir("/format/contextid", &contextid_value, false, "config:") &&
                    contextid_value == ETM_OPT_CTXTID2;

  std::vector<int> online_cpus = GetOnlineCpus();
  for (const auto& name : GetEntriesInDir(ETM_DIR)) {
    int cpu;
    if (sscanf(name.c_str(), "cpu%d", &cpu) == 1) {
      // We can't read ETM registers for offline cpus. So skip them.
      if (std::find(online_cpus.begin(), online_cpus.end(), cpu) == online_cpus.end()) {
        continue;
      }
      ETMPerCpu& cpu_info = etm_info_[cpu];
      bool success = ReadValueInEtmDir(name + "/trcidr/trcidr0", &cpu_info.trcidr0) &&
                     ReadValueInEtmDir(name + "/trcidr/trcidr1", &cpu_info.trcidr1) &&
                     ReadValueInEtmDir(name + "/trcidr/trcidr2", &cpu_info.trcidr2) &&
                     ReadValueInEtmDir(name + "/trcidr/trcidr4", &cpu_info.trcidr4) &&
                     ReadValueInEtmDir(name + "/trcidr/trcidr8", &cpu_info.trcidr8) &&
                     ReadValueInEtmDir(name + "/mgmt/trcauthstatus", &cpu_info.trcauthstatus);

      if (!ReadValueInEtmDir(name + "/mgmt/trcdevarch", &cpu_info.trcdevarch, false)) {
        cpu_info.trcdevarch = 0;
      }
      if (!success) {
        return false;
      }
    }
  }
  return (etm_info_.size() == online_cpus.size());
}

bool ETMRecorder::FindSinkConfig() {
  bool has_etr = false;
  bool has_trbe = false;
  for (const auto& name : GetEntriesInDir(ETM_DIR + "sinks")) {
    if (!has_etr && name.find("etr") != -1) {
      if (ReadValueInEtmDir("sinks/" + name, &sink_config_)) {
        has_etr = true;
      }
    }
    if (name.find("trbe") != -1) {
      has_trbe = true;
      break;
    }
  }
  if (has_trbe) {
    // When TRBE is present, let the driver choose the most suitable
    // configuration.
    sink_config_ = 0;
  }
  return has_trbe || has_etr;
}

void ETMRecorder::SetEtmPerfEventAttr(perf_event_attr* attr) {
  CHECK(etm_supported_);
  BuildEtmConfig();
  attr->config = etm_event_config_;
  attr->config2 = sink_config_;
  attr->config3 = cc_threshold_config_;
}

void ETMRecorder::BuildEtmConfig() {
  if (etm_event_config_ == 0) {
    if (use_contextid2_) {
      etm_event_config_ |= 1ULL << ETM_OPT_CTXTID2;
      etm_config_reg_ |= 1U << ETM4_CFG_BIT_VMID;
      etm_config_reg_ |= 1U << ETM4_CFG_BIT_VMID_OPT;
    } else {
      etm_event_config_ |= 1ULL << ETM_OPT_CTXTID;
      etm_config_reg_ |= 1U << ETM4_CFG_BIT_CTXTID;
    }

    if (record_timestamp_) {
      bool ts_supported = true;
      for (auto& p : etm_info_) {
        ts_supported &= p.second.IsTimestampSupported();
      }
      if (ts_supported) {
        etm_event_config_ |= 1ULL << ETM_OPT_TS;
        etm_config_reg_ |= 1U << ETM4_CFG_BIT_TS;
      }
    }

    if (record_cycles_) {
      bool cycles_supported = true;
      for (auto& p : etm_info_) {
        cycles_supported &= p.second.IsCycAccSupported();
      }
      if (cycles_supported) {
        etm_event_config_ |= 1ULL << ETM_OPT_CYCACC;
        etm_config_reg_ |= 1U << ETM4_CFG_BIT_CCI;

        if (cycle_threshold_) {
          cc_threshold_config_ |= cycle_threshold_;
        }
      }
    }
  }
}

AuxTraceInfoRecord ETMRecorder::CreateAuxTraceInfoRecord() {
  AuxTraceInfoRecord::DataType data;
  memset(&data, 0, sizeof(data));
  data.aux_type = AuxTraceInfoRecord::AUX_TYPE_ETM;
  data.version = 1;
  data.nr_cpu = etm_info_.size();
  data.pmu_type = GetEtmEventType();
  std::vector<AuxTraceInfoRecord::ETEInfo> ete(etm_info_.size());
  size_t pos = 0;
  for (auto& p : etm_info_) {
    auto& e = ete[pos++];
    if (p.second.trcdevarch == 0) {
      e.magic = AuxTraceInfoRecord::MAGIC_ETM4;
      e.nrtrcparams = sizeof(AuxTraceInfoRecord::ETM4Info) / sizeof(uint64_t) - 3;
    } else {
      e.magic = AuxTraceInfoRecord::MAGIC_ETE;
      e.nrtrcparams = sizeof(AuxTraceInfoRecord::ETEInfo) / sizeof(uint64_t) - 3;
    }
    e.cpu = p.first;
    e.trcconfigr = etm_config_reg_;
    e.trctraceidr = GetTraceId(p.first);
    e.trcidr0 = p.second.trcidr0;
    e.trcidr1 = p.second.trcidr1;
    e.trcidr2 = p.second.trcidr2;
    e.trcidr8 = p.second.trcidr8;
    e.trcauthstatus = p.second.trcauthstatus;
    e.trcdevarch = p.second.trcdevarch;
  }
  return AuxTraceInfoRecord(data, ete);
}

size_t ETMRecorder::GetAddrFilterPairs() {
  CHECK(etm_supported_);
  size_t min_pairs = std::numeric_limits<size_t>::max();
  for (auto& p : etm_info_) {
    min_pairs = std::min<size_t>(min_pairs, GetBits(p.second.trcidr4, 0, 3));
  }
  if (min_pairs > 0) {
    --min_pairs;  // One pair is used by the kernel to set default addr filter.
  }
  return min_pairs;
}

void ETMRecorder::SetRecordTimestamp(bool record) {
  record_timestamp_ = record;
}

void ETMRecorder::SetRecordCycles(bool record) {
  record_cycles_ = record;
}

void ETMRecorder::SetCycleThreshold(size_t threshold) {
  cycle_threshold_ = threshold;
}

}  // namespace simpleperf
