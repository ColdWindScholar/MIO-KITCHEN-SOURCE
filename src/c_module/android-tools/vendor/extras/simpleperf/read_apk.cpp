/*
**
** Copyright 2016, The Android Open Source Project
**
** Licensed under the Apache License, Version 2.0 (the "License");
** you may not use this file except in compliance with the License.
** You may obtain a copy of the License at
**
**     http://www.apache.org/licenses/LICENSE-2.0
**
** Unless required by applicable law or agreed to in writing, software
** distributed under the License is distributed on an "AS IS" BASIS,
** WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
** See the License for the specific language governing permissions and
** limitations under the License.
*/

#include "read_apk.h"

#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#include <memory>

#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/strings.h>
#include <ziparchive/zip_archive.h>
#include "read_elf.h"
#include "utils.h"

namespace simpleperf {

std::unordered_map<std::string, ApkInspector::ApkNode> ApkInspector::embedded_elf_cache_;

EmbeddedElf* ApkInspector::FindElfInApkByOffset(const std::string& apk_path, uint64_t file_offset) {
  // Already in cache?
  ApkNode& node = embedded_elf_cache_[apk_path];
  auto it = node.offset_map.find(file_offset);
  if (it != node.offset_map.end()) {
    return it->second.get();
  }
  std::unique_ptr<EmbeddedElf> elf = FindElfInApkByOffsetWithoutCache(apk_path, file_offset);
  EmbeddedElf* result = elf.get();
  node.offset_map[file_offset] = std::move(elf);
  if (result != nullptr) {
    node.name_map[result->entry_name()] = result;
  }
  return result;
}

EmbeddedElf* ApkInspector::FindElfInApkByName(const std::string& apk_path,
                                              const std::string& entry_name) {
  ApkNode& node = embedded_elf_cache_[apk_path];
  auto it = node.name_map.find(entry_name);
  if (it != node.name_map.end()) {
    return it->second;
  }
  std::unique_ptr<EmbeddedElf> elf = FindElfInApkByNameWithoutCache(apk_path, entry_name);
  EmbeddedElf* result = elf.get();
  node.name_map[entry_name] = result;
  if (result != nullptr) {
    node.offset_map[result->entry_offset()] = std::move(elf);
  }
  return result;
}

std::unique_ptr<EmbeddedElf> ApkInspector::FindElfInApkByOffsetWithoutCache(
    const std::string& apk_path, uint64_t file_offset) {
  std::unique_ptr<ArchiveHelper> ahelper = ArchiveHelper::CreateInstance(apk_path);
  if (!ahelper) {
    return nullptr;
  }

  // Iterate through the zip file. Look for a zip entry corresponding
  // to an uncompressed blob whose range intersects with the mmap
  // offset we're interested in.
  bool found = false;
  ZipEntry found_entry;
  std::string found_entry_name;
  bool result = ahelper->IterateEntries([&](ZipEntry& entry, const std::string& name) {
    if (entry.method == kCompressStored && file_offset >= static_cast<uint64_t>(entry.offset) &&
        file_offset < static_cast<uint64_t>(entry.offset) + entry.uncompressed_length) {
      found = true;
      found_entry = entry;
      found_entry_name = name;
      return false;
    }
    return true;
  });
  if (!result || !found) {
    return nullptr;
  }

  // We found something in the zip file at the right spot. Is it an ELF?
  if (IsValidElfFile(ahelper->GetFd(), found_entry.offset) != ElfStatus::NO_ERROR) {
    // Omit files that are not ELF files.
    return nullptr;
  }
  return std::unique_ptr<EmbeddedElf>(new EmbeddedElf(
      apk_path, found_entry_name, found_entry.offset, found_entry.uncompressed_length));
}

std::unique_ptr<EmbeddedElf> ApkInspector::FindElfInApkByNameWithoutCache(
    const std::string& apk_path, const std::string& entry_name) {
  std::unique_ptr<ArchiveHelper> ahelper = ArchiveHelper::CreateInstance(apk_path);
  if (!ahelper) {
    return nullptr;
  }
  ZipEntry zentry;
  if (!ahelper->FindEntry(entry_name, &zentry)) {
    return nullptr;
  }
  if (zentry.method != kCompressStored || zentry.compressed_length != zentry.uncompressed_length) {
    return nullptr;
  }
  return std::unique_ptr<EmbeddedElf>(
      new EmbeddedElf(apk_path, entry_name, zentry.offset, zentry.uncompressed_length));
}

// Refer file in apk in compliance with
// http://developer.android.com/reference/java/net/JarURLConnection.html.
std::string GetUrlInApk(const std::string& apk_path, const std::string& elf_filename) {
  return apk_path + "!/" + elf_filename;
}

std::tuple<bool, std::string, std::string> SplitUrlInApk(const std::string& path) {
  size_t pos = path.find("!/");
  if (pos == std::string::npos) {
    return std::make_tuple(false, "", "");
  }
  return std::make_tuple(true, path.substr(0, pos), path.substr(pos + 2));
}

// Parse path like "[anon:dalvik-classes.dex extracted in memory from /..base.apk] (deleted)",
// or "/dev/ashmem/dalvik-classes.dex extracted in memory from /..base.apk (deleted)" on Android P.
bool ParseExtractedInMemoryPath(const std::string& path, std::string* zip_path,
                                std::string* entry_name) {
  const char* prefixes[2] = {"[anon:dalvik-", "/dev/ashmem/dalvik-"};
  const char* key = " extracted in memory from ";
  size_t pos = path.find(key);
  if (pos != std::string::npos) {
    for (const char* prefix : prefixes) {
      if (android::base::StartsWith(path, prefix)) {
        size_t entry_name_start = strlen(prefix);
        size_t entry_name_end = pos;
        size_t zip_path_start = pos + strlen(key);
        size_t zip_path_end = path.find_first_of(" ]", zip_path_start);
        if (zip_path_end == std::string::npos) {
          zip_path_end = path.size();
        }
        if (entry_name_start < entry_name_end && zip_path_start < zip_path_end) {
          *entry_name = path.substr(entry_name_start, entry_name_end - entry_name_start);
          *zip_path = path.substr(zip_path_start, zip_path_end - zip_path_start);
          size_t multidex_separator_pos = zip_path->find('!');
          if (multidex_separator_pos != std::string::npos) {
            zip_path->resize(multidex_separator_pos);
          }
          return true;
        }
      }
    }
  }
  return false;
}

}  // namespace simpleperf
