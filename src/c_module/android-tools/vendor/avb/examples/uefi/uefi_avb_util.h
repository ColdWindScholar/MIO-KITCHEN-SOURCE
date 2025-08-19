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

// NOTE: See avb_sysdeps.h

#ifndef UEFI_AVB_UTIL_H_
#define UEFI_AVB_UTIL_H_

#include <libavb/libavb.h>

/* Converts UTF-8 to UCS-2. Returns |false| if invalid UTF-8 or if a
 * rune cannot be represented as UCS-2.
 */
bool uefi_avb_utf8_to_ucs2(const uint8_t* utf8_data,
                           size_t utf8_num_bytes,
                           uint16_t* ucs2_data,
                           size_t ucs2_data_capacity_num_bytes,
                           size_t* out_ucs2_data_num_bytes);

#endif /* UEFI_AVB_UTIL_H_ */
