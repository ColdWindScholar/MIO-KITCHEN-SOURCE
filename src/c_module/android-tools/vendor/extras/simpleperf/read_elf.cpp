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

#include "read_elf.h"
#include "read_apk.h"

#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>

#include <algorithm>
#include <limits>

#include <android-base/file.h>
#include <android-base/logging.h>

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wunused-parameter"

#include <llvm/ADT/StringRef.h>
#include <llvm/Object/ELFObjectFile.h>
#include <llvm/Object/ObjectFile.h>

#pragma clang diagnostic pop

#include "JITDebugReader.h"
#include "utils.h"

namespace simpleperf {

const static char* ELF_NOTE_GNU = "GNU";
const static int NT_GNU_BUILD_ID = 3;

std::ostream& operator<<(std::ostream& os, const ElfStatus& status) {
  switch (status) {
    case ElfStatus::NO_ERROR:
      os << "No error";
      break;
    case ElfStatus::FILE_NOT_FOUND:
      os << "File not found";
      break;
    case ElfStatus::READ_FAILED:
      os << "Read failed";
      break;
    case ElfStatus::FILE_MALFORMED:
      os << "Malformed file";
      break;
    case ElfStatus::NO_SYMBOL_TABLE:
      os << "No symbol table";
      break;
    case ElfStatus::NO_BUILD_ID:
      os << "No build id";
      break;
    case ElfStatus::BUILD_ID_MISMATCH:
      os << "Build id mismatch";
      break;
    case ElfStatus::SECTION_NOT_FOUND:
      os << "Section not found";
      break;
  }
  return os;
}

bool IsValidElfFileMagic(const char* buf, size_t buf_size) {
  static const char elf_magic[] = {0x7f, 'E', 'L', 'F'};
  return (buf_size >= 4u && memcmp(buf, elf_magic, 4) == 0);
}

ElfStatus IsValidElfFile(int fd, uint64_t file_offset) {
  char buf[4];
  if (!android::base::ReadFullyAtOffset(fd, buf, 4, file_offset)) {
    return ElfStatus::READ_FAILED;
  }
  return IsValidElfFileMagic(buf, 4) ? ElfStatus::NO_ERROR : ElfStatus::FILE_MALFORMED;
}

bool GetBuildIdFromNoteSection(const char* section, size_t section_size, BuildId* build_id) {
  const char* p = section;
  const char* end = p + section_size;
  while (p < end) {
    if (p + 12 >= end) {
      return false;
    }
    uint32_t namesz;
    uint32_t descsz;
    uint32_t type;
    MoveFromBinaryFormat(namesz, p);
    MoveFromBinaryFormat(descsz, p);
    MoveFromBinaryFormat(type, p);
    namesz = Align(namesz, 4);
    descsz = Align(descsz, 4);
    if ((type == NT_GNU_BUILD_ID) && (p < end) && (strcmp(p, ELF_NOTE_GNU) == 0)) {
      const char* desc_start = p + namesz;
      const char* desc_end = desc_start + descsz;
      if (desc_start > p && desc_start < desc_end && desc_end <= end) {
        *build_id = BuildId(p + namesz, descsz);
        return true;
      } else {
        return false;
      }
    }
    p += namesz + descsz;
  }
  return false;
}

ElfStatus GetBuildIdFromNoteFile(const std::string& filename, BuildId* build_id) {
  std::string content;
  if (!android::base::ReadFileToString(filename, &content)) {
    return ElfStatus::READ_FAILED;
  }
  if (!GetBuildIdFromNoteSection(content.c_str(), content.size(), build_id)) {
    return ElfStatus::NO_BUILD_ID;
  }
  return ElfStatus::NO_ERROR;
}

bool IsArmMappingSymbol(const char* name) {
  // Mapping symbols in arm, which are described in "ELF for ARM Architecture" and
  // "ELF for ARM 64-bit Architecture". The regular expression to match mapping symbol
  // is ^\$(a|d|t|x)(\..*)?$
  return name[0] == '$' && strchr("adtx", name[1]) != nullptr &&
         (name[2] == '\0' || name[2] == '.');
}

namespace {

struct BinaryWrapper {
  std::unique_ptr<llvm::MemoryBuffer> buffer;
  std::unique_ptr<llvm::object::ObjectFile> obj;
};

static ElfStatus OpenObjectFile(const std::string& filename, uint64_t file_offset,
                                uint64_t file_size, BinaryWrapper* wrapper) {
  if (!IsRegularFile(filename)) {
    return ElfStatus::FILE_NOT_FOUND;
  }
  android::base::unique_fd fd = FileHelper::OpenReadOnly(filename);
  if (fd == -1) {
    return ElfStatus::READ_FAILED;
  }
  if (file_size == 0) {
    file_size = GetFileSize(filename);
    if (file_size == 0) {
      return ElfStatus::READ_FAILED;
    }
  }
  ElfStatus status = IsValidElfFile(fd, file_offset);
  if (status != ElfStatus::NO_ERROR) {
    return status;
  }
  auto buffer_or_err = llvm::MemoryBuffer::getFileSlice(filename, file_size, file_offset);
  if (!buffer_or_err) {
    return ElfStatus::READ_FAILED;
  }
  auto obj_or_err =
      llvm::object::ObjectFile::createObjectFile(buffer_or_err.get()->getMemBufferRef());
  if (!obj_or_err) {
    return ElfStatus::READ_FAILED;
  }
  wrapper->buffer = std::move(buffer_or_err.get());
  wrapper->obj = std::move(obj_or_err.get());
  return ElfStatus::NO_ERROR;
}

static ElfStatus OpenObjectFileInMemory(const char* data, size_t size, BinaryWrapper* wrapper) {
  auto buffer = llvm::MemoryBuffer::getMemBuffer(llvm::StringRef(data, size));
  auto obj_or_err = llvm::object::ObjectFile::createObjectFile(buffer->getMemBufferRef());
  if (!obj_or_err) {
    return ElfStatus::FILE_MALFORMED;
  }
  wrapper->buffer = std::move(buffer);
  wrapper->obj = std::move(obj_or_err.get());
  return ElfStatus::NO_ERROR;
}

static inline llvm::Expected<uint32_t> GetSymbolFlags(const llvm::object::ELFSymbolRef& symbol) {
  return symbol.getFlags();
}

static inline llvm::Expected<uint64_t> GetSymbolValue(const llvm::object::ELFSymbolRef& symbol) {
  return symbol.getValue();
}

static inline llvm::Expected<llvm::StringRef> GetSectionName(
    const llvm::object::SectionRef& section) {
  return section.getName();
}

static inline llvm::Expected<llvm::StringRef> GetSectionContents(
    const llvm::object::SectionRef& section) {
  return section.getContents();
}

template <typename ELFT>
static inline const llvm::object::ELFFile<ELFT>* GetELFFile(
    const llvm::object::ELFObjectFile<ELFT>* obj) {
  return &obj->getELFFile();
}

template <typename ELFT>
static inline const typename ELFT::Ehdr& GetELFHeader(const llvm::object::ELFFile<ELFT>* elf) {
  return elf->getHeader();
}

template <typename ELFT>
static inline llvm::Expected<typename ELFT::PhdrRange> GetELFProgramHeaders(
    const llvm::object::ELFFile<ELFT>* elf) {
  return elf->program_headers();
}

template <typename ELFT>
static inline llvm::Expected<llvm::StringRef> GetELFSectionName(
    const llvm::object::ELFFile<ELFT>* elf, const typename ELFT::Shdr& section_header) {
  return elf->getSectionName(section_header);
}

void ReadSymbolTable(llvm::object::symbol_iterator sym_begin, llvm::object::symbol_iterator sym_end,
                     const std::function<void(const ElfFileSymbol&)>& callback, bool is_arm,
                     const llvm::object::section_iterator& section_end) {
  for (; sym_begin != sym_end; ++sym_begin) {
    ElfFileSymbol symbol;
    auto symbol_ref = static_cast<const llvm::object::ELFSymbolRef*>(&*sym_begin);
    // Exclude undefined symbols, otherwise we may wrongly use them as labels in functions.
    if (auto flags = GetSymbolFlags(*symbol_ref);
        !flags || (flags.get() & symbol_ref->SF_Undefined)) {
      continue;
    }
    llvm::Expected<llvm::object::section_iterator> section_it_or_err = symbol_ref->getSection();
    if (!section_it_or_err) {
      continue;
    }
    // Symbols in .dynsym section don't have associated section.
    if (section_it_or_err.get() != section_end) {
      llvm::Expected<llvm::StringRef> section_name = GetSectionName(*section_it_or_err.get());
      if (!section_name || section_name.get().empty()) {
        continue;
      }
      if (section_name.get() == ".text") {
        symbol.is_in_text_section = true;
      }
    }

    llvm::Expected<llvm::StringRef> symbol_name_or_err = symbol_ref->getName();
    if (!symbol_name_or_err || symbol_name_or_err.get().empty()) {
      continue;
    }

    symbol.name = symbol_name_or_err.get();
    llvm::Expected<uint64_t> symbol_value = GetSymbolValue(*symbol_ref);
    if (!symbol_value) {
      continue;
    }
    symbol.vaddr = symbol_value.get();
    if ((symbol.vaddr & 1) != 0 && is_arm) {
      // Arm sets bit 0 to mark it as thumb code, remove the flag.
      symbol.vaddr &= ~1;
    }
    symbol.len = symbol_ref->getSize();
    llvm::object::SymbolRef::Type symbol_type = *symbol_ref->getType();
    if (symbol_type == llvm::object::SymbolRef::ST_Function) {
      symbol.is_func = true;
    } else if (symbol_type == llvm::object::SymbolRef::ST_Unknown) {
      if (symbol.is_in_text_section) {
        symbol.is_label = true;
        if (is_arm) {
          // Remove mapping symbols in arm.
          const char* p = (symbol.name.compare(0, linker_prefix.size(), linker_prefix) == 0)
                              ? symbol.name.c_str() + linker_prefix.size()
                              : symbol.name.c_str();
          if (IsArmMappingSymbol(p)) {
            symbol.is_label = false;
          }
        }
      }
    }

    callback(symbol);
  }
}

template <class ELFT>
void AddSymbolForPltSection(const llvm::object::ELFObjectFile<ELFT>* elf,
                            const std::function<void(const ElfFileSymbol&)>& callback) {
  // We may sample instructions in .plt section if the program
  // calls functions from shared libraries. Different architectures use
  // different formats to store .plt section, so it needs a lot of work to match
  // instructions in .plt section to symbols. As samples in .plt section rarely
  // happen, and .plt section can hardly be a performance bottleneck, we can
  // just use a symbol @plt to represent instructions in .plt section.
  for (auto it = elf->section_begin(); it != elf->section_end(); ++it) {
    const llvm::object::ELFSectionRef& section_ref = *it;
    llvm::Expected<llvm::StringRef> section_name = GetSectionName(section_ref);
    if (!section_name || section_name.get() != ".plt") {
      continue;
    }
    const auto* shdr = elf->getSection(section_ref.getRawDataRefImpl());
    if (shdr == nullptr) {
      return;
    }
    ElfFileSymbol symbol;
    symbol.vaddr = shdr->sh_addr;
    symbol.len = shdr->sh_size;
    symbol.is_func = true;
    symbol.is_label = true;
    symbol.is_in_text_section = true;
    symbol.name = "@plt";
    callback(symbol);
    return;
  }
}

template <class ELFT>
void CheckSymbolSections(const llvm::object::ELFObjectFile<ELFT>* elf, bool* has_symtab,
                         bool* has_dynsym) {
  *has_symtab = false;
  *has_dynsym = false;
  for (auto it = elf->section_begin(); it != elf->section_end(); ++it) {
    const llvm::object::ELFSectionRef& section_ref = *it;
    llvm::Expected<llvm::StringRef> section_name = GetSectionName(section_ref);
    if (!section_name) {
      continue;
    }
    if (section_name.get() == ".dynsym") {
      *has_dynsym = true;
    } else if (section_name.get() == ".symtab") {
      *has_symtab = true;
    }
  }
}

template <typename T>
class ElfFileImpl {};

template <typename ELFT>
class ElfFileImpl<llvm::object::ELFObjectFile<ELFT>> : public ElfFile {
 public:
  ElfFileImpl(BinaryWrapper&& wrapper, const llvm::object::ELFObjectFile<ELFT>* elf_obj)
      : wrapper_(std::move(wrapper)), elf_obj_(elf_obj), elf_(GetELFFile(elf_obj_)) {}

