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
#include <endian.h>
#include "ioshark.h"

char *progname;

struct ioshark_header_old {
	int	num_files;
	int	num_io_operations;
};

struct ioshark_file_operation_old {
	/* delta us between previous file op and this */
	u_int64_t		delta_us;
	enum file_op		file_op;
	int			fileno;
	union {
		struct lseek_args_old {
#define lseek_offset_old	u.lseek_a.offset
#define lseek_action_old	u.lseek_a.action
			off_t	offset;
			int action;
		} lseek_a;
		struct prw_args_old {
#define prw_offset_old		u.prw_a.offset
#define prw_len_old		u.prw_a.len
			off_t	offset;
			size_t	len;
		} prw_a;
#define rw_len_old		u.rw_a.len
		struct rw_args_old {
			size_t	len;
		} rw_a;
#define mmap_offset_old		u.mmap_a.offset
#define mmap_len_old		u.mmap_a.len
#define mmap_prot_old		u.mmap_a.prot
		struct mmap_args_old {
			off_t	offset;
			size_t	len;
			int	prot;
	} mmap_a;
#define open_flags_old		u.open_a.flags
#define open_mode_old		u.open_a.mode
		struct open_args_old {
			int	flags;
			mode_t	mode;
		} open_a;
	} u;
};

struct ioshark_file_state_old {
	int	fileno;	/* 1..num_files, with files name ioshark.<fileno> */
	size_t	size;
	int	global_filename_ix;
};

void usage(void)
{
	fprintf(stderr, "%s in_file out_file\n", progname);
}

