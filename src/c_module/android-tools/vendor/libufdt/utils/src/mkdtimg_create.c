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

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "dt_table.h"
#include "mkdtimg_core.h"


static int calculate_args_entry_count(int argc, char *argv[], int arg_start) {
  int count = 0;

  int i;
  for (i = arg_start; i < argc; i++) {
    const char *arg = argv[i];
    char c = arg[0];
    /* Skip options starting with -- */
    if (c == '-') continue;
    count++;
  }

  return count;
}

static int parse_arg(char **option, char **value, char *arg) {
  if (arg[0] != '-') {
    /* This is not a option */
    *option = NULL;
    return 0;
  }

  /* An option must start with -- */
  if (arg[1] != '-') {
    return -1;
  }

  return parse_option(option, value, arg + 2);
}

static int output_img_with_args(FILE *img_fp, int argc, char *argv[], int arg_start) {
  int entry_count = calculate_args_entry_count(argc, argv, arg_start);
  struct dt_image_writer *writer = dt_image_writer_start(img_fp, entry_count);

  int is_entry = 0;
  int i;
  for (i = arg_start; i < argc; i++) {
    char *arg = argv[i];
    char *option, *value;
    if (parse_arg(&option, &value, arg) != 0) {
      fprintf(stderr, "Wrong syntax: %s\n", arg);
      return -1;
    }

    if (option == NULL) {
      /* This is a file name */
      if (dt_image_writer_add_entry(writer, arg) != 0) {
        return -1;
      }
      is_entry = 1;
      continue;
    }

    int ret = is_entry ?
      set_entry_options(writer, option, value) :
      set_global_options(writer, option, value);
    if (ret != 0) {
      fprintf(stderr, "Unknown option: %s\n", option);
      return -1;
    }
  } /* for all argv */

  if (dt_image_writer_end(writer) != 0) {
    return -1;
  }

  return 0;
}

void handle_usage_create(FILE *out_fp, const char *prog_name) {
  fprintf(out_fp, "  %s create <image_file> (<global_option>...) (<dtb_file> (<entry_option>...) ...)\n\n", prog_name);
  fprintf(out_fp,
          "    global_options:\n"
          "      --dt_type=<type>         Device Tree type (dtb|acpi). Default:"
          " dtb\n"
          "      --page_size=<number>     Output page size. Default: 2048\n"
          "      --version=<version>      DTBO version. Default: 0\n"
          "      --id=<number|path>       The default value to set property id "
          "in dt_table_entry. Default: 0\n"
          "      --rev=<number|path>\n"
          "      --custom0=<number|path>\n"
          "      --custom1=<number|path>\n"
          "      --custom2=<number|path>\n"
          "      --custom3=<number|path>\n\n"
          "      The value could be a number or a DT node path.\n"
          "      <number> could be a 32-bits digit or hex value, ex. 68000, "
          "0x6800.\n"
          "      <path> format is <full_node_path>:<property_name>, ex. "
          "/board/:id,\n"
          "      will read the value in given FTB file with the path.\n");
}

int handle_command_create(int argc, char *argv[], int arg_start) {
  int ret = -1;
  FILE *img_fp = NULL;

  if (argc - arg_start < 1) {
    handle_usage_create(stderr, argv[0]);
    goto end;
  }

  const char *img_filename = argv[arg_start];

  printf("create image file: %s...\n", img_filename);

  img_fp = fopen(img_filename, "wb");
  if (img_fp == NULL) {
    fprintf(stderr, "Can not create file: %s\n", img_filename);
    goto end;
  }

  ret = output_img_with_args(img_fp, argc, argv, arg_start + 1);
  if (ret < 0) fprintf(stderr, "Can not output image with args\n");

end:
  if (img_fp) {
    fclose(img_fp);
    if (ret < 0) unlink(img_filename);
  }

  return ret;
}
