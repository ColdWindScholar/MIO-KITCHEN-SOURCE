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
#include <sys/types.h>
#include <unistd.h>

#include "ioshark.h"

#define FILE_DB_HASHSIZE	8192

struct files_db_s {
	char *filename;
	int fileno;
	struct files_db_s *next;
	size_t	size;
	int	global_filename_ix;
};

/* Lifted from Wikipedia Jenkins Hash function page */
static inline u_int32_t
jenkins_one_at_a_time_hash(char *key, size_t len)
{
	u_int32_t hash, i;

	for(hash = i = 0; i < len; ++i) {
		hash += key[i];
		hash += (hash << 10);
		hash ^= (hash >> 6);
	}
	hash += (hash << 3);
	hash ^= (hash >> 11);
	hash += (hash << 15);
	return hash;
}

static inline void
files_db_update_size(void *node, u_int64_t new_size)
{
	struct files_db_s *db_node = (struct files_db_s *)node;

	if (db_node->size < new_size)
		db_node->size = new_size;
}

static inline void
files_db_add_to_size(void *node, u_int64_t size_incr)
{
	((struct files_db_s *)node)->size += size_incr;
}

static inline int
files_db_get_fileno(void *node)
{
	return (((struct files_db_s *)node)->fileno);
}

static inline char *
files_db_get_filename(void *node)
{
	return (((struct files_db_s *)node)->filename);
}

void *files_db_create_handle(void);
void files_db_write_objects(FILE *fp);
void *files_db_add(char *filename);
void *files_db_lookup(char *filename);
int files_db_get_total_obj(void);
void init_filename_cache(void);
void store_filename_cache(void);

int ioshark_write_header(FILE *fp, struct ioshark_header *header);
int ioshark_write_file_state(FILE *fp, struct ioshark_file_state *state);
int ioshark_write_file_op(FILE *fp, struct ioshark_file_operation *file_op);
