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

#include <efi.h>
#include <efilib.h>
#include <efistdarg.h>

#include <libavb/libavb.h>

#include "uefi_avb_util.h"

int avb_memcmp(const void* src1, const void* src2, size_t n) {
  return (int)CompareMem((VOID*)src1, (VOID*)src2, (UINTN)n);
}

int avb_strcmp(const char* s1, const char* s2) {
  return (int)strcmpa((CHAR8*)s1, (CHAR8*)s2);
}

void* avb_memcpy(void* dest, const void* src, size_t n) {
  CopyMem(dest, (VOID*)src, (UINTN)n);
  return dest;
}

void* avb_memset(void* dest, const int c, size_t n) {
  SetMem(dest, (UINTN)n, (UINT8)c);
  return dest;
}

void avb_print(const char* message) {
  size_t utf8_num_bytes = avb_strlen(message) + 1;
  size_t max_ucs2_bytes = utf8_num_bytes * 2;
  uint16_t* message_ucs2 = (uint16_t*)avb_calloc(max_ucs2_bytes);
  if (message_ucs2 == NULL) {
    return;
  }
  if (uefi_avb_utf8_to_ucs2((const uint8_t*)message,
                            utf8_num_bytes,
                            message_ucs2,
                            max_ucs2_bytes,
                            NULL)) {
    Print(message_ucs2);
  }
  avb_free(message_ucs2);
}

void avb_printv(const char* message, ...) {
  va_list ap;

  va_start(ap, message);
  do {
    avb_print(message);
    message = va_arg(ap, const char*);
  } while (message != NULL);
  va_end(ap);
}

void avb_abort(void) {
  avb_print("\nABORTING...\n");
  uefi_call_wrapper(BS->Stall, 1, 5 * 1000 * 1000);
  uefi_call_wrapper(BS->Exit, 4, NULL, EFI_NOT_FOUND, 0, NULL);
  while (true) {
    ;
  }
}

void* avb_malloc_(size_t size) {
  EFI_STATUS err;
  void* x;

  err = uefi_call_wrapper(
      BS->AllocatePool, 3, EfiBootServicesData, (UINTN)size, &x);
  if (EFI_ERROR(err)) {
    return NULL;
  }

  return x;
}

void avb_free(void* ptr) {
  EFI_STATUS err;
  err = uefi_call_wrapper(BS->FreePool, 1, ptr);

  if (EFI_ERROR(err)) {
    Print(L"Warning: Bad avb_free: %r\n", err);
    uefi_call_wrapper(BS->Stall, 1, 3 * 1000 * 1000);
  }
}

size_t avb_strlen(const char* str) {
  return strlena((CHAR8*)str);
}
