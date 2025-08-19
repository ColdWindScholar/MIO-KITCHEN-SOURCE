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

#include <ctype.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "dt_table.h"
#include "mkdtimg_core.h"


struct cfg_create_params {
  const char *img_filename;
  const char *cfg_filename;
  const char *dtb_dir;
};

static const char short_options[] = "d:";
static struct option options[] = {
  { "dtb-dir",   required_argument, NULL, 'd' },
  { 0,           0,                 NULL, 0 }
};


static char *trim_line(char *line) {
  /* Find the end of the string or the first of '#' */
  char *end = line;
  while (*end != '\0' && *end != '#') {
    end++;
  }
  do {
    end--;
  } while (end >= line && isspace(*end));

  *(end + 1) = '\0';

  while (isspace(*line)) {
    line++;
  }
  return line;
}

static int parse_config_entry_count(FILE *cfg_fp) {
  int count = 0;

  /* Any line without prefix spaces is entry filename */
  char line[1024];
  while (fgets(line, sizeof(line), cfg_fp) != NULL) {
    char c = line[0];
    if (c == '\0' || isspace(c) || c == '#') continue;
    count++;
  }

  return count;
}

static int output_img_with_config(FILE *img_fp, FILE *cfg_fp) {
  int entry_count = parse_config_entry_count(cfg_fp);
  struct dt_image_writer *writer = dt_image_writer_start(img_fp, entry_count);

  fseek(cfg_fp, 0, SEEK_SET); /* Reset the file pos to head */

  int is_entry = 0;
  char line[1024];
  while (fgets(line, sizeof(line), cfg_fp) != NULL) {
    char *trimmed = trim_line(line);
    if (trimmed[0] == '\0') {
      /* empty line, pass */
      continue;
    }

    if (trimmed == line) {
      /* This line is a file name,
        because it start from the first char of the line */
      if (dt_image_writer_add_entry(writer, trimmed) != 0) {
        return -1;
      }
      is_entry = 1;
      continue;
    }

    char *option, *value;
    if (parse_option(&option, &value, trimmed) != 0) {
      fprintf(stderr, "Wrong syntax: %s\n", trimmed);
      return -1;
    }

    int ret = is_entry ?
      set_entry_options(writer, option, value) :
      set_global_options(writer, option, value);
    if (ret != 0) {
      fprintf(stderr, "Unknown option: %s\n", option);
      return -1;
    }
  }

  if (dt_image_writer_end(writer) != 0) {
    return -1;
  }

  return 0;
}

static int process_command_cfg_create(const struct cfg_create_params *params) {
  int ret = -1;
  FILE *cfg_fp = NULL;
  FILE *img_fp = NULL;

  cfg_fp = fopen(params->cfg_filename, "r");
  if (cfg_fp == NULL) {
    fprintf(stderr, "Can not open config file: %s\n", params->cfg_filename);
    goto end;
  }

  printf("create image file: %s...\n", params->img_filename);

  img_fp = fopen(params->img_filename, "wb");
  if (img_fp == NULL) {
    fprintf(stderr, "Can not create file: %s\n", params->img_filename);
    goto end;
  }

  if (params->dtb_dir != NULL) {
    if (chdir(params->dtb_dir) != 0) {
      fprintf(stderr, "Can not switch to directory: %s\n", params->dtb_dir);
      goto end;
    }
  }

  ret = output_img_with_config(img_fp, cfg_fp);
  if (ret < 0)
    fprintf(stderr, "Can not output image with config: %s\n",
            params->cfg_filename);

end:
  if (img_fp) {
    fclose(img_fp);
    if (ret < 0) unlink(params->img_filename);
  }
  if (cfg_fp) fclose(cfg_fp);

  return ret;
}

void handle_usage_cfg_create(FILE *out_fp, const char *prog_name) {
  fprintf(out_fp, "  %s cfg_create <image_file> <config_file> (<option>...)\n\n", prog_name);
  fprintf(out_fp,
    "    options:\n"
    "      -d, --dtb-dir            The path to load dtb files.\n"
    "                               Default is load from the current path.\n");
}

int handle_command_cfg_create(int argc, char *argv[], int arg_start) {
  if (argc - arg_start < 2) {
    handle_usage_cfg_create(stderr, argv[0]);
    return 1;
  }

  struct cfg_create_params params;
  memset(&params, 0, sizeof(params));
  params.img_filename = argv[arg_start];
  params.cfg_filename = argv[arg_start + 1];

  optind = arg_start + 2;
  while (1) {
    int c = getopt_long(argc, argv, short_options, options, NULL);
    if (c == -1) {
      break;
    }
    switch (c) {
      case 'd':
        params.dtb_dir = optarg;
        break;
      default:
        /* Unknown option, return error */
        return 1;
    }
  }

  return process_command_cfg_create(&params);
}
