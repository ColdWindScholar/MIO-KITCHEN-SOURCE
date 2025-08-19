/*
 * Copyright (C) 2008 The Android Open Source Project
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

#include <errno.h>
#include <error.h>
#include <getopt.h>
#include <paths.h>
#include <pwd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <private/android_filesystem_config.h>

void pwtoid(const char* tok, uid_t* uid, gid_t* gid) {
    struct passwd* pw = getpwnam(tok);
    if (pw) {
        if (uid) *uid = pw->pw_uid;
        if (gid) *gid = pw->pw_gid;
    } else {
        char* end;
        errno = 0;
        uid_t tmpid = strtoul(tok, &end, 10);
        if (errno != 0 || end == tok) error(1, errno, "invalid uid/gid '%s'", tok);
        if (uid) *uid = tmpid;
        if (gid) *gid = tmpid;
    }
}

void extract_uidgids(const char* uidgids, uid_t* uid, gid_t* gid, gid_t* gids, int* gids_count) {
    char *clobberablegids;
    char *nexttok;
    char *tok;
    int gids_found;

    if (!uidgids || !*uidgids) {
        *gid = *uid = 0;
        *gids_count = 0;
        return;
    }

    clobberablegids = strdup(uidgids);
    strcpy(clobberablegids, uidgids);
    nexttok = clobberablegids;
    tok = strsep(&nexttok, ",");
    pwtoid(tok, uid, gid);
    tok = strsep(&nexttok, ",");
    if (!tok) {
        /* gid is already set above */
        *gids_count = 0;
        free(clobberablegids);
        return;
    }
    pwtoid(tok, NULL, gid);
    gids_found = 0;
    while ((gids_found < *gids_count) && (tok = strsep(&nexttok, ","))) {
        pwtoid(tok, NULL, gids);
        gids_found++;
        gids++;
    }
    if (nexttok && gids_found == *gids_count) {
        fprintf(stderr, "too many group ids\n");
    }
    *gids_count = gids_found;
    free(clobberablegids);
}

int main(int argc, char** argv) {
    uid_t current_uid = getuid();
    if (current_uid != AID_ROOT && current_uid != AID_SHELL) error(1, 0, "not allowed");

    // Handle -h and --help.
    ++argv;
    if (*argv && (strcmp(*argv, "--help") == 0 || strcmp(*argv, "-h") == 0)) {
        fprintf(stderr,
                "usage: su [WHO [COMMAND...]]\n"
                "\n"
                "Switch to WHO (default 'root') and run the given COMMAND (default sh).\n"
                "\n"
                "WHO is a comma-separated list of user, group, and supplementary groups\n"
                "in that order.\n"
                "\n");
        return 0;
    }

    // The default user is root.
    uid_t uid = 0;
    gid_t gid = 0;

    // If there are any arguments, the first argument is the uid/gid/supplementary groups.
    if (*argv) {
        gid_t gids[10];
        int gids_count = sizeof(gids)/sizeof(gids[0]);
        extract_uidgids(*argv, &uid, &gid, gids, &gids_count);
        if (gids_count) {
            if (setgroups(gids_count, gids)) {
                error(1, errno, "setgroups failed");
            }
        }
        ++argv;
    }

    if (setgid(gid)) error(1, errno, "setgid failed");
    if (setuid(uid)) error(1, errno, "setuid failed");

    // Reset parts of the environment.
    setenv("PATH", _PATH_DEFPATH, 1);
    unsetenv("IFS");
    struct passwd* pw = getpwuid(uid);
    if (pw) {
        setenv("LOGNAME", pw->pw_name, 1);
        setenv("USER", pw->pw_name, 1);
    } else {
        unsetenv("LOGNAME");
        unsetenv("USER");
    }

    // Set up the arguments for exec.
    char* exec_args[argc + 1];  // Having too much space is fine.
    size_t i = 0;
    for (; *argv != NULL; ++i) {
      exec_args[i] = *argv++;
    }
    // Default to the standard shell.
    if (i == 0) exec_args[i++] = const_cast<char*>("/system/bin/sh");
    exec_args[i] = NULL;

    execvp(exec_args[0], exec_args);
    error(1, errno, "failed to exec %s", exec_args[0]);
}
