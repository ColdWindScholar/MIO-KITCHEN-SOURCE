/*
 * Copyright (C) 2016 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
const char* optstr = "<1u:g:G:c:s";
const char* usage =
    R"(usage: runconuid [-s] [-u UID] [-g GID] [-G GROUPS] [-c CONTEXT] COMMAND ARGS

Run a command in the specified security context, as the specified user,
with the specified group membership.

-c  SELinux context
-g  Group ID by name or numeric value
-G  List of groups by name or numeric value
-s  Set enforcing mode
-u  User ID by name or numeric value
)";

#include <assert.h>
#include <errno.h>
#include <grp.h>
#include <pwd.h>
#include <selinux/selinux.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/capability.h>
#include <sys/prctl.h>
#include <sys/ptrace.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

static uid_t uid = -1;
static gid_t gid = -1;
static gid_t* groups = nullptr;
static size_t ngroups = 0;
static char* context = nullptr;
static bool setenforce = false;
static char** child_argv = nullptr;

[[noreturn]] void perror_exit(const char* message) {
  perror(message);
  exit(1);
}

void do_child(void) {

  if (context && setexeccon(context) < 0) {
    perror_exit("Setting context to failed");
  }

  // Disregard ambient capability failures, we may just be on a kernel
  // that does not support them.
  for (int i = 0; i < 64; ++i) {
      prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_RAISE, i, 0, 0);
  }

  if (ngroups && setgroups(ngroups, groups) < 0) {
    perror_exit("Setting supplementary groups failed.");
  }

  if (gid != (gid_t) -1 && setresgid(gid, gid, gid) < 0) {
    perror_exit("Setting group failed.");
  }

  if (uid != (uid_t) -1 && setresuid(uid, uid, uid) < 0) {
    perror_exit("Setting user failed.");
  }

  ptrace(PTRACE_TRACEME, 0, 0, 0);
  raise(SIGSTOP);
  execvp(child_argv[0], child_argv);
  perror_exit("Failed to execve");
}

uid_t lookup_uid(char* c) {
  struct passwd* pw;
  uid_t u;

  if (sscanf(c, "%d", &u) == 1) {
    return u;
  }

  if ((pw = getpwnam(c)) != 0) {
    return pw->pw_uid;
  }

  perror_exit("Could not resolve user ID by name");
}

gid_t lookup_gid(char* c) {
  struct group* gr;
  gid_t g;

  if (sscanf(c, "%d", &g) == 1) {
    return g;
  }

  if ((gr = getgrnam(c)) != 0) {
    return gr->gr_gid;
  }

  perror_exit("Could not resolve group ID by name");
}

void lookup_groups(char* c) {
  char* group;

  // Count the number of groups
  for (group = c; *group; group++) {
    if (*group == ',') {
      ngroups++;
      *group = '\0';
    }
  }

  // The last group is not followed by a comma.
  ngroups++;

  // Allocate enough space for all of them
  groups = (gid_t*)calloc(ngroups, sizeof(gid_t));
  group = c;

  // Fill in the group IDs
  for (size_t n = 0; n < ngroups; n++) {
    groups[n] = lookup_gid(group);
    group += strlen(group) + 1;
  }
}

void parse_arguments(int argc, char** argv) {
  int c;

  while ((c = getopt(argc, argv, optstr)) != -1) {
    switch (c) {
      case 'u':
        uid = lookup_uid(optarg);
        break;
      case 'g':
        gid = lookup_gid(optarg);
        break;
      case 'G':
        lookup_groups(optarg);
        break;
      case 's':
        setenforce = true;
        break;
      case 'c':
        context = optarg;
        break;
      default:
        perror_exit(usage);
        break;
    }
  }

  child_argv = &argv[optind];

  if (optind == argc) {
    perror_exit(usage);
  }
}

int main(int argc, char** argv) {
  pid_t child;

  parse_arguments(argc, argv);
  child = fork();

  if (child < 0) {
    perror_exit("Could not fork.");
  }

  if (setenforce && is_selinux_enabled()) {
    if (security_setenforce(0) < 0) {
      perror("Couldn't set enforcing status to 0");
    }
  }

  if (child == 0) {
    do_child();
  }

  if (ptrace(PTRACE_ATTACH, child, 0, 0) < 0) {
    int err = errno;
    kill(SIGKILL, child);
    errno = err;
    perror_exit("Could not ptrace child.");
  }

  // Wait for the SIGSTOP
  int status = 0;
  if (-1 == wait(&status)) {
    perror_exit("Could not wait for child SIGSTOP");
  }

  // Trace all syscalls.
  ptrace(PTRACE_SETOPTIONS, child, 0, PTRACE_O_TRACESYSGOOD);

  while (1) {
    ptrace(PTRACE_SYSCALL, child, 0, 0);
    waitpid(child, &status, 0);

    // Child raises SIGINT after the execve, on the first instruction.
    if (WIFSTOPPED(status) && WSTOPSIG(status) == SIGTRAP) {
      break;
    }

    // Child did some other syscall.
    if (WIFSTOPPED(status) && WSTOPSIG(status) & 0x80) {
      continue;
    }

    // Child exited.
    if (WIFEXITED(status)) {
      exit(WEXITSTATUS(status));
    }
  }

  if (setenforce && is_selinux_enabled()) {
    if (security_setenforce(1) < 0) {
      perror("Couldn't set enforcing status to 1");
    }
  }

  ptrace(PTRACE_DETACH, child, 0, 0);
  return 0;
}
