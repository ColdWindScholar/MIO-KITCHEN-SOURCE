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

#ifndef SIMPLE_PERF_RECORD_H_
#define SIMPLE_PERF_RECORD_H_

#include <stdio.h>
#include <sys/types.h>

#include <memory>
#include <queue>
#include <string>
#include <vector>

#include <android-base/logging.h>

#include "CallChainJoiner.h"
#include "OfflineUnwinder.h"
#include "build_id.h"
#include "perf_event.h"

namespace simpleperf {

enum user_record_type {
  PERF_RECORD_USER_DEFINED_TYPE_START = 64,
  PERF_RECORD_ATTR = 64,
  PERF_RECORD_EVENT_TYPE,
  PERF_RECORD_TRACING_DATA,
  PERF_RECORD_BUILD_ID,
  PERF_RECORD_FINISHED_ROUND,

  PERF_RECORD_AUXTRACE_INFO = 70,
  PERF_RECORD_AUXTRACE = 71,
  PERF_RECORD_COMPRESSED = 81,

  SIMPLE_PERF_RECORD_TYPE_START = 32768,
  SIMPLE_PERF_RECORD_KERNEL_SYMBOL,
  // TODO: remove DsoRecord and SymbolRecord.
  SIMPLE_PERF_RECORD_DSO,
  SIMPLE_PERF_RECORD_SYMBOL,
  SIMPLE_PERF_RECORD_SPLIT,
  SIMPLE_PERF_RECORD_SPLIT_END,
  SIMPLE_PERF_RECORD_EVENT_ID,
  SIMPLE_PERF_RECORD_CALLCHAIN,
  SIMPLE_PERF_RECORD_UNWINDING_RESULT,
  SIMPLE_PERF_RECORD_TRACING_DATA,
  SIMPLE_PERF_RECORD_DEBUG,
};

// perf_event_header uses u16 to store record size. However, that is not
// enough for storing records like KERNEL_SYMBOL or TRACING_DATA. So define
// a simpleperf_record_header struct to store record header for simpleperf
// defined records (type > SIMPLE_PERF_RECORD_TYPE_START).
struct simpleperf_record_header {
  uint32_t type;
  uint16_t size1;
  uint16_t size0;
};

static_assert(sizeof(simpleperf_record_header) == sizeof(perf_event_header),
              "simpleperf_record_header should have the same size as perf_event_header");

struct PerfSampleIpType {
  uint64_t ip;
};

struct PerfSampleTidType {
  uint32_t pid, tid;
};

struct PerfSampleTimeType {
  uint64_t time;
};

struct PerfSampleAddrType {
  uint64_t addr;
};

struct PerfSampleIdType {
  uint64_t id;
};

struct PerfSampleStreamIdType {
  uint64_t stream_id;
};

struct PerfSampleCpuType {
  uint32_t cpu, res;
};

struct PerfSamplePeriodType {
  uint64_t period;
};

struct PerfSampleReadType {
  uint64_t time_enabled = 0;
  uint64_t time_running = 0;
  std::vector<uint64_t> counts;
  std::vector<uint64_t> ids;
};

struct PerfSampleCallChainType {
  uint64_t ip_nr;
  uint64_t* ips;
};

struct PerfSampleRawType {
  uint32_t size;
  const char* data;
};

struct BranchStackItemType {
  uint64_t from;
  uint64_t to;
  uint64_t flags;
};

struct PerfSampleBranchStackType {
  uint64_t stack_nr;
  const BranchStackItemType* stack;
};

struct PerfSampleRegsUserType {
  uint64_t abi;
  uint64_t reg_mask;
  uint64_t reg_nr;
  const uint64_t* regs;
};

struct PerfSampleStackUserType {
  uint64_t size;
  char* data;
  uint64_t dyn_size;
};

struct RecordHeader {
 public:
  uint32_t type;
  uint16_t misc;
  uint32_t size;

  RecordHeader() : type(0), misc(0), size(0) {}

