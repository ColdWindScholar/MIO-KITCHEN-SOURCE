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

#include "report_utils.h"

#include <stdlib.h>

#include <android-base/parsebool.h>
#include <android-base/scopeguard.h>
#include <android-base/strings.h>

#include "JITDebugReader.h"
#include "RegEx.h"
#include "utils.h"

namespace simpleperf {

bool ProguardMappingRetrace::AddProguardMappingFile(std::string_view mapping_file) {
  // The mapping file format is described in
  // https://www.guardsquare.com/en/products/proguard/manual/retrace.
  // Additional info provided by R8 is described in
  // https://r8.googlesource.com/r8/+/refs/heads/main/doc/retrace.md.
  line_reader_.reset(new LineReader(mapping_file));
  android::base::ScopeGuard g([&]() { line_reader_ = nullptr; });

  if (!line_reader_->Ok()) {
    PLOG(ERROR) << "failed to read " << mapping_file;
    return false;
  }

  MoveToNextLine();
  while (cur_line_.type != LineType::LINE_EOF) {
    if (cur_line_.type == LineType::CLASS_LINE) {
      // Match line "original_classname -> obfuscated_classname:".
      std::string_view s = cur_line_.data;
      auto arrow_pos = s.find(" -> ");
      auto arrow_end_pos = arrow_pos + strlen(" -> ");
      if (auto colon_pos = s.find(':', arrow_end_pos); colon_pos != s.npos) {
        std::string_view original_classname = s.substr(0, arrow_pos);
        std::string obfuscated_classname(s.substr(arrow_end_pos, colon_pos - arrow_end_pos));
        MappingClass& cur_class = class_map_[obfuscated_classname];
        cur_class.original_classname = original_classname;
        MoveToNextLine();
        if (cur_line_.type == LineType::SYNTHESIZED_COMMENT) {
          cur_class.synthesized = true;
          MoveToNextLine();
        }

        while (cur_line_.type == LineType::METHOD_LINE) {
          ParseMethod(cur_class);
        }
        continue;
      }
    }

    // Skip unparsed line.
    MoveToNextLine();
  }
  return true;
}

void ProguardMappingRetrace::ParseMethod(MappingClass& mapping_class) {
  // Match line "... [original_classname.]original_methodname(...)... -> obfuscated_methodname".
  std::string_view s = cur_line_.data;
  auto arrow_pos = s.find(" -> ");
  auto arrow_end_pos = arrow_pos + strlen(" -> ");
  if (auto left_brace_pos = s.rfind('(', arrow_pos); left_brace_pos != s.npos) {
    if (auto space_pos = s.rfind(' ', left_brace_pos); space_pos != s.npos) {
      std::string_view name = s.substr(space_pos + 1, left_brace_pos - space_pos - 1);
      bool contains_classname = name.find('.') != name.npos;
      if (contains_classname && android::base::StartsWith(name, mapping_class.original_classname)) {
        name.remove_prefix(mapping_class.original_classname.size() + 1);
        contains_classname = false;
      }
      std::string original_methodname(name);
      std::string obfuscated_methodname(s.substr(arrow_end_pos));
      bool synthesized = false;

      MoveToNextLine();
      if (cur_line_.type == LineType::SYNTHESIZED_COMMENT) {
        synthesized = true;
        MoveToNextLine();
      }

      auto& method_map = mapping_class.method_map;
      if (auto it = method_map.find(obfuscated_methodname); it != method_map.end()) {
        // The obfuscated method name already exists. We don't know which one to choose.
        // So just prefer the latter one unless it's synthesized.
        if (!synthesized) {
          it->second.original_name = original_methodname;
          it->second.contains_classname = contains_classname;
          it->second.synthesized = synthesized;
        }
      } else {
        auto& method = method_map[obfuscated_methodname];
        method.original_name = original_methodname;
        method.contains_classname = contains_classname;
        method.synthesized = synthesized;
      }
      return;
    }
  }

  // Skip unparsed line.
  MoveToNextLine();
}

void ProguardMappingRetrace::MoveToNextLine() {
  std::string* line;
  while ((line = line_reader_->ReadLine()) != nullptr) {
    std::string_view s = *line;
    if (s.empty()) {
      continue;
    }
    size_t non_space_pos = s.find_first_not_of(' ');
    if (non_space_pos != s.npos && s[non_space_pos] == '#') {
      // Skip all comments unless it's synthesized comment.
      if (s.find("com.android.tools.r8.synthesized") != s.npos) {
        cur_line_.type = SYNTHESIZED_COMMENT;
        cur_line_.data = s;
        return;
      }
      continue;
    }
    if (s.find(" -> ") == s.npos) {
      // Skip unknown lines.
      continue;
    }
    cur_line_.data = s;
    if (s[0] == ' ') {
      cur_line_.type = METHOD_LINE;
    } else {
      cur_line_.type = CLASS_LINE;
    }
    return;
  }
  cur_line_.type = LINE_EOF;
}

bool ProguardMappingRetrace::DeObfuscateJavaMethods(std::string_view obfuscated_name,
                                                    std::string* original_name, bool* synthesized) {
  if (auto split_pos = obfuscated_name.rfind('.'); split_pos != obfuscated_name.npos) {
    std::string obfuscated_classname(obfuscated_name.substr(0, split_pos));

    if (auto it = class_map_.find(obfuscated_classname); it != class_map_.end()) {
      const MappingClass& mapping_class = it->second;
      const auto& method_map = mapping_class.method_map;
      std::string obfuscated_methodname(obfuscated_name.substr(split_pos + 1));

      if (auto method_it = method_map.find(obfuscated_methodname); method_it != method_map.end()) {
        const auto& method = method_it->second;
        if (method.contains_classname) {
          *original_name = method.original_name;
        } else {
          *original_name = mapping_class.original_classname + "." + method.original_name;
        }
        *synthesized = method.synthesized;
      } else {
        // Only the classname is obfuscated.
        *original_name = mapping_class.original_classname + "." + obfuscated_methodname;
        *synthesized = mapping_class.synthesized;
      }
      return true;
    }
  }
  return false;
}

static bool IsArtEntry(const CallChainReportEntry& entry, bool* is_jni_trampoline) {
  if (entry.execution_type == CallChainExecutionType::NATIVE_METHOD) {
    // art_jni_trampoline/art_quick_generic_jni_trampoline are trampolines used to call jni
    // methods in art runtime. We want to hide them when hiding art frames.
    *is_jni_trampoline = android::base::EndsWith(entry.symbol->Name(), "jni_trampoline");
    return *is_jni_trampoline || android::base::EndsWith(entry.dso->Path(), "/libart.so") ||
           android::base::EndsWith(entry.dso->Path(), "/libartd.so");
  }
  return false;
};

CallChainReportModifier::~CallChainReportModifier() {}

// Remove art frames.
class ArtFrameRemover : public CallChainReportModifier {
 public:
  void Modify(std::vector<CallChainReportEntry>& callchain) override {
    auto it =
        std::remove_if(callchain.begin(), callchain.end(), [](const CallChainReportEntry& entry) {
          return entry.execution_type == CallChainExecutionType::ART_METHOD;
        });
    callchain.erase(it, callchain.end());
  }
};

// Convert JIT methods to their corresponding interpreted Java methods.
class JITFrameConverter : public CallChainReportModifier {
 public:
  JITFrameConverter(const ThreadTree& thread_tree) : thread_tree_(thread_tree) {}

