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

#include <iostream>

#include <android-base/logging.h>
#include <android-base/strings.h>

#ifndef LOG_TAG
#define LOG_TAG "preopt2cachename"
#endif

static const char* kDalvikCacheDir = "/data/dalvik-cache/";
static const char* kOdexCacheSuffix = "@classes.dex";
static const char* kVdexCacheSuffix = "@classes.vdex";
static const char* kArtCacheSuffix = "@classes.art";

// Returns the ISA extracted from the file_location. file_location is formatted like
// /system{/product,}/{priv-,}app/<app_name>/oat/<isa>/<app_name>.{odex,vdex} for all functions. We
// return an empty string "" in error cases.
static std::string ExtractISA(const std::string& file_location) {
  std::vector<std::string> split_file_location = android::base::Split(file_location, "/");
  if (split_file_location.size() <= 1) {
    return "";
  } else if (split_file_location.size() != 7 && split_file_location.size() != 8) {
    LOG(WARNING) << "Unexpected length for file-location. We expected 7 or 8 segments but found "
                 << split_file_location.size() << " for " << file_location;
  }
  return split_file_location[split_file_location.size() - 2];
}

// Returns the apk name extracted from the file_location.
// file_location is formatted like /system/app/<app_name>/oat/<isa>/<app_name>.{odex,vdex}.
// We return the final <app_name> with the .{odex,vdex} replaced with .apk.
static std::string ExtractAPKName(const std::string& file_location) {
  // Find and copy filename.
  size_t file_location_start = file_location.rfind('/');
  if (file_location_start == std::string::npos) {
    return "";
  }
  size_t ext_start = file_location.rfind('.');
  if (ext_start == std::string::npos || ext_start < file_location_start) {
    return "";
  }
  std::string apk_name = file_location.substr(file_location_start + 1,
                                              ext_start - file_location_start);

  // Replace extension with .apk.
  apk_name += "apk";
  return apk_name;
}

// The cache file name is /data/dalvik-cache/<isa>/ prior to this function
static bool SystemBFilenameToCacheFile(const std::string& file_location,
                                       /*in-out*/std::string& cache_file) {
  // Skip the first '/' in file_location.
  size_t initial_position = file_location[0] == '/' ? 1 : 0;
  size_t apk_position = file_location.find("/oat", initial_position);
  if (apk_position == std::string::npos) {
    LOG(ERROR) << "Unable to find oat directory!";
    return false;
  }

  size_t cache_file_position = cache_file.size();
  cache_file += file_location.substr(initial_position, apk_position);
  // '/' -> '@' up to where the apk would be.
  cache_file_position = cache_file.find('/', cache_file_position);
  while (cache_file_position != std::string::npos) {
    cache_file[cache_file_position] = '@';
    cache_file_position = cache_file.find('/', cache_file_position);
  }

  // Add <apk_name>.
  std::string apk_name = ExtractAPKName(file_location);
  if (apk_name.empty()) {
    LOG(ERROR) << "Unable to determine apk name from file name '" << file_location << "'";
    return false;
  }
  std::string::size_type pos = file_location.find_last_of('.');
  if (pos == std::string::npos) {
    LOG(ERROR) << "Invalid file location '" << file_location << "'";
    return false;
  }
  cache_file += apk_name;
  std::string extension(file_location.substr(pos));
  if (extension == ".vdex") {
    cache_file += kVdexCacheSuffix;
  } else if (extension == ".art") {
    cache_file += kArtCacheSuffix;
  } else {
    cache_file += kOdexCacheSuffix;
  }
  return true;
}

// Do the overall transformation from file_location to output_file_location. Prior to this the
// output_file_location is empty.
static bool SystemBFileToCacheFile(const std::string& file_location,
                                   /*out*/std::string& output_file_location) {
  std::string isa = ExtractISA(file_location);
  if (isa.empty()) {
    LOG(ERROR) << "Unable to determine isa for file '" << file_location << "', skipping";
    return false;
  }
  output_file_location += isa;
  output_file_location += '/';
  return SystemBFilenameToCacheFile(file_location, output_file_location);
}

// This program is used to determine where in the /data directory the runtime will search for an
// odex file if it is unable to find one at the given 'preopt-name' location. This is used to allow
// us to store these preopted files in the unused system_b partition and copy them out on first
// boot of the device.
int main(int argc, char *argv[]) {
  if (argc != 2) {
    LOG(ERROR) << "usage: preopt2cachename preopt-location";
    return 2;
  }
  std::string file_location(argv[1]);
  std::string output_file_location(kDalvikCacheDir);
  if (!SystemBFileToCacheFile(file_location, output_file_location)) {
    return 1;
  } else {
    std::cout << output_file_location;
  }
  return 0;
}