int main(int argc, char **argv)
{
	FILE *old_fp, *new_fp;
	char *infile, *outfile;
	struct ioshark_header new_header;
	struct ioshark_file_operation new_disk_file_op;
	struct ioshark_header_old old_header;
	struct ioshark_file_operation_old old_disk_file_op;
	struct ioshark_file_state new_file_state;
	struct ioshark_file_state_old old_file_state;
	struct stat st;
	int i;
	u_int64_t aggr_old_file_size = 0;
	u_int64_t aggr_new_file_size = 0;

	progname = argv[0];
	if (argc != 3) {
		usage();
		exit(EXIT_FAILURE);
	}
	infile = argv[1];
	outfile = argv[2];
	if (stat(infile, &st) < 0) {
		fprintf(stderr, "%s Can't stat %s\n",
			progname, infile);
		exit(EXIT_FAILURE);
	}
	if (st.st_size == 0) {
		fprintf(stderr, "%s Empty file %s\n",
			progname, infile);
		exit(EXIT_FAILURE);
	}
	old_fp = fopen(infile, "r");
	if (old_fp == NULL) {
		fprintf(stderr, "%s Can't open %s\n",
			progname, infile);
		exit(EXIT_FAILURE);
	}
	new_fp = fopen(outfile, "w+");
	if (new_fp == NULL) {
		fprintf(stderr, "%s Can't open outfile\n",
			progname);
		exit(EXIT_FAILURE);
	}
	/* Convert header */
	if (fread(&old_header, sizeof(struct ioshark_header_old),
		  1, old_fp) != 1) {
		fprintf(stderr,
			"%s Read error Header\n",
			progname);
		exit(EXIT_FAILURE);
	}
	new_header.version = IOSHARK_VERSION;
	new_header.num_files = old_header.num_files;
	new_header.num_io_operations = old_header.num_io_operations;
	new_header.version = htobe64(new_header.version);
	new_header.num_files = htobe64(new_header.num_files);
	new_header.num_io_operations =
		htobe64(new_header.num_io_operations);
	if (fwrite(&new_header, sizeof(struct ioshark_header),
		   1, new_fp) != 1) {
		fprintf(stderr,
			"%s Write error Header\n",
			progname);
		exit(EXIT_FAILURE);
	}
	for (i = 0 ; i < old_header.num_files ; i++) {
		if (fread(&old_file_state,
			  sizeof(struct ioshark_file_state_old),
			  1, old_fp) != 1) {
			fprintf(stderr,
				"%s Read error file state\n",
				progname);
			exit(EXIT_FAILURE);
		}
		new_file_state.fileno = old_file_state.fileno;
		new_file_state.size = old_file_state.size;
		aggr_old_file_size += old_file_state.size;
		new_file_state.global_filename_ix =
			old_file_state.global_filename_ix;
		new_file_state.fileno = htobe64(new_file_state.fileno);
		new_file_state.size = htobe64(new_file_state.size);
		aggr_new_file_size += be64toh(new_file_state.size);
		new_file_state.global_filename_ix =
			htobe64(new_file_state.global_filename_ix);
		if (fwrite(&new_file_state,
			   sizeof(struct ioshark_file_state), 1, new_fp) != 1) {
			fprintf(stderr,
				"%s Write error file state\n",
				progname);
			exit(EXIT_FAILURE);
		}
	}
	if (aggr_new_file_size != aggr_old_file_size) {
		fprintf(stderr,
			"%s Aggr file size mismath %lu != %lu\n",
			progname, aggr_new_file_size, aggr_old_file_size);
		exit(EXIT_FAILURE);
	}

	for (i = 0 ; i < old_header.num_io_operations ; i++) {
		enum file_op op;

		if (fread(&old_disk_file_op,
			  sizeof(struct ioshark_file_operation_old),
			  1, old_fp) != 1)  {
			fprintf(stderr,
				"%s Read error file op\n",
				progname);
			exit(EXIT_FAILURE);
		}
		op = old_disk_file_op.file_op;
		new_disk_file_op.delta_us = old_disk_file_op.delta_us;
		new_disk_file_op.delta_us =
			htobe64(new_disk_file_op.delta_us);
		new_disk_file_op.ioshark_io_op = op;
		new_disk_file_op.op_union.enum_size =
			htobe32(new_disk_file_op.op_union.enum_size);
		new_disk_file_op.fileno = old_disk_file_op.fileno;
		new_disk_file_op.fileno = htobe64(new_disk_file_op.fileno);
		switch (op) {
		case IOSHARK_LSEEK:
		case IOSHARK_LLSEEK:
			new_disk_file_op.lseek_offset =
				old_disk_file_op.lseek_offset_old;
			new_disk_file_op.lseek_action =
				old_disk_file_op.lseek_action_old;
			new_disk_file_op.lseek_offset =
				htobe64(new_disk_file_op.lseek_offset);
			new_disk_file_op.lseek_action =
				htobe32(new_disk_file_op.lseek_action);
			break;
		case IOSHARK_PREAD64:
		case IOSHARK_PWRITE64:
			new_disk_file_op.prw_offset =
				old_disk_file_op.prw_offset_old;
			new_disk_file_op.prw_len =
				old_disk_file_op.prw_len_old;
			new_disk_file_op.prw_offset =
				htobe64(new_disk_file_op.prw_offset);
			new_disk_file_op.prw_len =
				htobe64(new_disk_file_op.prw_len);
			break;
		case IOSHARK_READ:
		case IOSHARK_WRITE:
			new_disk_file_op.rw_len =
				old_disk_file_op.rw_len_old;
			new_disk_file_op.rw_len =
				htobe64(new_disk_file_op.rw_len);
			break;
		case IOSHARK_MMAP:
		case IOSHARK_MMAP2:
			new_disk_file_op.mmap_offset =
				old_disk_file_op.mmap_offset_old;
			new_disk_file_op.mmap_len =
				old_disk_file_op.mmap_len_old;
			new_disk_file_op.mmap_prot =
				old_disk_file_op.mmap_prot;
			new_disk_file_op.mmap_offset =
				htobe64(new_disk_file_op.mmap_offset);
			new_disk_file_op.mmap_len =
				htobe64(new_disk_file_op.mmap_len);
			new_disk_file_op.mmap_prot =
				htobe32(new_disk_file_op.mmap_prot);
			break;
		case IOSHARK_OPEN:
			new_disk_file_op.open_flags =
				old_disk_file_op.open_flags_old;
			new_disk_file_op.open_mode =
				old_disk_file_op.open_mode_old;
			new_disk_file_op.open_flags =
				htobe32(new_disk_file_op.open_flags);
			new_disk_file_op.open_mode =
				htobe32(new_disk_file_op.open_mode);
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
		if (fwrite(&new_disk_file_op,
			   sizeof(struct ioshark_file_operation),
			   1, new_fp) != 1) {
			fprintf(stderr,
				"%s Write error file op\n",
				progname);
			exit(EXIT_FAILURE);
		}
	}
}
