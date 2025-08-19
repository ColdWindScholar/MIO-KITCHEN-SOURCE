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

#if !defined(AVB_INSIDE_LIBAVB_CERT_H) && !defined(AVB_COMPILATION)
#error \
    "Never include this file directly, include libavb_cert/libavb_cert.h instead."
#endif

#ifndef AVB_CERT_TYPES_H_
#define AVB_CERT_TYPES_H_

#include <libavb/libavb.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Size in bytes of a libavb_cert product ID. */
#define AVB_CERT_PRODUCT_ID_SIZE 16

/* Size in bytes of a libavb_cert unlock challenge. */
#define AVB_CERT_UNLOCK_CHALLENGE_SIZE 16

/* Size in bytes of a serialized public key with a 4096-bit modulus. */
#define AVB_CERT_PUBLIC_KEY_SIZE (sizeof(AvbRSAPublicKeyHeader) + 1024)

/* Data structure of libavb_cert permanent attributes. */
typedef struct AvbCertPermanentAttributes {
  uint32_t version;
  uint8_t product_root_public_key[AVB_CERT_PUBLIC_KEY_SIZE];
  uint8_t product_id[AVB_CERT_PRODUCT_ID_SIZE];
} AVB_ATTR_PACKED AvbCertPermanentAttributes;

/* Data structure of signed fields in a libavb_cert certificate. */
typedef struct AvbCertCertificateSignedData {
  uint32_t version;
  uint8_t public_key[AVB_CERT_PUBLIC_KEY_SIZE];
  uint8_t subject[AVB_SHA256_DIGEST_SIZE];
  uint8_t usage[AVB_SHA256_DIGEST_SIZE];
  uint64_t key_version;
} AVB_ATTR_PACKED AvbCertCertificateSignedData;

/* Data structure of a libavb_cert certificate. */
typedef struct AvbCertCertificate {
  AvbCertCertificateSignedData signed_data;
  uint8_t signature[AVB_RSA4096_NUM_BYTES];
} AVB_ATTR_PACKED AvbCertCertificate;

/* Data structure of the libavb_cert public key metadata in vbmeta. */
typedef struct AvbCertPublicKeyMetadata {
  uint32_t version;
  AvbCertCertificate product_intermediate_key_certificate;
  AvbCertCertificate product_signing_key_certificate;
} AVB_ATTR_PACKED AvbCertPublicKeyMetadata;

/* Data structure of a libavb_cert unlock challenge. */
typedef struct AvbCertUnlockChallenge {
  uint32_t version;
  uint8_t product_id_hash[AVB_SHA256_DIGEST_SIZE];
  uint8_t challenge[AVB_CERT_UNLOCK_CHALLENGE_SIZE];
} AVB_ATTR_PACKED AvbCertUnlockChallenge;

/* Data structure of a libavb_cert unlock credential. */
typedef struct AvbCertUnlockCredential {
  uint32_t version;
  AvbCertCertificate product_intermediate_key_certificate;
  AvbCertCertificate product_unlock_key_certificate;
  uint8_t challenge_signature[AVB_RSA4096_NUM_BYTES];
} AVB_ATTR_PACKED AvbCertUnlockCredential;

#ifdef __cplusplus
}
#endif

#endif /* AVB_CERT_TYPES_H_ */