  bool Parse(const char* p) {
    auto pheader = reinterpret_cast<const perf_event_header*>(p);
    if (pheader->type < SIMPLE_PERF_RECORD_TYPE_START) {
      type = pheader->type;
      misc = pheader->misc;
      size = pheader->size;
    } else {
      auto sheader = reinterpret_cast<const simpleperf_record_header*>(p);
      type = sheader->type;
      misc = 0;
      size = (sheader->size1 << 16) | sheader->size0;
    }
    if (size < sizeof(perf_event_header)) {
      LOG(ERROR) << "invalid record";
      return false;
    }
    return true;
  }

  void MoveToBinaryFormat(char*& p) const {
    if (type < SIMPLE_PERF_RECORD_TYPE_START) {
      auto pheader = reinterpret_cast<perf_event_header*>(p);
      pheader->type = type;
      pheader->misc = misc;
      CHECK_LT(size, 1u << 16);
      pheader->size = static_cast<uint16_t>(size);
    } else {
      auto sheader = reinterpret_cast<simpleperf_record_header*>(p);
      sheader->type = type;
      CHECK_EQ(misc, 0u);
      sheader->size1 = size >> 16;
      sheader->size0 = size & 0xffff;
    }
    p += sizeof(perf_event_header);
  }
};

// SampleId is optional at the end of a record in binary format. Its content is
// determined by sample_id_all and sample_type in perf_event_attr. To avoid the
// complexity of referring to perf_event_attr each time, we copy sample_id_all
// and sample_type inside the SampleId structure.
struct SampleId {
  bool sample_id_all;
  uint64_t sample_type;

  PerfSampleTidType tid_data;             // Valid if sample_id_all && PERF_SAMPLE_TID.
  PerfSampleTimeType time_data;           // Valid if sample_id_all && PERF_SAMPLE_TIME.
  PerfSampleIdType id_data;               // Valid if sample_id_all && PERF_SAMPLE_ID.
  PerfSampleStreamIdType stream_id_data;  // Valid if sample_id_all && PERF_SAMPLE_STREAM_ID.
  PerfSampleCpuType cpu_data;             // Valid if sample_id_all && PERF_SAMPLE_CPU.

  SampleId();

  // Create the content of sample_id. It depends on the attr we use.
  size_t CreateContent(const perf_event_attr& attr, uint64_t event_id);

  // Parse sample_id from binary format in the buffer pointed by p.
  bool ReadFromBinaryFormat(const perf_event_attr& attr, const char* p, const char* end);

  // Write the binary format of sample_id to the buffer pointed by p.
  void WriteToBinaryFormat(char*& p) const;
  void Dump(size_t indent) const;
  size_t Size() const;
};

// Usually one record contains the following three parts in order in binary
// format:
//   RecordHeader (at the head of a record, containing type and size info)
//   data depends on the record type
//   SampleId (optional part at the end of a record)
// We hold the common parts (RecordHeader and SampleId) in the base class
// Record, and hold the type specific data part in classes derived from Record.
struct Record {
  RecordHeader header;
  SampleId sample_id;

  Record() : binary_(nullptr), own_binary_(false) {}
  Record(Record&& other) noexcept;

  virtual ~Record() {
    if (own_binary_) {
      delete[] binary_;
    }
  }

  virtual bool Parse(const perf_event_attr& attr, char* p, char* end) = 0;

  void OwnBinary() { own_binary_ = true; }

  uint32_t type() const { return header.type; }

  uint16_t misc() const { return header.misc; }

  uint32_t size() const { return header.size; }

  static uint32_t header_size() { return sizeof(perf_event_header); }

  bool InKernel() const {
    uint16_t cpumode = header.misc & PERF_RECORD_MISC_CPUMODE_MASK;
    return cpumode == PERF_RECORD_MISC_KERNEL || cpumode == PERF_RECORD_MISC_GUEST_KERNEL;
  }