  void Modify(std::vector<CallChainReportEntry>& callchain) override {
    CollectJavaMethods();
    for (size_t i = 0; i < callchain.size();) {
      auto& entry = callchain[i];
      if (entry.execution_type == CallChainExecutionType::JIT_JVM_METHOD) {
        // This is a JIT java method, merge it with the interpreted java method having the same
        // name if possible. Otherwise, merge it with other JIT java methods having the same name
        // by assigning a common dso_name.
        if (auto it = java_method_map_.find(std::string(entry.symbol->FunctionName()));
            it != java_method_map_.end()) {
          entry.dso = it->second.dso;
          entry.symbol = it->second.symbol;
          // Not enough info to map an offset in a JIT method to an offset in a dex file. So just
          // use the symbol_addr.
          entry.vaddr_in_file = entry.symbol->addr;

          // ART may call from an interpreted Java method into its corresponding JIT method. To
          // avoid showing the method calling itself, remove the JIT frame.
          if (i + 1 < callchain.size() && callchain[i + 1].dso == entry.dso &&
              callchain[i + 1].symbol == entry.symbol) {
            callchain.erase(callchain.begin() + i);
            continue;
          }

        } else if (!JITDebugReader::IsPathInJITSymFile(entry.dso->Path())) {
          // Old JITSymFiles use names like "TemporaryFile-XXXXXX". So give them a better name.
          entry.dso_name = "[JIT cache]";
        }
      }
      i++;
    }
  }