  bool Is64Bit() override { return GetELFHeader(elf_).getFileClass() == llvm::ELF::ELFCLASS64; }

  llvm::MemoryBuffer* GetMemoryBuffer() override { return wrapper_.buffer.get(); }

  std::vector<ElfSegment> GetProgramHeader() override {
    auto program_headers = GetELFProgramHeaders(elf_);
    if (!program_headers) {
      return {};
    }
    std::vector<ElfSegment> segments(program_headers.get().size());
    for (size_t i = 0; i < program_headers.get().size(); i++) {
      const auto& phdr = program_headers.get()[i];
      segments[i].vaddr = phdr.p_vaddr;
      segments[i].file_offset = phdr.p_offset;
      segments[i].file_size = phdr.p_filesz;
      segments[i].is_executable =
          (phdr.p_type == llvm::ELF::PT_LOAD) && (phdr.p_flags & llvm::ELF::PF_X);
      segments[i].is_load = (phdr.p_type == llvm::ELF::PT_LOAD);
    }
    return segments;
  }

  std::vector<ElfSection> GetSectionHeader() override {
    auto section_headers_or_err = elf_->sections();
    if (!section_headers_or_err) {
      return {};
    }
    const auto& section_headers = section_headers_or_err.get();
    std::vector<ElfSection> sections(section_headers.size());
    for (size_t i = 0; i < section_headers.size(); i++) {
      const auto& shdr = section_headers[i];
      if (auto name = GetELFSectionName(elf_, shdr); name) {
        sections[i].name = name.get();
      }
      sections[i].vaddr = shdr.sh_addr;
      sections[i].file_offset = shdr.sh_offset;
      sections[i].size = shdr.sh_size;
    }
    return sections;
  }

