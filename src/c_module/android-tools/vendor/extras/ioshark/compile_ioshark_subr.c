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

#include <fcntl.h>
#include <stdio.h>
#include <sys/types.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <errno.h>
#include "ioshark.h"
#include "compile_ioshark.h"
#include <endian.h>

extern char *progname;

static struct files_db_s *files_db_buckets[FILE_DB_HASHSIZE];
static int current_fileno = 1;
static int num_objects = 0;

static int filename_cache_lookup(char *filename);

void
files_db_write_objects(FILE *fp)
{
	int i;
	struct ioshark_file_state st;

	for (i = 0 ; i < FILE_DB_HASHSIZE ; i++) {
		struct files_db_s *db_node, *s;

		db_node = files_db_buckets[i];
		while (db_node != NULL) {
			st.fileno = db_node->fileno;
			st.size = db_node->size;
			st.global_filename_ix =
				db_node->global_filename_ix;
			if (ioshark_write_file_state(fp, &st) != 1) {
				fprintf(stderr,
					"%s Write error trace.outfile\n",
					progname);
				exit(EXIT_FAILURE);
			}
			s = db_node;
			db_node = db_node->next;
			free(s->filename);
			free(s);
		}
	}
}

void *files_db_lookup(char *pathname)
{
	u_int32_t hash;
	struct files_db_s *db_node;

	hash = jenkins_one_at_a_time_hash(pathname, strlen(pathname));
	hash %= FILE_DB_HASHSIZE;
	db_node = files_db_buckets[hash];
	while (db_node != NULL) {
		if (strcmp(db_node->filename, pathname) == 0)
			break;
		db_node = db_node->next;
	}
	return db_node;
}

void *files_db_add(char *filename)
{
	u_int32_t hash;
	struct files_db_s *db_node;

	if ((db_node = files_db_lookup(filename)))
		return db_node;
	hash = jenkins_one_at_a_time_hash(filename, strlen(filename));
	hash %= FILE_DB_HASHSIZE;
	db_node = malloc(sizeof(struct files_db_s));
	db_node->filename = strdup(filename);
	db_node->global_filename_ix =
		filename_cache_lookup(filename);
	db_node->fileno = current_fileno++;
	db_node->next = files_db_buckets[hash];
	db_node->size = 0;
	files_db_buckets[hash] = db_node;
	num_objects++;
	return db_node;
}

int
files_db_get_total_obj(void)
{
	return num_objects;
}

static struct ioshark_filename_struct *filename_cache;
static int filename_cache_num_entries;
static int filename_cache_size;

void
init_filename_cache(void)
{
	static FILE *filename_cache_fp;
	struct stat st;
	int file_exists = 1;

	if (stat("ioshark_filenames", &st) < 0) {
		if (errno != ENOENT) {
			fprintf(stderr, "%s Can't stat ioshark_filenames file\n",
				progname);
			exit(EXIT_FAILURE);
		} else {
			file_exists = 0;
			filename_cache_num_entries = 0;
		}
	} else {
		filename_cache_num_entries = st.st_size /
			sizeof(struct ioshark_filename_struct);
	}
	if (file_exists) {
		filename_cache_fp = fopen("ioshark_filenames", "r");
		if (filename_cache_fp == NULL) {
			fprintf(stderr, "%s Cannot open ioshark_filenames file\n",
				progname);
			exit(EXIT_FAILURE);
		}
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
	if (file_exists)
		fclose(filename_cache_fp);
}

static int
filename_cache_lookup(char *filename)
{
	int ret;
	int i;

	for (i = 0 ; i < filename_cache_num_entries ; i++) {
		if (strcmp(filename_cache[i].path, filename) == 0)
			return i;
	}
	if (filename_cache_num_entries >= filename_cache_size) {
		int newsize;

		/* reallocate the filename cache up first */
		filename_cache_size += 1024;
		newsize = filename_cache_size *
			sizeof(struct ioshark_filename_struct);
		filename_cache = realloc(filename_cache, newsize);
		if (filename_cache == NULL) {
			fprintf(stderr,
				"%s Can't allocate memory - this is fatal\n",
				__func__);
			exit(EXIT_FAILURE);
		}
	}
	strcpy(filename_cache[filename_cache_num_entries].path,
	       filename);
	ret = filename_cache_num_entries;
	filename_cache_num_entries++;
	return ret;
}

void
store_filename_cache(void)
{
	static FILE *filename_cache_fp;

	filename_cache_fp = fopen("ioshark_filenames", "w+");
	if (filename_cache_fp == NULL) {
		fprintf(stderr, "%s Cannot open ioshark_filenames file\n",
			progname);
		exit(EXIT_FAILURE);
	}
	if (fwrite(filename_cache,
		   sizeof(struct ioshark_filename_struct),
		   filename_cache_num_entries,
		   filename_cache_fp) != (size_t)filename_cache_num_entries) {
		fprintf(stderr, "%s Can't read ioshark_filenames file\n",
			progname);
		exit(EXIT_FAILURE);
	}
	fclose(filename_cache_fp);
	free(filename_cache);
}

int
ioshark_write_header(FILE *fp, struct ioshark_header *header)
{
	header->version = htobe64(header->version);
	header->num_files = htobe64(header->num_files);
	header->num_io_operations = htobe64(header->num_io_operations);
	return fwrite(header, sizeof(struct ioshark_header), 1, fp);
}

int
ioshark_write_file_state(FILE *fp, struct ioshark_file_state *state)
{
	state->fileno = htobe64(state->fileno);
	state->size = htobe64(state->size);
	state->global_filename_ix = htobe64(state->global_filename_ix);
	return fwrite(state, sizeof(struct ioshark_file_state), 1, fp);
}

int
ioshark_write_file_op(FILE *fp, struct ioshark_file_operation *file_op)
{
	enum file_op op = file_op->ioshark_io_op;

	file_op->delta_us = htobe64(file_op->delta_us);
	file_op->op_union.enum_size = htobe32(file_op->op_union.enum_size);
	file_op->fileno = htobe64(file_op->fileno);
	switch (op) {
	case IOSHARK_LSEEK:
	case IOSHARK_LLSEEK:
		file_op->lseek_offset = htobe64(file_op->lseek_offset);
		file_op->lseek_action = htobe32(file_op->lseek_action);
		break;
	case IOSHARK_PREAD64:
	case IOSHARK_PWRITE64:
		file_op->prw_offset = htobe64(file_op->prw_offset);
		file_op->prw_len = htobe64(file_op->prw_len);
		break;
	case IOSHARK_READ:
	case IOSHARK_WRITE:
		file_op->rw_len = htobe64(file_op->rw_len);
		break;
	case IOSHARK_MMAP:
	case IOSHARK_MMAP2:
		file_op->mmap_offset = htobe64(file_op->mmap_offset);
		file_op->mmap_len = htobe64(file_op->mmap_len);
		file_op->mmap_prot = htobe32(file_op->mmap_prot);
		break;
	case IOSHARK_OPEN:
		file_op->open_flags = htobe32(file_op->open_flags);
		file_op->open_mode = htobe32(file_op->open_mode);
		break;
	case IOSHARK_FSYNC:
	case IOSHARK_FDATASYNC:
		break;
	case IOSHARK_CLOSE:
		break;
	default:
		fprintf(stderr, "%s: unknown FILE_OP %d\n",
			progname, op);
		exit(EXIT_FAILURE);
		break;
	}
	return fwrite(file_op, sizeof(struct ioshark_file_operation), 1, fp);
}
