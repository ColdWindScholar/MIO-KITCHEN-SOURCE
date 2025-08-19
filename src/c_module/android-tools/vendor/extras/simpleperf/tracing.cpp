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

#include "tracing.h"

#include <stdlib.h>
#include <string.h>

#include <map>
#include <optional>
#include <string>
#include <vector>

#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/parseint.h>
#include <android-base/stringprintf.h>
#include <android-base/strings.h>

#include "RegEx.h"
#include "environment.h"
#include "perf_event.h"
#include "utils.h"

using android::base::Split;
using android::base::StartsWith;

namespace simpleperf {

const char TRACING_INFO_MAGIC[10] = {23, 8, 68, 't', 'r', 'a', 'c', 'i', 'n', 'g'};

template <class T>
void AppendData(std::vector<char>& data, const T& s) {
  const char* p = reinterpret_cast<const char*>(&s);
  data.insert(data.end(), p, p + sizeof(T));
}

static void AppendData(std::vector<char>& data, const char* s) {
  data.insert(data.end(), s, s + strlen(s) + 1);
}

template <>
void AppendData(std::vector<char>& data, const std::string& s) {
  data.insert(data.end(), s.c_str(), s.c_str() + s.size() + 1);
}

static void AppendFile(std::vector<char>& data, const std::string& file,
                       uint32_t file_size_bytes = 8) {
  if (file_size_bytes == 8) {
    uint64_t file_size = file.size();
    AppendData(data, file_size);
  } else if (file_size_bytes == 4) {
    uint32_t file_size = file.size();
    AppendData(data, file_size);
  }
  data.insert(data.end(), file.begin(), file.end());
}

static std::string DetachFile(BinaryReader& reader, uint32_t file_size_bytes = 8) {
  if (!reader.CheckLeftSize(file_size_bytes)) {
    return "";
  }
  uint64_t file_size = ConvertBytesToValue(reader.head, file_size_bytes);
  reader.head += file_size_bytes;
  if (!reader.CheckLeftSize(file_size)) {
    return "";
  }
  std::string result(reader.head, file_size);
  reader.head += file_size;
  return result;
}

static bool ReadTraceFsFile(const std::string& path, std::string* content,
                            bool report_error = true) {
  const char* tracefs_dir = GetTraceFsDir();
  if (tracefs_dir == nullptr) {
    if (report_error) {
      LOG(ERROR) << "tracefs doesn't exist";
    }
    return false;
  }
  std::string full_path = tracefs_dir + path;
  if (!android::base::ReadFileToString(full_path, content)) {
    if (report_error) {
      PLOG(ERROR) << "failed to read " << full_path;
    }
    return false;
  }
  return true;
}

struct TraceType {
  std::string system;
  std::string name;
};

class TracingFile {
 public:
  TracingFile();
  bool RecordHeaderFiles();
  void RecordFtraceFiles(const std::vector<TraceType>& trace_types);
  bool RecordEventFiles(const std::vector<TraceType>& trace_types);
  bool RecordKallsymsFile();
  bool RecordPrintkFormatsFile();
  std::vector<char> BinaryFormat() const;
  bool LoadFromBinary(const std::vector<char>& data);
  void Dump(size_t indent) const;
  std::vector<TracingFormat> LoadTracingFormatsFromEventFiles() const;
  const std::string& GetKallsymsFile() const { return kallsyms_file; }
  uint32_t GetPageSize() const { return page_size; }

 private:
  char magic[10];
  std::string version;
  char endian;
  uint8_t size_of_long;
  uint32_t page_size;
  std::string header_page_file;
  std::string header_event_file;

  std::vector<std::string> ftrace_format_files;
  // pair of system, format_file_data.
  std::vector<std::pair<std::string, std::string>> event_format_files;

