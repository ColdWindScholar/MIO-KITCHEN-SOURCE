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
#include <sys/stat.h>
#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <assert.h>
#include <pthread.h>
#include <sys/statfs.h>
#include <sys/resource.h>
#include <inttypes.h>
#include "ioshark.h"
#define IOSHARK_MAIN
#include "ioshark_bench.h"

/*
 * Note on "quick" mode where we do reads on existing /system,
 * /vendor and other files in ro partitions, instead of creating
 * them. The ioshark compiler builds up a table of all the files
 * in /system, /vendor and other ro partitions. For files in this
 * list, the benchmark skips the pre-creation of these files and
 * reads them directly.
 * The code relevant to this is in *filename_cache*.
 */

char *progname;

#define MAX_INPUT_FILES		8192
#define MAX_THREADS		8192

struct thread_state_s {
	char *filename;
	FILE *fp;
	int num_files;
	void *db_handle;
};

struct thread_state_s thread_state[MAX_INPUT_FILES];
int num_input_files = 0;
int next_input_file;

pthread_t tid[MAX_THREADS];

/*
 * Global options
 */
int do_delay = 0;
int verbose = 0;
int summary_mode = 0;
int quick_mode = 0;
char *blockdev_name = NULL;	/* if user would like to specify blockdev */

#if 0
static long gettid()
{
        return syscall(__NR_gettid);
}
#endif

void usage()
{
	fprintf(stderr, "%s [-b blockdev_name] [-d preserve_delays] [-n num_iterations] [-t num_threads] -q -v | -s <list of parsed input files>\n",
		progname);
	fprintf(stderr, "%s -s, -v are mutually exclusive\n",
		progname);
	exit(EXIT_FAILURE);
}

pthread_mutex_t time_mutex = PTHREAD_MUTEX_INITIALIZER;
pthread_mutex_t stats_mutex = PTHREAD_MUTEX_INITIALIZER;
pthread_mutex_t work_mutex = PTHREAD_MUTEX_INITIALIZER;
struct timeval aggregate_file_create_time;
struct timeval debug_file_create_time;
struct timeval aggregate_file_remove_time;
struct timeval aggregate_IO_time;
struct timeval aggregate_delay_time;

u_int64_t aggr_op_counts[IOSHARK_MAX_FILE_OP];
struct rw_bytes_s aggr_io_rw_bytes;
struct rw_bytes_s aggr_create_rw_bytes;

/*
 * Locking needed here because aggregate_delay_time is updated
 * from multiple threads concurrently.
 */
static void
update_time(struct timeval *aggr_time,
	    struct timeval *delta_time)
{
	struct timeval tmp;

	pthread_mutex_lock(&time_mutex);
	timeradd(aggr_time, delta_time, &tmp);
	*aggr_time = tmp;
	pthread_mutex_unlock(&time_mutex);
}

static void
update_op_counts(u_int64_t *op_counts)
{
	int i;

	pthread_mutex_lock(&stats_mutex);
	for (i = IOSHARK_LSEEK ; i < IOSHARK_MAX_FILE_OP ; i++)
		aggr_op_counts[i] += op_counts[i];
	pthread_mutex_unlock(&stats_mutex);
}

static void
update_byte_counts(struct rw_bytes_s *dest, struct rw_bytes_s *delta)
{
	pthread_mutex_lock(&stats_mutex);
	dest->bytes_read += delta->bytes_read;
	dest->bytes_written += delta->bytes_written;
	pthread_mutex_unlock(&stats_mutex);
}

static int work_next_file;
static int work_num_files;

void
init_work(int next_file, int num_files)
{
	pthread_mutex_lock(&work_mutex);
	work_next_file = next_file;
	work_num_files = work_next_file + num_files;
	pthread_mutex_unlock(&work_mutex);
}

/* Dole out the next file to work on to the thread */
static struct thread_state_s *
get_work()
{
	struct thread_state_s *work = NULL;

	pthread_mutex_lock(&work_mutex);
	if (work_next_file < work_num_files)
		work = &thread_state[work_next_file++];
	pthread_mutex_unlock(&work_mutex);
	return work;
}