  void SetTypeAndMisc(uint32_t type, uint16_t misc) {
    header.type = type;
    header.misc = misc;
  }

  void SetSize(uint32_t size) { header.size = size; }

  void Dump(size_t indent = 0) const;

  const char* Binary() const { return binary_; }
  char* BinaryForTestingOnly() { return binary_; }

  virtual uint64_t Timestamp() const;
  virtual uint32_t Cpu() const;
  virtual uint64_t Id() const;

 protected:
  bool ParseHeader(char*& p, char*& end);
  void UpdateBinary(char* new_binary);
  virtual void DumpData(size_t) const = 0;

  char* binary_;
  bool own_binary_;

  DISALLOW_COPY_AND_ASSIGN(Record);
};

struct MmapRecord : public Record {
  struct MmapRecordDataType {
    uint32_t pid, tid;
    uint64_t addr;
    uint64_t len;
    uint64_t pgoff;
  };
  const MmapRecordDataType* data;
  const char* filename;

  MmapRecord() {}
  MmapRecord(const perf_event_attr& attr, bool in_kernel, uint32_t pid, uint32_t tid, uint64_t addr,
             uint64_t len, uint64_t pgoff, const std::string& filename, uint64_t event_id,
             uint64_t time = 0);

  bool Parse(const perf_event_attr& attr, char* p, char* end) override;
  void SetDataAndFilename(const MmapRecordDataType& data, const std::string& filename);

 protected:
  void DumpData(size_t indent) const override;
};

struct Mmap2Record : public Record {
  struct Mmap2RecordDataType {
    uint32_t pid, tid;
    uint64_t addr;
    uint64_t len;
    uint64_t pgoff;
    uint32_t maj;
    uint32_t min;
    uint64_t ino;
    uint64_t ino_generation;
    uint32_t prot, flags;
  };
  const Mmap2RecordDataType* data;
  const char* filename;

  Mmap2Record() {}
  Mmap2Record(const perf_event_attr& attr, bool in_kernel, uint32_t pid, uint32_t tid,
              uint64_t addr, uint64_t len, uint64_t pgoff, uint32_t prot,
              const std::string& filename, uint64_t event_id, uint64_t time = 0);

  bool Parse(const perf_event_attr& attr, char* p, char* end) override;
  void SetDataAndFilename(const Mmap2RecordDataType& data, const std::string& filename);

 protected:
  void DumpData(size_t indent) const override;
};

struct CommRecord : public Record {
  struct CommRecordDataType {
    uint32_t pid, tid;
  };
  const CommRecordDataType* data;
  const char* comm;

  CommRecord() {}
  CommRecord(const perf_event_attr& attr, uint32_t pid, uint32_t tid, const std::string& comm,
             uint64_t event_id, uint64_t time);

  bool Parse(const perf_event_attr& attr, char* p, char* end) override;
  void SetCommandName(const std::string& name);

 protected:
  void DumpData(size_t indent) const override;
};

struct ExitOrForkRecord : public Record {
  struct ExitOrForkRecordDataType {
    uint32_t pid, ppid;
    uint32_t tid, ptid;
    uint64_t time;
  };
  const ExitOrForkRecordDataType* data;

  ExitOrForkRecord() : data(nullptr) {}
  bool Parse(const perf_event_attr& attr, char* p, char* end) override;

 protected:
  void DumpData(size_t indent) const override;
};

struct ExitRecord : public ExitOrForkRecord {};

struct ForkRecord : public ExitOrForkRecord {
  ForkRecord() {}
  ForkRecord(const perf_event_attr& attr, uint32_t pid, uint32_t tid, uint32_t ppid, uint32_t ptid,
             uint64_t event_id);
};

struct LostRecord : public Record {
  uint64_t id;
  uint64_t lost;

  bool Parse(const perf_event_attr& attr, char* p, char* end) override;

 protected:
  void DumpData(size_t indent) const override;
};

struct SampleRecord : public Record {
  uint64_t sample_type;  // sample_type is a bit mask determining which fields
                         // below are valid.
  uint64_t read_format;

