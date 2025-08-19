/*
 * Copyright (C) 2016 The Android Open Source Project
 *
 * Permission is hereby granted, free of charge, to any person
 * obtaining a copy of this software and associated documentation
 * files (the "Software"), to deal in the Software without
 * restriction, including without limitation the rights to use, copy,
 * modify, merge, publish, distribute, sublicense, and/or sell copies
 * of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be
 * included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 * EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
 * NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
 * BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
 * ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

#include <iostream>

#include <endian.h>
#include <errno.h>
#include <inttypes.h>
#include <string.h>

#include <fcntl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#include <base/files/file_util.h>
#include <base/strings/string_util.h>
#include <base/strings/stringprintf.h>
#include <openssl/rand.h>
#include <openssl/sha.h>

#include "fake_avb_ops.h"

namespace avb {

std::set<std::string> FakeAvbOps::get_partition_names_read_from() {
  return partition_names_read_from_;
}

bool FakeAvbOps::preload_partition(const std::string& partition,
                                   const base::FilePath& path) {
  if (preloaded_partitions_.count(partition) > 0) {
    fprintf(stderr, "Partition '%s' already preloaded\n", partition.c_str());
    return false;
  }

  int64_t file_size;
  if (!base::GetFileSize(path, &file_size)) {
    fprintf(stderr, "Error getting size of file '%s'\n", path.value().c_str());
    return false;
  }

  int fd = open(path.value().c_str(), O_RDONLY);
  if (fd < 0) {
    fprintf(stderr,
            "Error opening file '%s': %s\n",
            path.value().c_str(),
            strerror(errno));
    return false;
  }

  uint8_t* buffer = static_cast<uint8_t*>(malloc(file_size));
  ssize_t num_read = read(fd, buffer, file_size);
  if (num_read != file_size) {
    fprintf(stderr,
            "Error reading %zd bytes from file '%s': %s\n",
            file_size,
            path.value().c_str(),
            strerror(errno));
    free(buffer);
    return false;
  }
  close(fd);

  preloaded_partitions_[partition] = buffer;
  return true;
}

bool FakeAvbOps::preload_preallocated_partition(const std::string& partition,
                                                uint8_t* buffer,
                                                size_t size) {
  if (preallocated_preloaded_partitions_.count(partition) > 0) {
    fprintf(stderr, "Partition '%s' already preloaded\n", partition.c_str());
    return false;
  }

  preallocated_preloaded_partitions_[partition] = std::make_pair(buffer, size);
  return true;
}

AvbIOResult FakeAvbOps::read_from_partition(const char* partition,
                                            int64_t offset,
                                            size_t num_bytes,
                                            void* buffer,
                                            size_t* out_num_read) {
  if (hidden_partitions_.find(partition) != hidden_partitions_.end()) {
    return AVB_IO_RESULT_ERROR_NO_SUCH_PARTITION;
  }

  base::FilePath path =
      partition_dir_.Append(std::string(partition)).AddExtension("img");

  partition_names_read_from_.insert(partition);

  if (offset < 0) {
    int64_t file_size;
    if (!base::GetFileSize(path, &file_size)) {
      fprintf(
          stderr, "Error getting size of file '%s'\n", path.value().c_str());
      return AVB_IO_RESULT_ERROR_IO;
    }
    offset = file_size - (-offset);
  }

  int fd = open(path.value().c_str(), O_RDONLY);
  if (fd < 0) {
    fprintf(stderr,
            "Error opening file '%s': %s\n",
            path.value().c_str(),
            strerror(errno));
    if (errno == ENOENT) {
      return AVB_IO_RESULT_ERROR_NO_SUCH_PARTITION;
    } else {
      return AVB_IO_RESULT_ERROR_IO;
    }
  }
  if (lseek(fd, offset, SEEK_SET) != offset) {
    fprintf(stderr,
            "Error seeking to pos %zd in file %s: %s\n",
            offset,
            path.value().c_str(),
            strerror(errno));
    close(fd);
    return AVB_IO_RESULT_ERROR_IO;
  }
  ssize_t num_read = read(fd, buffer, num_bytes);
  if (num_read < 0) {
    fprintf(stderr,
            "Error reading %zd bytes from pos %" PRId64 " in file %s: %s\n",
            num_bytes,
            offset,
            path.value().c_str(),
            strerror(errno));
    close(fd);
    return AVB_IO_RESULT_ERROR_IO;
  }
  close(fd);

  if (out_num_read != NULL) {
    *out_num_read = num_read;
  }

  return AVB_IO_RESULT_OK;
}

AvbIOResult FakeAvbOps::get_preloaded_partition(
    const char* partition,
    size_t num_bytes,
    uint8_t** out_pointer,
    size_t* out_num_bytes_preloaded) {
  if (hidden_partitions_.find(partition) != hidden_partitions_.end()) {
    return AVB_IO_RESULT_ERROR_NO_SUCH_PARTITION;
  }

  std::map<std::string, std::pair<uint8_t*, size_t>>::iterator prealloc_it =
      preallocated_preloaded_partitions_.find(std::string(partition));
  if (prealloc_it != preallocated_preloaded_partitions_.end()) {
    *out_pointer = prealloc_it->second.first;
    *out_num_bytes_preloaded = std::min(prealloc_it->second.second, num_bytes);
    return AVB_IO_RESULT_OK;
  }

  std::map<std::string, uint8_t*>::iterator it =
      preloaded_partitions_.find(std::string(partition));
  if (it == preloaded_partitions_.end()) {
    *out_pointer = NULL;
    *out_num_bytes_preloaded = 0;
    return AVB_IO_RESULT_OK;
  }

  uint64_t size;
  AvbIOResult result = get_size_of_partition(avb_ops(), partition, &size);
  if (result != AVB_IO_RESULT_OK) {
    return result;
  }

  *out_num_bytes_preloaded = std::min(static_cast<size_t>(size), num_bytes);
  *out_pointer = it->second;
  return AVB_IO_RESULT_OK;
}

AvbIOResult FakeAvbOps::write_to_partition(const char* partition,
                                           int64_t offset,
                                           size_t num_bytes,
                                           const void* buffer) {
  if (hidden_partitions_.find(partition) != hidden_partitions_.end()) {
    return AVB_IO_RESULT_ERROR_NO_SUCH_PARTITION;
  }

  base::FilePath path =
      partition_dir_.Append(std::string(partition)).AddExtension("img");

  if (offset < 0) {
    int64_t file_size;
    if (!base::GetFileSize(path, &file_size)) {
      fprintf(
          stderr, "Error getting size of file '%s'\n", path.value().c_str());
      return AVB_IO_RESULT_ERROR_IO;
    }
    offset = file_size - (-offset);
  }

  int fd = open(path.value().c_str(), O_WRONLY);
  if (fd < 0) {
    fprintf(stderr,
            "Error opening file '%s': %s\n",
            path.value().c_str(),
            strerror(errno));
    if (errno == ENOENT) {
      return AVB_IO_RESULT_ERROR_NO_SUCH_PARTITION;
    } else {
      return AVB_IO_RESULT_ERROR_IO;
    }
  }
  if (lseek(fd, offset, SEEK_SET) != offset) {
    fprintf(stderr,
            "Error seeking to pos %zd in file %s: %s\n",
            offset,
            path.value().c_str(),
            strerror(errno));
    close(fd);
    return AVB_IO_RESULT_ERROR_IO;
  }
  ssize_t num_written = write(fd, buffer, num_bytes);
  if (num_written < 0) {
    fprintf(stderr,
            "Error writing %zd bytes at pos %" PRId64 " in file %s: %s\n",
            num_bytes,
            offset,
            path.value().c_str(),
            strerror(errno));
    close(fd);
    return AVB_IO_RESULT_ERROR_IO;
  }
  close(fd);

  return AVB_IO_RESULT_OK;
}

AvbIOResult FakeAvbOps::validate_vbmeta_public_key(
    AvbOps* ops,
    const uint8_t* public_key_data,
    size_t public_key_length,
    const uint8_t* public_key_metadata,
    size_t public_key_metadata_length,
    bool* out_key_is_trusted) {
  if (out_key_is_trusted != NULL) {
    bool pk_matches = (public_key_length == expected_public_key_.size() &&
                       (memcmp(expected_public_key_.c_str(),
                               public_key_data,
                               public_key_length) == 0));
    bool pkmd_matches =
        (public_key_metadata_length == expected_public_key_metadata_.size() &&
         (memcmp(expected_public_key_metadata_.c_str(),
                 public_key_metadata,
                 public_key_metadata_length) == 0));
    *out_key_is_trusted = pk_matches && pkmd_matches;
  }
  return AVB_IO_RESULT_OK;
}

AvbIOResult FakeAvbOps::validate_public_key_for_partition(
    AvbOps* ops,
    const char* partition,
    const uint8_t* public_key_data,
    size_t public_key_length,
    const uint8_t* public_key_metadata,
    size_t public_key_metadata_length,
    bool* out_key_is_trusted,
    uint32_t* out_rollback_index_location) {
  std::string expected_public_key =
      expected_public_key_for_partition_map_[partition];
  uint32_t rollback_index_location =
      rollback_index_location_for_partition_map_[partition];
  if (out_key_is_trusted != NULL) {
    bool pk_matches = (public_key_length == expected_public_key.size() &&
                       (memcmp(expected_public_key.c_str(),
                               public_key_data,
                               public_key_length) == 0));
    *out_key_is_trusted = pk_matches;
    *out_rollback_index_location = rollback_index_location;
  }
  return AVB_IO_RESULT_OK;
}

AvbIOResult FakeAvbOps::read_rollback_index(AvbOps* ops,
                                            size_t rollback_index_location,
                                            uint64_t* out_rollback_index) {
  if (stored_rollback_indexes_.count(rollback_index_location) == 0) {
    fprintf(stderr,
            "No rollback index for location %zd (has %zd locations).\n",
            rollback_index_location,
            stored_rollback_indexes_.size());
    return AVB_IO_RESULT_ERROR_IO;
  }
  *out_rollback_index = stored_rollback_indexes_[rollback_index_location];
  return AVB_IO_RESULT_OK;
}

AvbIOResult FakeAvbOps::write_rollback_index(AvbOps* ops,
                                             size_t rollback_index_location,
                                             uint64_t rollback_index) {
  if (stored_rollback_indexes_.count(rollback_index_location) == 0) {
    fprintf(stderr,
            "No rollback index for location %zd (has %zd locations).\n",
            rollback_index_location,
            stored_rollback_indexes_.size());
    return AVB_IO_RESULT_ERROR_IO;
  }
  stored_rollback_indexes_[rollback_index_location] = rollback_index;
  return AVB_IO_RESULT_OK;
}

AvbIOResult FakeAvbOps::read_is_device_unlocked(AvbOps* ops,
                                                bool* out_is_device_unlocked) {
  *out_is_device_unlocked = stored_is_device_unlocked_ ? 1 : 0;
  return AVB_IO_RESULT_OK;
}

AvbIOResult FakeAvbOps::get_unique_guid_for_partition(AvbOps* ops,
                                                      const char* partition,
                                                      char* guid_buf,
                                                      size_t guid_buf_size) {
  if (hidden_partitions_.find(partition) != hidden_partitions_.end()) {
    return AVB_IO_RESULT_ERROR_NO_SUCH_PARTITION;
  }
  // This is faking it a bit but makes testing easy. It works
  // because avb_slot_verify.c doesn't check that the returned GUID
  // is wellformed.
  snprintf(guid_buf, guid_buf_size, "1234-fake-guid-for:%s", partition);
  return AVB_IO_RESULT_OK;
}

AvbIOResult FakeAvbOps::get_size_of_partition(AvbOps* ops,
                                              const char* partition,
                                              uint64_t* out_size) {
  if (hidden_partitions_.find(partition) != hidden_partitions_.end()) {
    return AVB_IO_RESULT_ERROR_NO_SUCH_PARTITION;
  }

  base::FilePath path =
      partition_dir_.Append(std::string(partition)).AddExtension("img");

  int64_t file_size;
  if (!base::GetFileSize(path, &file_size)) {
    return AVB_IO_RESULT_ERROR_NO_SUCH_PARTITION;
  }
  *out_size = file_size;
  return AVB_IO_RESULT_OK;
}

AvbIOResult FakeAvbOps::read_persistent_value(const char* name,
                                              size_t buffer_size,
                                              uint8_t* out_buffer,
                                              size_t* out_num_bytes_read) {
  if (out_buffer == NULL && buffer_size > 0) {
    return AVB_IO_RESULT_ERROR_INVALID_VALUE_SIZE;
  }
  if (stored_values_.count(name) == 0) {
    return AVB_IO_RESULT_ERROR_NO_SUCH_VALUE;
  }
  if (stored_values_[name].size() > buffer_size) {
    *out_num_bytes_read = stored_values_[name].size();
    return AVB_IO_RESULT_ERROR_INSUFFICIENT_SPACE;
  }
  memcpy(out_buffer, stored_values_[name].data(), stored_values_[name].size());
  *out_num_bytes_read = stored_values_[name].size();
  return AVB_IO_RESULT_OK;
}

AvbIOResult FakeAvbOps::write_persistent_value(const char* name,
                                               size_t value_size,
                                               const uint8_t* value) {
  stored_values_[name] =
      std::string(reinterpret_cast<const char*>(value), value_size);
  return AVB_IO_RESULT_OK;
}

AvbIOResult FakeAvbOps::read_permanent_attributes(
    AvbCertPermanentAttributes* attributes) {
  *attributes = permanent_attributes_;
  return AVB_IO_RESULT_OK;
}

AvbIOResult FakeAvbOps::read_permanent_attributes_hash(
    uint8_t hash[AVB_SHA256_DIGEST_SIZE]) {
  if (permanent_attributes_hash_.empty()) {
    SHA256(reinterpret_cast<const unsigned char*>(&permanent_attributes_),
           sizeof(AvbCertPermanentAttributes),
           hash);
    return AVB_IO_RESULT_OK;
  }
  memset(hash, 0, AVB_SHA256_DIGEST_SIZE);
  permanent_attributes_hash_.copy(reinterpret_cast<char*>(hash),
                                  AVB_SHA256_DIGEST_SIZE);
  return AVB_IO_RESULT_OK;
}

void FakeAvbOps::set_key_version(size_t rollback_index_location,
                                 uint64_t key_version) {
  verified_rollback_indexes_[rollback_index_location] = key_version;
}

AvbIOResult FakeAvbOps::get_random(size_t num_bytes, uint8_t* output) {
  if (!RAND_bytes(output, num_bytes)) {
    return AVB_IO_RESULT_ERROR_IO;
  }
  return AVB_IO_RESULT_OK;
}

static AvbIOResult my_ops_read_from_partition(AvbOps* ops,
                                              const char* partition,
                                              int64_t offset,
                                              size_t num_bytes,
                                              void* buffer,
                                              size_t* out_num_read) {
  return FakeAvbOps::GetInstanceFromAvbOps(ops)
      ->delegate()
      ->read_from_partition(partition, offset, num_bytes, buffer, out_num_read);
}

static AvbIOResult my_ops_get_preloaded_partition(
    AvbOps* ops,
    const char* partition,
    size_t num_bytes,
    uint8_t** out_pointer,
    size_t* out_num_bytes_preloaded) {
  return FakeAvbOps::GetInstanceFromAvbOps(ops)
      ->delegate()
      ->get_preloaded_partition(
          partition, num_bytes, out_pointer, out_num_bytes_preloaded);
}

static AvbIOResult my_ops_write_to_partition(AvbOps* ops,
                                             const char* partition,
                                             int64_t offset,
                                             size_t num_bytes,
                                             const void* buffer) {
  return FakeAvbOps::GetInstanceFromAvbOps(ops)->delegate()->write_to_partition(
      partition, offset, num_bytes, buffer);
}

static AvbIOResult my_ops_validate_vbmeta_public_key(
    AvbOps* ops,
    const uint8_t* public_key_data,
    size_t public_key_length,
    const uint8_t* public_key_metadata,
    size_t public_key_metadata_length,
    bool* out_key_is_trusted) {
  return FakeAvbOps::GetInstanceFromAvbOps(ops)
      ->delegate()
      ->validate_vbmeta_public_key(ops,
                                   public_key_data,
                                   public_key_length,
                                   public_key_metadata,
                                   public_key_metadata_length,
                                   out_key_is_trusted);
}

static AvbIOResult my_ops_validate_public_key_for_partition(
    AvbOps* ops,
    const char* partition,
    const uint8_t* public_key_data,
    size_t public_key_length,
    const uint8_t* public_key_metadata,
    size_t public_key_metadata_length,
    bool* out_key_is_trusted,
    uint32_t* out_rollback_index_location) {
  return FakeAvbOps::GetInstanceFromAvbOps(ops)
      ->delegate()
      ->validate_public_key_for_partition(ops,
                                          partition,
                                          public_key_data,
                                          public_key_length,
                                          public_key_metadata,
                                          public_key_metadata_length,
                                          out_key_is_trusted,
                                          out_rollback_index_location);
}

static AvbIOResult my_ops_read_rollback_index(AvbOps* ops,
                                              size_t rollback_index_location,
                                              uint64_t* out_rollback_index) {
  return FakeAvbOps::GetInstanceFromAvbOps(ops)
      ->delegate()
      ->read_rollback_index(ops, rollback_index_location, out_rollback_index);
}

static AvbIOResult my_ops_write_rollback_index(AvbOps* ops,
                                               size_t rollback_index_location,
                                               uint64_t rollback_index) {
  return FakeAvbOps::GetInstanceFromAvbOps(ops)
      ->delegate()
      ->write_rollback_index(ops, rollback_index_location, rollback_index);
}

static AvbIOResult my_ops_read_is_device_unlocked(
    AvbOps* ops, bool* out_is_device_unlocked) {
  return FakeAvbOps::GetInstanceFromAvbOps(ops)
      ->delegate()
      ->read_is_device_unlocked(ops, out_is_device_unlocked);
}

static AvbIOResult my_ops_get_unique_guid_for_partition(AvbOps* ops,
                                                        const char* partition,
                                                        char* guid_buf,
                                                        size_t guid_buf_size) {
  return FakeAvbOps::GetInstanceFromAvbOps(ops)
      ->delegate()
      ->get_unique_guid_for_partition(ops, partition, guid_buf, guid_buf_size);
}

static AvbIOResult my_ops_get_size_of_partition(AvbOps* ops,
                                                const char* partition,
                                                uint64_t* out_size) {
  return FakeAvbOps::GetInstanceFromAvbOps(ops)
      ->delegate()
      ->get_size_of_partition(ops, partition, out_size);
}

static AvbIOResult my_ops_read_persistent_value(AvbOps* ops,
                                                const char* name,
                                                size_t buffer_size,
                                                uint8_t* out_buffer,
                                                size_t* out_num_bytes_read) {
  return FakeAvbOps::GetInstanceFromAvbOps(ops)
      ->delegate()
      ->read_persistent_value(
          name, buffer_size, out_buffer, out_num_bytes_read);
}

static AvbIOResult my_ops_write_persistent_value(AvbOps* ops,
                                                 const char* name,
                                                 size_t value_size,
                                                 const uint8_t* value) {
  return FakeAvbOps::GetInstanceFromAvbOps(ops)
      ->delegate()
      ->write_persistent_value(name, value_size, value);
}

static AvbIOResult my_ops_read_permanent_attributes(
    AvbCertOps* cert_ops, AvbCertPermanentAttributes* attributes) {
  return FakeAvbOps::GetInstanceFromAvbOps(cert_ops->ops)
      ->delegate()
      ->read_permanent_attributes(attributes);
}

static AvbIOResult my_ops_read_permanent_attributes_hash(
    AvbCertOps* cert_ops, uint8_t hash[AVB_SHA256_DIGEST_SIZE]) {
  return FakeAvbOps::GetInstanceFromAvbOps(cert_ops->ops)
      ->delegate()
      ->read_permanent_attributes_hash(hash);
}

static void my_ops_set_key_version(AvbCertOps* cert_ops,
                                   size_t rollback_index_location,
                                   uint64_t key_version) {
  return FakeAvbOps::GetInstanceFromAvbOps(cert_ops->ops)
      ->delegate()
      ->set_key_version(rollback_index_location, key_version);
}

static AvbIOResult my_ops_get_random(AvbCertOps* cert_ops,
                                     size_t num_bytes,
                                     uint8_t* output) {
  return FakeAvbOps::GetInstanceFromAvbOps(cert_ops->ops)
      ->delegate()
      ->get_random(num_bytes, output);
}

FakeAvbOps::FakeAvbOps() {
  memset(&avb_ops_, 0, sizeof(avb_ops_));
  avb_ops_.ab_ops = &avb_ab_ops_;
  avb_ops_.cert_ops = &avb_cert_ops_;
  avb_ops_.user_data = this;
  avb_ops_.read_from_partition = my_ops_read_from_partition;
  avb_ops_.write_to_partition = my_ops_write_to_partition;
  avb_ops_.validate_vbmeta_public_key = my_ops_validate_vbmeta_public_key;
  avb_ops_.read_rollback_index = my_ops_read_rollback_index;
  avb_ops_.write_rollback_index = my_ops_write_rollback_index;
  avb_ops_.read_is_device_unlocked = my_ops_read_is_device_unlocked;
  avb_ops_.get_unique_guid_for_partition = my_ops_get_unique_guid_for_partition;
  avb_ops_.get_size_of_partition = my_ops_get_size_of_partition;
  avb_ops_.read_persistent_value = my_ops_read_persistent_value;
  avb_ops_.write_persistent_value = my_ops_write_persistent_value;
  avb_ops_.validate_public_key_for_partition =
      my_ops_validate_public_key_for_partition;

  // Just use the built-in A/B metadata read/write routines.
  avb_ab_ops_.ops = &avb_ops_;
  avb_ab_ops_.read_ab_metadata = avb_ab_data_read;
  avb_ab_ops_.write_ab_metadata = avb_ab_data_write;

  avb_cert_ops_.ops = &avb_ops_;
  avb_cert_ops_.read_permanent_attributes = my_ops_read_permanent_attributes;
  avb_cert_ops_.read_permanent_attributes_hash =
      my_ops_read_permanent_attributes_hash;
  avb_cert_ops_.set_key_version = my_ops_set_key_version;
  avb_cert_ops_.get_random = my_ops_get_random;

  delegate_ = this;
}

FakeAvbOps::~FakeAvbOps() {
  std::map<std::string, uint8_t*>::iterator it;
  for (it = preloaded_partitions_.begin(); it != preloaded_partitions_.end();
       it++) {
    free(it->second);
  }
}

void FakeAvbOps::enable_get_preloaded_partition() {
  avb_ops_.get_preloaded_partition = my_ops_get_preloaded_partition;
}

}  // namespace avb