static void
create_files(struct thread_state_s *state)
{
	int i;
	struct ioshark_file_state file_state;
	char path[MAX_IOSHARK_PATHLEN];
	void *db_node;
	struct rw_bytes_s rw_bytes;
	char *filename;
	int readonly;

	memset(&rw_bytes, 0, sizeof(struct rw_bytes_s));
	for (i = 0 ; i < state->num_files ; i++) {
		if (ioshark_read_file_state(state->fp, &file_state) != 1) {
			fprintf(stderr, "%s read error tracefile\n",
				progname);
			exit(EXIT_FAILURE);
		}
		/*
		 * Check to see if the file is in a readonly partition,
		 * in which case, we don't have to pre-create the file
		 * we can just read the existing file.
		 */
		filename =
			get_ro_filename(file_state.global_filename_ix);
		if (quick_mode)
			assert(filename != NULL);
		if (quick_mode == 0 ||
		    is_readonly_mount(filename, file_state.size) == 0) {
			sprintf(path, "file.%d.%"PRIu64"",
				(int)(state - thread_state),
				file_state.fileno);
			create_file(path, file_state.size,
				    &rw_bytes);
			filename = path;
			readonly = 0;
		} else {
			readonly = 1;
		}
		db_node = files_db_add_byfileno(state->db_handle,
						file_state.fileno,
						readonly);
		files_db_update_size(db_node, file_state.size);
		files_db_update_filename(db_node, filename);
	}
	update_byte_counts(&aggr_create_rw_bytes, &rw_bytes);
}

static void
do_one_io(void *db_node,
	  struct ioshark_file_operation *file_op,
	  u_int64_t *op_counts,
	  struct rw_bytes_s *rw_bytes,
	  char **bufp, int *buflen)
{
	assert(file_op->ioshark_io_op < IOSHARK_MAX_FILE_OP);
	op_counts[file_op->ioshark_io_op]++;
	switch (file_op->ioshark_io_op) {
	int ret;
	char *p;
	int fd;

	case IOSHARK_LSEEK:
	case IOSHARK_LLSEEK:
		ret = lseek(files_db_get_fd(db_node),
			    file_op->lseek_offset,
			    file_op->lseek_action);
		if (ret < 0) {
			fprintf(stderr,
				"%s: lseek(%s %"PRIu64" %d) returned error %d\n",
				progname, files_db_get_filename(db_node),
				file_op->lseek_offset,
				file_op->lseek_action, errno);
			exit(EXIT_FAILURE);
		}
		break;
	case IOSHARK_PREAD64:
		p = get_buf(bufp, buflen, file_op->prw_len, 0);
		ret = pread(files_db_get_fd(db_node), p,
			    file_op->prw_len, file_op->prw_offset);
		rw_bytes->bytes_read += file_op->prw_len;
		if (ret < 0) {
			fprintf(stderr,
				"%s: pread(%s %"PRIu64" %"PRIu64") error %d\n",
				progname,
				files_db_get_filename(db_node),
				file_op->prw_len,
				file_op->prw_offset, errno);
			exit(EXIT_FAILURE);
		}
		break;
	case IOSHARK_PWRITE64:
		p = get_buf(bufp, buflen, file_op->prw_len, 1);
		ret = pwrite(files_db_get_fd(db_node), p,
			     file_op->prw_len, file_op->prw_offset);
		rw_bytes->bytes_written += file_op->prw_len;
		if (ret < 0) {
			fprintf(stderr,
				"%s: pwrite(%s %"PRIu64" %"PRIu64") error %d\n",
				progname,
				files_db_get_filename(db_node),
				file_op->prw_len,
				file_op->prw_offset, errno);
			exit(EXIT_FAILURE);
		}
		break;
	case IOSHARK_READ:
		p = get_buf(bufp, buflen, file_op->rw_len, 0);
		ret = read(files_db_get_fd(db_node), p,
			   file_op->rw_len);
		rw_bytes->bytes_read += file_op->rw_len;
		if (ret < 0) {
			fprintf(stderr,
				"%s: read(%s %"PRIu64") error %d\n",
				progname,
				files_db_get_filename(db_node),
				file_op->rw_len,
				errno);
			exit(EXIT_FAILURE);
		}
		break;
	case IOSHARK_WRITE:
		p = get_buf(bufp, buflen, file_op->rw_len, 1);
		ret = write(files_db_get_fd(db_node), p,
			    file_op->rw_len);
		rw_bytes->bytes_written += file_op->rw_len;
		if (ret < 0) {
			fprintf(stderr,
				"%s: write(%s %"PRIu64") error %d\n",
				progname,
				files_db_get_filename(db_node),
				file_op->rw_len,
				errno);
			exit(EXIT_FAILURE);
		}
		break;
	case IOSHARK_MMAP:
	case IOSHARK_MMAP2:
		ioshark_handle_mmap(db_node, file_op,
				    bufp, buflen, op_counts,
				    rw_bytes);
		break;
	case IOSHARK_OPEN:
		if (file_op->open_flags & O_CREAT) {
			fd = open(files_db_get_filename(db_node),
				  file_op->open_flags,
				  file_op->open_mode);
			if (fd < 0) {
				/*
				 * EEXIST error acceptable, others are fatal.
				 * Although we failed to O_CREAT the file (O_EXCL)
				 * We will force an open of the file before any
				 * IO.
				 */
				if (errno == EEXIST) {
					return;
				} else {
					fprintf(stderr,
						"%s: O_CREAT open(%s %x %o) error %d\n",
						progname,
						files_db_get_filename(db_node),
						file_op->open_flags,
						file_op->open_mode, errno);
					exit(EXIT_FAILURE);
				}
			}
		} else {
			fd = open(files_db_get_filename(db_node),
				  file_op->open_flags);
			if (fd < 0) {
				if (file_op->open_flags & O_DIRECTORY) {
					/* O_DIRECTORY open()s should fail */
					return;
				} else {
					fprintf(stderr,
						"%s: open(%s %x) error %d\n",
						progname,
						files_db_get_filename(db_node),
						file_op->open_flags,
						errno);
					exit(EXIT_FAILURE);
				}
			}
		}
		files_db_close_fd(db_node);
		files_db_update_fd(db_node, fd);
		break;
	case IOSHARK_FSYNC:
	case IOSHARK_FDATASYNC:
		if (file_op->ioshark_io_op == IOSHARK_FSYNC) {
			ret = fsync(files_db_get_fd(db_node));
			if (ret < 0) {
				fprintf(stderr,
					"%s: fsync(%s) error %d\n",
					progname,
					files_db_get_filename(db_node),
					errno);
				exit(EXIT_FAILURE);
			}
		} else {
			ret = fdatasync(files_db_get_fd(db_node));
			if (ret < 0) {
				fprintf(stderr,
					"%s: fdatasync(%s) error %d\n",
					progname,
					files_db_get_filename(db_node),
					errno);
				exit(EXIT_FAILURE);
			}
		}
		break;
	case IOSHARK_CLOSE:
		ret = close(files_db_get_fd(db_node));
		if (ret < 0) {
			fprintf(stderr,
				"%s: close(%s) error %d\n",
				progname,
				files_db_get_filename(db_node), errno);
			exit(EXIT_FAILURE);
		}
		files_db_update_fd(db_node, -1);
		break;
	default:
		fprintf(stderr, "%s: unknown FILE_OP %d\n",
			progname, file_op->ioshark_io_op);
		exit(EXIT_FAILURE);
		break;
	}
}

