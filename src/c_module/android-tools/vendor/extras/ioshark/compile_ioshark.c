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
#include "compile_ioshark.h"

char *progname;

char in_buf[2048];

struct flags_map_s {
	char *flag_str;
	int flag;
};

#define ARRAY_SIZE(a)	(sizeof(a) / sizeof(a[0]))

struct flags_map_s open_flags_map[] = {
	{ "O_RDONLY", O_RDONLY },
	{ "O_WRONLY", O_WRONLY },
	{ "O_RDWR", O_RDWR },
	{ "O_CREAT", O_CREAT },
	{ "O_SYNC", O_SYNC },
	{ "O_TRUNC", O_TRUNC },
	{ "O_EXCL", O_EXCL },
	{ "O_APPEND", O_APPEND },
	{ "O_NOATIME", O_NOATIME },
	{ "O_ASYNC", O_ASYNC },
	{ "O_CLOEXEC", O_CLOEXEC },
	{ "O_DIRECT", O_DIRECT },
	{ "O_DIRECTORY", O_DIRECTORY },
	{ "O_LARGEFILE", O_LARGEFILE },
	{ "O_NOCTTY", O_NOCTTY },
	{ "O_NOFOLLOW", O_NOFOLLOW },
	{ "O_NONBLOCK", O_NONBLOCK },
	{ "O_NDELAY", O_NDELAY },
	{ "O_PATH", O_PATH }
};

struct flags_map_s lseek_action_map[] = {
	{ "SEEK_SET", SEEK_SET },
	{ "SEEK_CUR", SEEK_CUR },
	{ "SEEK_END", SEEK_END }
};

struct flags_map_s fileop_map[] = {
	{ "lseek", IOSHARK_LSEEK },
	{ "_llseek", IOSHARK_LLSEEK },
	{ "pread64", IOSHARK_PREAD64 },
	{ "pwrite64", IOSHARK_PWRITE64 },
	{ "read", IOSHARK_READ },
	{ "write", IOSHARK_WRITE },
	{ "mmap", IOSHARK_MMAP },
	{ "mmap2", IOSHARK_MMAP2 },
	{ "openat", IOSHARK_OPEN },
	{ "fsync", IOSHARK_FSYNC },
	{ "fdatasync", IOSHARK_FDATASYNC },
	{ "close", IOSHARK_CLOSE },
	{ "ftrace", IOSHARK_MAPPED_PREAD }
};

struct in_mem_file_op {
	struct ioshark_file_operation disk_file_op;
	struct in_mem_file_op *next;
};

struct in_mem_file_op *in_mem_file_op_head = NULL, *in_mem_file_op_tail = NULL;

void usage(void)
{
	fprintf(stderr, "%s in_file out_file\n", progname);
}

void
init_prev_time(struct timeval *tv)
{
	tv->tv_sec = tv->tv_usec = 0;
}

/*
 * delta ts is the time delta from the previous IO in this tracefile.
 */
static u_int64_t
get_delta_ts(char *buf, struct timeval *prev)
{
	struct timeval op_tv, tv_res;

	sscanf(buf, "%lu.%lu", &op_tv.tv_sec, &op_tv.tv_usec);
	/* First item */
	if (prev->tv_sec == 0 && prev->tv_usec == 0)
		tv_res.tv_sec = tv_res.tv_usec = 0;
	else
		timersub(&op_tv, prev, &tv_res);
	*prev = op_tv;
	return (tv_res.tv_usec + (tv_res.tv_sec * 1000000));
}

