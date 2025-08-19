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

#pragma once

#include <inttypes.h>

#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

#include "RegEx.h"
#include "dso.h"
#include "thread_tree.h"
#include "utils.h"

namespace simpleperf {

class ProguardMappingRetrace {
 public:
  // Add proguard mapping.txt to de-obfuscate minified symbols.
  bool AddProguardMappingFile(std::string_view mapping_file);

  bool DeObfuscateJavaMethods(std::string_view obfuscated_name, std::string* original_name,
                              bool* synthesized);

 private:
  struct MappingMethod {
    std::string original_name;
    bool contains_classname;
    bool synthesized;
  };

  struct MappingClass {
    std::string original_classname;
    bool synthesized = false;
    // Map from obfuscated method names to MappingMethod.
    std::unordered_map<std::string, MappingMethod> method_map;
  };

  enum LineType {
    SYNTHESIZED_COMMENT,
    CLASS_LINE,
    METHOD_LINE,
    LINE_EOF,
  };

  struct LineInfo {
    LineType type;
    std::string_view data;
  };

  void ParseMethod(MappingClass& mapping_class);
  void MoveToNextLine();

  // Map from obfuscated class names to ProguardMappingClass.
  std::unordered_map<std::string, MappingClass> class_map_;
  std::unique_ptr<LineReader> line_reader_;
  LineInfo cur_line_;
};

enum class CallChainExecutionType {
  NATIVE_METHOD,
  INTERPRETED_JVM_METHOD,
  JIT_JVM_METHOD,
  // ART methods near interpreted/JIT JVM methods. They're shown only when RemoveArtFrame = false.
  ART_METHOD,
};

struct CallChainReportEntry {
  uint64_t ip = 0;
  const Symbol* symbol = nullptr;
  Dso* dso = nullptr;
  const char* dso_name = nullptr;
  uint64_t vaddr_in_file = 0;
  const MapEntry* map = nullptr;
  CallChainExecutionType execution_type = CallChainExecutionType::NATIVE_METHOD;
};

// a base class for modifying callchain reports
class CallChainReportModifier {
 public:
  virtual ~CallChainReportModifier();

  virtual void Modify(std::vector<CallChainReportEntry>& callchain) = 0;
};

class CallChainReportBuilder {
 public:
  CallChainReportBuilder(ThreadTree& thread_tree);
  // If true, remove interpreter frames both before and after a Java frame.
  // Default is true.
  void SetRemoveArtFrame(bool enable);
  // If true, convert a JIT method into its corresponding interpreted Java method. So they can be
  // merged in reports like flamegraph. Default is true.
  void SetConvertJITFrame(bool enable);
  // Add proguard mapping.txt to de-obfuscate minified symbols.
  bool AddProguardMappingFile(std::string_view mapping_file);
  // Remove methods with name containing the given regular expression.
  bool RemoveMethod(std::string_view method_name_regex);
  std::vector<CallChainReportEntry> Build(const ThreadEntry* thread,
                                          const std::vector<uint64_t>& ips, size_t kernel_ip_count);

 private:
  void MarkArtFrame(std::vector<CallChainReportEntry>& callchain);

  ThreadTree& thread_tree_;
  bool remove_r8_synthesized_frame_ = false;
  std::unique_ptr<CallChainReportModifier> art_frame_remover_;
  std::unique_ptr<CallChainReportModifier> jit_frame_converter_;
  std::unique_ptr<CallChainReportModifier> java_method_deobfuscater_;
  std::unique_ptr<CallChainReportModifier> method_name_filter_;
};

struct ThreadReport {
  int pid;
  int tid;
  const char* thread_name;

  ThreadReport(int pid = 0, int tid = 0, const char* thread_name = nullptr)
      : pid(pid), tid(tid), thread_name(thread_name) {}
};

// Report thread info of a sample.
class ThreadReportBuilder {
 public:
  // Aggregate threads with names matching the same regex.
  bool AggregateThreads(const std::vector<std::string>& thread_name_regex);
  ThreadReport Build(const ThreadEntry& thread);

 private:
  void ModifyReportToAggregateThreads(ThreadReport& report);

  struct ThreadNameRegInfo {
    std::unique_ptr<RegEx> re;
    ThreadReport report;
  };

  std::vector<ThreadNameRegInfo> thread_regs_;
  // Map from thread name to the corresponding index in thread_regs_.
  // Return -1 if the thread name doesn't match any regular expression.
  std::unordered_map<std::string, int> thread_map_;
};

}  // namespace simpleperf
