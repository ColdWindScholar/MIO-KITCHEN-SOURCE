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


extern void handle_usage_help(FILE *out_fp, const char *prog_name);
extern int handle_command_help(int argc, char *argv[], int arg_start);
extern void handle_usage_dump(FILE *out_fp, const char *prog_name);
extern int handle_command_dump(int argc, char *argv[], int arg_start);
extern void handle_usage_create(FILE *out_fp, const char *prog_name);
extern int handle_command_create(int argc, char *argv[], int arg_start);
extern void handle_usage_cfg_create(FILE *out_fp, const char *prog_name);
extern int handle_command_cfg_create(int argc, char *argv[], int arg_start);


struct command_info {
  const char *command;
  void (*usage)(FILE *out_fp, const char *prog_name);
  int (*handler)(int argc, char *argv[], int arg_start);
};

static const struct command_info command_infos[] = {
  { "help", handle_usage_help, handle_command_help },
  { "dump", handle_usage_dump, handle_command_dump },
  { "create", handle_usage_create, handle_command_create },
  { "cfg_create", handle_usage_cfg_create, handle_command_cfg_create },
  { NULL, NULL, NULL }
};

static const struct command_info *search_command(const char *command) {
  const struct command_info *info;
  for (info = command_infos; info->command != NULL; info++) {
    if (strcmp(command, info->command) == 0) {
      break;
    }
  }
  if (info->command == NULL) {
    fprintf(stderr, "Unknown command: %s\n", command);
    return NULL;
  }
  return info;
}

static void print_all_commands(FILE *out_fp) {
  const struct command_info *info;
  for (info = command_infos; info->command != NULL; info++) {
    if (info != command_infos) {
      fprintf(out_fp, ", ");
    }
    fprintf(out_fp, "%s", info->command);
  }
  fprintf(out_fp, "\n");
}

static void output_all_usage(FILE *out_fp, const char *prog_name) {
  fprintf(out_fp, "  %s <command>\n\n", prog_name);
  fprintf(out_fp, "    commands:\n      ");
  print_all_commands(out_fp);
  fprintf(out_fp, "\n");

  const struct command_info *info;
  for (info = command_infos; info->command != NULL; info++) {
    info->usage(out_fp, prog_name);
    fprintf(out_fp, "\n");
  }
}

void handle_usage_help(FILE *out_fp, const char *prog_name) {
  fprintf(out_fp, "  %s help all\n", prog_name);
  fprintf(out_fp, "  %s help <command>\n\n", prog_name);
  fprintf(out_fp, "    commands:\n      ");
  print_all_commands(out_fp);
}

int handle_command_help(int argc, char *argv[], int arg_start) {
  const char *prog_name = argv[0];

  if (argc - arg_start < 1) {
    handle_usage_help(stderr, prog_name);
    return 1;
  }

  if (strcmp(argv[arg_start], "all") == 0) {
    output_all_usage(stdout, prog_name);
    return 0;
  }

  const struct command_info *info = search_command(argv[arg_start]);
  if (info == NULL) {
    handle_usage_help(stderr, prog_name);
    return 1;
  }

  info->usage(stdout, prog_name);

  return 0;
}

int main(int argc, char *argv[]) {
  if (argc <= 1) {
    output_all_usage(stderr, argv[0]);
    return 1;
  }

  const char *command = argv[1];
  const struct command_info *info = search_command(command);
  if (info == NULL) {
    return 1;
  }

  /* skip 2 arguments, argv[0] and argv[1] */
  return info->handler(argc, argv, 2);
}
