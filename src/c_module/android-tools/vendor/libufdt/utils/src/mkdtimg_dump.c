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

#include <getopt.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include "dt_table.h"
#include "libacpi.h"
#include "libfdt.h"

struct dump_params {
  const char *img_filename;
  const char *out_filename;
  const char *out_dtb_filename;
};

static const char short_options[] = "o:b:";
static struct option options[] = {{"output", required_argument, NULL, 'o'},
                                  {"dtb", required_argument, NULL, 'b'},
                                  {0, 0, NULL, 0}};

static void *read_fdt_from_image(FILE *img_fp,
                                 uint32_t dt_offset, uint32_t dt_size) {
  void *fdt = NULL;

  fdt = malloc(dt_size);
  if (fdt == NULL) {
    fprintf(stderr, "malloc(%" PRIu32 ") failed.\n", dt_size);
    return NULL;
  }

  fseek(img_fp, dt_offset, SEEK_SET);
  if (fread(fdt, dt_size, 1, img_fp) == 0) {
    fprintf(stderr, "Read FDT data error.\n");

    free(fdt);
    return NULL;
  }

  return fdt;
}

static int write_fdt_to_file(const char *filename, const void *fdt,
                             uint32_t (*get_fdt_size)(const void *)) {
  int ret = -1;
  FILE *out_fp = NULL;

  out_fp = fopen(filename, "wb");
  if (!out_fp) {
    fprintf(stderr, "Can not create file: %s\n", filename);
    goto end;
  }

  uint32_t fdt_size = get_fdt_size(fdt);
  if (fwrite(fdt, fdt_size, 1, out_fp) < 1) {
    fprintf(stderr, "Write FDT data error.\n");
    goto end;
  }

  ret = 0;

end:
  if (out_fp) fclose(out_fp);

  return ret;
}

static void free_fdt(void *fdt) {
  if (fdt == NULL) {
    /* do nothing */
    return;
  }

  free(fdt);
}


static void output_prop_int(FILE *out_fp, const char *name, uint32_t value) {
  fprintf(out_fp, "%20s = %d\n", name, fdt32_to_cpu(value));
}

static void output_prop_int_cpu(FILE *out_fp, const char *name, uint32_t value) {
  fprintf(out_fp, "%20s = %d\n", name, value);
}

static void output_prop_hex(FILE *out_fp, const char *name, uint32_t value) {
  fprintf(out_fp, "%20s = %08x\n", name, fdt32_to_cpu(value));
}

static void output_prop_str(FILE *out_fp, const char *name, const char *value) {
  fprintf(out_fp, "%20s = %s\n", name, value);
}

static void output_table_header(FILE *out_fp, const struct dt_table_header *header) {
  fprintf(out_fp, "dt_table_header:\n");
  output_prop_hex(out_fp, "magic", header->magic);
  output_prop_int(out_fp, "total_size", header->total_size);
  output_prop_int(out_fp, "header_size", header->header_size);
  output_prop_int(out_fp, "dt_entry_size", header->dt_entry_size);
  output_prop_int(out_fp, "dt_entry_count", header->dt_entry_count);
  output_prop_int(out_fp, "dt_entries_offset", header->dt_entries_offset);
  output_prop_int(out_fp, "page_size", header->page_size);
  output_prop_int(out_fp, "version", header->version);
}

static void output_table_entry(FILE *out_fp, int index, const struct dt_table_entry *entry) {
  fprintf(out_fp, "dt_table_entry[%d]:\n", index);
  output_prop_int(out_fp, "dt_size", entry->dt_size);
  output_prop_int(out_fp, "dt_offset", entry->dt_offset);
  output_prop_hex(out_fp, "id", entry->id);
  output_prop_hex(out_fp, "rev", entry->rev);
  output_prop_hex(out_fp, "custom[0]", entry->custom[0]);
  output_prop_hex(out_fp, "custom[1]", entry->custom[1]);
  output_prop_hex(out_fp, "custom[2]", entry->custom[2]);
  output_prop_hex(out_fp, "custom[3]", entry->custom[3]);
}

static int output_fdt_info(FILE *out_fp, void *fdt,
                           uint32_t (*get_fdt_size)(const void *)) {
  uint32_t fdt_size = get_fdt_size(fdt);

  output_prop_int_cpu(out_fp, "(FDT)size", fdt_size);

  int root_node_off = fdt_path_offset(fdt, "/");
  if (root_node_off < 0) {
    fprintf(stderr, "Can not get the root node.\n");
    return -1;
  }

  const char *compatible =
    (const char *)fdt_getprop(fdt, root_node_off, "compatible", NULL);
  output_prop_str(out_fp, "(FDT)compatible", compatible ? compatible : "(unknown)");

  return 0;
}