  std::string kallsyms_file;
  std::string printk_formats_file;
};

TracingFile::TracingFile() {
  memcpy(magic, TRACING_INFO_MAGIC, sizeof(TRACING_INFO_MAGIC));
  version = "0.5";
  endian = 0;
  size_of_long = static_cast<int>(sizeof(long));  // NOLINT(google-runtime-int)
  page_size = static_cast<uint32_t>(simpleperf::GetPageSize());
}

bool TracingFile::RecordHeaderFiles() {
  return ReadTraceFsFile("/events/header_page", &header_page_file) &&
         ReadTraceFsFile("/events/header_event", &header_event_file);
}

void TracingFile::RecordFtraceFiles(const std::vector<TraceType>& trace_types) {
  for (const auto& type : trace_types) {
    std::string format_data;
    if (ReadTraceFsFile("/events/ftrace/" + type.name + "/format", &format_data, false)) {
      ftrace_format_files.emplace_back(std::move(format_data));
    }
  }
}

bool TracingFile::RecordEventFiles(const std::vector<TraceType>& trace_types) {
  for (const auto& type : trace_types) {
    std::string format_data;
    if (!ReadTraceFsFile("/events/" + type.system + "/" + type.name + "/format", &format_data)) {
      return false;
    }
    event_format_files.emplace_back(type.system, std::move(format_data));
  }
  return true;
}

bool TracingFile::RecordPrintkFormatsFile() {
  return ReadTraceFsFile("/printk_formats", &printk_formats_file);
}

std::vector<char> TracingFile::BinaryFormat() const {
  std::vector<char> ret;
  ret.insert(ret.end(), magic, magic + sizeof(magic));
  AppendData(ret, version);
  ret.push_back(endian);
  AppendData(ret, size_of_long);
  AppendData(ret, page_size);
  AppendData(ret, "header_page");
  AppendFile(ret, header_page_file);
  AppendData(ret, "header_event");
  AppendFile(ret, header_event_file);
  int count = static_cast<int>(ftrace_format_files.size());
  AppendData(ret, count);
  for (const auto& format : ftrace_format_files) {
    AppendFile(ret, format);
  }
  count = static_cast<int>(event_format_files.size());
  AppendData(ret, count);
  for (const auto& pair : event_format_files) {
    AppendData(ret, pair.first);
    AppendData(ret, 1);
    AppendFile(ret, pair.second);
  }
  AppendFile(ret, kallsyms_file, 4);
  AppendFile(ret, printk_formats_file, 4);
  return ret;
}

bool TracingFile::LoadFromBinary(const std::vector<char>& data) {
  BinaryReader reader(data.data(), data.size());
  if (!reader.CheckLeftSize(sizeof(magic)) || memcmp(reader.head, magic, sizeof(magic)) != 0) {
    return false;
  }
  reader.head += sizeof(magic);
  version = reader.ReadString();
  reader.Read(endian);
  reader.Read(size_of_long);
  reader.Read(page_size);
  if (reader.ReadString() != "header_page") {
    return false;
  }
  header_page_file = DetachFile(reader);
  if (reader.ReadString() != "header_event") {
    return false;
  }
  header_event_file = DetachFile(reader);
  uint32_t count = 0;
  reader.Read(count);
  ftrace_format_files.clear();
  while (count-- > 0 && !reader.error) {
    ftrace_format_files.emplace_back(DetachFile(reader));
  }
  reader.Read(count);
  event_format_files.clear();
  while (count-- > 0 && !reader.error) {
    std::string system = reader.ReadString();
    uint32_t count_in_system = 0;
    reader.Read(count_in_system);
    while (count_in_system-- > 0 && !reader.error) {
      std::string format = DetachFile(reader);
      event_format_files.push_back(std::make_pair(system, std::move(format)));
    }
  }
  kallsyms_file = DetachFile(reader, 4);
  printk_formats_file = DetachFile(reader, 4);
  return !reader.error && reader.head == reader.end;
}

void TracingFile::Dump(size_t indent) const {
  PrintIndented(indent, "tracing data:\n");
  PrintIndented(indent + 1, "magic: ");
  for (size_t i = 0; i < 3u; ++i) {
    printf("0x%x ", magic[i]);
  }
  for (size_t i = 3; i < sizeof(magic); ++i) {
    printf("%c", magic[i]);
  }
  printf("\n");
  PrintIndented(indent + 1, "version: %s\n", version.c_str());
  PrintIndented(indent + 1, "endian: %d\n", endian);
  PrintIndented(indent + 1, "header_page:\n%s\n\n", header_page_file.c_str());
  PrintIndented(indent + 1, "header_event:\n%s\n\n", header_event_file.c_str());
  for (size_t i = 0; i < ftrace_format_files.size(); ++i) {
    PrintIndented(indent + 1, "ftrace format file %zu/%zu:\n%s\n\n", i + 1,
                  ftrace_format_files.size(), ftrace_format_files[i].c_str());
  }
  for (size_t i = 0; i < event_format_files.size(); ++i) {
    PrintIndented(indent + 1, "event format file %zu/%zu %s:\n%s\n\n", i + 1,
                  event_format_files.size(), event_format_files[i].first.c_str(),
                  event_format_files[i].second.c_str());
  }
  PrintIndented(indent + 1, "kallsyms:\n%s\n\n", kallsyms_file.c_str());
  PrintIndented(indent + 1, "printk_formats:\n%s\n\n", printk_formats_file.c_str());
}

enum class FormatParsingState {
  READ_NAME,
  READ_ID,
  READ_FIELDS,
  READ_PRINTFMT,
};

// Parse lines like: field:char comm[16]; offset:8; size:16;  signed:1;
static std::optional<TracingField> ParseTracingField(const std::string& s) {
  TracingField field;
  std::string name;
  std::string value;
  auto re = RegEx::Create(R"((\w+):(.+?);)");

  std::unique_ptr<RegExMatch> match = re->SearchAll(s);
  while (match->IsValid()) {
    std::string name = match->GetField(1);
    std::string value = match->GetField(2);
    match->MoveToNextMatch();

    if (name == "field") {
      std::string last_value_part = Split(value, " \t").back();

      if (StartsWith(value, "__data_loc char[]")) {
        // Parse value like "__data_loc char[] name".
        field.name = last_value_part;
        field.elem_count = 1;
        field.is_dynamic = true;
      } else if (auto left_bracket_pos = last_value_part.find('[');
                 left_bracket_pos != std::string::npos) {
        // Parse value with brackets like "char comm[16]".
        field.name = last_value_part.substr(0, left_bracket_pos);
        field.elem_count = 1;
        if (size_t right_bracket_pos = last_value_part.find(']', left_bracket_pos);
            right_bracket_pos != std::string::npos) {
          size_t len = right_bracket_pos - left_bracket_pos - 1;
          size_t elem_count;
          // Array size may not be a number, like field:u32 rates[IEEE80211_NUM_BANDS].
          if (android::base::ParseUint(last_value_part.substr(left_bracket_pos + 1, len),
                                       &elem_count) &&
              elem_count > 0) {
            field.elem_count = elem_count;
          }
        }
      } else {
        // Parse value like "int common_pid".
        field.name = last_value_part;
        field.elem_count = 1;
      }
    } else if (name == "offset") {
      if (!android::base::ParseUint(value, &field.offset)) {
        return std::nullopt;
      }
    } else if (name == "size") {
      size_t size;
      if (!android::base::ParseUint(value, &size) || size == 0 || size % field.elem_count != 0) {
        return std::nullopt;
      }
      field.elem_size = size / field.elem_count;
    } else if (name == "signed") {
      int is_signed;
      if (!android::base::ParseInt(value, &is_signed, 0, 1)) {
        return std::nullopt;
      }
      field.is_signed = (is_signed == 1);
    }
  }
  return field;
}

TracingFormat ParseTracingFormat(const std::string& data) {
  TracingFormat format;
  std::vector<std::string> strs = Split(data, "\n");
  FormatParsingState state = FormatParsingState::READ_NAME;
  for (const auto& s : strs) {
    if (state == FormatParsingState::READ_NAME) {
      if (size_t pos = s.find("name:"); pos != std::string::npos) {
        format.name = android::base::Trim(s.substr(pos + strlen("name:")));
        state = FormatParsingState::READ_ID;
      }
    } else if (state == FormatParsingState::READ_ID) {
      if (size_t pos = s.find("ID:"); pos != std::string::npos) {
        format.id = strtoull(s.substr(pos + strlen("ID:")).c_str(), nullptr, 10);
        state = FormatParsingState::READ_FIELDS;
      }
    } else if (state == FormatParsingState::READ_FIELDS) {
      if (size_t pos = s.find("field:"); pos != std::string::npos) {
        // Ignore errors parsing a field. Because it's not critical.
        if (std::optional<TracingField> field = ParseTracingField(s); field.has_value()) {
          format.fields.emplace_back(field.value());
        }
      }
    }
  }
  return format;
}

std::vector<TracingFormat> TracingFile::LoadTracingFormatsFromEventFiles() const {
  std::vector<TracingFormat> formats;
  for (const auto& pair : event_format_files) {
    TracingFormat format = ParseTracingFormat(pair.second);
    format.system_name = pair.first;
    formats.push_back(format);
  }
  return formats;
}

std::unique_ptr<Tracing> Tracing::Create(const std::vector<char>& data) {
  std::unique_ptr<Tracing> tracing(new Tracing);
  if (!tracing->tracing_file_->LoadFromBinary(data)) {
    LOG(ERROR) << "Failed to load tracing data";
    return nullptr;
  }
  return tracing;
}

Tracing::Tracing() : tracing_file_(new TracingFile) {}

Tracing::~Tracing() {}

void Tracing::Dump(size_t indent) {
  tracing_file_->Dump(indent);
}

std::optional<TracingFormat> Tracing::GetTracingFormatHavingId(uint64_t trace_event_id) {
  if (tracing_formats_.empty()) {
    tracing_formats_ = tracing_file_->LoadTracingFormatsFromEventFiles();
  }
  for (const auto& format : tracing_formats_) {
    if (format.id == trace_event_id) {
      return format;
    }
  }
  return std::nullopt;
}

std::string Tracing::GetTracingEventNameHavingId(uint64_t trace_event_id) {
  if (tracing_formats_.empty()) {
    tracing_formats_ = tracing_file_->LoadTracingFormatsFromEventFiles();
  }
  for (const auto& format : tracing_formats_) {
    if (format.id == trace_event_id) {
      return android::base::StringPrintf("%s:%s", format.system_name.c_str(), format.name.c_str());
    }
  }
  return "";
}

const std::string& Tracing::GetKallsyms() const {
  return tracing_file_->GetKallsymsFile();
}

uint32_t Tracing::GetPageSize() const {
  return tracing_file_->GetPageSize();
}

bool GetTracingData(const std::vector<const EventType*>& event_types, std::vector<char>* data) {
  data->clear();
  std::vector<TraceType> trace_types;
  for (const auto& type : event_types) {
    CHECK_EQ(static_cast<uint32_t>(PERF_TYPE_TRACEPOINT), type->type);
    size_t pos = type->name.find(':');
    TraceType trace_type;
    trace_type.system = type->name.substr(0, pos);
    trace_type.name = type->name.substr(pos + 1);
    trace_types.push_back(trace_type);
  }
  TracingFile tracing_file;
  if (!tracing_file.RecordHeaderFiles()) {
    return false;
  }
  tracing_file.RecordFtraceFiles(trace_types);
  if (!tracing_file.RecordEventFiles(trace_types)) {
    return false;
  }
  // Don't record /proc/kallsyms here, as it will be contained in
  // KernelSymbolRecord.
  if (!tracing_file.RecordPrintkFormatsFile()) {
    return false;
  }
  *data = tracing_file.BinaryFormat();
  return true;
}

namespace {

// Briefly check if the filter format is acceptable by the kernel, which is described in
// Documentation/trace/events.rst in the kernel. Also adjust quotes in string operands.
//
// filter := predicate_expr [logical_operator predicate_expr]*
// predicate_expr := predicate | '!' predicate_expr | '(' filter ')'
// predicate := field_name relational_operator value
//
// logical_operator := '&&' | '||'
// relational_operator := numeric_operator | string_operator
// numeric_operator := '==' | '!=' | '<' | '<=' | '>' | '>=' | '&'
// string_operator := '==' | '!=' | '~'
// value := int or string
struct FilterFormatAdjuster {
  FilterFormatAdjuster(bool use_quote) : use_quote(use_quote) {}