  ElfStatus GetBuildId(BuildId* build_id) override {
    llvm::StringRef data = elf_obj_->getData();
    const char* binary_start = data.data();
    const char* binary_end = data.data() + data.size();
    for (auto it = elf_obj_->section_begin(); it != elf_obj_->section_end(); ++it) {
      const llvm::object::ELFSectionRef& section_ref = *it;
      if (section_ref.getType() == llvm::ELF::SHT_NOTE) {
        llvm::Expected<llvm::StringRef> content = GetSectionContents(section_ref);
        if (!content) {
          return ElfStatus::NO_BUILD_ID;
        }
        const llvm::StringRef& data = content.get();
        if (data.data() < binary_start || data.data() + data.size() > binary_end) {
          return ElfStatus::NO_BUILD_ID;
        }
        if (GetBuildIdFromNoteSection(data.data(), data.size(), build_id)) {
          return ElfStatus::NO_ERROR;
        }
      }
    }
    return ElfStatus::NO_BUILD_ID;
  }

  ElfStatus ParseSymbols(const ParseSymbolCallback& callback) override {
    auto machine = GetELFHeader(elf_).e_machine;
    bool is_arm = (machine == llvm::ELF::EM_ARM || machine == llvm::ELF::EM_AARCH64);
    AddSymbolForPltSection(elf_obj_, callback);
    // Some applications deliberately ship elf files with broken section tables.
    // So check the existence of .symtab section and .dynsym section before reading symbols.
    bool has_symtab;
    bool has_dynsym;
    CheckSymbolSections(elf_obj_, &has_symtab, &has_dynsym);
    if (has_symtab && elf_obj_->symbol_begin() != elf_obj_->symbol_end()) {
      ReadSymbolTable(elf_obj_->symbol_begin(), elf_obj_->symbol_end(), callback, is_arm,
                      elf_obj_->section_end());
      return ElfStatus::NO_ERROR;
    } else if (has_dynsym && elf_obj_->dynamic_symbol_begin()->getRawDataRefImpl() !=
                                 llvm::object::DataRefImpl()) {
      ReadSymbolTable(elf_obj_->dynamic_symbol_begin(), elf_obj_->dynamic_symbol_end(), callback,
                      is_arm, elf_obj_->section_end());
    }
    std::string debugdata;
    ElfStatus result = ReadSection(".gnu_debugdata", &debugdata);
    if (result == ElfStatus::SECTION_NOT_FOUND) {
      return ElfStatus::NO_SYMBOL_TABLE;
    } else if (result == ElfStatus::NO_ERROR) {
      std::string decompressed_data;
      if (XzDecompress(debugdata, &decompressed_data)) {
        auto debugdata_elf =
            ElfFile::Open(decompressed_data.data(), decompressed_data.size(), &result);
        if (debugdata_elf) {
          return debugdata_elf->ParseSymbols(callback);
        }
      }
    }
    return result;
  }