static void
do_io(struct thread_state_s *state)
{
	void *db_node;
	struct ioshark_header header;
	struct ioshark_file_operation file_op;
	int fd;
	int i;
	char *buf = NULL;
	int buflen = 0;
	struct timeval total_delay_time;
	u_int64_t op_counts[IOSHARK_MAX_FILE_OP];
	struct rw_bytes_s rw_bytes;

	rewind(state->fp);
	if (ioshark_read_header(state->fp, &header) != 1) {
		fprintf(stderr, "%s read error %s\n",
			progname, state->filename);
		exit(EXIT_FAILURE);
	}
	/*
	 * First open and pre-create all the files. Indexed by fileno.
	 */
	timerclear(&total_delay_time);
	memset(&rw_bytes, 0, sizeof(struct rw_bytes_s));
	memset(op_counts, 0, sizeof(op_counts));
	fseek(state->fp,
	      sizeof(struct ioshark_header) +
	      header.num_files * sizeof(struct ioshark_file_state),
	      SEEK_SET);
	/*
	 * Loop over all the IOs, and launch each
	 */
	for (i = 0 ; i < (int)header.num_io_operations ; i++) {
		if (ioshark_read_file_op(state->fp, &file_op) != 1) {
			fprintf(stderr, "%s read error trace.outfile\n",
				progname);
			goto fail;
		}
		if (do_delay) {
			struct timeval start;

			(void)gettimeofday(&start, (struct timezone *)NULL);
			usleep(file_op.delta_us);
			update_delta_time(&start, &total_delay_time);
		}
		db_node = files_db_lookup_byfileno(state->db_handle,
						   file_op.fileno);
		if (db_node == NULL) {
			fprintf(stderr,
				"%s Can't lookup fileno %"PRIu64", fatal error\n",
				progname, file_op.fileno);
			fprintf(stderr,
				"%s state filename %s, i %d\n",
				progname, state->filename, i);
			goto fail;
		}
		if (file_op.ioshark_io_op != IOSHARK_OPEN &&
		    files_db_get_fd(db_node) == -1) {
			int openflags;

			/*
			 * This is a hack to workaround the fact that we did not
			 * see an open() for this file until now. open() the
			 * file O_RDWR, so that we can perform the IO.
			 */
			if (files_db_readonly(db_node))
				openflags = O_RDONLY;
			else
				openflags = O_RDWR;
			fd = open(files_db_get_filename(db_node),
				  openflags);
			if (fd < 0) {
				fprintf(stderr, "%s: open(%s %x) error %d\n",
					progname,
					files_db_get_filename(db_node),
					openflags,
					errno);
				goto fail;
			}
			files_db_update_fd(db_node, fd);
		}
		do_one_io(db_node, &file_op,
			  op_counts, &rw_bytes, &buf, &buflen);
	}

	free(buf);
	files_db_fsync_discard_files(state->db_handle);
	files_db_close_files(state->db_handle);
	update_time(&aggregate_delay_time, &total_delay_time);
	update_op_counts(op_counts);
	update_byte_counts(&aggr_io_rw_bytes, &rw_bytes);
	return;

fail:
	free(buf);
	exit(EXIT_FAILURE);
}

