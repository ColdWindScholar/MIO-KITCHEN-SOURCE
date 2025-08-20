
#pragma once

#include <sys/types.h>

typedef unsigned short __gid_t;

__inline struct group * getgrnam(char* g){ (void)g; return 0;}

struct group
  {
    char *gr_name;
    char *gr_passwd;
    __gid_t gr_gid;
    char **gr_mem;
  };

#define getgrgid(i) NULL