  bool MatchFilter(const char*& p) {
    bool ok = MatchPredicateExpr(p);
    while (ok && *p != '\0') {
      RemoveSpace(p);
      if (strncmp(p, "||", 2) == 0 || strncmp(p, "&&", 2) == 0) {
        CopyBytes(p, 2);
        ok = MatchPredicateExpr(p);
      } else {
        break;
      }
    }
    RemoveSpace(p);
    return ok;
  }

  void RemoveSpace(const char*& p) {
    size_t i = 0;
    while (isspace(p[i])) {
      i++;
    }
    if (i > 0) {
      CopyBytes(p, i);
    }
  }

  bool MatchPredicateExpr(const char*& p) {
    RemoveSpace(p);
    if (*p == '!') {
      CopyBytes(p, 1);
      return MatchPredicateExpr(p);
    }
    if (*p == '(') {
      CopyBytes(p, 1);
      bool ok = MatchFilter(p);
      if (!ok) {
        return false;
      }
      RemoveSpace(p);
      if (*p != ')') {
        return false;
      }
      CopyBytes(p, 1);
      return true;
    }
    return MatchPredicate(p);
  }

  bool MatchPredicate(const char*& p) {
    return MatchFieldName(p) && MatchRelationalOperator(p) && MatchValue(p);
  }