  void ParseDynamicSymbols(const ParseSymbolCallback& callback) override {
    auto machine = GetELFHeader(elf_).e_machine;
    bool is_arm = (machine == llvm::ELF::EM_ARM || machine == llvm::ELF::EM_AARCH64);
    ReadSymbolTable(elf_obj_->dynamic_symbol_begin(), elf_obj_->dynamic_symbol_end(), callback,
                    is_arm, elf_obj_->section_end());
  }

  ElfStatus ReadSection(const std::string& section_name, std::string* content) override {
    for (llvm::object::section_iterator it = elf_obj_->section_begin();
         it != elf_obj_->section_end(); ++it) {
      llvm::Expected<llvm::StringRef> name = GetSectionName(*it);
      if (!name || name.get() != section_name) {
        continue;
      }
      llvm::Expected<llvm::StringRef> data = GetSectionContents(*it);
      if (!data) {
        return ElfStatus::READ_FAILED;
      }
      *content = data.get();
      return ElfStatus::NO_ERROR;
    }
    return ElfStatus::SECTION_NOT_FOUND;
  }

  uint64_t ReadMinExecutableVaddr(uint64_t* file_offset) {
    bool has_vaddr = false;
    uint64_t min_addr = std::numeric_limits<uint64_t>::max();
    auto program_headers = GetELFProgramHeaders(elf_);
    if (program_headers) {
      for (const auto& ph : program_headers.get()) {
        if ((ph.p_type == llvm::ELF::PT_LOAD) && (ph.p_flags & llvm::ELF::PF_X) &&
            (ph.p_vaddr < min_addr)) {
          min_addr = ph.p_vaddr;
          *file_offset = ph.p_offset;
          has_vaddr = true;
        }
      }
    }
    if (!has_vaddr) {
      // JIT symfiles don't have program headers.
      min_addr = 0;
      *file_offset = 0;
    }
    return min_addr;
  }

