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

#ifndef _FSCRYPT_H_
#define _FSCRYPT_H_

#include <string>

bool IsFbeEnabled();

static const char* fscrypt_unencrypted_folder = "/unencrypted";
static const char* fscrypt_key_ref = "/unencrypted/ref";
static const char* fscrypt_key_per_boot_ref = "/unencrypted/per_boot_ref";
static const char* fscrypt_key_mode = "/unencrypted/mode";

namespace android {
namespace fscrypt {

struct EncryptionOptions {
    int version;
    int contents_mode;
    int filenames_mode;
    int flags;
    bool use_hw_wrapped_key;
    bool dusize_4k;

    // Ensure that "version" is not valid on creation and so must be explicitly set
    EncryptionOptions() : version(0) {}
};

struct EncryptionPolicy {
    EncryptionOptions options;
    std::string key_raw_ref;
};

void BytesToHex(const std::string& bytes, std::string* hex);

unsigned int GetFirstApiLevel();

bool OptionsToString(const EncryptionOptions& options, std::string* options_string);

bool OptionsToStringForApiLevel(unsigned int first_api_level, const EncryptionOptions& options,
                                std::string* options_string);

bool ParseOptions(const std::string& options_string, EncryptionOptions* options);

bool ParseOptionsForApiLevel(unsigned int first_api_level, const std::string& options_string,
                             EncryptionOptions* options);

bool EnsurePolicy(const EncryptionPolicy& policy, const std::string& directory);

inline bool operator==(const EncryptionOptions& lhs, const EncryptionOptions& rhs) {
    return (lhs.version == rhs.version) && (lhs.contents_mode == rhs.contents_mode) &&
           (lhs.filenames_mode == rhs.filenames_mode) && (lhs.flags == rhs.flags) &&
           (lhs.use_hw_wrapped_key == rhs.use_hw_wrapped_key) && (lhs.dusize_4k == rhs.dusize_4k);
}

inline bool operator!=(const EncryptionOptions& lhs, const EncryptionOptions& rhs) {
    return !(lhs == rhs);
}

inline bool operator==(const EncryptionPolicy& lhs, const EncryptionPolicy& rhs) {
    return lhs.key_raw_ref == rhs.key_raw_ref && lhs.options == rhs.options;
}

inline bool operator!=(const EncryptionPolicy& lhs, const EncryptionPolicy& rhs) {
    return !(lhs == rhs);
}

}  // namespace fscrypt
}  // namespace android

#endif  // _FSCRYPT_H_
