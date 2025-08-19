/*
 * Copyright (C) 2017 The Android Open Source Project
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

#include "avb_cert_slot_verify.h"

#include <libavb/avb_sha.h>
#include <libavb/libavb.h>
#include <libavb_cert/libavb_cert.h>

/* Chosen to be generous but still require a huge number of increase operations
 * before exhausting the 64-bit space.
 */
static const uint64_t kRollbackIndexIncreaseThreshold = 1000000000;

/* By convention, when a rollback index is not used the value remains zero. */
static const uint64_t kRollbackIndexNotUsed = 0;

typedef struct _AvbCertOpsContext {
  size_t key_version_location[AVB_MAX_NUMBER_OF_ROLLBACK_INDEX_LOCATIONS];
  uint64_t key_version_value[AVB_MAX_NUMBER_OF_ROLLBACK_INDEX_LOCATIONS];
  size_t next_key_version_slot;
} AvbCertOpsContext;

typedef struct _AvbCertOpsWithContext {
  AvbCertOps cert_ops;
  AvbCertOpsContext context;
} AvbCertOpsWithContext;

/* Returns context associated with |cert_ops| returned by
 * setup_ops_with_context().
 */
static AvbCertOpsContext* get_ops_context(AvbCertOps* cert_ops) {
  return &((AvbCertOpsWithContext*)cert_ops)->context;
}

/* An implementation of AvbCertOps::set_key_version that saves the key version
 * information to ops context data.
 */
static void save_key_version_to_context(AvbCertOps* cert_ops,
                                        size_t rollback_index_location,
                                        uint64_t key_version) {
  AvbCertOpsContext* context = get_ops_context(cert_ops);
  size_t offset = context->next_key_version_slot++;
  if (offset < AVB_MAX_NUMBER_OF_ROLLBACK_INDEX_LOCATIONS) {
    context->key_version_location[offset] = rollback_index_location;
    context->key_version_value[offset] = key_version;
  }
}

/* Attaches context data to |existing_ops| and returns new ops. The
 * |ops_with_context| will be used to store the new combined ops and context.
 * The set_key_version function will be replaced in order to collect the key
 * version information in the context.
 */
static AvbCertOps* setup_ops_with_context(
    const AvbCertOps* existing_ops, AvbCertOpsWithContext* ops_with_context) {
  avb_memset(ops_with_context, 0, sizeof(AvbCertOpsWithContext));
  ops_with_context->cert_ops = *existing_ops;
  // Close the loop on the circular reference.
  ops_with_context->cert_ops.ops->cert_ops = &ops_with_context->cert_ops;
  ops_with_context->cert_ops.set_key_version = save_key_version_to_context;
  return &ops_with_context->cert_ops;
}

/* Updates the stored rollback index value for |location| to match |value|. */
static AvbSlotVerifyResult update_rollback_index(AvbOps* ops,
                                                 size_t location,
                                                 uint64_t value) {
  AvbIOResult io_result = AVB_IO_RESULT_OK;
  uint64_t current_value;
  io_result = ops->read_rollback_index(ops, location, &current_value);
  if (io_result == AVB_IO_RESULT_ERROR_OOM) {
    return AVB_SLOT_VERIFY_RESULT_ERROR_OOM;
  } else if (io_result != AVB_IO_RESULT_OK) {
    avb_error("Error getting rollback index for slot.\n");
    return AVB_SLOT_VERIFY_RESULT_ERROR_IO;
  }
  if (current_value == value) {
    // No update necessary.
    return AVB_SLOT_VERIFY_RESULT_OK;
  }
  // The difference between the new and current value must not exceed the
  // increase threshold, and the value must not decrease.
  if (value - current_value > kRollbackIndexIncreaseThreshold) {
    avb_error("Rollback index value cannot increase beyond the threshold.\n");
    return AVB_SLOT_VERIFY_RESULT_ERROR_ROLLBACK_INDEX;
  }
  // This should have been checked during verification, but check again here as
  // a safeguard.
  if (value < current_value) {
    avb_error("Rollback index value cannot decrease.\n");
    return AVB_SLOT_VERIFY_RESULT_ERROR_ROLLBACK_INDEX;
  }
  io_result = ops->write_rollback_index(ops, location, value);
  if (io_result == AVB_IO_RESULT_ERROR_OOM) {
    return AVB_SLOT_VERIFY_RESULT_ERROR_OOM;
  } else if (io_result != AVB_IO_RESULT_OK) {
    avb_error("Error setting stored rollback index.\n");
    return AVB_SLOT_VERIFY_RESULT_ERROR_IO;
  }
  return AVB_SLOT_VERIFY_RESULT_OK;
}