void
get_tracetype(char *buf, char *trace_type)
{
	char *s, *s2;

	*trace_type = '\0';
	s = strchr(buf, ' ');
	if (s == NULL) {
		fprintf(stderr,
			"%s Malformed Trace Type ? %s\n",
			progname, __func__);
		exit(EXIT_FAILURE);
	}
	while (*s == ' ')
		s++;
	if (sscanf(s, "%s", trace_type) != 1) {
		fprintf(stderr,
			"%s Malformed Trace Type ? %s\n",
			progname, __func__);
		exit(EXIT_FAILURE);
	}
	if (strcmp(trace_type, "strace") != 0 &&
	    strcmp(trace_type, "ftrace") != 0) {
		fprintf(stderr,
			"%s Unknown/Missing Trace Type (has to be strace|ftrace) %s\n",
			progname, __func__);
		exit(EXIT_FAILURE);
	}
	/*
	 * Remove the keyword "strace"/"ftrace" from the buffer
	 */
	s2 = strchr(s, ' ');
	if (s2 == NULL) {
		fprintf(stderr,
			"%s Malformed Trace Type ? %s\n",
			progname, __func__);
		exit(EXIT_FAILURE);
	}
	while (*s2 == ' ')
		s2++;
	if (*s2  == '\0') {
		/*
		 * Premature end of input record
		 */
		fprintf(stderr,
			"%s Mal-formed strace/ftrace record %s:%s\n",
			progname, __func__, buf);
		exit(EXIT_FAILURE);
	}
	/* strcpy() expects non-overlapping buffers, but bcopy doesn't */
	bcopy(s2, s, strlen(s2) + 1);
}

void
get_pathname(char *buf, char *pathname, enum file_op file_op)
{
	char *s, *s2, save;

	if (file_op == IOSHARK_MAPPED_PREAD) {
		s = strchr(buf, '/');
		if (s == NULL) {
			fprintf(stderr, "%s: Malformed line: %s\n",
				__func__, buf);
			exit(EXIT_FAILURE);
		}
		s2 = strchr(s, ' ');
		if (s2 == NULL) {
			fprintf(stderr, "%s: Malformed line: %s\n",
				__func__, buf);
			exit(EXIT_FAILURE);
		}
	} else {
		if (file_op == IOSHARK_OPEN)
			s = strchr(buf, '"');
		else
			s = strchr(buf, '<');
		if (s == NULL) {
			fprintf(stderr, "%s: Malformed line: %s\n",
				__func__, buf);
			exit(EXIT_FAILURE);
		}
		s += 1;
		if (file_op == IOSHARK_OPEN)
			s2 = strchr(s, '"');
		else
			s2 = strchr(s, '>');
		if (s2 == NULL) {
			fprintf(stderr, "%s: Malformed line: %s\n",
				__func__, buf);
			exit(EXIT_FAILURE);
		}
	}
	save = *s2;
	*s2 = '\0';
	strcpy(pathname, s);
	*s2 = save;
}

void
get_syscall(char *buf, char *syscall)
{
	char *s, *s2;

	s = strchr(buf, ' ');
	if (s == NULL) {
		fprintf(stderr, "%s: Malformed line: %s\n",
			__func__, buf);
		exit(EXIT_FAILURE);
	}
	s += 1;
	s2 = strchr(s, '(');
	if (s2 == NULL) {
		fprintf(stderr, "%s: Malformed line: %s\n",
			__func__, buf);
		exit(EXIT_FAILURE);
	}
	*s2 = '\0';
	strcpy(syscall, s);
	*s2 = '(';
}

void
get_mmap_offset_len_prot(char *buf, int *prot, off_t *offset, u_int64_t *len)
{
	char *s, *s1;
	int i;
	char protstr[128];

	s = strchr(buf, ',');
	if (s == NULL) {
		fprintf(stderr, "%s: Malformed line: %s\n",
			__func__, buf);
		exit(EXIT_FAILURE);
	}
	s += 2;
	sscanf(s, "%ju", len);
	s1 = strchr(s, ',');
	if (s1 == NULL) {
		fprintf(stderr, "%s: Malformed line: %s\n",
			__func__, buf);
		exit(EXIT_FAILURE);
	}
	s1 += 2;
	s = strchr(s1, ',');
	if (s == NULL) {
		fprintf(stderr, "%s: Malformed line: %s\n",
			__func__, buf);
		exit(EXIT_FAILURE);
	}
	*s = '\0';
	strcpy(protstr, s1);
	*prot = 0;
	if (strstr(protstr, "PROT_READ"))
		*prot |= IOSHARK_PROT_READ;
	if (strstr(protstr, "PROT_WRITE"))
		*prot |= IOSHARK_PROT_WRITE;
	*s = ',';
	s += 2;
	for (i = 0 ; i < 2 ; i++) {
		s = strchr(s, ',');
		if (s == NULL) {
			fprintf(stderr, "%s: Malformed line: %s\n",
				__func__, buf);
			exit(EXIT_FAILURE);
		}
		s += 2;
	}
	sscanf(s, "%jx", offset);
}

