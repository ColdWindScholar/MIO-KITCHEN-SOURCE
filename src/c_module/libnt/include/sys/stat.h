#pragma once

#include_next <sys/stat.h>

#ifndef _NT_EXTRA_STAT_H
#define _NT_EXTRA_STAT_H

#include <stdint.h>

#define ino_t uint64_t

typedef unsigned int uid_t;
typedef unsigned int gid_t;

typedef int64_t fileoffset_t;
typedef uint16_t nlink_t;
typedef uint32_t blksize_t;
typedef uint64_t blkcnt_t;

typedef struct nt_stat {
	dev_t st_dev;
	ino_t st_ino;
	mode_t st_mode;
	nlink_t st_nlink;
	uid_t st_uid;
	gid_t st_gid;
	dev_t st_rdev;
	fileoffset_t st_size;
	blksize_t st_blksize;
	blkcnt_t st_blocks;
	time_t st_atime;
	time_t st_mtime;
	time_t st_ctime;
} stat_t;
#endif