void *
io_thread(void *unused __attribute__((unused)))
{
	struct thread_state_s *state;

	srand(gettid());
	while ((state = get_work()))
		do_io(state);
	pthread_exit(NULL);
        return(NULL);
}

static void
do_create(struct thread_state_s *state)
{
	struct ioshark_header header;

	if (ioshark_read_header(state->fp, &header) != 1) {
		fprintf(stderr, "%s read error %s\n",
			progname, state->filename);
		exit(EXIT_FAILURE);
	}
	state->num_files = header.num_files;
	state->db_handle = files_db_create_handle();
	create_files(state);
}

void *
create_files_thread(void *unused __attribute__((unused)))
{
	struct thread_state_s *state;

	while ((state = get_work()))
		do_create(state);
	pthread_exit(NULL);
	return(NULL);
}

int
get_start_end(int *start_ix)
{
	int i, j, ret_numfiles;
	u_int64_t free_fs_bytes;
	char *infile;
	FILE *fp;
	struct ioshark_header header;
	struct ioshark_file_state file_state;
	struct statfs fsstat;
	static int fssize_clamp_next_index = 0;
	static int chunk = 0;

	if (fssize_clamp_next_index == num_input_files)
		return 0;
	if (statfs("/data/local/tmp", &fsstat) < 0) {
		fprintf(stderr, "%s: Can't statfs /data/local/tmp\n",
			progname);
		exit(EXIT_FAILURE);
	}
	free_fs_bytes = (fsstat.f_bavail * fsstat.f_bsize) * 9 /10;
	for (i = fssize_clamp_next_index; i < num_input_files; i++) {
		infile = thread_state[i].filename;
		fp = fopen(infile, "r");
		if (fp == NULL) {
			fprintf(stderr, "%s: Can't open %s\n",
				progname, infile);
			exit(EXIT_FAILURE);
		}
		if (ioshark_read_header(fp, &header) != 1) {
			fprintf(stderr, "%s read error %s\n",
				progname, infile);
			exit(EXIT_FAILURE);
		}
		for (j = 0 ; j < (int)header.num_files ; j++) {
			if (ioshark_read_file_state(fp, &file_state) != 1) {
				fprintf(stderr, "%s read error tracefile\n",
					progname);
				exit(EXIT_FAILURE);
			}
			if (quick_mode == 0 ||
			    !is_readonly_mount(
				    get_ro_filename(file_state.global_filename_ix),
				    file_state.size)) {
				if (file_state.size > free_fs_bytes) {
					fclose(fp);
					goto out;
				}
				free_fs_bytes -= file_state.size;
			}
		}
		fclose(fp);
	}
out:
	if (verbose) {
		if (chunk > 0 || i < num_input_files) {
			printf("Breaking up input files, Chunk %d: %d to %d\n",
			       chunk++, fssize_clamp_next_index, i - 1);
		} else {
			printf("Entire Dataset fits start = %d to %d, free_bytes = %ju\n",
			       fssize_clamp_next_index,
			       i - fssize_clamp_next_index,
			       free_fs_bytes);
		}
	}
	*start_ix = fssize_clamp_next_index;
	ret_numfiles = i - fssize_clamp_next_index;
	fssize_clamp_next_index = i;
	return ret_numfiles;
}

