#pragma once

#include_next <unistd.h>

#ifndef _SVB_UNISTD_H
#define _SVB_UNISTD_H

typedef unsigned short __uid_t;
typedef unsigned short __gid_t;

// FIXED VALUE
#define getuid() 0
#define geteuid() 0
#define getgid() 0
#define getegid() 0

// NOP
//#define sync()

#endif /* _SVB_UNISTD_H */