 private:
  struct JavaMethod {
    Dso* dso;
    const Symbol* symbol;
    JavaMethod(Dso* dso, const Symbol* symbol) : dso(dso), symbol(symbol) {}
  };

  void CollectJavaMethods() {
    if (!java_method_initialized_) {
      java_method_initialized_ = true;
      for (Dso* dso : thread_tree_.GetAllDsos()) {
        if (dso->type() == DSO_DEX_FILE) {
          dso->LoadSymbols();
          for (auto& symbol : dso->GetSymbols()) {
            java_method_map_.emplace(symbol.Name(), JavaMethod(dso, &symbol));
          }
        }
      }
    }
  }

  const ThreadTree& thread_tree_;
  bool java_method_initialized_ = false;
  std::unordered_map<std::string, JavaMethod> java_method_map_;
};

// Use proguard mapping.txt to de-obfuscate minified symbols.
class JavaMethodDeobfuscater : public CallChainReportModifier {
 public:
  JavaMethodDeobfuscater(bool remove_r8_synthesized_frame)
      : remove_r8_synthesized_frame_(remove_r8_synthesized_frame) {}

  bool AddProguardMappingFile(std::string_view mapping_file) {
    return retrace_.AddProguardMappingFile(mapping_file);
  }

  void Modify(std::vector<CallChainReportEntry>& callchain) override {
    for (size_t i = 0; i < callchain.size();) {
      auto& entry = callchain[i];
      if (!IsJavaEntry(entry)) {
        i++;
        continue;
      }
      std::string_view name = entry.symbol->FunctionName();
      std::string original_name;
      bool synthesized;
      if (retrace_.DeObfuscateJavaMethods(name, &original_name, &synthesized)) {
        if (synthesized && remove_r8_synthesized_frame_) {
          callchain.erase(callchain.begin() + i);
          continue;
        }
        entry.symbol->SetDemangledName(original_name);
      }
      i++;
    }
  }

 private:
  bool IsJavaEntry(const CallChainReportEntry& entry) {
    static const char* COMPILED_JAVA_FILE_SUFFIXES[] = {".odex", ".oat", ".dex"};
    if (entry.execution_type == CallChainExecutionType::JIT_JVM_METHOD ||
        entry.execution_type == CallChainExecutionType::INTERPRETED_JVM_METHOD) {
      return true;
    }
    if (entry.execution_type == CallChainExecutionType::NATIVE_METHOD) {
      const std::string& path = entry.dso->Path();
      for (const char* suffix : COMPILED_JAVA_FILE_SUFFIXES) {
        if (android::base::EndsWith(path, suffix)) {
          return true;
        }
      }
    }
    return false;
  }