int
ioshark_pthread_create(pthread_t *tidp, void *(*start_routine)(void *))
{
	pthread_attr_t attr;

	pthread_attr_init(&attr);
	pthread_attr_setscope(&attr, PTHREAD_SCOPE_SYSTEM);
	pthread_attr_setstacksize(&attr, (size_t)(1024*1024));
	return pthread_create(tidp, &attr, start_routine, (void *)NULL);
}

void
wait_for_threads(int num_threads)
{
	int i;

	for (i = 0; i < num_threads; i++) {
		pthread_join(tid[i], NULL);
		tid[i] = 0;
	}
}

#define IOSHARK_FD_LIM		8192

static void
sizeup_fd_limits(void)
{
	struct rlimit r;

	getrlimit(RLIMIT_NOFILE, &r);
	if (r.rlim_cur >= IOSHARK_FD_LIM)
		/* cur limit already at what we want */
		return;
	/*
	 * Size up both the Max and Cur to IOSHARK_FD_LIM.
	 * If we are not running as root, this will fail,
	 * catch that below and exit.
	 */
	if (r.rlim_max < IOSHARK_FD_LIM)
		r.rlim_max = IOSHARK_FD_LIM;
	r.rlim_cur = IOSHARK_FD_LIM;
	if (setrlimit(RLIMIT_NOFILE, &r) < 0) {
		fprintf(stderr, "%s: Can't setrlimit (RLIMIT_NOFILE, 8192)\n",
			progname);
		exit(EXIT_FAILURE);
	}
	getrlimit(RLIMIT_NOFILE, &r);
	if (r.rlim_cur < IOSHARK_FD_LIM) {
		fprintf(stderr, "%s: Can't setrlimit up to 8192\n",
			progname);
		fprintf(stderr, "%s: Running as root ?\n",
			progname);
		exit(EXIT_FAILURE);
	}
}

