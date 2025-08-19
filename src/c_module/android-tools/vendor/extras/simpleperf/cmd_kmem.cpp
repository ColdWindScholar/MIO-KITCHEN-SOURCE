/*
 * Copyright (C) 2016 The Android Open Source Project
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

#include "command.h"

#include <unordered_map>

#include <android-base/logging.h>
#include <android-base/strings.h>

#include "callchain.h"
#include "event_attr.h"
#include "event_type.h"
#include "record_file.h"
#include "sample_tree.h"
#include "tracing.h"
#include "utils.h"

namespace simpleperf {
namespace {

struct SlabSample {
  const Symbol* symbol;                 // the function making allocation
  uint64_t ptr;                         // the start address of the allocated space
  uint64_t bytes_req;                   // requested space size
  uint64_t bytes_alloc;                 // allocated space size
  uint64_t sample_count;                // count of allocations
  uint64_t gfp_flags;                   // flags used for allocation
  uint64_t cross_cpu_allocations;       // count of allocations freed not on the
                                        // cpu allocating them
  CallChainRoot<SlabSample> callchain;  // a callchain tree representing all
                                        // callchains in this sample
  SlabSample(const Symbol* symbol, uint64_t ptr, uint64_t bytes_req, uint64_t bytes_alloc,
             uint64_t sample_count, uint64_t gfp_flags, uint64_t cross_cpu_allocations)
      : symbol(symbol),
        ptr(ptr),
        bytes_req(bytes_req),
        bytes_alloc(bytes_alloc),
        sample_count(sample_count),
        gfp_flags(gfp_flags),
        cross_cpu_allocations(cross_cpu_allocations) {}

  uint64_t GetPeriod() const { return sample_count; }
};

struct SlabAccumulateInfo {
  uint64_t bytes_req;
  uint64_t bytes_alloc;
};

BUILD_COMPARE_VALUE_FUNCTION(ComparePtr, ptr);
BUILD_COMPARE_VALUE_FUNCTION_REVERSE(CompareBytesReq, bytes_req);
BUILD_COMPARE_VALUE_FUNCTION_REVERSE(CompareBytesAlloc, bytes_alloc);
BUILD_COMPARE_VALUE_FUNCTION(CompareGfpFlags, gfp_flags);
BUILD_COMPARE_VALUE_FUNCTION_REVERSE(CompareCrossCpuAllocations, cross_cpu_allocations);

BUILD_DISPLAY_HEX64_FUNCTION(DisplayPtr, ptr);
BUILD_DISPLAY_UINT64_FUNCTION(DisplayBytesReq, bytes_req);
BUILD_DISPLAY_UINT64_FUNCTION(DisplayBytesAlloc, bytes_alloc);
BUILD_DISPLAY_HEX64_FUNCTION(DisplayGfpFlags, gfp_flags);
BUILD_DISPLAY_UINT64_FUNCTION(DisplayCrossCpuAllocations, cross_cpu_allocations);

static int CompareFragment(const SlabSample* sample1, const SlabSample* sample2) {
  uint64_t frag1 = sample1->bytes_alloc - sample1->bytes_req;
  uint64_t frag2 = sample2->bytes_alloc - sample2->bytes_req;
  return Compare(frag2, frag1);
}

static std::string DisplayFragment(const SlabSample* sample) {
  return android::base::StringPrintf("%" PRIu64, sample->bytes_alloc - sample->bytes_req);
}

struct SlabSampleTree {
  std::vector<SlabSample*> samples;
  uint64_t total_requested_bytes;
  uint64_t total_allocated_bytes;
  uint64_t nr_allocations;
  uint64_t nr_frees;
  uint64_t nr_cross_cpu_allocations;
};

struct SlabFormat {
  enum {
    KMEM_ALLOC,
    KMEM_FREE,
  } type;
  TracingFieldPlace call_site;
  TracingFieldPlace ptr;
  TracingFieldPlace bytes_req;
  TracingFieldPlace bytes_alloc;
  TracingFieldPlace gfp_flags;
};

class SlabSampleTreeBuilder : public SampleTreeBuilder<SlabSample, SlabAccumulateInfo> {
 public:
  SlabSampleTreeBuilder(const SampleComparator<SlabSample>& sample_comparator,
                        ThreadTree* thread_tree)
      : SampleTreeBuilder(sample_comparator),
        thread_tree_(thread_tree),
        total_requested_bytes_(0),
        total_allocated_bytes_(0),
        nr_allocations_(0),
        nr_cross_cpu_allocations_(0) {}

  SlabSampleTree GetSampleTree() const {
    SlabSampleTree sample_tree;
    sample_tree.samples = GetSamples();
    sample_tree.total_requested_bytes = total_requested_bytes_;
    sample_tree.total_allocated_bytes = total_allocated_bytes_;
    sample_tree.nr_allocations = nr_allocations_;
    sample_tree.nr_frees = nr_frees_;
    sample_tree.nr_cross_cpu_allocations = nr_cross_cpu_allocations_;
    return sample_tree;
  }

  void AddSlabFormat(const std::vector<uint64_t>& event_ids, SlabFormat format) {
    std::unique_ptr<SlabFormat> p(new SlabFormat(format));
    for (auto id : event_ids) {
      event_id_to_format_map_[id] = p.get();
    }
    formats_.push_back(std::move(p));
  }

 protected:
  SlabSample* CreateSample(const SampleRecord& r, bool in_kernel,
                           SlabAccumulateInfo* acc_info) override {
    if (!in_kernel) {
      // Normally we don't parse records in user space because tracepoint
      // events all happen in kernel. But if r.ip_data.ip == 0, it may be
      // a kernel record failed to dump ip register and is still useful.
      if (r.ip_data.ip == 0) {
        // It seems we are on a kernel can't dump regset for tracepoint events
        // because of lacking perf_arch_fetch_caller_regs(). We can't get
        // callchain, but we can still do a normal report.
        static bool first = true;
        if (first) {
          first = false;
          if (accumulate_callchain_) {
            // The kernel doesn't seem to support dumping registers for
            // tracepoint events because of lacking
            // perf_arch_fetch_caller_regs().
            LOG(WARNING) << "simpleperf may not get callchains for tracepoint"
                         << " events because of lacking kernel support.";
          }
        }
      } else {
        return nullptr;
      }
    }
    uint64_t id = r.id_data.id;
    auto it = event_id_to_format_map_.find(id);
    if (it == event_id_to_format_map_.end()) {
      return nullptr;
    }
    const char* raw_data = r.raw_data.data;
    SlabFormat* format = it->second;
    if (format->type == SlabFormat::KMEM_ALLOC) {
      uint64_t call_site = format->call_site.ReadFromData(raw_data);
      const Symbol* symbol = thread_tree_->FindKernelSymbol(call_site);
      uint64_t ptr = format->ptr.ReadFromData(raw_data);
      uint64_t bytes_req = format->bytes_req.ReadFromData(raw_data);
      uint64_t bytes_alloc = format->bytes_alloc.ReadFromData(raw_data);
      uint64_t gfp_flags = format->gfp_flags.ReadFromData(raw_data);
      SlabSample* sample = InsertSample(std::unique_ptr<SlabSample>(
          new SlabSample(symbol, ptr, bytes_req, bytes_alloc, 1, gfp_flags, 0)));
      alloc_cpu_record_map_.insert(std::make_pair(ptr, std::make_pair(r.cpu_data.cpu, sample)));
      acc_info->bytes_req = bytes_req;
      acc_info->bytes_alloc = bytes_alloc;
      return sample;
    } else if (format->type == SlabFormat::KMEM_FREE) {
      uint64_t ptr = format->ptr.ReadFromData(raw_data);
      auto it = alloc_cpu_record_map_.find(ptr);
      if (it != alloc_cpu_record_map_.end()) {
        SlabSample* sample = it->second.second;
        if (r.cpu_data.cpu != it->second.first) {
          sample->cross_cpu_allocations++;
          nr_cross_cpu_allocations_++;
        }
        alloc_cpu_record_map_.erase(it);
      }
      nr_frees_++;
    }
    return nullptr;
  }

  SlabSample* CreateBranchSample(const SampleRecord&, const BranchStackItemType&) override {
    return nullptr;
  }

  SlabSample* CreateCallChainSample(const ThreadEntry*, const SlabSample* sample, uint64_t ip,
                                    bool in_kernel, const std::vector<SlabSample*>& callchain,
                                    const SlabAccumulateInfo& acc_info) override {
    if (!in_kernel) {
      return nullptr;
    }
    const Symbol* symbol = thread_tree_->FindKernelSymbol(ip);
    return InsertCallChainSample(
        std::unique_ptr<SlabSample>(new SlabSample(symbol, sample->ptr, acc_info.bytes_req,
                                                   acc_info.bytes_alloc, 1, sample->gfp_flags, 0)),
        callchain);
  }

  const ThreadEntry* GetThreadOfSample(SlabSample*) override { return nullptr; }

  uint64_t GetPeriodForCallChain(const SlabAccumulateInfo&) override {
    // Decide the percentage of callchain by the sample_count, so use 1 as the
    // period when calling AddCallChain().
    return 1;
  }

  void UpdateSummary(const SlabSample* sample) override {
    total_requested_bytes_ += sample->bytes_req;
    total_allocated_bytes_ += sample->bytes_alloc;
    nr_allocations_++;
  }

  void MergeSample(SlabSample* sample1, SlabSample* sample2) override {
    sample1->bytes_req += sample2->bytes_req;
    sample1->bytes_alloc += sample2->bytes_alloc;
    sample1->sample_count += sample2->sample_count;
  }

 private:
  ThreadTree* thread_tree_;
  uint64_t total_requested_bytes_;
  uint64_t total_allocated_bytes_;
  uint64_t nr_allocations_;
  uint64_t nr_frees_;
  uint64_t nr_cross_cpu_allocations_;

  std::unordered_map<uint64_t, SlabFormat*> event_id_to_format_map_;
  std::vector<std::unique_ptr<SlabFormat>> formats_;
  std::unordered_map<uint64_t, std::pair<uint32_t, SlabSample*>> alloc_cpu_record_map_;
};

using SlabSampleTreeSorter = SampleTreeSorter<SlabSample>;
using SlabSampleTreeDisplayer = SampleTreeDisplayer<SlabSample, SlabSampleTree>;
using SlabSampleCallgraphDisplayer = CallgraphDisplayer<SlabSample, CallChainNode<SlabSample>>;

struct EventAttrWithName {
  perf_event_attr attr;
  std::string name;
  std::vector<uint64_t> event_ids;
};

class KmemCommand : public Command {
 public:
  KmemCommand()
      : Command("kmem", "collect kernel memory allocation information",
                // clang-format off
"Usage: kmem (record [record options] | report [report options])\n"
"kmem record\n"
"-g        Enable call graph recording. Same as '--call-graph fp'.\n"
"--slab    Collect slab allocation information. Default option.\n"
"Other record options provided by simpleperf record command are also available.\n"
"kmem report\n"
"--children  Print the accumulated allocation info appeared in the callchain.\n"
"            Can be used on perf.data recorded with `--call-graph fp` option.\n"
"-g [callee|caller]  Print call graph for perf.data recorded with\n"
"                    `--call-graph fp` option. If callee mode is used, the graph\n"
"                     shows how functions are called from others. Otherwise, the\n"
"                     graph shows how functions call others. Default is callee\n"
"                     mode. The percentage shown in the graph is determined by\n"
"                     the hit count of the callchain.\n"
"-i          Specify path of record file, default is perf.data\n"
"-o report_file_name  Set report file name, default is stdout.\n"
"--slab      Report slab allocation information. Default option.\n"
"--slab-sort key1,key2,...\n"
"            Select the keys to sort and print slab allocation information.\n"
"            Should be used with --slab option. Possible keys include:\n"
"              hit         -- the allocation count.\n"
"              caller      -- the function calling allocation.\n"
"              ptr         -- the address of the allocated space.\n"
"              bytes_req   -- the total requested space size.\n"
"              bytes_alloc -- the total allocated space size.\n"
"              fragment    -- the extra allocated space size\n"
"                             (bytes_alloc - bytes_req).\n"
"              gfp_flags   -- the flags used for allocation.\n"
"              pingpong    -- the count of allocations that are freed not on\n"
"                             the cpu allocating them.\n"
"            The default slab sort keys are:\n"
"              hit,caller,bytes_req,bytes_alloc,fragment,pingpong.\n"
                // clang-format on
                ),
        is_record_(false),
        use_slab_(false),
        accumulate_callchain_(false),
        print_callgraph_(false),
        callgraph_show_callee_(false),
        record_filename_("perf.data"),
        record_file_arch_(GetTargetArch()) {}

  bool Run(const std::vector<std::string>& args);

 private:
  bool ParseOptions(const std::vector<std::string>& args, std::vector<std::string>* left_args);
  bool RecordKmemInfo(const std::vector<std::string>& record_args);
  bool ReportKmemInfo();
  bool PrepareToBuildSampleTree();
  void ReadEventAttrsFromRecordFile();
  bool ReadFeaturesFromRecordFile();
  bool ReadSampleTreeFromRecordFile();
  bool ProcessRecord(std::unique_ptr<Record> record);
  bool ProcessTracingData(const std::vector<char>& data);
  bool PrintReport();
  void PrintReportContext(FILE* fp);
  void PrintSlabReportContext(FILE* fp);

  bool is_record_;
  bool use_slab_;
  std::vector<std::string> slab_sort_keys_;
  bool accumulate_callchain_;
  bool print_callgraph_;
  bool callgraph_show_callee_;

  std::string record_filename_;
  std::unique_ptr<RecordFileReader> record_file_reader_;
  std::vector<EventAttrWithName> event_attrs_;
  std::string record_cmdline_;
  ArchType record_file_arch_;

  ThreadTree thread_tree_;
  SlabSampleTree slab_sample_tree_;
  std::unique_ptr<SlabSampleTreeBuilder> slab_sample_tree_builder_;
  std::unique_ptr<SlabSampleTreeSorter> slab_sample_tree_sorter_;
  std::unique_ptr<SlabSampleTreeDisplayer> slab_sample_tree_displayer_;

  std::string report_filename_;
};

bool KmemCommand::Run(const std::vector<std::string>& args) {
  std::vector<std::string> left_args;
  if (!ParseOptions(args, &left_args)) {
    return false;
  }
  if (!use_slab_) {
    use_slab_ = true;
  }
  if (is_record_) {
    return RecordKmemInfo(left_args);
  }
  return ReportKmemInfo();
}

bool KmemCommand::ParseOptions(const std::vector<std::string>& args,
                               std::vector<std::string>* left_args) {
  if (args.empty()) {
    LOG(ERROR) << "No subcommand specified";
    return false;
  }
  if (args[0] == "record") {
    if (!IsRoot()) {
      LOG(ERROR) << "simpleperf kmem record command needs root privilege";
      return false;
    }
    is_record_ = true;
    size_t i;
    for (i = 1; i < args.size() && !args[i].empty() && args[i][0] == '-'; ++i) {
      if (args[i] == "-g") {
        left_args->push_back("--call-graph");
        left_args->push_back("fp");
      } else if (args[i] == "--slab") {
        use_slab_ = true;
      } else {
        left_args->push_back(args[i]);
      }
    }
    left_args->insert(left_args->end(), args.begin() + i, args.end());
  } else if (args[0] == "report") {
    is_record_ = false;
    for (size_t i = 1; i < args.size(); ++i) {
      if (args[i] == "--children") {
        accumulate_callchain_ = true;
      } else if (args[i] == "-g") {
        print_callgraph_ = true;
        accumulate_callchain_ = true;
        callgraph_show_callee_ = true;
        if (i + 1 < args.size() && args[i + 1][0] != '-') {
          ++i;
          if (args[i] == "callee") {
            callgraph_show_callee_ = true;
          } else if (args[i] == "caller") {
            callgraph_show_callee_ = false;
          } else {
            LOG(ERROR) << "Unknown argument with -g option: " << args[i];
            return false;
          }
        }
      } else if (args[i] == "-i") {
        if (!NextArgumentOrError(args, &i)) {
          return false;
        }
        record_filename_ = args[i];
      } else if (args[i] == "-o") {
        if (!NextArgumentOrError(args, &i)) {
          return false;
        }
        report_filename_ = args[i];
      } else if (args[i] == "--slab") {
        use_slab_ = true;
      } else if (args[i] == "--slab-sort") {
        if (!NextArgumentOrError(args, &i)) {
          return false;
        }
        slab_sort_keys_ = android::base::Split(args[i], ",");
      } else {
        ReportUnknownOption(args, i);
        return false;
      }
    }
  } else {
    LOG(ERROR) << "Unknown subcommand for " << Name() << ": " << args[0]
               << ". Try `simpleperf help " << Name() << "`";
    return false;
  }
  return true;
}

bool KmemCommand::RecordKmemInfo(const std::vector<std::string>& record_args) {
  std::vector<std::string> args;
  if (use_slab_) {
    std::vector<std::string> trace_events = {"kmem:kmalloc",      "kmem:kmem_cache_alloc",
                                             "kmem:kmalloc_node", "kmem:kmem_cache_alloc_node",
                                             "kmem:kfree",        "kmem:kmem_cache_free"};
    for (const auto& name : trace_events) {
      if (ParseEventType(name)) {
        args.insert(args.end(), {"-e", name});
      }
    }
  }
  if (args.empty()) {
    LOG(ERROR) << "Kernel allocation related trace events are not supported.";
    return false;
  }
  args.push_back("-a");
  args.insert(args.end(), record_args.begin(), record_args.end());
  std::unique_ptr<Command> record_cmd = CreateCommandInstance("record");
  if (record_cmd == nullptr) {
    LOG(ERROR) << "record command isn't available";
    return false;
  }
  return record_cmd->Run(args);
}

bool KmemCommand::ReportKmemInfo() {
  if (!PrepareToBuildSampleTree()) {
    return false;
  }
  record_file_reader_ = RecordFileReader::CreateInstance(record_filename_);
  if (record_file_reader_ == nullptr) {
    return false;
  }
  ReadEventAttrsFromRecordFile();
  if (!ReadFeaturesFromRecordFile()) {
    return false;
  }
  if (!ReadSampleTreeFromRecordFile()) {
    return false;
  }
  if (!PrintReport()) {
    return false;
  }
  return true;
}

bool KmemCommand::PrepareToBuildSampleTree() {
  if (use_slab_) {
    if (slab_sort_keys_.empty()) {
      slab_sort_keys_ = {"hit", "caller", "bytes_req", "bytes_alloc", "fragment", "pingpong"};
    }
    SampleComparator<SlabSample> comparator;
    SampleComparator<SlabSample> sort_comparator;
    SampleDisplayer<SlabSample, SlabSampleTree> displayer;
    std::string accumulated_name = accumulate_callchain_ ? "Accumulated_" : "";

    if (print_callgraph_) {
      displayer.AddExclusiveDisplayFunction(SlabSampleCallgraphDisplayer());
    }

    for (const auto& key : slab_sort_keys_) {
      if (key == "hit") {
        sort_comparator.AddCompareFunction(CompareSampleCount);
        displayer.AddDisplayFunction(accumulated_name + "Hit", DisplaySampleCount<SlabSample>);
      } else if (key == "caller") {
        comparator.AddCompareFunction(CompareSymbol);
        displayer.AddDisplayFunction("Caller", DisplaySymbol<SlabSample>);
      } else if (key == "ptr") {
        comparator.AddCompareFunction(ComparePtr);
        displayer.AddDisplayFunction("Ptr", DisplayPtr<SlabSample>);
      } else if (key == "bytes_req") {
        sort_comparator.AddCompareFunction(CompareBytesReq);
        displayer.AddDisplayFunction(accumulated_name + "BytesReq", DisplayBytesReq<SlabSample>);
      } else if (key == "bytes_alloc") {
        sort_comparator.AddCompareFunction(CompareBytesAlloc);
        displayer.AddDisplayFunction(accumulated_name + "BytesAlloc",
                                     DisplayBytesAlloc<SlabSample>);
      } else if (key == "fragment") {
        sort_comparator.AddCompareFunction(CompareFragment);
        displayer.AddDisplayFunction(accumulated_name + "Fragment", DisplayFragment);
      } else if (key == "gfp_flags") {
        comparator.AddCompareFunction(CompareGfpFlags);
        displayer.AddDisplayFunction("GfpFlags", DisplayGfpFlags<SlabSample>);
      } else if (key == "pingpong") {
        sort_comparator.AddCompareFunction(CompareCrossCpuAllocations);
        displayer.AddDisplayFunction("Pingpong", DisplayCrossCpuAllocations<SlabSample>);
      } else {
        LOG(ERROR) << "Unknown sort key for slab allocation: " << key;
        return false;
      }
      slab_sample_tree_builder_.reset(new SlabSampleTreeBuilder(comparator, &thread_tree_));
      slab_sample_tree_builder_->SetCallChainSampleOptions(accumulate_callchain_, print_callgraph_,
                                                           !callgraph_show_callee_);
      sort_comparator.AddComparator(comparator);
      slab_sample_tree_sorter_.reset(new SlabSampleTreeSorter(sort_comparator));
      slab_sample_tree_displayer_.reset(new SlabSampleTreeDisplayer(displayer));
    }
  }
  return true;
}

void KmemCommand::ReadEventAttrsFromRecordFile() {
  for (const EventAttrWithId& attr_with_id : record_file_reader_->AttrSection()) {
    EventAttrWithName attr;
    attr.attr = attr_with_id.attr;
    attr.event_ids = attr_with_id.ids;
    attr.name = GetEventNameByAttr(attr.attr);
    event_attrs_.push_back(attr);
  }
}

bool KmemCommand::ReadFeaturesFromRecordFile() {
  if (!record_file_reader_->LoadBuildIdAndFileFeatures(thread_tree_)) {
    return false;
  }
  std::string arch = record_file_reader_->ReadFeatureString(PerfFileFormat::FEAT_ARCH);
  if (!arch.empty()) {
    record_file_arch_ = GetArchType(arch);
    if (record_file_arch_ == ARCH_UNSUPPORTED) {
      return false;
    }
  }
  std::vector<std::string> cmdline = record_file_reader_->ReadCmdlineFeature();
  if (!cmdline.empty()) {
    record_cmdline_ = android::base::Join(cmdline, ' ');
  }
  if (record_file_reader_->HasFeature(PerfFileFormat::FEAT_TRACING_DATA)) {
    std::vector<char> tracing_data;
    if (!record_file_reader_->ReadFeatureSection(PerfFileFormat::FEAT_TRACING_DATA,
                                                 &tracing_data)) {
      return false;
    }
    ProcessTracingData(tracing_data);
  }
  return true;
}

bool KmemCommand::ReadSampleTreeFromRecordFile() {
  if (!record_file_reader_->ReadDataSection(
          [this](std::unique_ptr<Record> record) { return ProcessRecord(std::move(record)); })) {
    return false;
  }
  if (use_slab_) {
    slab_sample_tree_ = slab_sample_tree_builder_->GetSampleTree();
    slab_sample_tree_sorter_->Sort(slab_sample_tree_.samples, print_callgraph_);
  }
  return true;
}

bool KmemCommand::ProcessRecord(std::unique_ptr<Record> record) {
  thread_tree_.Update(*record);
  if (record->type() == PERF_RECORD_SAMPLE) {
    if (use_slab_) {
      slab_sample_tree_builder_->ProcessSampleRecord(
          *static_cast<const SampleRecord*>(record.get()));
    }
  } else if (record->type() == PERF_RECORD_TRACING_DATA ||
             record->type() == SIMPLE_PERF_RECORD_TRACING_DATA) {
    const auto& r = *static_cast<TracingDataRecord*>(record.get());
    if (!ProcessTracingData(std::vector<char>(r.data, r.data + r.data_size))) {
      return false;
    }
  }
  return true;
}

bool KmemCommand::ProcessTracingData(const std::vector<char>& data) {
  auto tracing = Tracing::Create(data);
  if (!tracing) {
    return false;
  }
  for (auto& attr : event_attrs_) {
    if (attr.attr.type == PERF_TYPE_TRACEPOINT) {
      uint64_t trace_event_id = attr.attr.config;
      attr.name = tracing->GetTracingEventNameHavingId(trace_event_id);
      std::optional<TracingFormat> opt_format = tracing->GetTracingFormatHavingId(trace_event_id);
      if (!opt_format.has_value()) {
        return false;
      }
      const TracingFormat& format = opt_format.value();
      if (use_slab_) {
        if (format.name == "kmalloc" || format.name == "kmem_cache_alloc" ||
            format.name == "kmalloc_node" || format.name == "kmem_cache_alloc_node") {
          SlabFormat f;
          f.type = SlabFormat::KMEM_ALLOC;
          format.GetField("call_site", f.call_site);
          format.GetField("ptr", f.ptr);
          format.GetField("bytes_req", f.bytes_req);
          format.GetField("bytes_alloc", f.bytes_alloc);
          format.GetField("gfp_flags", f.gfp_flags);
          slab_sample_tree_builder_->AddSlabFormat(attr.event_ids, f);
        } else if (format.name == "kfree" || format.name == "kmem_cache_free") {
          SlabFormat f;
          f.type = SlabFormat::KMEM_FREE;
          format.GetField("call_site", f.call_site);
          format.GetField("ptr", f.ptr);
          slab_sample_tree_builder_->AddSlabFormat(attr.event_ids, f);
        }
      }
    }
  }
  return true;
}

bool KmemCommand::PrintReport() {
  std::unique_ptr<FILE, decltype(&fclose)> file_handler(nullptr, fclose);
  FILE* report_fp = stdout;
  if (!report_filename_.empty()) {
    file_handler.reset(fopen(report_filename_.c_str(), "w"));
    if (file_handler == nullptr) {
      PLOG(ERROR) << "failed to open " << report_filename_;
      return false;
    }
    report_fp = file_handler.get();
  }
  PrintReportContext(report_fp);
  if (use_slab_) {
    fprintf(report_fp, "\n\n");
    PrintSlabReportContext(report_fp);
    slab_sample_tree_displayer_->DisplaySamples(report_fp, slab_sample_tree_.samples,
                                                &slab_sample_tree_);
  }
  return true;
}

void KmemCommand::PrintReportContext(FILE* fp) {
  if (!record_cmdline_.empty()) {
    fprintf(fp, "Cmdline: %s\n", record_cmdline_.c_str());
  }
  fprintf(fp, "Arch: %s\n", GetArchString(record_file_arch_).c_str());
  for (const auto& attr : event_attrs_) {
    fprintf(fp, "Event: %s (type %u, config %llu)\n", attr.name.c_str(), attr.attr.type,
            attr.attr.config);
  }
}

void KmemCommand::PrintSlabReportContext(FILE* fp) {
  fprintf(fp, "Slab allocation information:\n");
  fprintf(fp, "Total requested bytes: %" PRIu64 "\n", slab_sample_tree_.total_requested_bytes);
  fprintf(fp, "Total allocated bytes: %" PRIu64 "\n", slab_sample_tree_.total_allocated_bytes);
  uint64_t fragment =
      slab_sample_tree_.total_allocated_bytes - slab_sample_tree_.total_requested_bytes;
  double percentage = 0.0;
  if (slab_sample_tree_.total_allocated_bytes != 0) {
    percentage = 100.0 * fragment / slab_sample_tree_.total_allocated_bytes;
  }
  fprintf(fp, "Total fragment: %" PRIu64 ", %f%%\n", fragment, percentage);
  fprintf(fp, "Total allocations: %" PRIu64 "\n", slab_sample_tree_.nr_allocations);
  fprintf(fp, "Total frees: %" PRIu64 "\n", slab_sample_tree_.nr_frees);
  percentage = 0.0;
  if (slab_sample_tree_.nr_allocations != 0) {
    percentage =
        100.0 * slab_sample_tree_.nr_cross_cpu_allocations / slab_sample_tree_.nr_allocations;
  }
  fprintf(fp, "Total cross cpu allocation/free: %" PRIu64 ", %f%%\n",
          slab_sample_tree_.nr_cross_cpu_allocations, percentage);
  fprintf(fp, "\n");
}

}  // namespace

void RegisterKmemCommand() {
  RegisterCommand("kmem", [] { return std::unique_ptr<Command>(new KmemCommand()); });
}

}  // namespace simpleperf