void
get_lseek_offset_action(char *buf, enum file_op op,
			off_t *offset, char *action)
{
	char *s, *s2;

	s = strchr(buf, ',');
	if (s == NULL) {
		fprintf(stderr, "%s: Malformed line: %s\n",
			__func__, buf);
		exit(EXIT_FAILURE);
	}
	s += 2;
	sscanf(s, "%ju", offset);
	s = strchr(s, ',');
	if (s == NULL) {
		fprintf(stderr, "%s: Malformed line: %s\n",
			__func__, buf);
		exit(EXIT_FAILURE);
	}
	s += 2;
	if (op == IOSHARK_LLSEEK) {
		s = strchr(s, ',');
		if (s == NULL) {
			fprintf(stderr, "%s: Malformed line: %s\n",
				__func__, buf);
			exit(EXIT_FAILURE);
		}
		s += 2;
	}
	s2 = strchr(s, ')');
	if (s2 == NULL) {
		fprintf(stderr, "%s: Malformed line: %s\n",
			__func__, buf);
		exit(EXIT_FAILURE);
	}
	*s2 = '\0';
	strcpy(action, s);
	*s2 = ')';
}

void
get_rw_len(char *buf,
	   u_int64_t *len)
{
	char *s_len;

	s_len = strrchr(buf, ',');
	if (s_len == NULL) {
		fprintf(stderr, "%s: Malformed line: %s\n",
			__func__, buf);
		exit(EXIT_FAILURE);
	}
	sscanf(s_len + 2, "%ju", len);
}

void
get_prw64_offset_len(char *buf,
		     off_t *offset,
		     u_int64_t *len)
{
	char *s_offset, *s_len;

	s_offset = strrchr(buf, ',');
	if (s_offset == NULL) {
		fprintf(stderr, "%s: Malformed line 1: %s\n",
			__func__, buf);
		exit(EXIT_FAILURE);
	}
	*s_offset = '\0';
	s_len = strrchr(buf, ',');
	if (s_len == NULL) {
		fprintf(stderr, "%s: Malformed line 2: %s\n",
			__func__, buf);
		exit(EXIT_FAILURE);
	}
	*s_offset = ',';
	sscanf(s_len + 2, "%ju", len);
	sscanf(s_offset + 2, "%ju", offset);
}


void
get_ftrace_offset_len(char *buf,
		      off_t *offset,
		      u_int64_t *len)
{
	char *s_offset;

	s_offset = strchr(buf, '/');
	if (s_offset == NULL) {
		fprintf(stderr, "%s: Malformed line 1: %s\n",
			__func__, buf);
		exit(EXIT_FAILURE);
	}
	s_offset = strchr(s_offset, ' ');
	if (s_offset == NULL) {
		fprintf(stderr, "%s: Malformed line 2: %s\n",
			__func__, buf);
		exit(EXIT_FAILURE);
	}
	while (*s_offset == ' ')
		s_offset++;
	if (sscanf(s_offset, "%ju %ju", offset, len) != 2) {
		fprintf(stderr, "%s: Malformed line 3: %s\n",
			__func__, buf);
		exit(EXIT_FAILURE);
	}
}

