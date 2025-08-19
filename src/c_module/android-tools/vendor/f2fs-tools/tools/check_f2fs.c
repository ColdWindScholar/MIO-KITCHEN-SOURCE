#include <stdio.h>
#include <sys/mman.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/time.h>
#include <unistd.h>
#include <sys/wait.h>
#include <sys/syscall.h>
#include <errno.h>
#include <fcntl.h>
#include <getopt.h>
#include <string.h>
#include <stdlib.h>

#define F2FS_IOCTL_MAGIC		0xf5
#define F2FS_IOC_START_ATOMIC_WRITE     _IO(F2FS_IOCTL_MAGIC, 1)
#define F2FS_IOC_COMMIT_ATOMIC_WRITE    _IO(F2FS_IOCTL_MAGIC, 2)
#define F2FS_IOC_START_VOLATILE_WRITE   _IO(F2FS_IOCTL_MAGIC, 3)
#define F2FS_IOC_RELEASE_VOLATILE_WRITE _IO(F2FS_IOCTL_MAGIC, 4)
#define F2FS_IOC_ABORT_VOLATILE_WRITE   _IO(F2FS_IOCTL_MAGIC, 5)
#define F2FS_IOC_GARBAGE_COLLECT        _IO(F2FS_IOCTL_MAGIC, 6)

#define DB1_PATH "/data/database_file1"
#define DB2_PATH "/mnt/androidwritable/0/emulated/0/Android/data/database_file2"
#define FILE_PATH "/data/testfile"

#define F2FS_BLKSIZE 4096
#define BLKS_TO_SECTOR_BITS 3
#define BLOCK 4096
#define BLOCKS (2 * BLOCK)

char buf[BLOCKS];
char cmd[BLOCK];

static int run(const char *cmd)
{
	int status;

	fflush(stdout);

	switch (fork()) {
	case 0:
		/* redirect stderr to stdout */
		dup2(1, 2);
		execl("/system/bin/sh", "sh", "-c", cmd, (char *) NULL);
	case -1:
		printf("fork failed in run() errno:%d\n", errno);
		return -1;
	default:
		wait(&status);
	}
	return 0;
}

static int test_atomic_write(char *path)
{
	int db, ret, written;

	printf("\tOpen  %s... \n", path);
	db = open(path, O_RDWR|O_CREAT, 0666);
	if (db < 0) {
		printf("open failed errno:%d\n", errno);
		return -1;
	}
	printf("\tStart ... \n");
	ret = ioctl(db, F2FS_IOC_START_ATOMIC_WRITE);
	if (ret) {
		printf("ioctl failed errno:%d\n", errno);
		return -1;
	}
	printf("\tWrite to the %dkB ... \n", BLOCKS / 1024);
	written = write(db, buf, BLOCKS);
	if (written != BLOCKS) {
		printf("write fail written:%d, errno:%d\n", written, errno);
		return -1;
	}
	printf("\tCheck : Atomic in-memory count: 2\n");
	if (access("/dev/sys/fs/by-name/userdata/current_atomic_write", F_OK)
			== 0) {
		printf("- inmem: ");
		run("cat /dev/sys/fs/by-name/userdata/current_atomic_write");
	} else {
		run("grep \"atomic IO\" /sys/kernel/debug/f2fs/status");
	}

	printf("\tCommit  ... \n");
	ret = ioctl(db, F2FS_IOC_COMMIT_ATOMIC_WRITE);
	if (ret) {
		printf("ioctl failed errno:%d\n", errno);
		return -1;
	}
	return 0;
}

static int test_bad_write_call(char *path)
{
	int fd, written;
	struct stat sb;
	int large_size = 1024 * 1024 * 100;	/* 100 MB */
	int blocks;

	printf("\tOpen  %s... \n", path);
	fd = open(path, O_RDWR|O_CREAT|O_TRUNC, 0666);
	if (fd < 0) {
		printf("open failed errno:%d\n", errno);
		return -1;
	}

	/* 8KB-sized buffer, but submit 100 MB size */
	printf("\tWrite to the %dkB ... \n", BLOCKS / 1024);
	written = write(fd, buf, large_size);
	if (written != BLOCKS)
		printf("Ok: write fail written:%d, errno:%d\n", written, errno);
	close(fd);

	fd = open(path, O_RDONLY);
	if (fd < 0) {
		printf("open failed errno:%d\n", errno);
		return -1;
	}

	if (stat(path, &sb) == -1) {
		printf("stat failed errno:%d\n", errno);
		return -1;
	}

	blocks = (long long)sb.st_size / F2FS_BLKSIZE;
	if (sb.st_size % F2FS_BLKSIZE)
		blocks++;

	if (blocks << BLKS_TO_SECTOR_BITS != (long long)sb.st_blocks) {
		printf("FAIL: Mismatch i_size and i_blocks: %lld %lld\n",
			(long long)sb.st_size, (long long)sb.st_blocks);
		printf("FAIL: missing patch "
			"\"f2fs: do not preallocate blocks which has wrong buffer\"\n");
	}
	close(fd);
	unlink(path);
	return 0;
}

int main(void)
{
	memset(buf, 0xff, BLOCKS);

	printf("# Test 0: Check F2FS support\n");
	run("cat /proc/filesystems");

	printf("# Test 1: Check F2FS status on /userdata\n");
	printf("\t= FS type /userdata\n");
	run("mount | grep data");

	printf("\n\t= F2FS features\n");
	run("ls -1 /sys/fs/f2fs/features/");
	run("find /sys/fs/f2fs -type f -name \"features\" -print -exec cat {} \\;");
	run("find /sys/fs/f2fs -type f -name \"ipu_policy\" -print -exec cat {} \\;");
	run("find /sys/fs/f2fs -type f -name \"discard_granularity\" -print -exec cat {} \\;");
	run("cat /sys/kernel/debug/f2fs/status");

	printf("\n\n# Test 2: Atomic_write on /userdata\n");
	if (test_atomic_write(DB1_PATH))
		return 0;

	printf("# Test 3: Atomic_write on /sdcard\n");
	if (test_atomic_write(DB2_PATH))
		return 0;

	printf("# Test 4: Bad write(2) call\n");
	if (test_bad_write_call(FILE_PATH))
		return 0;
	return 0;
}
