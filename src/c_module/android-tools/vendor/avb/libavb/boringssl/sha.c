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

#include "../avb_sha.h"
#include "avb_crypto_ops_impl.h"

/* SHA-256 implementation */
void avb_sha256_init(AvbSHA256Ctx* ctx) {
  SHA256_CTX* realCtx = (SHA256_CTX*)ctx->reserved;
  SHA256_Init(realCtx);
}

void avb_sha256_update(AvbSHA256Ctx* ctx, const uint8_t* data, size_t len) {
  SHA256_CTX* realCtx = (SHA256_CTX*)ctx->reserved;
  SHA256_Update(realCtx, data, len);
}

uint8_t* avb_sha256_final(AvbSHA256Ctx* ctx) {
  SHA256_CTX* realCtx = (SHA256_CTX*)ctx->reserved;
  SHA256_Final(ctx->buf, realCtx);
  return ctx->buf;
}

/* SHA-512 implementation */
void avb_sha512_init(AvbSHA512Ctx* ctx) {
  SHA512_CTX* realCtx = (SHA512_CTX*)ctx->reserved;
  SHA512_Init(realCtx);
}

void avb_sha512_update(AvbSHA512Ctx* ctx, const uint8_t* data, size_t len) {
  SHA512_CTX* realCtx = (SHA512_CTX*)ctx->reserved;
  SHA512_Update(realCtx, data, len);
}

uint8_t* avb_sha512_final(AvbSHA512Ctx* ctx) {
  SHA512_CTX* realCtx = (SHA512_CTX*)ctx->reserved;
  SHA512_Final(ctx->buf, realCtx);
  return ctx->buf;
}
