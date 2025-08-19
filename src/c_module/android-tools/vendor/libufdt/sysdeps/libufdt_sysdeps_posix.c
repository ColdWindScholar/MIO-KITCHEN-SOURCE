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

#include "libufdt_sysdeps.h"

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int dto_print(const char *fmt, ...) {
  int err;

  va_list ap;
  va_start(ap, fmt);
  err = vfprintf(stderr, fmt, ap);
  va_end(ap);

  return err;
}

void dto_qsort(void *base, size_t nmemb, size_t size,
               int (*compar)(const void *, const void *)) {
  qsort(base, nmemb, size, compar);
}

void *dto_malloc(size_t size) { return malloc(size); }

void dto_free(void *ptr) { free(ptr); }

char *dto_strchr(const char *s, int c) { return strchr(s, c); }

unsigned long int dto_strtoul(const char *nptr, char **endptr, int base) {
  return strtoul(nptr, endptr, base);
}

size_t dto_strlen(const char *s) { return strlen(s); }

int dto_memcmp(const void *lhs, const void *rhs, size_t n) {
  return memcmp(lhs, rhs, n);
}

void *dto_memcpy(void *dest, const void *src, size_t n) {
  return memcpy(dest, src, n);
}

int dto_strcmp(const char *s1, const char *s2) { return strcmp(s1, s2); }

int dto_strncmp(const char *s1, const char *s2, size_t n) {
  return strncmp(s1, s2, n);
}

void *dto_memchr(const void *s, int c, size_t n) { return memchr(s, c, n); }

void *dto_memset(void *s, int c, size_t n) { return memset(s, c, n); }
