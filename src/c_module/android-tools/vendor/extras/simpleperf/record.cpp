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

#include "record.h"

#include <inttypes.h>
#include <algorithm>
#include <unordered_map>

#include <android-base/logging.h>
#include <android-base/macros.h>
#include <android-base/stringprintf.h>

#include "OfflineUnwinder.h"
#include "dso.h"
#include "perf_regs.h"
#include "tracing.h"
#include "utils.h"

namespace simpleperf {

#define CHECK_SIZE(p, end, size)          \
  do {                                    \
    if (UNLIKELY((end) - (p) < (size))) { \
      return false;                       \
    }                                     \
  } while (0)

#define CHECK_SIZE_U64(p, end, u64_count)                           \
  do {                                                              \
    if (UNLIKELY(((end) - (p)) / sizeof(uint64_t) < (u64_count))) { \
      return false;                                                 \
    }                                                               \
  } while (0)

static std::string RecordTypeToString(int record_type) {
  static std::unordered_map<int, std::string> record_type_names = {
      {PERF_RECORD_MMAP, "mmap"},
      {PERF_RECORD_LOST, "lost"},
      {PERF_RECORD_COMM, "comm"},
      {PERF_RECORD_EXIT, "exit"},
      {PERF_RECORD_THROTTLE, "throttle"},
      {PERF_RECORD_UNTHROTTLE, "unthrottle"},
      {PERF_RECORD_FORK, "fork"},
      {PERF_RECORD_READ, "read"},
      {PERF_RECORD_SAMPLE, "sample"},
      {PERF_RECORD_BUILD_ID, "build_id"},
      {PERF_RECORD_MMAP2, "mmap2"},
      {PERF_RECORD_AUX, "aux"},
      {PERF_RECORD_SWITCH, "switch"},
      {PERF_RECORD_SWITCH_CPU_WIDE, "switch_cpu_wide"},
      {PERF_RECORD_TRACING_DATA, "tracing_data"},
      {PERF_RECORD_AUXTRACE_INFO, "auxtrace_info"},
      {PERF_RECORD_AUXTRACE, "auxtrace"},
      {SIMPLE_PERF_RECORD_KERNEL_SYMBOL, "kernel_symbol"},
      {SIMPLE_PERF_RECORD_DSO, "dso"},
      {SIMPLE_PERF_RECORD_SYMBOL, "symbol"},
      {SIMPLE_PERF_RECORD_EVENT_ID, "event_id"},
      {SIMPLE_PERF_RECORD_CALLCHAIN, "callchain"},
      {SIMPLE_PERF_RECORD_UNWINDING_RESULT, "unwinding_result"},
      {SIMPLE_PERF_RECORD_TRACING_DATA, "tracing_data"},
      {SIMPLE_PERF_RECORD_DEBUG, "debug"},
  };

  auto it = record_type_names.find(record_type);
  if (it != record_type_names.end()) {
    return it->second;
  }
  return android::base::StringPrintf("unknown(%d)", record_type);
}

template <>
void MoveToBinaryFormat(const RecordHeader& data, char*& p) {
  data.MoveToBinaryFormat(p);
}

SampleId::SampleId() {
  memset(this, 0, sizeof(SampleId));
}

// Return sample_id size in binary format.
size_t SampleId::CreateContent(const perf_event_attr& attr, uint64_t event_id) {
  sample_id_all = attr.sample_id_all;
  sample_type = attr.sample_type;
  id_data.id = event_id;
  // Other data are not necessary. TODO: Set missing SampleId data.
  return Size();
}

bool SampleId::ReadFromBinaryFormat(const perf_event_attr& attr, const char* p, const char* end) {
  sample_id_all = attr.sample_id_all;
  sample_type = attr.sample_type;
  if (sample_id_all) {
    const uint64_t sample_id_mask = PERF_SAMPLE_TID | PERF_SAMPLE_TIME | PERF_SAMPLE_ID |
                                    PERF_SAMPLE_STREAM_ID | PERF_SAMPLE_CPU |
                                    PERF_SAMPLE_IDENTIFIER;
    CHECK_SIZE_U64(p, end, __builtin_popcountll(sample_type & sample_id_mask));
    if (sample_type & PERF_SAMPLE_TID) {
      MoveFromBinaryFormat(tid_data, p);
    }
    if (sample_type & PERF_SAMPLE_TIME) {
      MoveFromBinaryFormat(time_data, p);
    }
    if (sample_type & PERF_SAMPLE_ID) {
      MoveFromBinaryFormat(id_data, p);
    }
    if (sample_type & PERF_SAMPLE_STREAM_ID) {
      MoveFromBinaryFormat(stream_id_data, p);
    }
    if (sample_type & PERF_SAMPLE_CPU) {
      MoveFromBinaryFormat(cpu_data, p);
    }
    if (sample_type & PERF_SAMPLE_IDENTIFIER) {
      MoveFromBinaryFormat(id_data, p);
    }
  }
  if (UNLIKELY(p < end)) {
    LOG(DEBUG) << "Record SampleId part has " << end - p << " bytes left\n";
  }
  return true;
}

void SampleId::WriteToBinaryFormat(char*& p) const {
  if (sample_id_all) {
    if (sample_type & PERF_SAMPLE_TID) {
      MoveToBinaryFormat(tid_data, p);
    }
    if (sample_type & PERF_SAMPLE_TIME) {
      MoveToBinaryFormat(time_data, p);
    }
    if (sample_type & PERF_SAMPLE_ID) {
      MoveToBinaryFormat(id_data, p);
    }
    if (sample_type & PERF_SAMPLE_STREAM_ID) {
      MoveToBinaryFormat(stream_id_data, p);
    }
    if (sample_type & PERF_SAMPLE_CPU) {
      MoveToBinaryFormat(cpu_data, p);
    }
  }
}

void SampleId::Dump(size_t indent) const {
  if (sample_id_all) {
    if (sample_type & PERF_SAMPLE_TID) {
      PrintIndented(indent, "sample_id: pid %u, tid %u\n", tid_data.pid, tid_data.tid);
    }
    if (sample_type & PERF_SAMPLE_TIME) {
      PrintIndented(indent, "sample_id: time %" PRId64 "\n", time_data.time);
    }
    if (sample_type & (PERF_SAMPLE_ID | PERF_SAMPLE_IDENTIFIER)) {
      PrintIndented(indent, "sample_id: id %" PRId64 "\n", id_data.id);
    }
    if (sample_type & PERF_SAMPLE_STREAM_ID) {
      PrintIndented(indent, "sample_id: stream_id %" PRId64 "\n", stream_id_data.stream_id);
    }
    if (sample_type & PERF_SAMPLE_CPU) {
      PrintIndented(indent, "sample_id: cpu %u, res %u\n", cpu_data.cpu, cpu_data.res);
    }
  }
}

size_t SampleId::Size() const {
  size_t size = 0;
  if (sample_id_all) {
    if (sample_type & PERF_SAMPLE_TID) {
      size += sizeof(PerfSampleTidType);
    }
    if (sample_type & PERF_SAMPLE_TIME) {
      size += sizeof(PerfSampleTimeType);
    }
    if (sample_type & PERF_SAMPLE_ID) {
      size += sizeof(PerfSampleIdType);
    }
    if (sample_type & PERF_SAMPLE_STREAM_ID) {
      size += sizeof(PerfSampleStreamIdType);
    }
    if (sample_type & PERF_SAMPLE_CPU) {
      size += sizeof(PerfSampleCpuType);
    }
    if (sample_type & PERF_SAMPLE_IDENTIFIER) {
      size += sizeof(PerfSampleIdType);
    }
  }
  return size;
}

Record::Record(Record&& other) noexcept {
  header = other.header;
  sample_id = other.sample_id;
  binary_ = other.binary_;
  own_binary_ = other.own_binary_;
  other.binary_ = nullptr;
  other.own_binary_ = false;
}

bool Record::ParseHeader(char*& p, char*& end) {
  binary_ = p;
  CHECK(end != nullptr);
  CHECK_SIZE(p, end, sizeof(perf_event_header));
  if (!header.Parse(p)) {
    return false;
  }
  CHECK_SIZE(p, end, header.size);
  end = p + header.size;
  p += sizeof(perf_event_header);
  return true;
}

void Record::Dump(size_t indent) const {
  PrintIndented(indent, "record %s: type %u, misc 0x%x, size %u\n",
                RecordTypeToString(type()).c_str(), type(), misc(), size());
  DumpData(indent + 1);
  sample_id.Dump(indent + 1);
}

uint64_t Record::Timestamp() const {
  return sample_id.time_data.time;
}
uint32_t Record::Cpu() const {
  return sample_id.cpu_data.cpu;
}
uint64_t Record::Id() const {
  return sample_id.id_data.id;
}

void Record::UpdateBinary(char* new_binary) {
  if (own_binary_) {
    delete[] binary_;
  }
  own_binary_ = true;
  binary_ = new_binary;
}

bool MmapRecord::Parse(const perf_event_attr& attr, char* p, char* end) {
  if (!ParseHeader(p, end)) {
    return false;
  }
  data = reinterpret_cast<const MmapRecordDataType*>(p);
  CHECK_SIZE(p, end, sizeof(*data));
  p += sizeof(*data);
  size_t size = Align(SafeStrlen(p, end) + 1, 8);
  CHECK_SIZE(p, end, size);
  filename = p;
  p += size;
  return sample_id.ReadFromBinaryFormat(attr, p, end);
}

MmapRecord::MmapRecord(const perf_event_attr& attr, bool in_kernel, uint32_t pid, uint32_t tid,
                       uint64_t addr, uint64_t len, uint64_t pgoff, const std::string& filename,
                       uint64_t event_id, uint64_t time) {
  SetTypeAndMisc(PERF_RECORD_MMAP, in_kernel ? PERF_RECORD_MISC_KERNEL : PERF_RECORD_MISC_USER);
  sample_id.CreateContent(attr, event_id);
  sample_id.time_data.time = time;
  MmapRecordDataType data;
  data.pid = pid;
  data.tid = tid;
  data.addr = addr;
  data.len = len;
  data.pgoff = pgoff;
  SetDataAndFilename(data, filename);
}

void MmapRecord::SetDataAndFilename(const MmapRecordDataType& data, const std::string& filename) {
  SetSize(header_size() + sizeof(data) + Align(filename.size() + 1, 8) + sample_id.Size());
  char* new_binary = new char[size()];
  char* p = new_binary;
  MoveToBinaryFormat(header, p);
  this->data = reinterpret_cast<MmapRecordDataType*>(p);
  MoveToBinaryFormat(data, p);
  this->filename = p;
  strcpy(p, filename.c_str());
  p += Align(filename.size() + 1, 8);
  sample_id.WriteToBinaryFormat(p);
  UpdateBinary(new_binary);
}

void MmapRecord::DumpData(size_t indent) const {
  PrintIndented(indent, "pid %u, tid %u, addr 0x%" PRIx64 ", len 0x%" PRIx64 "\n", data->pid,
                data->tid, data->addr, data->len);
  PrintIndented(indent, "pgoff 0x%" PRIx64 ", filename %s\n", data->pgoff, filename);
}

bool Mmap2Record::Parse(const perf_event_attr& attr, char* p, char* end) {
  if (!ParseHeader(p, end)) {
    return false;
  }
  data = reinterpret_cast<const Mmap2RecordDataType*>(p);
  CHECK_SIZE(p, end, sizeof(*data));
  p += sizeof(*data);
  size_t size = Align(SafeStrlen(p, end) + 1, 8);
  CHECK_SIZE(p, end, size);
  filename = p;
  p += size;
  return sample_id.ReadFromBinaryFormat(attr, p, end);
}

Mmap2Record::Mmap2Record(const perf_event_attr& attr, bool in_kernel, uint32_t pid, uint32_t tid,
                         uint64_t addr, uint64_t len, uint64_t pgoff, uint32_t prot,
                         const std::string& filename, uint64_t event_id, uint64_t time) {
  SetTypeAndMisc(PERF_RECORD_MMAP2, in_kernel ? PERF_RECORD_MISC_KERNEL : PERF_RECORD_MISC_USER);
  sample_id.CreateContent(attr, event_id);
  sample_id.time_data.time = time;
  Mmap2RecordDataType data;
  data.pid = pid;
  data.tid = tid;
  data.addr = addr;
  data.len = len;
  data.pgoff = pgoff;
  data.prot = prot;
  SetDataAndFilename(data, filename);
}

void Mmap2Record::SetDataAndFilename(const Mmap2RecordDataType& data, const std::string& filename) {
  SetSize(header_size() + sizeof(data) + Align(filename.size() + 1, 8) + sample_id.Size());
  char* new_binary = new char[size()];
  char* p = new_binary;
  MoveToBinaryFormat(header, p);
  this->data = reinterpret_cast<Mmap2RecordDataType*>(p);
  MoveToBinaryFormat(data, p);
  this->filename = p;
  strcpy(p, filename.c_str());
  p += Align(filename.size() + 1, 8);
  sample_id.WriteToBinaryFormat(p);
  UpdateBinary(new_binary);
}

void Mmap2Record::DumpData(size_t indent) const {
  PrintIndented(indent, "pid %u, tid %u, addr 0x%" PRIx64 ", len 0x%" PRIx64 "\n", data->pid,
                data->tid, data->addr, data->len);
  PrintIndented(
      indent, "pgoff 0x%" PRIx64 ", maj %u, min %u, ino %" PRId64 ", ino_generation %" PRIu64 "\n",
      data->pgoff, data->maj, data->min, data->ino, data->ino_generation);
  PrintIndented(indent, "prot %u, flags %u, filename %s\n", data->prot, data->flags, filename);
}

bool CommRecord::Parse(const perf_event_attr& attr, char* p, char* end) {
  if (!ParseHeader(p, end)) {
    return false;
  }
  data = reinterpret_cast<const CommRecordDataType*>(p);
  CHECK_SIZE(p, end, sizeof(*data));
  p += sizeof(*data);
  size_t size = Align(SafeStrlen(p, end) + 1, 8);
  CHECK_SIZE(p, end, size);
  comm = p;
  p += size;
  return sample_id.ReadFromBinaryFormat(attr, p, end);
}

CommRecord::CommRecord(const perf_event_attr& attr, uint32_t pid, uint32_t tid,
                       const std::string& comm, uint64_t event_id, uint64_t time) {
  SetTypeAndMisc(PERF_RECORD_COMM, 0);
  CommRecordDataType data;
  data.pid = pid;
  data.tid = tid;
  size_t sample_id_size = sample_id.CreateContent(attr, event_id);
  sample_id.time_data.time = time;
  SetSize(header_size() + sizeof(data) + Align(comm.size() + 1, 8) + sample_id_size);
  char* new_binary = new char[size()];
  char* p = new_binary;
  MoveToBinaryFormat(header, p);
  this->data = reinterpret_cast<CommRecordDataType*>(p);
  MoveToBinaryFormat(data, p);
  this->comm = p;
  strcpy(p, comm.c_str());
  p += Align(comm.size() + 1, 8);
  sample_id.WriteToBinaryFormat(p);
  UpdateBinary(new_binary);
}

void CommRecord::SetCommandName(const std::string& name) {
  if (name.compare(comm) == 0) {
    return;
  }
  // The kernel uses a 8-byte aligned space to store command name. Follow it here to allow the same
  // reading code.
  size_t old_name_len = Align(strlen(comm) + 1, 8);
  size_t new_name_len = Align(name.size() + 1, 8);
  size_t new_size = size() - old_name_len + new_name_len;
  char* new_binary = new char[new_size];
  char* p = new_binary;
  header.size = new_size;
  MoveToBinaryFormat(header, p);
  MoveToBinaryFormat(*data, p);
  data = reinterpret_cast<CommRecordDataType*>(p - sizeof(CommRecordDataType));
  comm = p;
  strcpy(p, name.c_str());
  p += new_name_len;
  sample_id.WriteToBinaryFormat(p);
  CHECK_EQ(p, new_binary + new_size);
  UpdateBinary(new_binary);
}

void CommRecord::DumpData(size_t indent) const {
  PrintIndented(indent, "pid %u, tid %u, comm %s\n", data->pid, data->tid, comm);
}

bool ExitOrForkRecord::Parse(const perf_event_attr& attr, char* p, char* end) {
  if (!ParseHeader(p, end)) {
    return false;
  }
  data = reinterpret_cast<const ExitOrForkRecordDataType*>(p);
  CHECK_SIZE(p, end, sizeof(*data));
  p += sizeof(*data);
  return sample_id.ReadFromBinaryFormat(attr, p, end);
}

void ExitOrForkRecord::DumpData(size_t indent) const {
  PrintIndented(indent, "pid %u, ppid %u, tid %u, ptid %u\n", data->pid, data->ppid, data->tid,
                data->ptid);
}

ForkRecord::ForkRecord(const perf_event_attr& attr, uint32_t pid, uint32_t tid, uint32_t ppid,
                       uint32_t ptid, uint64_t event_id) {
  SetTypeAndMisc(PERF_RECORD_FORK, 0);
  ExitOrForkRecordDataType data;
  data.pid = pid;
  data.ppid = ppid;
  data.tid = tid;
  data.ptid = ptid;
  data.time = 0;
  size_t sample_id_size = sample_id.CreateContent(attr, event_id);
  SetSize(header_size() + sizeof(data) + sample_id_size);
  char* new_binary = new char[size()];
  char* p = new_binary;
  MoveToBinaryFormat(header, p);
  this->data = reinterpret_cast<ExitOrForkRecordDataType*>(p);
  MoveToBinaryFormat(data, p);
  sample_id.WriteToBinaryFormat(p);
  UpdateBinary(new_binary);
}

bool LostRecord::Parse(const perf_event_attr& attr, char* p, char* end) {
  if (!ParseHeader(p, end)) {
    return false;
  }
  CHECK_SIZE_U64(p, end, 2);
  MoveFromBinaryFormat(id, p);
  MoveFromBinaryFormat(lost, p);
  return sample_id.ReadFromBinaryFormat(attr, p, end);
}

void LostRecord::DumpData(size_t indent) const {
  PrintIndented(indent, "id %" PRIu64 ", lost %" PRIu64 "\n", id, lost);
}

bool SampleRecord::Parse(const perf_event_attr& attr, char* p, char* end) {
  if (!ParseHeader(p, end)) {
    return false;
  }
  sample_type = attr.sample_type;
  read_format = attr.read_format;
  const uint64_t sample_mask = PERF_SAMPLE_IDENTIFIER | PERF_SAMPLE_IP | PERF_SAMPLE_TID |
                               PERF_SAMPLE_TIME | PERF_SAMPLE_ADDR | PERF_SAMPLE_ID |
                               PERF_SAMPLE_STREAM_ID | PERF_SAMPLE_CPU | PERF_SAMPLE_PERIOD;
  CHECK_SIZE_U64(p, end, __builtin_popcountll(sample_type & sample_mask));

  // Set a default id value to report correctly even if ID is not recorded.
  id_data.id = 0;
  if (sample_type & PERF_SAMPLE_IDENTIFIER) {
    MoveFromBinaryFormat(id_data, p);
  }
  if (sample_type & PERF_SAMPLE_IP) {
    MoveFromBinaryFormat(ip_data, p);
  }
  if (sample_type & PERF_SAMPLE_TID) {
    MoveFromBinaryFormat(tid_data, p);
  }
  if (sample_type & PERF_SAMPLE_TIME) {
    MoveFromBinaryFormat(time_data, p);
  }
  if (sample_type & PERF_SAMPLE_ADDR) {
    MoveFromBinaryFormat(addr_data, p);
  }
  if (sample_type & PERF_SAMPLE_ID) {
    MoveFromBinaryFormat(id_data, p);
  }
  if (sample_type & PERF_SAMPLE_STREAM_ID) {
    MoveFromBinaryFormat(stream_id_data, p);
  }
  if (sample_type & PERF_SAMPLE_CPU) {
    MoveFromBinaryFormat(cpu_data, p);
  }
  if (sample_type & PERF_SAMPLE_PERIOD) {
    MoveFromBinaryFormat(period_data, p);
  }
  if (sample_type & PERF_SAMPLE_READ) {
    uint64_t nr = 1;
    if (read_format & PERF_FORMAT_GROUP) {
      CHECK_SIZE_U64(p, end, 1);
      MoveFromBinaryFormat(nr, p);
    }
    uint64_t u64_count = (read_format & PERF_FORMAT_TOTAL_TIME_ENABLED) ? 1 : 0;
    u64_count += (read_format & PERF_FORMAT_TOTAL_TIME_RUNNING) ? 1 : 0;
    if (__builtin_add_overflow(u64_count, nr, &u64_count)) {
      return false;
    }
    if (read_format & PERF_FORMAT_ID) {
      if (__builtin_add_overflow(u64_count, nr, &u64_count)) {
        return false;
      }
    }
    CHECK_SIZE_U64(p, end, u64_count);
    if (read_format & PERF_FORMAT_TOTAL_TIME_ENABLED) {
      MoveFromBinaryFormat(read_data.time_enabled, p);
    }
    if (read_format & PERF_FORMAT_TOTAL_TIME_RUNNING) {
      MoveFromBinaryFormat(read_data.time_running, p);
    }
    read_data.counts.resize(nr);
    if (read_format & PERF_FORMAT_ID) {
      read_data.ids.resize(nr);
    }
    for (uint64_t i = 0; i < nr; i++) {
      MoveFromBinaryFormat(read_data.counts[i], p);
      if (read_format & PERF_FORMAT_ID) {
        MoveFromBinaryFormat(read_data.ids[i], p);
      }
    }
  }
  if (sample_type & PERF_SAMPLE_CALLCHAIN) {
    CHECK_SIZE_U64(p, end, 1);
    MoveFromBinaryFormat(callchain_data.ip_nr, p);
    CHECK_SIZE_U64(p, end, callchain_data.ip_nr);
    callchain_data.ips = reinterpret_cast<uint64_t*>(p);
    p += callchain_data.ip_nr * sizeof(uint64_t);
  }
  if (sample_type & PERF_SAMPLE_RAW) {
    CHECK_SIZE(p, end, sizeof(uint32_t));
    MoveFromBinaryFormat(raw_data.size, p);
    CHECK_SIZE(p, end, raw_data.size);
    raw_data.data = p;
    p += raw_data.size;
  }
  if (sample_type & PERF_SAMPLE_BRANCH_STACK) {
    CHECK_SIZE_U64(p, end, 1);
    MoveFromBinaryFormat(branch_stack_data.stack_nr, p);
    CHECK_SIZE(p, end, branch_stack_data.stack_nr * sizeof(BranchStackItemType));
    branch_stack_data.stack = reinterpret_cast<BranchStackItemType*>(p);
    p += branch_stack_data.stack_nr * sizeof(BranchStackItemType);
  }
  if (sample_type & PERF_SAMPLE_REGS_USER) {
    CHECK_SIZE_U64(p, end, 1);
    MoveFromBinaryFormat(regs_user_data.abi, p);
    if (regs_user_data.abi == 0) {
      regs_user_data.reg_mask = 0;
      regs_user_data.reg_nr = 0;
      regs_user_data.regs = nullptr;
    } else {
      regs_user_data.reg_mask = attr.sample_regs_user;
      size_t bit_nr = __builtin_popcountll(regs_user_data.reg_mask);
      CHECK_SIZE_U64(p, end, bit_nr);
      regs_user_data.reg_nr = bit_nr;
      regs_user_data.regs = reinterpret_cast<uint64_t*>(p);
      p += bit_nr * sizeof(uint64_t);
    }
  }
  if (sample_type & PERF_SAMPLE_STACK_USER) {
    CHECK_SIZE_U64(p, end, 1);
    MoveFromBinaryFormat(stack_user_data.size, p);
    if (stack_user_data.size == 0) {
      stack_user_data.dyn_size = 0;
    } else {
      CHECK_SIZE(p, end, stack_user_data.size + sizeof(uint64_t));
      stack_user_data.data = p;
      p += stack_user_data.size;
      MoveFromBinaryFormat(stack_user_data.dyn_size, p);
    }
  }
  // TODO: Add parsing of other PERF_SAMPLE_*.
  if (UNLIKELY(p < end)) {
    LOG(VERBOSE) << "Sample (" << time_data.time << ") has " << end - p << " bytes left";
  }
  return true;
}

SampleRecord::SampleRecord(const perf_event_attr& attr, uint64_t id, uint64_t ip, uint32_t pid,
                           uint32_t tid, uint64_t time, uint32_t cpu, uint64_t period,
                           const PerfSampleReadType& read_data, const std::vector<uint64_t>& ips,
                           const std::vector<char>& stack, uint64_t dyn_stack_size) {
  SetTypeAndMisc(PERF_RECORD_SAMPLE, PERF_RECORD_MISC_USER);
  sample_type = attr.sample_type;
  read_format = attr.read_format;
  CHECK_EQ(0u,
           sample_type & ~(PERF_SAMPLE_IP | PERF_SAMPLE_TID | PERF_SAMPLE_TIME | PERF_SAMPLE_ID |
                           PERF_SAMPLE_CPU | PERF_SAMPLE_PERIOD | PERF_SAMPLE_READ |
                           PERF_SAMPLE_CALLCHAIN | PERF_SAMPLE_REGS_USER | PERF_SAMPLE_STACK_USER));
  ip_data.ip = ip;
  tid_data.pid = pid;
  tid_data.tid = tid;
  time_data.time = time;
  id_data.id = id;
  cpu_data.cpu = cpu;
  cpu_data.res = 0;
  period_data.period = period;
  this->read_data = read_data;
  callchain_data.ip_nr = ips.size();
  raw_data.size = 0;
  branch_stack_data.stack_nr = 0;
  regs_user_data.abi = 0;
  regs_user_data.reg_mask = 0;
  regs_user_data.reg_nr = 0;
  stack_user_data.size = stack.size();
  stack_user_data.dyn_size = dyn_stack_size;

  uint32_t size = header_size();
  if (sample_type & PERF_SAMPLE_IP) {
    size += sizeof(ip_data);
  }
  if (sample_type & PERF_SAMPLE_TID) {
    size += sizeof(tid_data);
  }
  if (sample_type & PERF_SAMPLE_TIME) {
    size += sizeof(time_data);
  }
  if (sample_type & PERF_SAMPLE_ID) {
    size += sizeof(id_data);
  }
  if (sample_type & PERF_SAMPLE_CPU) {
    size += sizeof(cpu_data);
  }
  if (sample_type & PERF_SAMPLE_PERIOD) {
    size += sizeof(period_data);
  }
  if (sample_type & PERF_SAMPLE_READ) {
    size_t u64_count = (read_format & PERF_FORMAT_GROUP) ? 1 : 0;
    u64_count += (read_format & PERF_FORMAT_TOTAL_TIME_ENABLED) ? 1 : 0;
    u64_count += (read_format & PERF_FORMAT_TOTAL_TIME_RUNNING) ? 1 : 0;
    u64_count += read_data.counts.size() + read_data.ids.size();
    size += sizeof(uint64_t) * u64_count;
  }
  if (sample_type & PERF_SAMPLE_CALLCHAIN) {
    size += sizeof(uint64_t) * (ips.size() + 1);
  }
  if (sample_type & PERF_SAMPLE_REGS_USER) {
    size += sizeof(uint64_t);
  }
  if (sample_type & PERF_SAMPLE_STACK_USER) {
    size += sizeof(uint64_t) + (stack.empty() ? 0 : stack.size() + sizeof(uint64_t));
  }

  SetSize(size);
  char* new_binary = new char[size];
  char* p = new_binary;
  MoveToBinaryFormat(header, p);
  if (sample_type & PERF_SAMPLE_IP) {
    MoveToBinaryFormat(ip_data, p);
  }
  if (sample_type & PERF_SAMPLE_TID) {
    MoveToBinaryFormat(tid_data, p);
  }
  if (sample_type & PERF_SAMPLE_TIME) {
    MoveToBinaryFormat(time_data, p);
  }
  if (sample_type & PERF_SAMPLE_ID) {
    MoveToBinaryFormat(id_data, p);
  }
  if (sample_type & PERF_SAMPLE_CPU) {
    MoveToBinaryFormat(cpu_data, p);
  }
  if (sample_type & PERF_SAMPLE_PERIOD) {
    MoveToBinaryFormat(period_data, p);
  }
  if (sample_type & PERF_SAMPLE_READ) {
    if (read_format & PERF_FORMAT_GROUP) {
      uint64_t nr = read_data.counts.size();
      MoveToBinaryFormat(nr, p);
    }
    if (read_format & PERF_FORMAT_TOTAL_TIME_ENABLED) {
      MoveToBinaryFormat(read_data.time_enabled, p);
    }
    if (read_format & PERF_FORMAT_TOTAL_TIME_RUNNING) {
      MoveToBinaryFormat(read_data.time_running, p);
    }
    for (size_t i = 0; i < read_data.counts.size(); i++) {
      MoveToBinaryFormat(read_data.counts[i], p);
      if (read_format & PERF_FORMAT_ID) {
        MoveToBinaryFormat(read_data.ids[i], p);
      }
    }
  }
  if (sample_type & PERF_SAMPLE_CALLCHAIN) {
    MoveToBinaryFormat(callchain_data.ip_nr, p);
    callchain_data.ips = reinterpret_cast<uint64_t*>(p);
    MoveToBinaryFormat(ips.data(), ips.size(), p);
  }
  if (sample_type & PERF_SAMPLE_REGS_USER) {
    MoveToBinaryFormat(regs_user_data.abi, p);
  }
  if (sample_type & PERF_SAMPLE_STACK_USER) {
    MoveToBinaryFormat(stack_user_data.size, p);
    if (stack_user_data.size > 0) {
      stack_user_data.data = p;
      MoveToBinaryFormat(stack.data(), stack_user_data.size, p);
      MoveToBinaryFormat(stack_user_data.dyn_size, p);
    }
  }
  CHECK_EQ(p, new_binary + size);
  UpdateBinary(new_binary);
}

void SampleRecord::ReplaceRegAndStackWithCallChain(const std::vector<uint64_t>& ips) {
  CHECK(sample_type & PERF_SAMPLE_CALLCHAIN);
  uint32_t new_size = reinterpret_cast<char*>(callchain_data.ips) - binary_ +
                      callchain_data.ip_nr * sizeof(uint64_t);
  if (!ips.empty()) {
    new_size += (ips.size() + 1) * sizeof(uint64_t);
  }
  if (sample_type & PERF_SAMPLE_RAW) {
    new_size += raw_data.size + sizeof(uint32_t);
  }
  if (sample_type & PERF_SAMPLE_BRANCH_STACK) {
    new_size += branch_stack_data.stack_nr * sizeof(BranchStackItemType) + sizeof(uint64_t);
  }
  // Check that there is no sample data after user stack.
  CHECK_EQ(sample_type & (PERF_SAMPLE_WEIGHT | PERF_SAMPLE_DATA_SRC | (UINT64_MAX << 17)), 0);
  sample_type &= ~(PERF_SAMPLE_STACK_USER | PERF_SAMPLE_REGS_USER);
  BuildBinaryWithNewCallChain(new_size, ips);
}

bool SampleRecord::ExcludeKernelCallChain() {
  if (!(sample_type & PERF_SAMPLE_CALLCHAIN)) {
    return true;
  }
  size_t i;
  for (i = 0; i < callchain_data.ip_nr; ++i) {
    if (callchain_data.ips[i] == PERF_CONTEXT_USER) {
      break;
    }
    // Erase kernel callchain.
    callchain_data.ips[i] = PERF_CONTEXT_USER;
  }
  while (++i < callchain_data.ip_nr) {
    if (callchain_data.ips[i] < PERF_CONTEXT_MAX) {
      // Change the sample to make it hit the user space ip address.
      ip_data.ip = callchain_data.ips[i];
      if (sample_type & PERF_SAMPLE_IP) {
        *reinterpret_cast<uint64_t*>(binary_ + header_size()) = ip_data.ip;
      }
      header.misc = (header.misc & ~PERF_RECORD_MISC_CPUMODE_MASK) | PERF_RECORD_MISC_USER;
      reinterpret_cast<perf_event_header*>(binary_)->misc = header.misc;
      return true;
    }
  }
  return false;
}

bool SampleRecord::HasUserCallChain() const {
  if ((sample_type & PERF_SAMPLE_CALLCHAIN) == 0) {
    return false;
  }
  bool in_user_context = !InKernel();
  for (size_t i = 0; i < callchain_data.ip_nr; ++i) {
    if (in_user_context && callchain_data.ips[i] < PERF_CONTEXT_MAX) {
      return true;
    }
    if (callchain_data.ips[i] == PERF_CONTEXT_USER) {
      in_user_context = true;
    }
  }
  return false;
}

void SampleRecord::UpdateUserCallChain(const std::vector<uint64_t>& user_ips) {
  size_t kernel_ip_count = 0;
  for (size_t i = 0; i < callchain_data.ip_nr; ++i) {
    if (callchain_data.ips[i] == PERF_CONTEXT_USER) {
      break;
    }
    kernel_ip_count++;
  }
  if (kernel_ip_count + 1 + user_ips.size() <= callchain_data.ip_nr) {
    // Callchain isn't changed.
    return;
  }
  size_t new_size =
      size() + (kernel_ip_count + 1 + user_ips.size() - callchain_data.ip_nr) * sizeof(uint64_t);
  callchain_data.ip_nr = kernel_ip_count;
  BuildBinaryWithNewCallChain(new_size, user_ips);
}

void SampleRecord::BuildBinaryWithNewCallChain(uint32_t new_size,
                                               const std::vector<uint64_t>& ips) {
  CHECK_EQ(sample_type & (PERF_SAMPLE_REGS_USER | PERF_SAMPLE_STACK_USER), 0);
  size_t callchain_pos = reinterpret_cast<char*>(callchain_data.ips) - binary_ - sizeof(uint64_t);
  std::vector<char> raw;
  std::vector<BranchStackItemType> branch_stack;
  if (sample_type & PERF_SAMPLE_RAW) {
    raw = std::vector<char>(raw_data.data, raw_data.data + raw_data.size);
  }
  if (sample_type & PERF_SAMPLE_BRANCH_STACK) {
    branch_stack = std::vector<BranchStackItemType>(
        branch_stack_data.stack, branch_stack_data.stack + branch_stack_data.stack_nr);
  }

  char* new_binary = binary_;
  if (new_size > size()) {
    new_binary = new char[new_size];
    memcpy(new_binary, binary_, callchain_pos);
  }
  char* p = new_binary;
  SetSize(new_size);
  MoveToBinaryFormat(header, p);
  p = new_binary + callchain_pos;
  uint64_t old_ip_nr = callchain_data.ip_nr;
  callchain_data.ip_nr += ips.empty() ? 0 : (1 + ips.size());
  MoveToBinaryFormat(callchain_data.ip_nr, p);
  if (p == reinterpret_cast<char*>(callchain_data.ips)) {
    p += old_ip_nr * sizeof(uint64_t);
  } else {
    uint64_t* old_ips = callchain_data.ips;
    callchain_data.ips = reinterpret_cast<uint64_t*>(p);
    MoveToBinaryFormat(old_ips, old_ip_nr, p);
  }
  if (!ips.empty()) {
    MoveToBinaryFormat(static_cast<uint64_t>(PERF_CONTEXT_USER), p);
    MoveToBinaryFormat(ips.data(), ips.size(), p);
  }
  if (sample_type & PERF_SAMPLE_RAW) {
    MoveToBinaryFormat(raw_data.size, p);
    raw_data.data = p;
    MoveToBinaryFormat(raw.data(), raw.size(), p);
  }
  if (sample_type & PERF_SAMPLE_BRANCH_STACK) {
    MoveToBinaryFormat(branch_stack_data.stack_nr, p);
    branch_stack_data.stack = reinterpret_cast<BranchStackItemType*>(p);
    MoveToBinaryFormat(branch_stack.data(), branch_stack.size(), p);
  }

  CHECK_LE(p, new_binary + size()) << "record time " << time_data.time;
  if (new_binary != binary_) {
    UpdateBinary(new_binary);
  }
}

void SampleRecord::DumpData(size_t indent) const {
  PrintIndented(indent, "sample_type: 0x%" PRIx64 "\n", sample_type);
  if (sample_type & PERF_SAMPLE_IP) {
    PrintIndented(indent, "ip %p\n", reinterpret_cast<void*>(ip_data.ip));
  }
  if (sample_type & PERF_SAMPLE_TID) {
    PrintIndented(indent, "pid %u, tid %u\n", tid_data.pid, tid_data.tid);
  }
  if (sample_type & PERF_SAMPLE_TIME) {
    PrintIndented(indent, "time %" PRId64 "\n", time_data.time);
  }
  if (sample_type & PERF_SAMPLE_ADDR) {
    PrintIndented(indent, "addr %p\n", reinterpret_cast<void*>(addr_data.addr));
  }
  if (sample_type & (PERF_SAMPLE_ID | PERF_SAMPLE_IDENTIFIER)) {
    PrintIndented(indent, "id %" PRId64 "\n", id_data.id);
  }
  if (sample_type & PERF_SAMPLE_STREAM_ID) {
    PrintIndented(indent, "stream_id %" PRId64 "\n", stream_id_data.stream_id);
  }
  if (sample_type & PERF_SAMPLE_CPU) {
    PrintIndented(indent, "cpu %u, res %u\n", cpu_data.cpu, cpu_data.res);
  }
  if (sample_type & PERF_SAMPLE_PERIOD) {
    PrintIndented(indent, "period %" PRId64 "\n", period_data.period);
  }
  if (sample_type & PERF_SAMPLE_READ) {
    PrintIndented(indent, "read nr=%zu\n", read_data.counts.size());
    if (read_format & PERF_FORMAT_TOTAL_TIME_ENABLED) {
      PrintIndented(indent + 1, "time_enabled %" PRIu64 "\n", read_data.time_enabled);
    }
    if (read_format & PERF_FORMAT_TOTAL_TIME_RUNNING) {
      PrintIndented(indent + 1, "time_running %" PRIu64 "\n", read_data.time_running);
    }
    for (size_t i = 0; i < read_data.counts.size(); i++) {
      PrintIndented(indent + 1, "count[%zu] %" PRIu64 "\n", i, read_data.counts[i]);
      if (read_format & PERF_FORMAT_ID) {
        PrintIndented(indent + 1, "id[%zu] %" PRIu64 "\n", i, read_data.ids[i]);
      }
    }
  }
  if (sample_type & PERF_SAMPLE_CALLCHAIN) {
    PrintIndented(indent, "callchain nr=%" PRIu64 "\n", callchain_data.ip_nr);
    for (uint64_t i = 0; i < callchain_data.ip_nr; ++i) {
      PrintIndented(indent + 1, "0x%" PRIx64 "\n", callchain_data.ips[i]);
    }
  }
  if (sample_type & PERF_SAMPLE_RAW) {
    PrintIndented(indent, "raw size=%zu\n", raw_data.size);
    const uint32_t* data = reinterpret_cast<const uint32_t*>(raw_data.data);
    size_t size = raw_data.size / sizeof(uint32_t);
    for (size_t i = 0; i < size; ++i) {
      PrintIndented(indent + 1, "0x%08x (%zu)\n", data[i], data[i]);
    }
  }
  if (sample_type & PERF_SAMPLE_BRANCH_STACK) {
    PrintIndented(indent, "branch_stack nr=%" PRIu64 "\n", branch_stack_data.stack_nr);
    for (uint64_t i = 0; i < branch_stack_data.stack_nr; ++i) {
      auto& item = branch_stack_data.stack[i];
      PrintIndented(indent + 1, "from 0x%" PRIx64 ", to 0x%" PRIx64 ", flags 0x%" PRIx64 "\n",
                    item.from, item.to, item.flags);
    }
  }
  if (sample_type & PERF_SAMPLE_REGS_USER) {
    PrintIndented(indent, "user regs: abi=%" PRId64 "\n", regs_user_data.abi);
    RegSet regs(regs_user_data.abi, regs_user_data.reg_mask, regs_user_data.regs);
    for (size_t i = 0; i < 64; ++i) {
      uint64_t value;
      if (regs.GetRegValue(i, &value)) {
        PrintIndented(indent + 1, "reg (%s) 0x%016" PRIx64 "\n", GetRegName(i, regs.arch).c_str(),
                      value);
      }
    }
  }
  if (sample_type & PERF_SAMPLE_STACK_USER) {
    PrintIndented(indent, "user stack: size %zu dyn_size %" PRIu64 "\n", stack_user_data.size,
                  stack_user_data.dyn_size);
    const uint64_t* p = reinterpret_cast<const uint64_t*>(stack_user_data.data);
    const uint64_t* end = p + (stack_user_data.size / sizeof(uint64_t));
    while (p < end) {
      PrintIndented(indent + 1, "");
      for (size_t i = 0; i < 4 && p < end; ++i, ++p) {
        printf(" %016" PRIx64, *p);
      }
      printf("\n");
    }
    printf("\n");
  }
}

uint64_t SampleRecord::Timestamp() const {
  return time_data.time;
}
uint32_t SampleRecord::Cpu() const {
  return cpu_data.cpu;
}
uint64_t SampleRecord::Id() const {
  return id_data.id;
}

void SampleRecord::AdjustCallChainGeneratedByKernel() {
  // The kernel stores return addrs in the callchain, but we want the addrs of call instructions
  // along the callchain.
  uint64_t* ips = callchain_data.ips;
  uint64_t context =
      header.misc == PERF_RECORD_MISC_KERNEL ? PERF_CONTEXT_KERNEL : PERF_CONTEXT_USER;
  bool first_frame = true;
  for (size_t i = 0; i < callchain_data.ip_nr; ++i) {
    if (ips[i] < PERF_CONTEXT_MAX) {
      if (first_frame) {
        first_frame = false;
      } else {
        if (ips[i] < 2) {
          // A wrong ip address, erase it.
          ips[i] = context;
        } else {
          // Here we want to change the return addr to the addr of the previous instruction. We
          // don't need to find the exact start addr of the previous instruction. A location in
          // [start_addr_of_call_inst, start_addr_of_next_inst) is enough.
#if defined(__arm__) || defined(__aarch64__)
          // If we are built for arm/aarch64, this may be a callchain of thumb code. For thumb code,
          // the real instruction addr is (ip & ~1), and ip - 2 can used to hit the address range
          // of the previous instruction. For non thumb code, any addr in [ip - 4, ip - 1] is fine.
          ips[i] -= 2;
#else
          ips[i]--;
#endif
        }
      }
    } else {
      context = ips[i];
    }
  }
}

std::vector<uint64_t> SampleRecord::GetCallChain(size_t* kernel_ip_count) const {
  std::vector<uint64_t> ips;
  bool in_kernel = InKernel();
  ips.push_back(ip_data.ip);
  *kernel_ip_count = in_kernel ? 1 : 0;
  if ((sample_type & PERF_SAMPLE_CALLCHAIN) == 0) {
    return ips;
  }
  bool first_ip = true;
  for (uint64_t i = 0; i < callchain_data.ip_nr; ++i) {
    uint64_t ip = callchain_data.ips[i];
    if (ip >= PERF_CONTEXT_MAX) {
      switch (ip) {
        case PERF_CONTEXT_KERNEL:
          in_kernel = true;
          break;
        case PERF_CONTEXT_USER:
          in_kernel = false;
          break;
        default:
          LOG(DEBUG) << "Unexpected perf_context in callchain: " << std::hex << ip << std::dec;
      }
    } else {
      if (first_ip) {
        first_ip = false;
        // Remove duplication with sample ip.
        if (ip == ip_data.ip) {
          continue;
        }
      }
      ips.push_back(ip);
      if (in_kernel) {
        ++*kernel_ip_count;
      }
    }
  }
  return ips;
}

bool AuxRecord::Parse(const perf_event_attr& attr, char* p, char* end) {
  if (!ParseHeader(p, end)) {
    return false;
  }
  data = reinterpret_cast<DataType*>(p);
  CHECK_SIZE(p, end, sizeof(*data));
  p += sizeof(*data);
  return sample_id.ReadFromBinaryFormat(attr, p, end);
}

void AuxRecord::DumpData(size_t indent) const {
  PrintIndented(indent, "aux_offset %" PRIu64 "\n", data->aux_offset);
  PrintIndented(indent, "aux_size %" PRIu64 "\n", data->aux_size);
  PrintIndented(indent, "flags 0x%" PRIx64 "\n", data->flags);
}

bool SwitchRecord::Parse(const perf_event_attr& attr, char* p, char* end) {
  if (!ParseHeader(p, end)) {
    return false;
  }
  return sample_id.ReadFromBinaryFormat(attr, p, end);
}

bool SwitchCpuWideRecord::Parse(const perf_event_attr& attr, char* p, char* end) {
  if (!ParseHeader(p, end)) {
    return false;
  }
  CHECK_SIZE(p, end, sizeof(tid_data));
  MoveFromBinaryFormat(tid_data, p);
  return sample_id.ReadFromBinaryFormat(attr, p, end);
}

void SwitchCpuWideRecord::DumpData(size_t indent) const {
  if (header.misc & PERF_RECORD_MISC_SWITCH_OUT) {
    PrintIndented(indent, "next_pid %u, next_tid %u\n", tid_data.pid, tid_data.tid);
  } else {
    PrintIndented(indent, "prev_pid %u, prev_tid %u\n", tid_data.pid, tid_data.tid);
  }
}

bool BuildIdRecord::Parse(const perf_event_attr&, char* p, char* end) {
  if (!ParseHeader(p, end)) {
    return false;
  }
  size_t size = Align(BUILD_ID_SIZE, 8);
  CHECK_SIZE(p, end, sizeof(uint32_t) + size);
  MoveFromBinaryFormat(pid, p);
  build_id = BuildId(p, BUILD_ID_SIZE);
  p += size;
  size = Align(SafeStrlen(p, end) + 1, 64);
  CHECK_SIZE(p, end, size);
  filename = p;
  p += size;
  return p == end;
}

void BuildIdRecord::DumpData(size_t indent) const {
  PrintIndented(indent, "pid %u\n", pid);
  PrintIndented(indent, "build_id %s\n", build_id.ToString().c_str());
  PrintIndented(indent, "filename %s\n", filename);
}

BuildIdRecord::BuildIdRecord(bool in_kernel, uint32_t pid, const BuildId& build_id,
                             const std::string& filename) {
  SetTypeAndMisc(PERF_RECORD_BUILD_ID, in_kernel ? PERF_RECORD_MISC_KERNEL : PERF_RECORD_MISC_USER);
  this->pid = pid;
  this->build_id = build_id;
  SetSize(header_size() + sizeof(this->pid) + Align(build_id.Size(), 8) +
          Align(filename.size() + 1, 64));
  char* new_binary = new char[size()];
  char* p = new_binary;
  MoveToBinaryFormat(header, p);
  MoveToBinaryFormat(this->pid, p);
  memcpy(p, build_id.Data(), build_id.Size());
  p += Align(build_id.Size(), 8);
  this->filename = p;
  strcpy(p, filename.c_str());
  UpdateBinary(new_binary);
}

bool AuxTraceInfoRecord::Parse(const perf_event_attr&, char* p, char* end) {
  if (!ParseHeader(p, end)) {
    return false;
  }
  data = reinterpret_cast<DataType*>(p);
  CHECK_SIZE(p, end, sizeof(*data));
  p += sizeof(*data);
  if (data->aux_type != AUX_TYPE_ETM || data->version != 1) {
    return false;
  }
  for (uint32_t i = 0; i < data->nr_cpu; ++i) {
    CHECK_SIZE(p, end, sizeof(uint64_t));
    uint64_t magic = *reinterpret_cast<uint64_t*>(p);
    if (magic == MAGIC_ETM4) {
      CHECK_SIZE(p, end, sizeof(ETM4Info));
      p += sizeof(ETM4Info);
    } else if (magic == MAGIC_ETE) {
      CHECK_SIZE(p, end, sizeof(ETEInfo));
      p += sizeof(ETEInfo);
    } else {
      return false;
    }
  }
  return p == end;
}

AuxTraceInfoRecord::AuxTraceInfoRecord(const DataType& data, const std::vector<ETEInfo>& ete_info) {
  SetTypeAndMisc(PERF_RECORD_AUXTRACE_INFO, 0);

  uint32_t size = header_size() + sizeof(DataType);
  for (auto& ete : ete_info) {
    size += (ete.trcdevarch == 0) ? sizeof(ETM4Info) : sizeof(ETEInfo);
  }
  SetSize(size);
  char* new_binary = new char[size];
  char* p = new_binary;
  MoveToBinaryFormat(header, p);
  this->data = reinterpret_cast<DataType*>(p);
  MoveToBinaryFormat(data, p);
  for (auto& ete : ete_info) {
    if (ete.trcdevarch == 0) {
      ETM4Info etm4;
      static_assert(sizeof(ETM4Info) + sizeof(uint64_t) == sizeof(ETEInfo));
      memcpy(&etm4, &ete, sizeof(ETM4Info));
      MoveToBinaryFormat(etm4, p);
    } else {
      MoveToBinaryFormat(ete, p);
    }
  }
  UpdateBinary(new_binary);
}

void AuxTraceInfoRecord::DumpData(size_t indent) const {
  PrintIndented(indent, "aux_type %u\n", data->aux_type);
  PrintIndented(indent, "version %" PRIu64 "\n", data->version);
  PrintIndented(indent, "nr_cpu %u\n", data->nr_cpu);
  PrintIndented(indent, "pmu_type %u\n", data->pmu_type);
  PrintIndented(indent, "snapshot %" PRIu64 "\n", data->snapshot);
  indent++;
  uint64_t* info = data->info;

  for (int i = 0; i < data->nr_cpu; i++) {
    if (info[0] == MAGIC_ETM4) {
      ETM4Info& e = *reinterpret_cast<ETM4Info*>(info);
      PrintIndented(indent, "magic 0x%" PRIx64 "\n", e.magic);
      PrintIndented(indent, "cpu %" PRIu64 "\n", e.cpu);
      PrintIndented(indent, "nrtrcparams %" PRIu64 "\n", e.nrtrcparams);
      PrintIndented(indent, "trcconfigr 0x%" PRIx64 "\n", e.trcconfigr);
      PrintIndented(indent, "trctraceidr 0x%" PRIx64 "\n", e.trctraceidr);
      PrintIndented(indent, "trcidr0 0x%" PRIx64 "\n", e.trcidr0);
      PrintIndented(indent, "trcidr1 0x%" PRIx64 "\n", e.trcidr1);
      PrintIndented(indent, "trcidr2 0x%" PRIx64 "\n", e.trcidr2);
      PrintIndented(indent, "trcidr8 0x%" PRIx64 "\n", e.trcidr8);
      PrintIndented(indent, "trcauthstatus 0x%" PRIx64 "\n", e.trcauthstatus);
      info = reinterpret_cast<uint64_t*>(&e + 1);
    } else {
      CHECK_EQ(info[0], MAGIC_ETE);
      ETEInfo& e = *reinterpret_cast<ETEInfo*>(info);
      PrintIndented(indent, "magic 0x%" PRIx64 "\n", e.magic);
      PrintIndented(indent, "cpu %" PRIu64 "\n", e.cpu);
      PrintIndented(indent, "nrtrcparams %" PRIu64 "\n", e.nrtrcparams);
      PrintIndented(indent, "trcconfigr 0x%" PRIx64 "\n", e.trcconfigr);
      PrintIndented(indent, "trctraceidr 0x%" PRIx64 "\n", e.trctraceidr);
      PrintIndented(indent, "trcidr0 0x%" PRIx64 "\n", e.trcidr0);
      PrintIndented(indent, "trcidr1 0x%" PRIx64 "\n", e.trcidr1);
      PrintIndented(indent, "trcidr2 0x%" PRIx64 "\n", e.trcidr2);
      PrintIndented(indent, "trcidr8 0x%" PRIx64 "\n", e.trcidr8);
      PrintIndented(indent, "trcauthstatus 0x%" PRIx64 "\n", e.trcauthstatus);
      PrintIndented(indent, "trcdevarch 0x%" PRIx64 "\n", e.trcdevarch);
      info = reinterpret_cast<uint64_t*>(&e + 1);
    }
  }
}

bool AuxTraceRecord::Parse(const perf_event_attr&, char* p, char* end) {
  if (!ParseHeader(p, end)) {
    return false;
  }
  data = reinterpret_cast<DataType*>(p);
  CHECK_SIZE(p, end, sizeof(*data));
  p += sizeof(*data);
  return p == end;
}

AuxTraceRecord::AuxTraceRecord(uint64_t aux_size, uint64_t offset, uint32_t idx, uint32_t tid,
                               uint32_t cpu) {
  SetTypeAndMisc(PERF_RECORD_AUXTRACE, 0);
  SetSize(header_size() + sizeof(DataType));
  char* new_binary = new char[size()];
  char* p = new_binary;
  MoveToBinaryFormat(header, p);
  data = reinterpret_cast<DataType*>(p);
  data->aux_size = aux_size;
  data->offset = offset;
  data->reserved0 = 0;
  data->idx = idx;
  data->tid = tid;
  data->cpu = cpu;
  data->reserved1 = 0;
  UpdateBinary(new_binary);
}

void AuxTraceRecord::DumpData(size_t indent) const {
  PrintIndented(indent, "aux_size %" PRIu64 "\n", data->aux_size);
  PrintIndented(indent, "offset %" PRIu64 "\n", data->offset);
  PrintIndented(indent, "idx %u\n", data->idx);
  PrintIndented(indent, "tid %u\n", data->tid);
  PrintIndented(indent, "cpu %u\n", data->cpu);
  PrintIndented(indent, "location.file_offset %" PRIu64 "\n", location.file_offset);
}

bool KernelSymbolRecord::Parse(const perf_event_attr&, char* p, char* end) {
  if (!ParseHeader(p, end)) {
    return false;
  }
  CHECK_SIZE(p, end, sizeof(uint32_t));
  MoveFromBinaryFormat(kallsyms_size, p);
  size_t size = Align(kallsyms_size, 8);
  CHECK_SIZE(p, end, size);
  kallsyms = p;
  p += size;
  return p == end;
}

void KernelSymbolRecord::DumpData(size_t indent) const {
  PrintIndented(indent, "kallsyms: %s\n", std::string(kallsyms, kallsyms + kallsyms_size).c_str());
}

KernelSymbolRecord::KernelSymbolRecord(const std::string& kallsyms) {
  SetTypeAndMisc(SIMPLE_PERF_RECORD_KERNEL_SYMBOL, 0);
  kallsyms_size = kallsyms.size();
  SetSize(header_size() + 4 + Align(kallsyms.size(), 8));
  char* new_binary = new char[size()];
  char* p = new_binary;
  MoveToBinaryFormat(header, p);
  MoveToBinaryFormat(kallsyms_size, p);
  this->kallsyms = p;
  memcpy(p, kallsyms.data(), kallsyms_size);
  UpdateBinary(new_binary);
}

bool DsoRecord::Parse(const perf_event_attr&, char* p, char* end) {
  if (!ParseHeader(p, end)) {
    return false;
  }
  CHECK_SIZE_U64(p, end, 3);
  MoveFromBinaryFormat(dso_type, p);
  MoveFromBinaryFormat(dso_id, p);
  MoveFromBinaryFormat(min_vaddr, p);
  size_t size = Align(SafeStrlen(p, end) + 1, 8);
  dso_name = p;
  p += size;
  return p == end;
}

DsoRecord::DsoRecord(uint64_t dso_type, uint64_t dso_id, const std::string& dso_name,
                     uint64_t min_vaddr) {
  SetTypeAndMisc(SIMPLE_PERF_RECORD_DSO, 0);
  this->dso_type = dso_type;
  this->dso_id = dso_id;
  this->min_vaddr = min_vaddr;
  SetSize(header_size() + 3 * sizeof(uint64_t) + Align(dso_name.size() + 1, 8));
  char* new_binary = new char[size()];
  char* p = new_binary;
  MoveToBinaryFormat(header, p);
  MoveToBinaryFormat(dso_type, p);
  MoveToBinaryFormat(dso_id, p);
  MoveToBinaryFormat(min_vaddr, p);
  this->dso_name = p;
  strcpy(p, dso_name.c_str());
  UpdateBinary(new_binary);
}

void DsoRecord::DumpData(size_t indent) const {
  PrintIndented(indent, "dso_type: %s(%" PRIu64 ")\n",
                DsoTypeToString(static_cast<DsoType>(dso_type)), dso_type);
  PrintIndented(indent, "dso_id: %" PRIu64 "\n", dso_id);
  PrintIndented(indent, "min_vaddr: 0x%" PRIx64 "\n", min_vaddr);
  PrintIndented(indent, "dso_name: %s\n", dso_name);
}

bool SymbolRecord::Parse(const perf_event_attr&, char* p, char* end) {
  if (!ParseHeader(p, end)) {
    return false;
  }
  CHECK_SIZE_U64(p, end, 3);
  MoveFromBinaryFormat(addr, p);
  MoveFromBinaryFormat(len, p);
  MoveFromBinaryFormat(dso_id, p);
  size_t size = Align(SafeStrlen(p, end) + 1, 8);
  name = p;
  p += size;
  return p == end;
}

SymbolRecord::SymbolRecord(uint64_t addr, uint64_t len, const std::string& name, uint64_t dso_id) {
  SetTypeAndMisc(SIMPLE_PERF_RECORD_SYMBOL, 0);
  this->addr = addr;
  this->len = len;
  this->dso_id = dso_id;
  SetSize(header_size() + 3 * sizeof(uint64_t) + Align(name.size() + 1, 8));
  char* new_binary = new char[size()];
  char* p = new_binary;
  MoveToBinaryFormat(header, p);
  MoveToBinaryFormat(addr, p);
  MoveToBinaryFormat(len, p);
  MoveToBinaryFormat(dso_id, p);
  this->name = p;
  strcpy(p, name.c_str());
  UpdateBinary(new_binary);
}

void SymbolRecord::DumpData(size_t indent) const {
  PrintIndented(indent, "name: %s\n", name);
  PrintIndented(indent, "addr: 0x%" PRIx64 "\n", addr);
  PrintIndented(indent, "len: 0x%" PRIx64 "\n", len);
  PrintIndented(indent, "dso_id: %" PRIu64 "\n", dso_id);
}

bool TracingDataRecord::Parse(const perf_event_attr&, char* p, char* end) {
  if (!ParseHeader(p, end)) {
    return false;
  }
  CHECK_SIZE(p, end, sizeof(uint32_t));
  MoveFromBinaryFormat(data_size, p);
  size_t size = Align(data_size, 64);
  CHECK_SIZE(p, end, size);
  data = p;
  p += size;
  return p == end;
}

TracingDataRecord::TracingDataRecord(const std::vector<char>& tracing_data) {
  SetTypeAndMisc(SIMPLE_PERF_RECORD_TRACING_DATA, 0);
  data_size = tracing_data.size();
  SetSize(header_size() + sizeof(uint32_t) + Align(tracing_data.size(), 64));
  char* new_binary = new char[size()];
  char* p = new_binary;
  MoveToBinaryFormat(header, p);
  MoveToBinaryFormat(data_size, p);
  data = p;
  memcpy(p, tracing_data.data(), data_size);
  UpdateBinary(new_binary);
}

void TracingDataRecord::DumpData(size_t indent) const {
  auto tracing = Tracing::Create(std::vector<char>(data, data + data_size));
  if (tracing) {
    tracing->Dump(indent);
  }
}

bool EventIdRecord::Parse(const perf_event_attr&, char* p, char* end) {
  if (!ParseHeader(p, end)) {
    return false;
  }
  CHECK_SIZE_U64(p, end, 1);
  MoveFromBinaryFormat(count, p);
  data = reinterpret_cast<const EventIdData*>(p);
  CHECK_SIZE(p, end, sizeof(data[0]) * count);
  p += sizeof(data[0]) * count;
  return p == end;
}

EventIdRecord::EventIdRecord(const std::vector<uint64_t>& data) {
  SetTypeAndMisc(SIMPLE_PERF_RECORD_EVENT_ID, 0);
  SetSize(header_size() + sizeof(uint64_t) * (1 + data.size()));
  char* new_binary = new char[size()];
  char* p = new_binary;
  MoveToBinaryFormat(header, p);
  count = data.size() / 2;
  MoveToBinaryFormat(count, p);
  this->data = reinterpret_cast<EventIdData*>(p);
  memcpy(p, data.data(), sizeof(uint64_t) * data.size());
  UpdateBinary(new_binary);
}

void EventIdRecord::DumpData(size_t indent) const {
  PrintIndented(indent, "count: %" PRIu64 "\n", count);
  for (size_t i = 0; i < count; ++i) {
    PrintIndented(indent, "attr_id[%" PRIu64 "]: %" PRIu64 "\n", i, data[i].attr_id);
    PrintIndented(indent, "event_id[%" PRIu64 "]: %" PRIu64 "\n", i, data[i].event_id);
  }
}

bool CallChainRecord::Parse(const perf_event_attr&, char* p, char* end) {
  if (!ParseHeader(p, end)) {
    return false;
  }
  CHECK_SIZE_U64(p, end, 4);
  MoveFromBinaryFormat(pid, p);
  MoveFromBinaryFormat(tid, p);
  MoveFromBinaryFormat(chain_type, p);
  MoveFromBinaryFormat(time, p);
  MoveFromBinaryFormat(ip_nr, p);
  CHECK_SIZE_U64(p, end, ip_nr * 2);
  ips = reinterpret_cast<uint64_t*>(p);
  p += ip_nr * sizeof(uint64_t);
  sps = reinterpret_cast<uint64_t*>(p);
  p += ip_nr * sizeof(uint64_t);
  return p == end;
}

CallChainRecord::CallChainRecord(pid_t pid, pid_t tid, CallChainJoiner::ChainType type,
                                 uint64_t time, const std::vector<uint64_t>& ips,
                                 const std::vector<uint64_t>& sps) {
  CHECK_EQ(ips.size(), sps.size());
  SetTypeAndMisc(SIMPLE_PERF_RECORD_CALLCHAIN, 0);
  this->pid = pid;
  this->tid = tid;
  this->chain_type = static_cast<int>(type);
  this->time = time;
  this->ip_nr = ips.size();
  SetSize(header_size() + (4 + ips.size() * 2) * sizeof(uint64_t));
  char* new_binary = new char[size()];
  char* p = new_binary;
  MoveToBinaryFormat(header, p);
  MoveToBinaryFormat(this->pid, p);
  MoveToBinaryFormat(this->tid, p);
  MoveToBinaryFormat(this->chain_type, p);
  MoveToBinaryFormat(this->time, p);
  MoveToBinaryFormat(this->ip_nr, p);
  this->ips = reinterpret_cast<uint64_t*>(p);
  MoveToBinaryFormat(ips.data(), ips.size(), p);
  this->sps = reinterpret_cast<uint64_t*>(p);
  MoveToBinaryFormat(sps.data(), sps.size(), p);
  UpdateBinary(new_binary);
}

void CallChainRecord::DumpData(size_t indent) const {
  const char* type_name = "";
  switch (chain_type) {
    case CallChainJoiner::ORIGINAL_OFFLINE:
      type_name = "ORIGINAL_OFFLINE";
      break;
    case CallChainJoiner::ORIGINAL_REMOTE:
      type_name = "ORIGINAL_REMOTE";
      break;
    case CallChainJoiner::JOINED_OFFLINE:
      type_name = "JOINED_OFFLINE";
      break;
    case CallChainJoiner::JOINED_REMOTE:
      type_name = "JOINED_REMOTE";
      break;
  }
  PrintIndented(indent, "pid %u\n", pid);
  PrintIndented(indent, "tid %u\n", tid);
  PrintIndented(indent, "chain_type %s\n", type_name);
  PrintIndented(indent, "time %" PRIu64 "\n", time);
  PrintIndented(indent, "ip_nr %" PRIu64 "\n", ip_nr);
  for (size_t i = 0; i < ip_nr; ++i) {
    PrintIndented(indent + 1, "ip 0x%" PRIx64 ", sp 0x%" PRIx64 "\n", ips[i], sps[i]);
  }
}

bool UnwindingResultRecord::Parse(const perf_event_attr&, char* p, char* end) {
  if (!ParseHeader(p, end)) {
    return false;
  }
  CHECK_SIZE_U64(p, end, 8);
  MoveFromBinaryFormat(time, p);
  MoveFromBinaryFormat(unwinding_result.used_time, p);
  MoveFromBinaryFormat(unwinding_result.error_code, p);
  MoveFromBinaryFormat(unwinding_result.error_addr, p);
  MoveFromBinaryFormat(unwinding_result.stack_start, p);
  MoveFromBinaryFormat(unwinding_result.stack_end, p);

  // regs_user_data
  MoveFromBinaryFormat(regs_user_data.abi, p);
  MoveFromBinaryFormat(regs_user_data.reg_mask, p);
  size_t bit_nr = __builtin_popcountll(regs_user_data.reg_mask);
  CHECK_SIZE_U64(p, end, bit_nr);
  regs_user_data.reg_nr = bit_nr;
  regs_user_data.regs = reinterpret_cast<uint64_t*>(p);
  p += bit_nr * sizeof(uint64_t);

  // stack_user_data
  CHECK_SIZE_U64(p, end, 1);
  MoveFromBinaryFormat(stack_user_data.size, p);
  if (stack_user_data.size == 0) {
    stack_user_data.dyn_size = 0;
  } else {
    CHECK_SIZE(p, end, stack_user_data.size + sizeof(uint64_t));
    stack_user_data.data = p;
    p += stack_user_data.size;
    MoveFromBinaryFormat(stack_user_data.dyn_size, p);
  }

  // callchain
  if (p < end) {
    CHECK_SIZE_U64(p, end, 1);
    MoveFromBinaryFormat(callchain.length, p);
    CHECK_SIZE_U64(p, end, callchain.length * 2);
    callchain.ips = reinterpret_cast<uint64_t*>(p);
    p += callchain.length * sizeof(uint64_t);
    callchain.sps = reinterpret_cast<uint64_t*>(p);
    p += callchain.length * sizeof(uint64_t);
  }
  return true;
}

UnwindingResultRecord::UnwindingResultRecord(uint64_t time, const UnwindingResult& unwinding_result,
                                             const PerfSampleRegsUserType& regs_user_data,
                                             const PerfSampleStackUserType& stack_user_data,
                                             const std::vector<uint64_t>& ips,
                                             const std::vector<uint64_t>& sps) {
  SetTypeAndMisc(SIMPLE_PERF_RECORD_UNWINDING_RESULT, 0);
  uint32_t size = header_size() + 6 * sizeof(uint64_t);
  size += (2 + regs_user_data.reg_nr) * sizeof(uint64_t);
  size +=
      stack_user_data.size == 0 ? sizeof(uint64_t) : (2 * sizeof(uint64_t) + stack_user_data.size);
  CHECK_EQ(ips.size(), sps.size());
  size += (1 + ips.size() * 2) * sizeof(uint64_t);
  SetSize(size);
  this->time = time;
  this->unwinding_result = unwinding_result;
  char* new_binary = new char[size];
  char* p = new_binary;
  MoveToBinaryFormat(header, p);
  MoveToBinaryFormat(this->time, p);
  MoveToBinaryFormat(unwinding_result.used_time, p);
  MoveToBinaryFormat(unwinding_result.error_code, p);
  MoveToBinaryFormat(unwinding_result.error_addr, p);
  MoveToBinaryFormat(unwinding_result.stack_start, p);
  MoveToBinaryFormat(unwinding_result.stack_end, p);
  MoveToBinaryFormat(regs_user_data.abi, p);
  MoveToBinaryFormat(regs_user_data.reg_mask, p);
  if (regs_user_data.reg_nr > 0) {
    MoveToBinaryFormat(regs_user_data.regs, regs_user_data.reg_nr, p);
  }
  MoveToBinaryFormat(stack_user_data.size, p);
  if (stack_user_data.size > 0) {
    MoveToBinaryFormat(stack_user_data.data, stack_user_data.size, p);
    MoveToBinaryFormat(stack_user_data.dyn_size, p);
  }
  MoveToBinaryFormat(static_cast<uint64_t>(ips.size()), p);
  MoveToBinaryFormat(ips.data(), ips.size(), p);
  MoveToBinaryFormat(sps.data(), sps.size(), p);
  CHECK_EQ(p, new_binary + size);
  UpdateBinary(new_binary);
}

void UnwindingResultRecord::DumpData(size_t indent) const {
  PrintIndented(indent, "time %" PRIu64 "\n", time);
  PrintIndented(indent, "used_time %" PRIu64 "\n", unwinding_result.used_time);
  PrintIndented(indent, "error_code %" PRIu64 "\n", unwinding_result.error_code);
  PrintIndented(indent, "error_addr 0x%" PRIx64 "\n", unwinding_result.error_addr);
  PrintIndented(indent, "stack_start 0x%" PRIx64 "\n", unwinding_result.stack_start);
  PrintIndented(indent, "stack_end 0x%" PRIx64 "\n", unwinding_result.stack_end);
  if (regs_user_data.reg_nr > 0) {
    PrintIndented(indent, "user regs: abi=%" PRId64 "\n", regs_user_data.abi);
    RegSet regs(regs_user_data.abi, regs_user_data.reg_mask, regs_user_data.regs);
    for (size_t i = 0; i < 64; ++i) {
      uint64_t value;
      if (regs.GetRegValue(i, &value)) {
        PrintIndented(indent + 1, "reg (%s) 0x%016" PRIx64 "\n", GetRegName(i, regs.arch).c_str(),
                      value);
      }
    }
  }
  if (stack_user_data.size > 0) {
    PrintIndented(indent, "user stack: size %zu dyn_size %" PRIu64 "\n", stack_user_data.size,
                  stack_user_data.dyn_size);
    const uint64_t* p = reinterpret_cast<const uint64_t*>(stack_user_data.data);
    const uint64_t* end = p + (stack_user_data.size / sizeof(uint64_t));
    while (p < end) {
      PrintIndented(indent + 1, "");
      for (size_t i = 0; i < 4 && p < end; ++i, ++p) {
        printf(" %016" PRIx64, *p);
      }
      printf("\n");
    }
    printf("\n");
  }
  if (callchain.length > 0) {
    PrintIndented(indent, "callchain length=%" PRIu64 ":\n", callchain.length);
    for (uint64_t i = 0; i < callchain.length; i++) {
      PrintIndented(indent + 1, "ip_%" PRIu64 ": 0x%" PRIx64 "\n", i + 1, callchain.ips[i]);
      PrintIndented(indent + 1, "sp_%" PRIu64 ": 0x%" PRIx64 "\n", i + 1, callchain.sps[i]);
    }
  }
}

DebugRecord::DebugRecord(uint64_t time, const std::string& s) {
  SetTypeAndMisc(SIMPLE_PERF_RECORD_DEBUG, 0);
  uint32_t size = header_size() + sizeof(uint64_t) + Align(strlen(s.c_str()) + 1, sizeof(uint64_t));
  SetSize(size);
  char* new_binary = new char[size];
  char* p = new_binary;
  MoveToBinaryFormat(header, p);
  MoveToBinaryFormat(time, p);
  this->time = time;
  this->s = p;
  MoveToBinaryFormat(s.c_str(), strlen(s.c_str()) + 1, p);
  CHECK_LE(p, new_binary + size);
  UpdateBinary(new_binary);
}

bool DebugRecord::Parse(const perf_event_attr&, char* p, char* end) {
  if (!ParseHeader(p, end)) {
    return false;
  }
  CHECK_SIZE_U64(p, end, 1);
  MoveFromBinaryFormat(time, p);
  if (memchr(p, '\0', end - p) == nullptr) {
    return false;
  }
  s = p;
  return true;
}

void DebugRecord::DumpData(size_t indent) const {
  PrintIndented(indent, "s %s\n", s);
}

bool UnknownRecord::Parse(const perf_event_attr&, char* p, char* end) {
  if (!ParseHeader(p, end)) {
    return false;
  }
  data = p;
  return true;
}

void UnknownRecord::DumpData(size_t) const {}

std::unique_ptr<Record> ReadRecordFromBuffer(const perf_event_attr& attr, uint32_t type, char* p,
                                             char* end) {
  std::unique_ptr<Record> r;
  switch (type) {
    case PERF_RECORD_MMAP:
      r.reset(new MmapRecord);
      break;
    case PERF_RECORD_MMAP2:
      r.reset(new Mmap2Record);
      break;
    case PERF_RECORD_COMM:
      r.reset(new CommRecord);
      break;
    case PERF_RECORD_EXIT:
      r.reset(new ExitRecord);
      break;
    case PERF_RECORD_FORK:
      r.reset(new ForkRecord);
      break;
    case PERF_RECORD_LOST:
      r.reset(new LostRecord);
      break;
    case PERF_RECORD_SAMPLE:
      r.reset(new SampleRecord);
      break;
    case PERF_RECORD_AUX:
      r.reset(new AuxRecord);
      break;
    case PERF_RECORD_SWITCH:
      r.reset(new SwitchRecord);
      break;
    case PERF_RECORD_SWITCH_CPU_WIDE:
      r.reset(new SwitchCpuWideRecord);
      break;
    case PERF_RECORD_TRACING_DATA:
      r.reset(new TracingDataRecord);
      break;
    case PERF_RECORD_AUXTRACE_INFO:
      r.reset(new AuxTraceInfoRecord);
      break;
    case PERF_RECORD_AUXTRACE:
      r.reset(new AuxTraceRecord);
      break;
    case SIMPLE_PERF_RECORD_KERNEL_SYMBOL:
      r.reset(new KernelSymbolRecord);
      break;
    case SIMPLE_PERF_RECORD_DSO:
      r.reset(new DsoRecord);
      break;
    case SIMPLE_PERF_RECORD_SYMBOL:
      r.reset(new SymbolRecord);
      break;
    case SIMPLE_PERF_RECORD_EVENT_ID:
      r.reset(new EventIdRecord);
      break;
    case SIMPLE_PERF_RECORD_CALLCHAIN:
      r.reset(new CallChainRecord);
      break;
    case SIMPLE_PERF_RECORD_UNWINDING_RESULT:
      r.reset(new UnwindingResultRecord);
      break;
    case SIMPLE_PERF_RECORD_TRACING_DATA:
      r.reset(new TracingDataRecord);
      break;
    case SIMPLE_PERF_RECORD_DEBUG:
      r.reset(new DebugRecord);
      break;
    default:
      r.reset(new UnknownRecord);
      break;
  }
  if (UNLIKELY(!r->Parse(attr, p, end))) {
    LOG(ERROR) << "failed to parse record " << RecordTypeToString(type);
    return nullptr;
  }
  return r;
}

std::vector<std::unique_ptr<Record>> ReadRecordsFromBuffer(const perf_event_attr& attr, char* buf,
                                                           size_t buf_size) {
  std::vector<std::unique_ptr<Record>> result;
  char* p = buf;
  char* end = buf + buf_size;
  while (p < end) {
    std::unique_ptr<Record> r = ReadRecordFromBuffer(attr, p, end);
    if (!r) {
      return {};
    }
    p += r->size();
    result.emplace_back(std::move(r));
  }
  return result;
}

std::unique_ptr<Record> ReadRecordFromBuffer(const perf_event_attr& attr, char* p, char* end) {
  auto header = reinterpret_cast<const perf_event_header*>(p);
  return ReadRecordFromBuffer(attr, header->type, p, end);
}

}  // namespace simpleperf