int
main(int argc, char **argv)
{
	int i;
	FILE *fp;
	struct stat st;
	char *infile;
	int num_threads = 0;
	int num_iterations = 1;
	int c;
	int num_files, start_file;
	struct thread_state_s *state;

	progname = argv[0];
        while ((c = getopt(argc, argv, "b:dn:st:qv")) != EOF) {
                switch (c) {
                case 'b':
			blockdev_name = strdup(optarg);
			break;
                case 'd':
			do_delay = 1;
			break;
                case 'n':
			num_iterations = atoi(optarg);
			break;
                case 's':
			/* Non-verbose summary mode for nightly runs */
			summary_mode = 1;
			break;
                case 't':
			num_threads = atoi(optarg);
			break;
                case 'q':
			/*
			 * If quick mode is enabled, then we won't
			 * pre-create files that we are doing IO on that
			 * live in readonly partitions (/system, /vendor etc)
			 */
			quick_mode = 1;
			break;
                case 'v':
			verbose = 1;
			break;
 	        default:
			usage();
		}
	}

	if ((verbose + summary_mode) == 2)
		usage();

	if (num_threads > MAX_THREADS)
		usage();

	if (optind == argc)
                usage();

	sizeup_fd_limits();

	for (i = optind; i < argc; i++) {
		infile = argv[i];
		if (stat(infile, &st) < 0) {
			fprintf(stderr, "%s: Can't stat %s\n",
				progname, infile);
			exit(EXIT_FAILURE);
		}
		if (st.st_size == 0) {
			fprintf(stderr, "%s: Empty file %s\n",
				progname, infile);
			continue;
		}
		fp = fopen(infile, "r");
		if (fp == NULL) {
			fprintf(stderr, "%s: Can't open %s\n",
				progname, infile);
			continue;
		}
		thread_state[num_input_files].filename = infile;
		thread_state[num_input_files].fp = fp;
		num_input_files++;
	}

	if (num_input_files == 0) {
		exit(EXIT_SUCCESS);
	}
	if (verbose) {
		printf("Total Input Files = %d\n", num_input_files);
		printf("Num Iterations = %d\n", num_iterations);
	}
	timerclear(&aggregate_file_create_time);
	timerclear(&aggregate_file_remove_time);
	timerclear(&aggregate_IO_time);

	if (quick_mode)
		init_filename_cache();

	capture_util_state_before();

	/*
	 * We pre-create the files that we need once and then we
	 * loop around N times doing IOs on the pre-created files.
	 *
	 * get_start_end() breaks up the total work here to make sure
	 * that all the files we need to pre-create fit into the
	 * available space in /data/local/tmp (hardcoded for now).
	 *
	 * If it won't fit, then we do several sweeps.
	 */
	while ((num_files = get_start_end(&start_file))) {
		struct timeval time_for_pass;

		/* Create files once */
		if (!summary_mode)
			printf("Doing Pre-creation of Files\n");
		if (quick_mode && !summary_mode)
			printf("Skipping Pre-creation of read-only Files\n");
		if (num_threads == 0 || num_threads > num_files)
			num_threads = num_files;
		(void)system("echo 3 > /proc/sys/vm/drop_caches");
		init_work(start_file, num_files);
		(void)gettimeofday(&time_for_pass,
				   (struct timezone *)NULL);
		for (i = 0; i < num_threads; i++) {
			if (ioshark_pthread_create(&(tid[i]),
						   create_files_thread)) {
				fprintf(stderr,
					"%s: Can't create creator thread %d\n",
					progname, i);
				exit(EXIT_FAILURE);
			}
		}
		wait_for_threads(num_threads);
		update_delta_time(&time_for_pass, &aggregate_file_create_time);
		/* Do the IOs N times */
		for (i = 0 ; i < num_iterations ; i++) {
			(void)system("echo 3 > /proc/sys/vm/drop_caches");
			if (!summary_mode) {
				if (num_iterations > 1)
					printf("Starting Test. Iteration %d...\n",
					       i);
				else
					printf("Starting Test...\n");
			}
			init_work(start_file, num_files);
			(void)gettimeofday(&time_for_pass,
					   (struct timezone *)NULL);
			for (c = 0; c < num_threads; c++) {
				if (ioshark_pthread_create(&(tid[c]),
							   io_thread)) {
					fprintf(stderr,
						"%s: Can't create thread %d\n",
						progname, c);
					exit(EXIT_FAILURE);
				}
			}
			wait_for_threads(num_threads);
			update_delta_time(&time_for_pass,
					  &aggregate_IO_time);
		}

		/*
		 * We are done with the N iterations of IO.
		 * Destroy the files we pre-created.
		 */
		init_work(start_file, num_files);
		while ((state = get_work())) {
			struct timeval start;

			(void)gettimeofday(&start, (struct timezone *)NULL);
			files_db_unlink_files(state->db_handle);
			update_delta_time(&start, &aggregate_file_remove_time);
			files_db_free_memory(state->db_handle);
		}
	}
	if (!summary_mode) {
		printf("Total Creation time = %ju.%ju (msecs.usecs)\n",
		       get_msecs(&aggregate_file_create_time),
		       get_usecs(&aggregate_file_create_time));
		printf("Total Remove time = %ju.%ju (msecs.usecs)\n",
		       get_msecs(&aggregate_file_remove_time),
		       get_usecs(&aggregate_file_remove_time));
		if (do_delay)
			printf("Total delay time = %ju.%ju (msecs.usecs)\n",
			       get_msecs(&aggregate_delay_time),
			       get_usecs(&aggregate_delay_time));
		printf("Total Test (IO) time = %ju.%ju (msecs.usecs)\n",
		       get_msecs(&aggregate_IO_time),
		       get_usecs(&aggregate_IO_time));
		if (verbose)
			print_bytes("Upfront File Creation bytes",
				    &aggr_create_rw_bytes);
		print_bytes("Total Test (IO) bytes", &aggr_io_rw_bytes);
		if (verbose)
			print_op_stats(aggr_op_counts);
		report_cpu_disk_util();
	} else {
		printf("%ju.%ju ",
		       get_msecs(&aggregate_file_create_time),
		       get_usecs(&aggregate_file_create_time));
		printf("%ju.%ju ",
		       get_msecs(&aggregate_file_remove_time),
		       get_usecs(&aggregate_file_remove_time));
		if (do_delay)
			printf("%ju.%ju ",
			       get_msecs(&aggregate_delay_time),
			       get_usecs(&aggregate_delay_time));
		printf("%ju.%ju ",
		       get_msecs(&aggregate_IO_time),
		       get_usecs(&aggregate_IO_time));
		print_bytes(NULL, &aggr_io_rw_bytes);
		report_cpu_disk_util();
		printf("\n");
	}
	if (quick_mode)
		free_filename_cache();
}
