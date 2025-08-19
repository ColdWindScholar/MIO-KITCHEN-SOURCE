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
#include <stdio.h>
#include <sys/time.h>
#include <sys/types.h>
#include <unistd.h>
#include <stdlib.h>
#include <signal.h>
#include <string.h>
#include <sys/stat.h>
#include <errno.h>
#include <fcntl.h>
#include <ctype.h>
#include "ioshark.h"

/*
 * Real simple utility that just extracts and dumps the IOshark filenames
 * one per line from the ioshark_filenames file. Useful in debugging.
 */
int
main(int argc __attribute__((unused)), char **argv)
{
	char *progname;
	static FILE *filename_cache_fp;
	struct stat st;
	struct ioshark_filename_struct *filename_cache;
	int filename_cache_num_entries;
	size_t filename_cache_size;
	int i;

	progname = argv[0];
	if (stat("ioshark_filenames", &st) < 0) {
		fprintf(stderr, "%s Can't stat ioshark_filenames file\n",
			progname);
			exit(EXIT_FAILURE);
	}
	filename_cache_num_entries = st.st_size /
		sizeof(struct ioshark_filename_struct);
	filename_cache_fp = fopen("ioshark_filenames", "r");
	if (filename_cache_fp == NULL) {
		fprintf(stderr, "%s Cannot open ioshark_filenames file\n",
			progname);
		exit(EXIT_FAILURE);
	}
	/* Preallocate a fixed size of entries */
	filename_cache_size = filename_cache_num_entries + 1024;
	filename_cache = calloc(filename_cache_size,
				sizeof(struct ioshark_filename_struct));
	if (filename_cache == NULL) {
		fprintf(stderr, "%s Can't allocate memory - this is fatal\n",
			__func__);
		exit(EXIT_FAILURE);
	}
	if (fread(filename_cache,
		  sizeof(struct ioshark_filename_struct),
		  filename_cache_num_entries,
		  filename_cache_fp) != (size_t)filename_cache_num_entries) {
		fprintf(stderr, "%s Can't read ioshark_filenames file\n",
			progname);
		exit(EXIT_FAILURE);
	}
       for (i = 0 ; i < filename_cache_num_entries ; i++) {
	       printf("%s\n", filename_cache[i].path);
       }
       free(filename_cache);
       fclose(filename_cache_fp);
}