void
get_openat_flags_mode(char *buf, char *flags, mode_t *mode)
{
	char *s, *s2, lookfor;

	s = strchr(buf, ',');
	if (s == NULL) {
		fprintf(stderr, "%s: Malformed line: %s\n",
			__func__, buf);
		exit(EXIT_FAILURE);
	}
	s += 2;
	s = strchr(s, ',');
	if (s == NULL) {
		fprintf(stderr, "%s: Malformed line: %s\n",
			__func__, buf);
		exit(EXIT_FAILURE);
	}
	s += 2;
	if (strstr(s, "O_CREAT") == NULL)
		lookfor = ')';
	else
		lookfor = ',';
	s2 = strchr(s, lookfor);
	if (s2 == NULL) {
		fprintf(stderr, "%s: Malformed line: %s\n",
			__func__, buf);
		exit(EXIT_FAILURE);
	}
	*s2 = '\0';
	strcpy(flags, s);
	*s2 = lookfor;
	if (strstr(s, "O_CREAT") != NULL) {
		s = s2 + 2;
		s2 = strchr(s, ')');
		if (s2 == NULL) {
			fprintf(stderr, "%s: Malformed line: %s\n",
				__func__, buf);
			exit(EXIT_FAILURE);
		}
		*s2 = '\0';
		sscanf(s, "%o", mode);
		*s2 = ')';
	}
}

int
lookup_map(char *s, struct flags_map_s *flags_map, int maplen)
{
	int found = 0, flag = 0;
	int i;

	while (isspace(*s))
		s++;
	for (i = 0 ; i < maplen ; i++) {
		if (strcmp(flags_map[i].flag_str, s) == 0) {
			flag = flags_map[i].flag;
			found = 1;
			break;
		}
	}
	if (found == 0) {
		fprintf(stderr, "%s: Unknown syscall %s\n",
			__func__, s);
		exit(1);
	}
	return flag;
}

int
map_open_flags(char *s)
{
	int flags = 0;
	char *s1;

	while ((s1 = strchr(s, '|'))) {
		*s1 = '\0';
		flags |= lookup_map(s, open_flags_map,
				    ARRAY_SIZE(open_flags_map));
		*s1 = '|';
		s = s1 + 1;
	}
	/* Last option */
	flags |= lookup_map(s, open_flags_map,
			    ARRAY_SIZE(open_flags_map));
	return flags;
}

int
map_lseek_action(char *s)
{
	int flags = 0;
	char *s1;

	while ((s1 = strchr(s, '|'))) {
		*s1 = '\0';
		flags |= lookup_map(s, lseek_action_map,
				    ARRAY_SIZE(lseek_action_map));
		*s1 = '|';
		s = s1 + 1;
	}
	/* Last option */
	flags |= lookup_map(s, lseek_action_map,
			    ARRAY_SIZE(lseek_action_map));
	return flags;
}

enum file_op
map_syscall(char *syscall)
{
	return lookup_map(syscall, fileop_map,
			  ARRAY_SIZE(fileop_map));
}

/*
 * For each tracefile, we first create in-memory structures, then once
 * we've processed each tracefile completely, we write out the in-memory
 * structures and free them.
 */
