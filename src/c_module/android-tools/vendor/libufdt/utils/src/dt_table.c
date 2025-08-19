/*
 * Copyright (C) 2017 The Android Open Source Project
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

#include "dt_table.h"

#include <memory.h>

#include "libacpi.h"
#include "libfdt.h"
#include "libufdt_sysdeps.h"

void dt_table_header_init(struct dt_table_header *header, enum DT_TYPE dt_type) {
  const uint32_t header_size = sizeof(struct dt_table_header);
  const uint32_t entry_size = sizeof(struct dt_table_entry);

  dto_memset(header, 0, header_size);
  if (dt_type == ACPI)
    header->magic = cpu_to_fdt32(ACPI_TABLE_MAGIC);
  else
    header->magic = cpu_to_fdt32(DT_TABLE_MAGIC);

  header->total_size = cpu_to_fdt32(header_size);
  header->header_size = cpu_to_fdt32(header_size);
  header->dt_entry_size = cpu_to_fdt32(entry_size);
  header->dt_entries_offset = cpu_to_fdt32(header_size);
  header->page_size = cpu_to_fdt32(DT_TABLE_DEFAULT_PAGE_SIZE);
  header->version = cpu_to_fdt32(DT_TABLE_DEFAULT_VERSION);
}
