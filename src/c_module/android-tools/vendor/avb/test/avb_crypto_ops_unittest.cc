/*
 * Copyright (C) 2021 The Android Open Source Project
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

#include <string.h>

#include <gtest/gtest.h>

#include <libavb/avb_sha.h>

#include "avb_unittest_util.h"

namespace avb {

/* These smoke tests are intended to check that the cryptographic operations
 * conform to the AVB interface and not to check the correctness of the
 * cryptograhpy.
 */

TEST(CryptoOpsTest, Sha256) {
  AvbSHA256Ctx ctx;

  /* Compare with
   *
   * $ echo -n foobar |sha256sum
   * c3ab8ff13720e8ad9047dd39466b3c8974e592c2fa383d4a3960714caef0c4f2 -
   */
  avb_sha256_init(&ctx);
  avb_sha256_update(&ctx, (const uint8_t*)"foobar", 6);
  EXPECT_EQ("c3ab8ff13720e8ad9047dd39466b3c8974e592c2fa383d4a3960714caef0c4f2",
            mem_to_hexstring(avb_sha256_final(&ctx), AVB_SHA256_DIGEST_SIZE));
}

// Disabled for now because it takes ~30 seconds to run.
TEST(CryptoOpsTest, DISABLED_Sha256Large) {
  AvbSHA256Ctx ctx;

  /* Also check we this works with greater than 4GiB input. Compare with
   *
   * $ dd if=/dev/zero bs=1048576 count=4097 |sha256sum
   * 829816e339ff597ec3ada4c30fc840d3f2298444169d242952a54bcf3fcd7747 -
   */
  const size_t kMebibyte = 1048576;
  uint8_t* megabuf;
  megabuf = new uint8_t[kMebibyte];
  memset((char*)megabuf, '\0', kMebibyte);
  avb_sha256_init(&ctx);
  for (size_t n = 0; n < 4097; n++) {
    avb_sha256_update(&ctx, megabuf, kMebibyte);
  }
  EXPECT_EQ("829816e339ff597ec3ada4c30fc840d3f2298444169d242952a54bcf3fcd7747",
            mem_to_hexstring(avb_sha256_final(&ctx), AVB_SHA256_DIGEST_SIZE));
  delete[] megabuf;
}

TEST(CryptoOpsTest, Sha512) {
  AvbSHA512Ctx ctx;

  /* Compare with
   *
   * $ echo -n foobar |sha512sum
   * 0a50261ebd1a390fed2bf326f2673c145582a6342d523204973d0219337f81616a8069b012587cf5635f6925f1b56c360230c19b273500ee013e030601bf2425
   * -
   */
  avb_sha512_init(&ctx);
  avb_sha512_update(&ctx, (const uint8_t*)"foobar", 6);
  EXPECT_EQ(
      "0a50261ebd1a390fed2bf326f2673c145582a6342d523204973d0219337f81616a8069b0"
      "12587cf5635f6925f1b56c360230c19b273500ee013e030601bf2425",
      mem_to_hexstring(avb_sha512_final(&ctx), AVB_SHA512_DIGEST_SIZE));
}

// Disabled for now because it takes ~30 seconds to run.
TEST(CryptoOpsTest, DISABLED_Sha512Large) {
  AvbSHA512Ctx ctx;

  /* Also check we this works with greater than 4GiB input. Compare with
   *
   * $ dd if=/dev/zero bs=1048576 count=4097 |sha512sum
   * eac1685671cc2060315888746de072398116c0c83b7ee9463f0576e11bfdea9cdd5ddbf291fb3ffc4ee8a1b459c798d9fb9b50b7845e2871c4b1402470aaf4c0
   * -
   */
  const size_t kMebibyte = 1048576;
  uint8_t* megabuf;
  megabuf = new uint8_t[kMebibyte];
  memset((char*)megabuf, '\0', kMebibyte);
  avb_sha512_init(&ctx);
  for (size_t n = 0; n < 4097; n++) {
    avb_sha512_update(&ctx, megabuf, kMebibyte);
  }
  EXPECT_EQ(
      "eac1685671cc2060315888746de072398116c0c83b7ee9463f0576e11bfdea9cdd5ddbf2"
      "91fb3ffc4ee8a1b459c798d9fb9b50b7845e2871c4b1402470aaf4c0",
      mem_to_hexstring(avb_sha512_final(&ctx), AVB_SHA512_DIGEST_SIZE));
  delete[] megabuf;
}

}  // namespace avb