static inline uint32_t get_acpi_file_size(const void *acpi) {
  return acpi_length(acpi);
}

static inline uint32_t get_fdt_file_size(const void *fdt) {
  return fdt_totalsize(fdt);
}

static int dump_image_from_fp(FILE *out_fp, FILE *img_fp,
                              const struct dump_params *params) {
  struct dt_table_header header;
  if (fread(&header, sizeof(header), 1, img_fp) != 1) {
    fprintf(stderr, "Read error.\n");
    return -1;
  }
  /* TODO: check header */
  output_table_header(out_fp, &header);

  uint32_t (*get_fdt_size)(const void *);
  uint32_t entry_magic = fdt32_to_cpu(header.magic);
  if (entry_magic == ACPI_TABLE_MAGIC)
    get_fdt_size = get_acpi_file_size;
  else
    get_fdt_size = get_fdt_file_size;

  uint32_t entry_size = fdt32_to_cpu(header.dt_entry_size);
  uint32_t entry_offset = fdt32_to_cpu(header.dt_entries_offset);
  uint32_t entry_count = fdt32_to_cpu(header.dt_entry_count);
  uint32_t i;
  for (i = 0; i < entry_count; i++) {
    struct dt_table_entry entry;
    fseek(img_fp, entry_offset, SEEK_SET);
    if (fread(&entry, sizeof(entry), 1, img_fp) != 1) {
      fprintf(stderr, "Read dt_table_entry error.\n");
      return -1;
    }
    output_table_entry(out_fp, i, &entry);

    uint32_t dt_size = fdt32_to_cpu(entry.dt_size);
    uint32_t dt_offset = fdt32_to_cpu(entry.dt_offset);
    if (dt_size > 0 && dt_offset > 0) {
      void *fdt = read_fdt_from_image(img_fp, dt_offset, dt_size);
      if (fdt) {
        output_fdt_info(out_fp, fdt, get_fdt_size);

        if (params->out_dtb_filename != NULL) {
          char filename[256];
          snprintf(filename, sizeof(filename), "%s.%d",
                   params->out_dtb_filename, i);
          write_fdt_to_file(filename, fdt, get_fdt_size);
        }

        free_fdt(fdt);
      }
    }

    entry_offset += entry_size;
  }

  return 0;
}

static int process_command_dump(const struct dump_params *params) {
  int ret = -1;
  FILE *out_fp = NULL;
  FILE *img_fp = NULL;

  img_fp = fopen(params->img_filename, "rb");
  if (img_fp == NULL) {
    fprintf(stderr, "Can not open image file: %s\n", params->img_filename);
    goto end;
  }

  if (params->out_filename != NULL) {
    out_fp = fopen(params->out_filename, "w");
    if (out_fp == NULL) {
      fprintf(stderr, "Can not create file: %s\n", params->out_filename);
      goto end;
    }
  }

  ret = dump_image_from_fp(out_fp ? out_fp : stdout, img_fp, params);

end:
  if (img_fp) fclose(img_fp);
  if (out_fp) fclose(out_fp);

  return ret;
}

void handle_usage_dump(FILE *out_fp, const char *prog_name) {
  fprintf(out_fp, "  %s dump <image_file> (<option>...)\n\n", prog_name);
  fprintf(out_fp,
    "    options:\n"
    "      -o, --output <filename>  Output file name.\n"
    "                               Default is output to stdout.\n"
    "      -b, --dtb <filename>     Dump dtb/dtbo files from image.\n"
    "                               Will output to <filename>.0, <filename>.1, etc.\n");
}

int handle_command_dump(int argc, char *argv[], int arg_start) {
  if (argc - arg_start < 1) {
    handle_usage_dump(stderr, argv[0]);
    return 1;
  }

  struct dump_params params;
  memset(&params, 0, sizeof(params));
  params.img_filename = argv[arg_start];

  optind = arg_start + 1;
  while (1) {
    int c = getopt_long(argc, argv, short_options, options, NULL);
    if (c == -1) {
      break;
    }
    switch (c) {
      case 'o':
        params.out_filename = optarg;
        break;
      case 'b':
        params.out_dtb_filename = optarg;
        break;
      default:
        /* Unknown option, return error */
        return 1;
    }
  }

  return process_command_dump(&params);
}