int main(int argc, char **argv)
{
	FILE *fp;
	char path[512];
	char syscall[512];
	char lseek_action_str[512];
	char *s;
	char open_flags_str[64];
	void *db_node;
	int num_io_operations = 0;
	struct ioshark_header header;
	struct ioshark_file_operation *disk_file_op;
	struct in_mem_file_op *in_mem_fop;
	struct stat st;
	char *infile, *outfile;
	struct timeval prev_time;
	char trace_type[64];

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
	init_prev_time(&prev_time);
	init_filename_cache();
	fp = fopen(infile, "r");
	if (fp == NULL) {
		fprintf(stderr, "%s Can't open %s\n",
			progname, infile);
		exit(EXIT_FAILURE);
	}
	while (fgets(in_buf, 2048, fp)) {
		s = in_buf;
		while (isspace(*s))
			s++;
		in_mem_fop = malloc(sizeof(struct in_mem_file_op));
		disk_file_op = &in_mem_fop->disk_file_op;
		disk_file_op->delta_us = get_delta_ts(s, &prev_time);
		get_tracetype(s, trace_type);
		if (strcmp(trace_type, "strace") == 0) {
			get_syscall(s, syscall);
			disk_file_op->ioshark_io_op = map_syscall(syscall);
		} else
			disk_file_op->ioshark_io_op = map_syscall("ftrace");
		get_pathname(s, path, disk_file_op->ioshark_io_op);
		db_node = files_db_add(path);
		disk_file_op->fileno = files_db_get_fileno(db_node);
		switch (disk_file_op->ioshark_io_op) {
		case IOSHARK_LLSEEK:
		case IOSHARK_LSEEK:
			get_lseek_offset_action(s,
					disk_file_op->ioshark_io_op,
					(off_t *)&disk_file_op->lseek_offset,
					lseek_action_str);
			disk_file_op->lseek_action =
				map_lseek_action(lseek_action_str);
			if (disk_file_op->lseek_action == SEEK_SET)
				files_db_update_size(db_node,
						     disk_file_op->lseek_offset);
			break;
		case IOSHARK_PREAD64:
		case IOSHARK_PWRITE64:
			get_prw64_offset_len(s,
					     (off_t *)&disk_file_op->prw_offset,
					     (u_int64_t *)&disk_file_op->prw_len);
			files_db_update_size(db_node,
					     disk_file_op->prw_offset +
					     disk_file_op->prw_len);
			break;
		case IOSHARK_READ:
		case IOSHARK_WRITE:
			get_rw_len(s, (u_int64_t *)&disk_file_op->rw_len);
			files_db_add_to_size(db_node,
					     disk_file_op->rw_len);
			break;
		case IOSHARK_MMAP:
		case IOSHARK_MMAP2:
			get_mmap_offset_len_prot(s,
			            (int *)&disk_file_op->mmap_prot,
				    (off_t *)&disk_file_op->mmap_offset,
				    (u_int64_t *)&disk_file_op->mmap_len);
			files_db_update_size(db_node,
				     disk_file_op->mmap_offset +
				     disk_file_op->mmap_len);
			break;
		case IOSHARK_OPEN:
			disk_file_op->open_mode = 0;
			get_openat_flags_mode(s, open_flags_str,
				      &disk_file_op->open_mode);
			disk_file_op->open_flags =
				map_open_flags(open_flags_str);
			break;
		case IOSHARK_FSYNC:
		case IOSHARK_FDATASYNC:
			break;
		case IOSHARK_CLOSE:
			break;
		case IOSHARK_MAPPED_PREAD:
			/* Convert a mmap'ed read into a PREAD64 */
			disk_file_op->ioshark_io_op = IOSHARK_PREAD64;
			get_ftrace_offset_len(s,
					      (off_t *)&disk_file_op->prw_offset,
					      (u_int64_t *)&disk_file_op->prw_len);
			files_db_update_size(db_node,
					     disk_file_op->prw_offset +
					     disk_file_op->prw_len);
			break;
		default:
			break;
		}
		/* Chain at the end */
		num_io_operations++;
		in_mem_fop->next = NULL;
		if (in_mem_file_op_head == NULL) {
			in_mem_file_op_tail = in_mem_fop;
			in_mem_file_op_head = in_mem_fop;
		} else {
			in_mem_file_op_tail->next = in_mem_fop;
			in_mem_file_op_tail = in_mem_fop;
		}
	}
	fclose(fp);
	/*
	 * Now we can write everything out to the output tracefile.
	 */
	fp = fopen(outfile, "w+");
	if (fp == NULL) {
		fprintf(stderr, "%s Can't open trace.outfile\n",
			progname);
		exit(EXIT_FAILURE);
	}
	header.num_io_operations = num_io_operations;
	header.num_files = files_db_get_total_obj();
	if (ioshark_write_header(fp, &header) != 1) {
		fprintf(stderr, "%s Write error trace.outfile\n",
			progname);
		exit(EXIT_FAILURE);
	}
	files_db_write_objects(fp);
	while (in_mem_file_op_head != NULL) {
		struct in_mem_file_op *temp;

		disk_file_op = &in_mem_file_op_head->disk_file_op;
		if (ioshark_write_file_op(fp, disk_file_op) != 1) {
			fprintf(stderr, "%s Write error trace.outfile\n",
				progname);
			exit(EXIT_FAILURE);
		}
		temp = in_mem_file_op_head;
		in_mem_file_op_head = in_mem_file_op_head->next;
		free(temp);
	}
	store_filename_cache();
}