  bool VaddrToOff(uint64_t vaddr, uint64_t* file_offset) override {
    auto program_headers = GetELFProgramHeaders(elf_);
    if (!program_headers) {
      return false;
    }
    for (const auto& ph : program_headers.get()) {
      if (ph.p_type == llvm::ELF::PT_LOAD && vaddr >= ph.p_vaddr &&
          vaddr < ph.p_vaddr + ph.p_filesz) {
        *file_offset = vaddr - ph.p_vaddr + ph.p_offset;
        return true;
      }
    }
    return false;
  }

 private:
  BinaryWrapper wrapper_;
  const llvm::object::ELFObjectFile<ELFT>* elf_obj_;
  const llvm::object::ELFFile<ELFT>* elf_;
};

std::unique_ptr<ElfFile> CreateElfFileImpl(BinaryWrapper&& wrapper, ElfStatus* status) {
  if (auto obj = llvm::dyn_cast<llvm::object::ELF32LEObjectFile>(wrapper.obj.get())) {
    return std::unique_ptr<ElfFile>(
        new ElfFileImpl<llvm::object::ELF32LEObjectFile>(std::move(wrapper), obj));
  }
  if (auto obj = llvm::dyn_cast<llvm::object::ELF64LEObjectFile>(wrapper.obj.get())) {
    return std::unique_ptr<ElfFile>(
        new ElfFileImpl<llvm::object::ELF64LEObjectFile>(std::move(wrapper), obj));
  }
  *status = ElfStatus::FILE_MALFORMED;
  return nullptr;
}

}  // namespace

std::unique_ptr<ElfFile> ElfFile::Open(const std::string& filename) {
  ElfStatus status;
  auto elf = Open(filename, &status);
  if (!elf) {
    LOG(ERROR) << "failed to open " << filename << ": " << status;
  }
  return elf;
}

std::unique_ptr<ElfFile> ElfFile::Open(const std::string& filename,
                                       const BuildId* expected_build_id, ElfStatus* status) {
  BinaryWrapper wrapper;
  auto tuple = SplitUrlInApk(filename);
  if (std::get<0>(tuple)) {
    EmbeddedElf* elf = ApkInspector::FindElfInApkByName(std::get<1>(tuple), std::get<2>(tuple));
    if (elf == nullptr) {
      *status = ElfStatus::FILE_NOT_FOUND;
    } else {
      *status = OpenObjectFile(elf->filepath(), elf->entry_offset(), elf->entry_size(), &wrapper);
    }
  } else if (JITDebugReader::IsPathInJITSymFile(filename)) {
    size_t colon_pos = filename.rfind(':');
    CHECK_NE(colon_pos, std::string::npos);
    // path generated by JITDebugReader: app_jit_cache:<file_start>-<file_end>
    uint64_t file_start;
    uint64_t file_end;
    if (sscanf(filename.data() + colon_pos, ":%" PRIu64 "-%" PRIu64, &file_start, &file_end) != 2) {
      *status = ElfStatus::FILE_NOT_FOUND;
      return nullptr;
    }
    *status =
        OpenObjectFile(filename.substr(0, colon_pos), file_start, file_end - file_start, &wrapper);
  } else {
    *status = OpenObjectFile(filename, 0, 0, &wrapper);
  }
  if (*status != ElfStatus::NO_ERROR) {
    return nullptr;
  }
  auto elf = CreateElfFileImpl(std::move(wrapper), status);
  if (elf && expected_build_id != nullptr && !expected_build_id->IsEmpty()) {
    BuildId real_build_id;
    *status = elf->GetBuildId(&real_build_id);
    if (*status != ElfStatus::NO_ERROR) {
      return nullptr;
    }
    if (*expected_build_id != real_build_id) {
      *status = ElfStatus::BUILD_ID_MISMATCH;
      return nullptr;
    }
  }
  return elf;
}

std::unique_ptr<ElfFile> ElfFile::Open(const char* data, size_t size, ElfStatus* status) {
  BinaryWrapper wrapper;
  *status = OpenObjectFileInMemory(data, size, &wrapper);
  if (*status != ElfStatus::NO_ERROR) {
    return nullptr;
  }
  return CreateElfFileImpl(std::move(wrapper), status);
}

}  // namespace simpleperf

// LLVM libraries uses ncurses library, but that isn't needed by simpleperf.
// So support a naive implementation to avoid depending on ncurses.
__attribute__((weak)) extern "C" int setupterm(char*, int, int*) {
  return -1;
}

__attribute__((weak)) extern "C" struct term* set_curterm(struct term*) {
  return nullptr;
}

__attribute__((weak)) extern "C" int del_curterm(struct term*) {
  return -1;
}

__attribute__((weak)) extern "C" int tigetnum(char*) {
  return -1;
}
