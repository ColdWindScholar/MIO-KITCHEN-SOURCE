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
#include <sys/syscall.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <sys/stat.h>
#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <assert.h>
#include "ioshark.h"
#include "ioshark_bench.h"

/*
 * The purpose of this code is to convert mmap() calls into
 * a mix of (semi)-random reads and writes.
 * PROT_READ => 4KB/8KB/16KB random reads.
 * PROT_WRITE => adds 4KB random writes.
 */

extern char *progname;

#define IOSHARK_MAX_MMAP_IOLEN	(16*1024)

#define MMAP_ENTS		16

struct mmap_io_ent_tab_s {
	off_t offset;
	size_t len;
};

struct mmap_io_ent_s {
	int				num_entries;
	struct mmap_io_ent_tab_s	table[MMAP_ENTS + 1];
	size_t				resid;
};

static void
setup_mmap_io_state(struct mmap_io_ent_s *mio,
		    size_t total_len, off_t offset)
{
	int slice;

	memset(mio, 0, sizeof(struct mmap_io_ent_s));
	mio->resid = total_len;
	slice = MAX(IOSHARK_MAX_MMAP_IOLEN,
		    total_len / MMAP_ENTS);
	while (total_len > 0) {
		assert(mio->num_entries < MMAP_ENTS + 1);
		mio->table[mio->num_entries].offset = offset;
		mio->table[mio->num_entries].len =
			MIN((u_int64_t)total_len, (u_int64_t)slice);
		total_len -= mio->table[mio->num_entries].len;
		offset += mio->table[mio->num_entries].len;
		mio->num_entries++;
	}
}

static size_t
mmap_getnext_off_len(struct mmap_io_ent_s *mio,
		     off_t *offset)
{
	int i;
	int find_rand_index[MMAP_ENTS + 1];
	int rand_index_len = 0;
	size_t iolength;

	if (mio->resid == 0)
		return 0;
	/* Pick a slot with residual length > 0 at random first */
	for (i = 0 ; i < MMAP_ENTS + 1 ; i++) {
		if (mio->table[i].len > 0)
			find_rand_index[rand_index_len++] = i;
	}
	i = find_rand_index[rand() % rand_index_len];
	/* Randomize iolength 4K-16K */
	iolength = ((rand() % 4) + 1) * 4096;
	iolength = MIN(mio->table[i].len, iolength);
	*offset = mio->table[i].offset;
	mio->table[i].offset += iolength;
	mio->table[i].len -= iolength;
	mio->resid -= iolength;
	return iolength;
}

static void
mmap_do_io(void *db_node, int prot, off_t offset, size_t len,
	   char **bufp, int *buflen, u_int64_t *op_counts,
	   struct rw_bytes_s *rw_bytes)
{
	char *p;
	int ret;

	if (!(prot & IOSHARK_PROT_WRITE)) {
		/* Only preads */
		p = get_buf(bufp, buflen, len, 0);
		ret = pread(files_db_get_fd(db_node),
			    p, len, offset);
		rw_bytes->bytes_read += len;
		if (ret < 0) {
			fprintf(stderr,
				"%s: mapped pread(%s %zu %lu) error fd=%d %s\n",
				progname, files_db_get_filename(db_node),
				len, offset, files_db_get_fd(db_node),
				strerror(errno));
			exit(EXIT_FAILURE);
		}
		op_counts[IOSHARK_MAPPED_PREAD]++;
	} else {
		/* 50-50 R/W */
		if ((rand() % 2) == 1) {
			p = get_buf(bufp, buflen, len, 1);
			ret = pwrite(files_db_get_fd(db_node),
				     p, len, offset);
			rw_bytes->bytes_written += len;
			if (ret < 0) {
#if 0
				fprintf(stderr,
					"%s: mapped pwrite failed, file unwriteable ? open_flags=%x\n",
					progname,
					fcntl(files_db_get_fd(db_node), F_GETFL));
				exit(EXIT_FAILURE);
#endif
			} else
				op_counts[IOSHARK_MAPPED_PWRITE]++;
		} else {
			p = get_buf(bufp, buflen, len, 0);
			ret = pread(files_db_get_fd(db_node),
				    p, len, offset);
			rw_bytes->bytes_read += len;
			if (ret < 0) {
				fprintf(stderr,
				"%s: mapped pread(%s %zu %lu) error fd=%d %s\n",
					progname, files_db_get_filename(db_node),
					len,
					offset, files_db_get_fd(db_node),
					strerror(errno));
				exit(EXIT_FAILURE);
			}
			op_counts[IOSHARK_MAPPED_PREAD]++;
		}
	}
}

void
ioshark_handle_mmap(void *db_node,
		    struct ioshark_file_operation *file_op,
		    char **bufp, int *buflen, u_int64_t *op_counts,
		    struct rw_bytes_s *rw_bytes)
{
	off_t offset = file_op->mmap_offset;
	size_t len = file_op->mmap_len;
	int prot = file_op->mmap_prot;
	struct mmap_io_ent_s mio;
	struct stat statbuf;

	if (fstat(files_db_get_fd(db_node), &statbuf) < 0) {
		fprintf(stderr,
			"%s: fstat failure %s\n",
			__func__, strerror(errno));
		exit(EXIT_FAILURE);
	}
	/*
	 * The size of the file better accommodate offset + len
	 * Else there is an issue with pre-creation
	 */
	assert(offset + len <= statbuf.st_size);
	if (len <= IOSHARK_MAX_MMAP_IOLEN) {
		mmap_do_io(db_node, prot, offset, len,
			   bufp, buflen, op_counts,
			   rw_bytes);
		return;
	}
	setup_mmap_io_state(&mio, len, offset);
	assert(mio.num_entries > 0);
	while ((len = mmap_getnext_off_len(&mio, &offset))) {
		assert((offset + len) <=
		       (file_op->mmap_offset + file_op->mmap_len));
		mmap_do_io(db_node, prot, offset, len, bufp, buflen,
			   op_counts, rw_bytes);
	}
}
