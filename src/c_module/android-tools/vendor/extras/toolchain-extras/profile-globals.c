/*
 * Copyright (C) 2019 The Android Open Source Project
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

#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/types.h>

// This file provides a wrapper for getenv that appends the userid (geteuid())
// of the current process to GCOV_PREFIX.  This avoids conflicts and permissions
// issues when different processes try to create/access the same directories and
// files under $GCOV_PREFIX.
//
// When this file is linked to a binary, the -Wl,--wrap,getenv flag must be
// used.  The linker redirects calls to getenv to __wrap_getenv and sets
// __real_getenv to point to libc's getenv.

char *__real_getenv(const char *name);

static char modified_gcov_prefix[128];

__attribute__((weak)) char *__wrap_getenv(const char *name) {
  if (strcmp(name, "GCOV_PREFIX") != 0) {
    return __real_getenv(name);
  }

  sprintf(modified_gcov_prefix, "%s/%u", __real_getenv(name), geteuid());
  mkdir(modified_gcov_prefix, 0777);
  return modified_gcov_prefix;
}
