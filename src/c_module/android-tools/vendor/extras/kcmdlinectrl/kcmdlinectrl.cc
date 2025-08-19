/*
 * Copyright (C) 2022 The Android Open Source Project
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

#include <getopt.h>
#include <unistd.h>

#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/properties.h>
#include <android-base/strings.h>
#include <android-base/unique_fd.h>
#include <bootloader_message/bootloader_message.h>

#include <functional>
#include <iostream>

void PrintUsage(const char* progname) {
  std::cerr << "USAGE: " << progname << " get [PROPERTY]" << std::endl;
  std::cerr << "       " << progname << " store [PROPERTY] [VALUE]" << std::endl;
  std::cerr << "       " << progname << " update-props" << std::endl;
}

int UpdateProps() {
  misc_kcmdline_message m = {.version = MISC_KCMDLINE_MESSAGE_VERSION,
                             .magic = MISC_KCMDLINE_MAGIC_HEADER};
  std::string err;
  if (!ReadMiscKcmdlineMessage(&m, &err)) {
    LOG(ERROR) << "Failed to read from misc: " << err;
    return 1;
  }

  // If invalid, treat it as-if all flags are zero.
  if (m.magic != MISC_KCMDLINE_MAGIC_HEADER || m.version != MISC_KCMDLINE_MESSAGE_VERSION) {
    m = {.version = MISC_KCMDLINE_MESSAGE_VERSION,
         .magic = MISC_KCMDLINE_MAGIC_HEADER,
         .kcmdline_flags = 0};
  }

  bool use_rust_binder = (m.kcmdline_flags & MISC_KCMDLINE_BINDER_RUST) != 0;
  android::base::SetProperty("kcmdline.binder", use_rust_binder ? "rust" : "c");

  android::base::SetProperty("kcmdline.loaded", "1");
  return 0;
}

int PrintProperty(const char* property_name) {
  misc_kcmdline_message m = {.version = MISC_KCMDLINE_MESSAGE_VERSION,
                             .magic = MISC_KCMDLINE_MAGIC_HEADER};

  std::string err;
  if (!ReadMiscKcmdlineMessage(&m, &err)) {
    LOG(ERROR) << "Failed to read from misc: " << err;
    return 1;
  }

  if (m.magic != MISC_KCMDLINE_MAGIC_HEADER || m.version != MISC_KCMDLINE_MESSAGE_VERSION) {
    std::cout << "kcmdline message is invalid, treating all flags as zero" << std::endl;
    m = {.version = MISC_KCMDLINE_MESSAGE_VERSION,
         .magic = MISC_KCMDLINE_MAGIC_HEADER,
         .kcmdline_flags = 0};
  }

  if (!strcmp(property_name, "binder")) {
    bool use_rust_binder = (m.kcmdline_flags & MISC_KCMDLINE_BINDER_RUST) != 0;
    const char* binder_value = use_rust_binder ? "rust" : "c";
    std::cout << "binder=" << binder_value << std::endl;
    return 0;
  } else {
    LOG(ERROR) << "Unknown property name: " << property_name;
    return 1;
  }
}

int StoreProperty(const char* property_name, const char* new_value) {
  misc_kcmdline_message m = {.version = MISC_KCMDLINE_MESSAGE_VERSION,
                             .magic = MISC_KCMDLINE_MAGIC_HEADER};

  std::string err;
  if (!ReadMiscKcmdlineMessage(&m, &err)) {
    LOG(ERROR) << "Failed to read from misc: " << err;
    return 1;
  }

  if (m.magic != MISC_KCMDLINE_MAGIC_HEADER || m.version != MISC_KCMDLINE_MESSAGE_VERSION) {
    std::cout << "kcmdline message is invalid, resetting it" << std::endl;
    m = {.version = MISC_KCMDLINE_MESSAGE_VERSION,
         .magic = MISC_KCMDLINE_MAGIC_HEADER,
         .kcmdline_flags = 0};
  }

  if (!strcmp(property_name, "binder")) {
    if (!strcmp(new_value, "rust")) {
      m.kcmdline_flags |= MISC_KCMDLINE_BINDER_RUST;
    } else if (!strcmp(new_value, "c")) {
      m.kcmdline_flags &= !MISC_KCMDLINE_BINDER_RUST;
    } else {
      LOG(ERROR) << "Binder property can only be 'c' or 'rust', but got " << new_value;
      return 1;
    }
  } else {
    LOG(ERROR) << "Unknown property name: " << property_name;
    return 1;
  }

  if (!WriteMiscKcmdlineMessage(m, &err)) {
    LOG(ERROR) << "Failed to write to misc: " << err;
    return 1;
  }

  return 0;
}

int main(int argc, char** argv) {
  char *action, *property_name, *new_value;

  if (argc == 2) {
    action = argv[1];
    property_name = NULL;
    new_value = NULL;
  } else if (argc == 3) {
    action = argv[1];
    property_name = argv[2];
    new_value = NULL;
  } else if (argc == 4) {
    action = argv[1];
    property_name = argv[2];
    new_value = argv[3];
  } else {
    PrintUsage(*argv);
    return 1;
  }

  if (!strcmp(action, "update-props") && property_name == NULL) {
    return UpdateProps();
  } else if (!strcmp(action, "get") && property_name != NULL && new_value == NULL) {
    return PrintProperty(property_name);
  } else if (!strcmp(action, "store") && property_name != NULL && new_value != NULL) {
    return StoreProperty(property_name, new_value);
  } else {
    PrintUsage(*argv);
    return 1;
  }
}