AvbSlotVerifyResult avb_cert_slot_verify(
    AvbCertOps* cert_ops,
    const char* ab_suffix,
    AvbCertLockState lock_state,
    AvbCertSlotState slot_state,
    AvbCertOemDataState oem_data_state,
    AvbSlotVerifyData** verify_data,
    uint8_t vbmeta_digest[AVB_SHA256_DIGEST_SIZE]) {
  const char* partitions_without_oem[] = {"boot", NULL};
  const char* partitions_with_oem[] = {"boot", "oem_bootloader", NULL};
  AvbSlotVerifyResult result = AVB_SLOT_VERIFY_RESULT_OK;
  size_t i = 0;
  AvbCertOpsWithContext ops_with_context;

  cert_ops = setup_ops_with_context(cert_ops, &ops_with_context);

  result = avb_slot_verify(cert_ops->ops,
                           (oem_data_state == AVB_CERT_OEM_DATA_NOT_USED)
                               ? partitions_without_oem
                               : partitions_with_oem,
                           ab_suffix,
                           (lock_state == AVB_CERT_UNLOCKED)
                               ? AVB_SLOT_VERIFY_FLAGS_ALLOW_VERIFICATION_ERROR
                               : AVB_SLOT_VERIFY_FLAGS_NONE,
                           AVB_HASHTREE_ERROR_MODE_EIO,
                           verify_data);

  if (result != AVB_SLOT_VERIFY_RESULT_OK || lock_state == AVB_CERT_UNLOCKED) {
    return result;
  }

  /* Compute the vbmeta digest. */
  avb_slot_verify_data_calculate_vbmeta_digest(
      *verify_data, AVB_DIGEST_TYPE_SHA256, vbmeta_digest);

  /* Increase rollback index values to match the verified slot. */
  if (slot_state == AVB_CERT_SLOT_MARKED_SUCCESSFUL) {
    for (i = 0; i < AVB_MAX_NUMBER_OF_ROLLBACK_INDEX_LOCATIONS; i++) {
      uint64_t rollback_index_value = (*verify_data)->rollback_indexes[i];
      if (rollback_index_value != kRollbackIndexNotUsed) {
        result = update_rollback_index(cert_ops->ops, i, rollback_index_value);
        if (result != AVB_SLOT_VERIFY_RESULT_OK) {
          goto out;
        }
      }
    }

    /* Also increase rollback index values for the avb_cert key version
     * locations.
     */
    for (i = 0; i < AVB_MAX_NUMBER_OF_ROLLBACK_INDEX_LOCATIONS; i++) {
      size_t rollback_index_location =
          ops_with_context.context.key_version_location[i];
      uint64_t rollback_index_value =
          ops_with_context.context.key_version_value[i];
      if (rollback_index_value != kRollbackIndexNotUsed) {
        result = update_rollback_index(
            cert_ops->ops, rollback_index_location, rollback_index_value);
        if (result != AVB_SLOT_VERIFY_RESULT_OK) {
          goto out;
        }
      }
    }
  }

out:
  if (result != AVB_SLOT_VERIFY_RESULT_OK) {
    avb_slot_verify_data_free(*verify_data);
    *verify_data = NULL;
  }
  return result;
}
