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

#ifdef IOSHARK_MAIN
const char *IO_op[] = {
	"LSEEK",
	"LLSEEK",
	"PREAD64",
	"PWRITE64",
	"READ",
	"WRITE",
	"MMAP",
	"MMAP2",
	"OPEN",
	"FSYNC",
	"FDATASYNC",
	"CLOSE",
	"MAPPED_PREAD",
	"MAPPED_PWRITE",
	"MAX_FILE_OP"
};
#endif

#define MAX(A, B)	((A) > (B) ? (A) : (B))
#define MIN(A, B)	((A) < (B) ? (A) : (B))

#define MINBUFLEN	(16*1024)

#define FILE_DB_HASHSIZE	8192

struct files_db_s {
	char *filename;
	int fileno;
	size_t	size;
	int fd;
	int readonly;
	int debug_open_flags;
	struct files_db_s *next;
};

struct files_db_handle {
	struct files_db_s *files_db_buckets[FILE_DB_HASHSIZE];
};

struct IO_operation_s {
	char *IO_op;
};

struct rw_bytes_s {
	u_int64_t bytes_read;
	u_int64_t bytes_written;
};

static inline void
files_db_update_size(void *node, u_int64_t new_size)
{
	struct files_db_s *db_node = (struct files_db_s *)node;

	if (db_node->size < new_size)
		db_node->size = new_size;
}

static inline void
files_db_update_filename(void *node, char *filename)
{
	((struct files_db_s *)node)->filename = strdup(filename);
}

static inline int
files_db_get_fileno(void *node)
{
	return (((struct files_db_s *)node)->fileno);
}

static inline int
files_db_get_fd(void *node)
{
	return (((struct files_db_s *)node)->fd);
}

static inline char *
files_db_get_filename(void *node)
{
	return (((struct files_db_s *)node)->filename);
}

static inline int
files_db_readonly(void *node)
{
	return (((struct files_db_s *)node)->readonly);
}

static inline u_int64_t
get_msecs(struct timeval *tv)
{
	return ((tv->tv_sec * 1000) + (tv->tv_usec / 1000));
}

static inline u_int64_t
get_usecs(struct timeval *tv)
{
	return (tv->tv_usec % 1000);
}

static inline void
update_delta_time(struct timeval *start,
		  struct timeval *destination)
{
	struct timeval res, finish;

	(void)gettimeofday(&finish, (struct timezone *)NULL);
	timersub(&finish, start, &res);
	timeradd(destination, &res, &finish);
	*destination = finish;
}

void *files_db_create_handle(void);
void *files_db_lookup_byfileno(void *handle, int fileno);
void *files_db_add_byfileno(void *handle, int fileno, int readonly);
void files_db_update_fd(void *node, int fd);
void files_db_unlink_files(void *db_handle);
void files_db_close_files(void *handle);
void files_db_close_fd(void *node);
void files_db_free_memory(void *handle);
void create_file(char *path, size_t size,
		 struct rw_bytes_s *rw_bytes);
char *get_buf(char **buf, int *buflen, int len, int do_fill);
void files_db_fsync_discard_files(void *handle);
void print_op_stats(u_int64_t *op_counts);
void print_bytes(char *desc, struct rw_bytes_s *rw_bytes);
void ioshark_handle_mmap(void *db_node,
			 struct ioshark_file_operation *file_op,
			 char **bufp, int *buflen, u_int64_t *op_counts,
			 struct rw_bytes_s *rw_bytes);
void capture_util_state_before(void);
void report_cpu_disk_util(void);

char *get_ro_filename(int ix);
void init_filename_cache(void);
void free_filename_cache(void);
int is_readonly_mount(char *filename, size_t size);

int ioshark_read_header(FILE *fp, struct ioshark_header *header);
int ioshark_read_file_state(FILE *fp, struct ioshark_file_state *state);
int ioshark_read_file_op(FILE *fp, struct ioshark_file_operation *file_op);
