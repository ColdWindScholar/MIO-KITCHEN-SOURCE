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

#include <ctype.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/cdefs.h>

#define MAX_PATH 4096
#define MAX_FILE_VERSION 100

#ifndef __STRING
#define __STRING(x) #x
#endif
#define ___STRING(x) __STRING(x)

static void usage(char* filename) {
    fprintf(stderr, "Usage: %s input_blk_alloc_file output_base_fs_file \n", filename);
}

int main(int argc, char** argv) {
    FILE *blk_alloc_file = NULL, *base_fs_file = NULL;
    char filename[MAX_PATH + 1], file_version[MAX_FILE_VERSION + 1], *spaced_allocs = NULL;
    size_t spaced_allocs_len = 0;

    if (argc != 3) {
        usage(argv[0]);
        exit(EXIT_FAILURE);
    }
    blk_alloc_file = fopen(argv[1], "r");
    if (blk_alloc_file == NULL) {
        fprintf(stderr, "failed to open %s: %s\n", argv[1], strerror(errno));
        exit(EXIT_FAILURE);
    }
    base_fs_file = fopen(argv[2], "w");
    if (base_fs_file == NULL) {
        fprintf(stderr, "failed to open %s: %s\n", argv[2], strerror(errno));
        exit(EXIT_FAILURE);
    }
    if (fscanf(blk_alloc_file, "Base EXT4 version %" ___STRING(MAX_FILE_VERSION) "s",
               file_version) > 0) {
        int c;
        printf("%s is already in *.base_fs format, just copying into %s...\n", argv[1], argv[2]);
        rewind(blk_alloc_file);
        while ((c = fgetc(blk_alloc_file)) != EOF) {
            fputc(c, base_fs_file);
        }
        return 0;
    } else {
        printf("Converting %s into *.base_fs format as %s...\n", argv[1], argv[2]);
        rewind(blk_alloc_file);
    }
    fprintf(base_fs_file, "Base EXT4 version 1.0\n");
    while (fscanf(blk_alloc_file, "%" ___STRING(MAX_PATH) "s ", filename) != EOF) {
        int i;
        fprintf(base_fs_file, "%s ", filename);
        if (getline(&spaced_allocs, &spaced_allocs_len, blk_alloc_file) == -1) {
            fprintf(stderr, "Bad blk_alloc format\n");
            exit(EXIT_FAILURE);
        }
        for (i = 0; spaced_allocs[i]; i++) {
            if (spaced_allocs[i] == ' ') {
                if (!isspace(spaced_allocs[i + 1])) fputc(',', base_fs_file);
            } else
                fputc(spaced_allocs[i], base_fs_file);
        }
    }
    free(spaced_allocs);
    fclose(blk_alloc_file);
    fclose(base_fs_file);
    return 0;
}