  PerfSampleIpType ip_data;               // Valid if PERF_SAMPLE_IP.
  PerfSampleTidType tid_data;             // Valid if PERF_SAMPLE_TID.
  PerfSampleTimeType time_data;           // Valid if PERF_SAMPLE_TIME.
  PerfSampleAddrType addr_data;           // Valid if PERF_SAMPLE_ADDR.
  PerfSampleIdType id_data;               // Valid if PERF_SAMPLE_ID.
  PerfSampleStreamIdType stream_id_data;  // Valid if PERF_SAMPLE_STREAM_ID.
  PerfSampleCpuType cpu_data;             // Valid if PERF_SAMPLE_CPU.
  PerfSamplePeriodType period_data;       // Valid if PERF_SAMPLE_PERIOD.
  PerfSampleReadType read_data;           // Valid if PERF_SAMPLE_READ.

  PerfSampleCallChainType callchain_data;       // Valid if PERF_SAMPLE_CALLCHAIN.
  PerfSampleRawType raw_data;                   // Valid if PERF_SAMPLE_RAW.
  PerfSampleBranchStackType branch_stack_data;  // Valid if PERF_SAMPLE_BRANCH_STACK.
  PerfSampleRegsUserType regs_user_data;        // Valid if PERF_SAMPLE_REGS_USER.
  PerfSampleStackUserType stack_user_data;      // Valid if PERF_SAMPLE_STACK_USER.

  SampleRecord() {}
  SampleRecord(const perf_event_attr& attr, uint64_t id, uint64_t ip, uint32_t pid, uint32_t tid,
               uint64_t time, uint32_t cpu, uint64_t period, const PerfSampleReadType& read_data,
               const std::vector<uint64_t>& ips, const std::vector<char>& stack,
               uint64_t dyn_stack_size);

  bool Parse(const perf_event_attr& attr, char* p, char* end) override;
  void ReplaceRegAndStackWithCallChain(const std::vector<uint64_t>& ips);
  // Remove kernel callchain, return true if there is a user space callchain left, otherwise
  // return false.
  bool ExcludeKernelCallChain();
  bool HasUserCallChain() const;
  void UpdateUserCallChain(const std::vector<uint64_t>& user_ips);

  uint64_t Timestamp() const override;
  uint32_t Cpu() const override;
  uint64_t Id() const override;

  uint64_t GetValidStackSize() const {
    // Invaid stack data has been removed by RecordReadThread::PushRecordToRecordBuffer().
    return stack_user_data.size;
  }

  void AdjustCallChainGeneratedByKernel();
  std::vector<uint64_t> GetCallChain(size_t* kernel_ip_count) const;

 protected:
  void BuildBinaryWithNewCallChain(uint32_t new_size, const std::vector<uint64_t>& ips);
  void DumpData(size_t indent) const override;
};

struct AuxRecord : public Record {
  struct DataType {
    uint64_t aux_offset;
    uint64_t aux_size;
    uint64_t flags;
  }* data;

  bool Parse(const perf_event_attr& attr, char* p, char* end) override;
  bool Unformatted() const { return data->flags & PERF_AUX_FLAG_CORESIGHT_FORMAT_RAW; }

 protected:
  void DumpData(size_t indent) const override;
};

struct SwitchRecord : public Record {
  bool Parse(const perf_event_attr& attr, char* p, char* end) override;

 protected:
  void DumpData(size_t) const override {}
};

struct SwitchCpuWideRecord : public Record {
  PerfSampleTidType tid_data;

  bool Parse(const perf_event_attr& attr, char* p, char* end) override;

 protected:
  void DumpData(size_t indent) const override;
};

// BuildIdRecord is defined in user-space, stored in BuildId feature section in
// record file.
struct BuildIdRecord : public Record {
  uint32_t pid;
  BuildId build_id;
  const char* filename;