  bool MatchFieldName(const char*& p) {
    RemoveSpace(p);
    std::string name;
    for (size_t i = 0; isalnum(p[i]) || p[i] == '_'; i++) {
      name.push_back(p[i]);
    }
    CopyBytes(p, name.size());
    if (name.empty()) {
      return false;
    }
    used_fields.emplace(std::move(name));
    return true;
  }

  bool MatchRelationalOperator(const char*& p) {
    RemoveSpace(p);
    // "==", "!=", "<", "<=", ">", ">=", "&", "~"
    if (*p == '=' || *p == '!' || *p == '<' || *p == '>') {
      if (p[1] == '=') {
        CopyBytes(p, 2);
        return true;
      }
    }
    if (*p == '<' || *p == '>' || *p == '&' || *p == '~') {
      CopyBytes(p, 1);
      return true;
    }
    return false;
  }

  bool MatchValue(const char*& p) {
    RemoveSpace(p);
    // Match a string with quotes.
    if (*p == '\'' || *p == '"') {
      char quote = *p;
      size_t len = 1;
      while (p[len] != quote && p[len] != '\0') {
        len++;
      }
      if (p[len] != quote) {
        return false;
      }
      len++;
      if (use_quote) {
        CopyBytes(p, len);
      } else {
        p++;
        CopyBytes(p, len - 2);
        p++;
      }
      return true;
    }
    // Match an int value.
    char* end;
    errno = 0;
    if (*p == '-') {
      strtoll(p, &end, 0);
    } else {
      strtoull(p, &end, 0);
    }
    if (errno == 0 && end != p) {
      CopyBytes(p, end - p);
      return true;
    }
    // Match a string without quotes, stopping at ), &&, || or space.
    size_t len = 0;
    while (p[len] != '\0' && strchr(")&| \t", p[len]) == nullptr) {
      len++;
    }
    if (len == 0) {
      return false;
    }
    if (use_quote) {
      adjusted_filter += '"';
    }
    CopyBytes(p, len);
    if (use_quote) {
      adjusted_filter += '"';
    }
    return true;
  }

