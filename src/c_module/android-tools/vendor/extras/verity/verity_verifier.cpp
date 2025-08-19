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

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>

#include <memory>
#include <string>

#include <android-base/file.h>
#include <android-base/unique_fd.h>
#include <crypto_utils/android_pubkey.h>
#include <fec/io.h>
#include <openssl/obj_mac.h>
#include <openssl/rsa.h>
#include <openssl/sha.h>
#include <sparse/sparse.h>

static RSA* load_key(const char* path) {
  std::string content;
  if (!android::base::ReadFileToString(path, &content) ||
      content.size() < ANDROID_PUBKEY_ENCODED_SIZE) {
    fprintf(stderr, "Failed to load key from %s\n", path);
    return nullptr;
  }

  RSA* key = nullptr;
  if (!android_pubkey_decode(reinterpret_cast<const uint8_t*>(content.c_str()),
                             ANDROID_PUBKEY_ENCODED_SIZE, &key)) {
    fprintf(stderr, "Failed to parse key!\n");
    return nullptr;
  }

  return key;
}

static int verify_table(const char* key_path, const uint8_t* signature, size_t signature_size,
                        const char* table, uint32_t table_length) {
  // Hash the table
  uint8_t hash_buf[SHA256_DIGEST_LENGTH];
  SHA256(const_cast<uint8_t*>(reinterpret_cast<const uint8_t*>(table)), table_length, hash_buf);

  // Now get the public key from the keyfile
  std::unique_ptr<RSA, decltype(&RSA_free)> key(load_key(key_path), RSA_free);
  if (!key) {
    fprintf(stderr, "Couldn't load verity keys\n");
    return -1;
  }

  // Verify the result
  if (!RSA_verify(NID_sha256, hash_buf, sizeof(hash_buf), signature, signature_size, key.get())) {
    fprintf(stderr, "Couldn't verify table\n");
    return -1;
  }

  return 0;
}

int main(int argc, char* argv[]) {
  if (argc != 4 || strcmp(argv[2], "-mincrypt") != 0) {
    printf("Usage: %s <image> -mincrypt <verity_key>\n"
           "  image       the image file (raw or sparse image) to be verified\n"
           "  verity_key  the verity key in mincrypt format (/verity_key on device)\n", argv[0]);
    return 2;
  }

  // Get the raw image.
  android::base::unique_fd fd(open(argv[1], O_RDONLY));
  if (fd == -1) {
    fprintf(stderr, "failed to open %s: %s\n", argv[1], strerror(errno));
    return 1;
  }

  struct sparse_file* file = sparse_file_import_auto(fd, false, false);
  if (file == nullptr) {
    fprintf(stderr, "failed to read file %s\n", argv[1]);
    return 1;
  }

  TemporaryFile tf;
  if (sparse_file_write(file, tf.fd, false, false, false) < 0) {
    fprintf(stderr, "failed to write output file\n");
    return 1;
  }
  sparse_file_destroy(file);

  // Verify.
  fec::io input(tf.path);
  if (!input) {
    return 1;
  }

  fec_verity_metadata verity;
  if (!input.get_verity_metadata(verity)) {
    fprintf(stderr, "failed to get verity metadata\n");
    return 1;
  }

  int ret = verify_table(argv[3], verity.signature, sizeof(verity.signature),
                         verity.table, verity.table_length);
  printf("%s\n", ret == 0 ? "VERIFIED" : "FAILED");
  return ret;
}