  const bool remove_r8_synthesized_frame_;
  ProguardMappingRetrace retrace_;
};

// Use regex to filter method names.
class MethodNameFilter : public CallChainReportModifier {
 public:
  bool RemoveMethod(std::string_view method_name_regex) {
    if (auto regex = RegEx::Create(method_name_regex); regex != nullptr) {
      exclude_names_.emplace_back(std::move(regex));
      return true;
    }
    return false;
  }

  void Modify(std::vector<CallChainReportEntry>& callchain) override {
    auto it = std::remove_if(callchain.begin(), callchain.end(),
                             [this](const CallChainReportEntry& entry) {
                               return SearchInRegs(entry.symbol->DemangledName(), exclude_names_);
                             });
    callchain.erase(it, callchain.end());
  }

 private:
  std::vector<std::unique_ptr<RegEx>> exclude_names_;
};

CallChainReportBuilder::CallChainReportBuilder(ThreadTree& thread_tree)
    : thread_tree_(thread_tree) {
  const char* env_name = "REMOVE_R8_SYNTHESIZED_FRAME";
  const char* s = getenv(env_name);
  if (s != nullptr) {
    auto result = android::base::ParseBool(s);
    if (result == android::base::ParseBoolResult::kError) {
      LOG(WARNING) << "invalid value in env variable " << env_name;
    } else if (result == android::base::ParseBoolResult::kTrue) {
      LOG(INFO) << "R8 synthesized frames will be removed.";
      remove_r8_synthesized_frame_ = true;
    }
  }
  SetRemoveArtFrame(true);
  SetConvertJITFrame(true);
}

void CallChainReportBuilder::SetRemoveArtFrame(bool enable) {
  if (enable) {
    art_frame_remover_.reset(new ArtFrameRemover);
  } else {
    art_frame_remover_.reset(nullptr);
  }
}

void CallChainReportBuilder::SetConvertJITFrame(bool enable) {
  if (enable) {
    jit_frame_converter_.reset(new JITFrameConverter(thread_tree_));
  } else {
    jit_frame_converter_.reset(nullptr);
  }
}

bool CallChainReportBuilder::AddProguardMappingFile(std::string_view mapping_file) {
  if (!java_method_deobfuscater_) {
    java_method_deobfuscater_.reset(new JavaMethodDeobfuscater(remove_r8_synthesized_frame_));
  }
  return static_cast<JavaMethodDeobfuscater&>(*java_method_deobfuscater_)
      .AddProguardMappingFile(mapping_file);
}

bool CallChainReportBuilder::RemoveMethod(std::string_view method_name_regex) {
  if (!method_name_filter_) {
    method_name_filter_.reset(new MethodNameFilter);
  }
  return static_cast<MethodNameFilter&>(*method_name_filter_).RemoveMethod(method_name_regex);
}

std::vector<CallChainReportEntry> CallChainReportBuilder::Build(const ThreadEntry* thread,
                                                                const std::vector<uint64_t>& ips,
                                                                size_t kernel_ip_count) {
  std::vector<CallChainReportEntry> result;
  result.reserve(ips.size());
  for (size_t i = 0; i < ips.size(); i++) {
    const MapEntry* map = thread_tree_.FindMap(thread, ips[i], i < kernel_ip_count);
    Dso* dso = map->dso;
    uint64_t vaddr_in_file;
    const Symbol* symbol = thread_tree_.FindSymbol(map, ips[i], &vaddr_in_file, &dso);
    CallChainExecutionType execution_type = CallChainExecutionType::NATIVE_METHOD;
    if (dso->IsForJavaMethod()) {
      if (dso->type() == DSO_DEX_FILE) {
        execution_type = CallChainExecutionType::INTERPRETED_JVM_METHOD;
      } else {
        execution_type = CallChainExecutionType::JIT_JVM_METHOD;
      }
    }
    result.resize(result.size() + 1);
    auto& entry = result.back();
    entry.ip = ips[i];
    entry.symbol = symbol;
    entry.dso = dso;
    entry.vaddr_in_file = vaddr_in_file;
    entry.map = map;
    entry.execution_type = execution_type;
  }
  MarkArtFrame(result);
  if (art_frame_remover_) {
    art_frame_remover_->Modify(result);
  }
  if (jit_frame_converter_) {
    jit_frame_converter_->Modify(result);
  }
  if (java_method_deobfuscater_) {
    java_method_deobfuscater_->Modify(result);
  }
  if (method_name_filter_) {
    method_name_filter_->Modify(result);
  }
  return result;
}

void CallChainReportBuilder::MarkArtFrame(std::vector<CallChainReportEntry>& callchain) {
  // Mark art methods before or after a JVM method.
  bool near_java_method = false;
  bool is_jni_trampoline = false;
  std::vector<size_t> jni_trampoline_positions;
  for (size_t i = 0; i < callchain.size(); ++i) {
    auto& entry = callchain[i];
    if (entry.execution_type == CallChainExecutionType::INTERPRETED_JVM_METHOD ||
        entry.execution_type == CallChainExecutionType::JIT_JVM_METHOD) {
      near_java_method = true;

      // Mark art frames before this entry.
      for (int j = static_cast<int>(i) - 1; j >= 0; j--) {
        if (!IsArtEntry(callchain[j], &is_jni_trampoline)) {
          break;
        }
        callchain[j].execution_type = CallChainExecutionType::ART_METHOD;
        if (is_jni_trampoline) {
          jni_trampoline_positions.push_back(j);
        }
      }
    } else if (near_java_method && IsArtEntry(entry, &is_jni_trampoline)) {
      entry.execution_type = CallChainExecutionType::ART_METHOD;
      if (is_jni_trampoline) {
        jni_trampoline_positions.push_back(i);
      }
    } else {
      near_java_method = false;
    }
  }
  // Functions called by art_jni_trampoline are jni methods. And we don't want to hide them.
  for (auto i : jni_trampoline_positions) {
    if (i > 0 && callchain[i - 1].execution_type == CallChainExecutionType::ART_METHOD) {
      callchain[i - 1].execution_type = CallChainExecutionType::NATIVE_METHOD;
    }
  }
}

bool ThreadReportBuilder::AggregateThreads(const std::vector<std::string>& thread_name_regex) {
  size_t i = thread_regs_.size();
  thread_regs_.resize(i + thread_name_regex.size());
  for (const auto& reg_str : thread_name_regex) {
    std::unique_ptr<RegEx> re = RegEx::Create(reg_str);
    if (!re) {
      return false;
    }
    thread_regs_[i++].re = std::move(re);
  }
  return true;
}

ThreadReport ThreadReportBuilder::Build(const ThreadEntry& thread) {
  ThreadReport report(thread.pid, thread.tid, thread.comm);
  ModifyReportToAggregateThreads(report);
  return report;
}

void ThreadReportBuilder::ModifyReportToAggregateThreads(ThreadReport& report) {
  if (thread_regs_.empty()) {
    // No modification when there are no regular expressions.
    return;
  }
  const std::string thread_name = report.thread_name;
  if (auto it = thread_map_.find(thread_name); it != thread_map_.end()) {
    // Found cached result in thread_map_.
    if (it->second != -1) {
      report = thread_regs_[it->second].report;
    }
    return;
  }
  // Run the slow path to walk through every regular expression.
  size_t index;
  for (index = 0; index < thread_regs_.size(); ++index) {
    if (thread_regs_[index].re->Match(thread_name)) {
      break;
    }
  }
  if (index == thread_regs_.size()) {
    thread_map_[thread_name] = -1;
  } else {
    thread_map_[thread_name] = static_cast<int>(index);
    // Modify thread report.
    auto& aggregated_report = thread_regs_[index].report;
    if (aggregated_report.thread_name == nullptr) {
      // Use regular expression as the name of the aggregated thread. So users know it's an
      // aggregated thread.
      aggregated_report =
          ThreadReport(report.pid, report.tid, thread_regs_[index].re->GetPattern().c_str());
    }
    report = aggregated_report;
  }
}

}  // namespace simpleperf