  void CopyBytes(const char*& p, size_t len) {
    adjusted_filter.append(p, len);
    p += len;
  }

  const bool use_quote;
  std::string adjusted_filter;
  FieldNameSet used_fields;
};

}  // namespace

std::optional<std::string> AdjustTracepointFilter(const std::string& filter, bool use_quote,
                                                  FieldNameSet* used_fields) {
  FilterFormatAdjuster adjuster(use_quote);
  const char* p = filter.c_str();
  if (!adjuster.MatchFilter(p) || *p != '\0') {
    LOG(ERROR) << "format error in filter \"" << filter << "\" starting from \"" << p << "\"";
    return std::nullopt;
  }
  *used_fields = std::move(adjuster.used_fields);
  return std::move(adjuster.adjusted_filter);
}

std::optional<FieldNameSet> GetFieldNamesForTracepointEvent(const EventType& event) {
  std::vector<std::string> strs = Split(event.name, ":");
  if (strs.size() != 2) {
    return {};
  }
  std::string data;
  if (!ReadTraceFsFile("/events/" + strs[0] + "/" + strs[1] + "/format", &data, false)) {
    return {};
  }
  TracingFormat format = ParseTracingFormat(data);
  FieldNameSet names;
  for (auto& field : format.fields) {
    names.emplace(std::move(field.name));
  }
  return names;
}

}  // namespace simpleperf
