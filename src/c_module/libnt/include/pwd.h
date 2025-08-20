
#pragma once

#include <sys/types.h>

typedef unsigned short __uid_t;
typedef unsigned short __gid_t;

__inline struct passwd* getpwnam (char* g){ (void)g; return 0;}

struct passwd
{
  char *pw_name;
  char *pw_passwd;
  __uid_t pw_uid;
  __gid_t pw_gid;
  char *pw_gecos;
  char *pw_dir;
  char *pw_shell;
};

#define getpwuid(i) NULL