  BuildIdRecord() {}
  BuildIdRecord(bool in_kernel, uint32_t pid, const BuildId& build_id, const std::string& filename);
  bool Parse(const perf_event_attr& attr, char* p, char* end) override;

 protected:
  void DumpData(size_t indent) const override;
};

struct AuxTraceInfoRecord : public Record {
  // magic values to be compatible with linux perf
  static constexpr uint32_t AUX_TYPE_ETM = 3;
  static constexpr uint64_t MAGIC_ETM4 = 0x4040404040404040ULL;
  static constexpr uint64_t MAGIC_ETE = 0x5050505050505050ULL;

  struct ETM4Info {
    uint64_t magic;
    uint64_t cpu;
    uint64_t nrtrcparams;
    uint64_t trcconfigr;
    uint64_t trctraceidr;
    uint64_t trcidr0;
    uint64_t trcidr1;
    uint64_t trcidr2;
    uint64_t trcidr8;
    uint64_t trcauthstatus;
  };

  struct ETEInfo {
    uint64_t magic;
    uint64_t cpu;
    uint64_t nrtrcparams;
    uint64_t trcconfigr;
    uint64_t trctraceidr;
    uint64_t trcidr0;
    uint64_t trcidr1;
    uint64_t trcidr2;
    uint64_t trcidr8;
    uint64_t trcauthstatus;
    uint64_t trcdevarch;
  };

  struct DataType {
    uint32_t aux_type;
    uint32_t reserved;
    uint64_t version;
    uint32_t nr_cpu;
    uint32_t pmu_type;
    uint64_t snapshot;
    uint64_t info[0];
  }* data;

  AuxTraceInfoRecord() {}
  AuxTraceInfoRecord(const DataType& data, const std::vector<ETEInfo>& ete_info);
  bool Parse(const perf_event_attr& attr, char* p, char* end) override;

 protected:
  void DumpData(size_t indent) const override;
};

struct AuxTraceRecord : public Record {
  struct DataType {
    uint64_t aux_size;
    uint64_t offset;
    uint64_t reserved0;  // reference
    uint32_t idx;
    uint32_t tid;
    uint32_t cpu;
    uint32_t reserved1;
  }* data;
  // AuxTraceRecord is followed by aux tracing data with size data->aux_size.
  // The location of aux tracing data in memory or file is kept in location.
  struct AuxDataLocation {
    const char* addr = nullptr;
    uint64_t file_offset = 0;
  } location;

  AuxTraceRecord() {}
  AuxTraceRecord(uint64_t aux_size, uint64_t offset, uint32_t idx, uint32_t tid, uint32_t cpu);

  bool Parse(const perf_event_attr& attr, char* p, char* end) override;
  uint32_t Cpu() const override { return data->cpu; }
  static size_t Size() { return sizeof(perf_event_header) + sizeof(DataType); }

 protected:
  void DumpData(size_t indent) const override;
};

struct KernelSymbolRecord : public Record {
  uint32_t kallsyms_size;
  const char* kallsyms;

  KernelSymbolRecord() {}
  explicit KernelSymbolRecord(const std::string& kallsyms);
  bool Parse(const perf_event_attr& attr, char* p, char* end) override;

 protected:
  void DumpData(size_t indent) const override;
};

struct DsoRecord : public Record {
  uint64_t dso_type;
  uint64_t dso_id;
  uint64_t min_vaddr;
  const char* dso_name;

  DsoRecord() {}
  DsoRecord(uint64_t dso_type, uint64_t dso_id, const std::string& dso_name, uint64_t min_vaddr);
  bool Parse(const perf_event_attr& attr, char* p, char* end) override;

 protected:
  void DumpData(size_t indent) const override;
};

struct SymbolRecord : public Record {
  uint64_t addr;
  uint64_t len;
  uint64_t dso_id;
  const char* name;

