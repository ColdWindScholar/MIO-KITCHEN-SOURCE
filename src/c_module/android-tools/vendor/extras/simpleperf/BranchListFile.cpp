/*
 * Copyright (C) 2023 The Android Open Source Project
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

#include "BranchListFile.h"

#include "ETMDecoder.h"
#include "system/extras/simpleperf/branch_list.pb.h"

namespace simpleperf {

static constexpr const char* ETM_BRANCH_LIST_PROTO_MAGIC = "simpleperf:EtmBranchList";

std::string ETMBranchToProtoString(const std::vector<bool>& branch) {
  size_t bytes = (branch.size() + 7) / 8;
  std::string res(bytes, '\0');
  for (size_t i = 0; i < branch.size(); i++) {
    if (branch[i]) {
      res[i >> 3] |= 1 << (i & 7);
    }
  }
  return res;
}

std::vector<bool> ProtoStringToETMBranch(const std::string& s, size_t bit_size) {
  std::vector<bool> branch(bit_size, false);
  for (size_t i = 0; i < bit_size; i++) {
    if (s[i >> 3] & (1 << (i & 7))) {
      branch[i] = true;
    }
  }
  return branch;
}

static std::optional<proto::ETMBinary::BinaryType> ToProtoBinaryType(DsoType dso_type) {
  switch (dso_type) {
    case DSO_ELF_FILE:
      return proto::ETMBinary::ELF_FILE;
    case DSO_KERNEL:
      return proto::ETMBinary::KERNEL;
    case DSO_KERNEL_MODULE:
      return proto::ETMBinary::KERNEL_MODULE;
    default:
      LOG(ERROR) << "unexpected dso type " << dso_type;
      return std::nullopt;
  }
}

bool ETMBinaryMapToString(const ETMBinaryMap& binary_map, std::string& s) {
  proto::BranchList branch_list_proto;
  branch_list_proto.set_magic(ETM_BRANCH_LIST_PROTO_MAGIC);
  std::vector<char> branch_buf;
  for (const auto& p : binary_map) {
    const BinaryKey& key = p.first;
    const ETMBinary& binary = p.second;
    auto binary_proto = branch_list_proto.add_etm_data();

    binary_proto->set_path(key.path);
    if (!key.build_id.IsEmpty()) {
      binary_proto->set_build_id(key.build_id.ToString().substr(2));
    }
    auto opt_binary_type = ToProtoBinaryType(binary.dso_type);
    if (!opt_binary_type.has_value()) {
      return false;
    }
    binary_proto->set_type(opt_binary_type.value());

    for (const auto& addr_p : binary.branch_map) {
      auto addr_proto = binary_proto->add_addrs();
      addr_proto->set_addr(addr_p.first);

      for (const auto& branch_p : addr_p.second) {
        const std::vector<bool>& branch = branch_p.first;
        auto branch_proto = addr_proto->add_branches();

        branch_proto->set_branch(ETMBranchToProtoString(branch));
        branch_proto->set_branch_size(branch.size());
        branch_proto->set_count(branch_p.second);
      }
    }

    if (binary.dso_type == DSO_KERNEL) {
      binary_proto->mutable_kernel_info()->set_kernel_start_addr(key.kernel_start_addr);
    }
  }
  if (!branch_list_proto.SerializeToString(&s)) {
    LOG(ERROR) << "failed to serialize branch list binary map";
    return false;
  }
  return true;
}

static std::optional<DsoType> ToDsoType(proto::ETMBinary::BinaryType binary_type) {
  switch (binary_type) {
    case proto::ETMBinary::ELF_FILE:
      return DSO_ELF_FILE;
    case proto::ETMBinary::KERNEL:
      return DSO_KERNEL;
    case proto::ETMBinary::KERNEL_MODULE:
      return DSO_KERNEL_MODULE;
    default:
      LOG(ERROR) << "unexpected binary type " << binary_type;
      return std::nullopt;
  }
}

static UnorderedETMBranchMap BuildUnorderedETMBranchMap(const proto::ETMBinary& binary_proto) {
  UnorderedETMBranchMap branch_map;
  for (size_t i = 0; i < binary_proto.addrs_size(); i++) {
    const auto& addr_proto = binary_proto.addrs(i);
    auto& b_map = branch_map[addr_proto.addr()];
    for (size_t j = 0; j < addr_proto.branches_size(); j++) {
      const auto& branch_proto = addr_proto.branches(j);
      std::vector<bool> branch =
          ProtoStringToETMBranch(branch_proto.branch(), branch_proto.branch_size());
      b_map[branch] = branch_proto.count();
    }
  }
  return branch_map;
}

bool StringToETMBinaryMap(const std::string& s, ETMBinaryMap& binary_map) {
  LBRData lbr_data;
  return ParseBranchListData(s, binary_map, lbr_data);
}

class ETMThreadTreeWhenRecording : public ETMThreadTree {
 public:
  ETMThreadTreeWhenRecording(bool dump_maps_from_proc)
      : dump_maps_from_proc_(dump_maps_from_proc) {}

  ThreadTree& GetThreadTree() { return thread_tree_; }
  void ExcludePid(pid_t pid) { exclude_pid_ = pid; }

  const ThreadEntry* FindThread(int tid) override {
    const ThreadEntry* thread = thread_tree_.FindThread(tid);
    if (thread == nullptr) {
      if (dump_maps_from_proc_) {
        thread = FindThreadFromProc(tid);
      }
      if (thread == nullptr) {
        return nullptr;
      }
    }
    if (exclude_pid_ && exclude_pid_ == thread->pid) {
      return nullptr;
    }

    if (dump_maps_from_proc_) {
      DumpMapsFromProc(thread->pid);
    }
    return thread;
  }

  void DisableThreadExitRecords() override { thread_tree_.DisableThreadExitRecords(); }
  const MapSet& GetKernelMaps() override { return thread_tree_.GetKernelMaps(); }

 private:
  const ThreadEntry* FindThreadFromProc(int tid) {
    std::string comm;
    pid_t pid;
    if (ReadThreadNameAndPid(tid, &comm, &pid)) {
      thread_tree_.SetThreadName(pid, tid, comm);
      return thread_tree_.FindThread(tid);
    }
    return nullptr;
  }

  void DumpMapsFromProc(int pid) {
    if (dumped_processes_.count(pid) == 0) {
      dumped_processes_.insert(pid);
      std::vector<ThreadMmap> maps;
      if (GetThreadMmapsInProcess(pid, &maps)) {
        for (const auto& map : maps) {
          thread_tree_.AddThreadMap(pid, pid, map.start_addr, map.len, map.pgoff, map.name);
        }
      }
    }
  }

  ThreadTree thread_tree_;
  bool dump_maps_from_proc_;
  std::unordered_set<int> dumped_processes_;
  std::optional<pid_t> exclude_pid_;
};

class ETMBranchListGeneratorImpl : public ETMBranchListGenerator {
 public:
  ETMBranchListGeneratorImpl(bool dump_maps_from_proc)
      : thread_tree_(dump_maps_from_proc), binary_filter_(nullptr) {}

  void SetExcludePid(pid_t pid) override { thread_tree_.ExcludePid(pid); }
  void SetBinaryFilter(const RegEx* binary_name_regex) override {
    binary_filter_.SetRegex(binary_name_regex);
  }

  bool ProcessRecord(const Record& r, bool& consumed) override;
  ETMBinaryMap GetETMBinaryMap() override;

 private:
  struct AuxRecordData {
    uint64_t start;
    uint64_t end;
    bool formatted;
    AuxRecordData(uint64_t start, uint64_t end, bool formatted)
        : start(start), end(end), formatted(formatted) {}
  };

  struct PerCpuData {
    std::vector<uint8_t> aux_data;
    uint64_t data_offset = 0;
    std::queue<AuxRecordData> aux_records;
  };

  bool ProcessAuxRecord(const AuxRecord& r);
  bool ProcessAuxTraceRecord(const AuxTraceRecord& r);
  void ProcessBranchList(const ETMBranchList& branch_list);

  ETMThreadTreeWhenRecording thread_tree_;
  uint64_t kernel_map_start_addr_ = 0;
  BinaryFilter binary_filter_;
  std::map<uint32_t, PerCpuData> cpu_map_;
  std::unique_ptr<ETMDecoder> etm_decoder_;
  std::unordered_map<Dso*, ETMBinary> branch_list_binary_map_;
};

bool ETMBranchListGeneratorImpl::ProcessRecord(const Record& r, bool& consumed) {
  consumed = true;  // No need to store any records.
  uint32_t type = r.type();
  if (type == PERF_RECORD_AUXTRACE_INFO) {
    etm_decoder_ = ETMDecoder::Create(*static_cast<const AuxTraceInfoRecord*>(&r), thread_tree_);
    if (!etm_decoder_) {
      return false;
    }
    etm_decoder_->RegisterCallback(
        [this](const ETMBranchList& branch) { ProcessBranchList(branch); });
    return true;
  }
  if (type == PERF_RECORD_AUX) {
    return ProcessAuxRecord(*static_cast<const AuxRecord*>(&r));
  }
  if (type == PERF_RECORD_AUXTRACE) {
    return ProcessAuxTraceRecord(*static_cast<const AuxTraceRecord*>(&r));
  }
  if (type == PERF_RECORD_MMAP && r.InKernel()) {
    auto& mmap_r = *static_cast<const MmapRecord*>(&r);
    if (android::base::StartsWith(mmap_r.filename, DEFAULT_KERNEL_MMAP_NAME)) {
      kernel_map_start_addr_ = mmap_r.data->addr;
    }
  }
  thread_tree_.GetThreadTree().Update(r);
  return true;
}

bool ETMBranchListGeneratorImpl::ProcessAuxRecord(const AuxRecord& r) {
  OverflowResult result = SafeAdd(r.data->aux_offset, r.data->aux_size);
  if (result.overflow || r.data->aux_size > SIZE_MAX) {
    LOG(ERROR) << "invalid aux record";
    return false;
  }
  size_t size = r.data->aux_size;
  uint64_t start = r.data->aux_offset;
  uint64_t end = result.value;
  PerCpuData& data = cpu_map_[r.Cpu()];
  if (start >= data.data_offset && end <= data.data_offset + data.aux_data.size()) {
    // The ETM data is available. Process it now.
    uint8_t* p = data.aux_data.data() + (start - data.data_offset);
    if (!etm_decoder_) {
      LOG(ERROR) << "ETMDecoder isn't created";
      return false;
    }
    return etm_decoder_->ProcessData(p, size, !r.Unformatted(), r.Cpu());
  }
  // The ETM data isn't available. Put the aux record into queue.
  data.aux_records.emplace(start, end, !r.Unformatted());
  return true;
}

bool ETMBranchListGeneratorImpl::ProcessAuxTraceRecord(const AuxTraceRecord& r) {
  OverflowResult result = SafeAdd(r.data->offset, r.data->aux_size);
  if (result.overflow || r.data->aux_size > SIZE_MAX) {
    LOG(ERROR) << "invalid auxtrace record";
    return false;
  }
  size_t size = r.data->aux_size;
  uint64_t start = r.data->offset;
  uint64_t end = result.value;
  PerCpuData& data = cpu_map_[r.Cpu()];
  data.data_offset = start;
  CHECK(r.location.addr != nullptr);
  data.aux_data.resize(size);
  memcpy(data.aux_data.data(), r.location.addr, size);

  // Process cached aux records.
  while (!data.aux_records.empty() && data.aux_records.front().start < end) {
    const AuxRecordData& aux = data.aux_records.front();
    if (aux.start >= start && aux.end <= end) {
      uint8_t* p = data.aux_data.data() + (aux.start - start);
      if (!etm_decoder_) {
        LOG(ERROR) << "ETMDecoder isn't created";
        return false;
      }
      if (!etm_decoder_->ProcessData(p, aux.end - aux.start, aux.formatted, r.Cpu())) {
        return false;
      }
    }
    data.aux_records.pop();
  }
  return true;
}

void ETMBranchListGeneratorImpl::ProcessBranchList(const ETMBranchList& branch_list) {
  if (!binary_filter_.Filter(branch_list.dso)) {
    return;
  }
  auto& branch_map = branch_list_binary_map_[branch_list.dso].branch_map;
  ++branch_map[branch_list.addr][branch_list.branch];
}

ETMBinaryMap ETMBranchListGeneratorImpl::GetETMBinaryMap() {
  ETMBinaryMap binary_map;
  for (auto& p : branch_list_binary_map_) {
    Dso* dso = p.first;
    ETMBinary& binary = p.second;
    binary.dso_type = dso->type();
    BuildId build_id;
    GetBuildId(*dso, build_id);
    BinaryKey key(dso->Path(), build_id);
    if (binary.dso_type == DSO_KERNEL) {
      if (kernel_map_start_addr_ == 0) {
        LOG(WARNING) << "Can't convert kernel ip addresses without kernel start addr. So remove "
                        "branches for the kernel.";
        continue;
      }
      key.kernel_start_addr = kernel_map_start_addr_;
    }
    binary_map[key] = std::move(binary);
  }
  return binary_map;
}

std::unique_ptr<ETMBranchListGenerator> ETMBranchListGenerator::Create(bool dump_maps_from_proc) {
  return std::unique_ptr<ETMBranchListGenerator>(
      new ETMBranchListGeneratorImpl(dump_maps_from_proc));
}

ETMBranchListGenerator::~ETMBranchListGenerator() {}

bool LBRDataToString(const LBRData& data, std::string& s) {
  proto::BranchList branch_list_proto;
  branch_list_proto.set_magic(ETM_BRANCH_LIST_PROTO_MAGIC);
  auto lbr_proto = branch_list_proto.mutable_lbr_data();
  for (const LBRSample& sample : data.samples) {
    auto sample_proto = lbr_proto->add_samples();
    sample_proto->set_binary_id(sample.binary_id);
    sample_proto->set_vaddr_in_file(sample.vaddr_in_file);
    for (const LBRBranch& branch : sample.branches) {
      auto branch_proto = sample_proto->add_branches();
      branch_proto->set_from_binary_id(branch.from_binary_id);
      branch_proto->set_to_binary_id(branch.to_binary_id);
      branch_proto->set_from_vaddr_in_file(branch.from_vaddr_in_file);
      branch_proto->set_to_vaddr_in_file(branch.to_vaddr_in_file);
    }
  }
  for (const BinaryKey& binary : data.binaries) {
    auto binary_proto = lbr_proto->add_binaries();
    binary_proto->set_path(binary.path);
    binary_proto->set_build_id(binary.build_id.ToString().substr(2));
  }
  if (!branch_list_proto.SerializeToString(&s)) {
    LOG(ERROR) << "failed to serialize lbr data";
    return false;
  }
  return true;
}

bool ParseBranchListData(const std::string& s, ETMBinaryMap& etm_data, LBRData& lbr_data) {
  proto::BranchList branch_list_proto;
  if (!branch_list_proto.ParseFromString(s)) {
    PLOG(ERROR) << "failed to read ETMBranchList msg";
    return false;
  }
  if (branch_list_proto.magic() != ETM_BRANCH_LIST_PROTO_MAGIC) {
    PLOG(ERROR) << "not in etm branch list format in branch_list.proto";
    return false;
  }
  for (size_t i = 0; i < branch_list_proto.etm_data_size(); i++) {
    const auto& binary_proto = branch_list_proto.etm_data(i);
    BinaryKey key(binary_proto.path(), BuildId(binary_proto.build_id()));
    if (binary_proto.has_kernel_info()) {
      key.kernel_start_addr = binary_proto.kernel_info().kernel_start_addr();
    }
    ETMBinary& binary = etm_data[key];
    auto dso_type = ToDsoType(binary_proto.type());
    if (!dso_type) {
      LOG(ERROR) << "invalid binary type " << binary_proto.type();
      return false;
    }
    binary.dso_type = dso_type.value();
    binary.branch_map = BuildUnorderedETMBranchMap(binary_proto);
  }
  if (branch_list_proto.has_lbr_data()) {
    const auto& lbr_data_proto = branch_list_proto.lbr_data();
    lbr_data.samples.resize(lbr_data_proto.samples_size());
    for (size_t i = 0; i < lbr_data_proto.samples_size(); ++i) {
      const auto& sample_proto = lbr_data_proto.samples(i);
      LBRSample& sample = lbr_data.samples[i];
      sample.binary_id = sample_proto.binary_id();
      sample.vaddr_in_file = sample_proto.vaddr_in_file();
      sample.branches.resize(sample_proto.branches_size());
      for (size_t j = 0; j < sample_proto.branches_size(); ++j) {
        const auto& branch_proto = sample_proto.branches(j);
        LBRBranch& branch = sample.branches[j];
        branch.from_binary_id = branch_proto.from_binary_id();
        branch.to_binary_id = branch_proto.to_binary_id();
        branch.from_vaddr_in_file = branch_proto.from_vaddr_in_file();
        branch.to_vaddr_in_file = branch_proto.to_vaddr_in_file();
      }
    }
    for (size_t i = 0; i < lbr_data_proto.binaries_size(); ++i) {
      const auto& binary_proto = lbr_data_proto.binaries(i);
      lbr_data.binaries.emplace_back(binary_proto.path(), BuildId(binary_proto.build_id()));
    }
  }
  return true;
}

}  // namespace simpleperf
