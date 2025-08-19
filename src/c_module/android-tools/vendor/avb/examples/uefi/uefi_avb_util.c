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

#include "uefi_avb_util.h"

bool uefi_avb_utf8_to_ucs2(const uint8_t* utf8_data,
                           size_t utf8_num_bytes,
                           uint16_t* ucs2_data,
                           size_t ucs2_data_capacity_num_bytes,
                           size_t* out_ucs2_data_num_bytes) {
  uint32_t i8 = 0;
  uint32_t i2 = 0;

  do {
    if (i2 >= ucs2_data_capacity_num_bytes) {
      break;
    }

    // cannot represent this character, too long
    if ((utf8_data[i8] & 0xF8) == 0xF0) {
      return false;
    } else if ((utf8_data[i8] & 0xF0) == 0xE0) {
      ucs2_data[i2] = (uint16_t)((uint16_t)utf8_data[i8] << 12) |
                      (uint16_t)(((uint16_t)utf8_data[i8 + 1] << 6) & 0x0FC0) |
                      (uint16_t)((uint16_t)utf8_data[i8 + 2] & 0x003F);
      i8 += 3;
    } else if ((utf8_data[i8] & 0xE0) == 0XC0) {
      ucs2_data[i2] = (uint16_t)(((uint16_t)utf8_data[i8] << 6) & 0x07C0) |
                      (uint16_t)((uint16_t)utf8_data[i8 + 1] & 0x003F);
      i8 += 2;
    } else if (!(utf8_data[i8] >> 7)) {
      ucs2_data[i2] = (uint16_t)((uint16_t)utf8_data[i8] & 0x00FF);
      i8++;
    } else {
      // invalid utf-8
      return false;
    }
    i2++;
  } while (i8 < utf8_num_bytes);

  if (out_ucs2_data_num_bytes != NULL) {
    *out_ucs2_data_num_bytes = i2 * 2;
  }
  return true;
}