  SymbolRecord() {}
  SymbolRecord(uint64_t addr, uint64_t len, const std::string& name, uint64_t dso_id);
  bool Parse(const perf_event_attr& attr, char* p, char* end) override;

 protected:
  void DumpData(size_t indent) const override;
};

struct TracingDataRecord : public Record {
  uint32_t data_size;
  const char* data;

  TracingDataRecord() {}
  explicit TracingDataRecord(const std::vector<char>& tracing_data);
  bool Parse(const perf_event_attr& attr, char* p, char* end) override;

 protected:
  void DumpData(size_t indent) const override;
};

struct EventIdRecord : public Record {
  uint64_t count;
  struct EventIdData {
    uint64_t attr_id;
    uint64_t event_id;
  } const* data;

  EventIdRecord() {}
  explicit EventIdRecord(const std::vector<uint64_t>& data);
  bool Parse(const perf_event_attr& attr, char* p, char* end) override;

 protected:
  void DumpData(size_t indent) const override;
};

struct CallChainRecord : public Record {
  uint32_t pid;
  uint32_t tid;
  uint64_t chain_type;
  uint64_t time;
  uint64_t ip_nr;
  uint64_t* ips;
  uint64_t* sps;

  CallChainRecord() {}

  CallChainRecord(pid_t pid, pid_t tid, simpleperf::CallChainJoiner::ChainType type, uint64_t time,
                  const std::vector<uint64_t>& ips, const std::vector<uint64_t>& sps);

  bool Parse(const perf_event_attr& attr, char* p, char* end) override;
  uint64_t Timestamp() const override { return time; }

 protected:
  void DumpData(size_t indent) const override;
};

struct UnwindingResultRecord : public Record {
  uint64_t time;
  UnwindingResult unwinding_result;
  PerfSampleRegsUserType regs_user_data;
  PerfSampleStackUserType stack_user_data;

  struct CallChain {
    uint64_t length = 0;
    uint64_t* ips = nullptr;
    uint64_t* sps = nullptr;
  } callchain;

  UnwindingResultRecord() {}

  UnwindingResultRecord(uint64_t time, const simpleperf::UnwindingResult& unwinding_result,
                        const PerfSampleRegsUserType& regs_user_data,
                        const PerfSampleStackUserType& stack_user_data,
                        const std::vector<uint64_t>& ips, const std::vector<uint64_t>& sps);

  bool Parse(const perf_event_attr& attr, char* p, char* end) override;
  uint64_t Timestamp() const override { return time; }

 protected:
  void DumpData(size_t indent) const override;
};

// Add a debug string in the recording file.
struct DebugRecord : public Record {
  uint64_t time = 0;
  char* s = nullptr;

  DebugRecord() {}

  DebugRecord(uint64_t time, const std::string& s);

  bool Parse(const perf_event_attr& attr, char* p, char* end) override;
  uint64_t Timestamp() const override { return time; }

 protected:
  void DumpData(size_t indent) const override;
};

// UnknownRecord is used for unknown record types, it makes sure all unknown
// records are not changed when modifying perf.data.
struct UnknownRecord : public Record {
  const char* data;

  bool Parse(const perf_event_attr& attr, char* p, char* end) override;

 protected:
  void DumpData(size_t indent) const override;
};

// Read record from the buffer pointed by [p]. But the record doesn't own
// the buffer.
std::unique_ptr<Record> ReadRecordFromBuffer(const perf_event_attr& attr, uint32_t type, char* p,
                                             char* end);

// Read records from the buffer pointed by [buf]. None of the records own
// the buffer.
std::vector<std::unique_ptr<Record>> ReadRecordsFromBuffer(const perf_event_attr& attr, char* buf,
                                                           size_t buf_size);

// Read one record from the buffer pointed by [p]. But the record doesn't
// own the buffer.
std::unique_ptr<Record> ReadRecordFromBuffer(const perf_event_attr& attr, char* p, char* end);

}  // namespace simpleperf

#endif  // SIMPLE_PERF_RECORD_H_
