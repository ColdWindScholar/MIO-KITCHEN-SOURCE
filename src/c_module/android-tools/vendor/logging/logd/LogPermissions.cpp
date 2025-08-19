/*
 * Copyright (C) 2012-2014 The Android Open Source Project
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

#include "LogPermissions.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>

#include <vector>

#include <private/android_filesystem_config.h>

static bool checkGroup(char* buf, gid_t gidToCheck) {
    char* ptr;
    static const char ws[] = " \n";

    for (buf = strtok_r(buf, ws, &ptr); buf; buf = strtok_r(nullptr, ws, &ptr)) {
        errno = 0;
        gid_t Gid = strtol(buf, nullptr, 10);
        if (errno != 0) {
            return false;
        }
        if (Gid == gidToCheck) {
            return true;
        }
    }
    return false;
}

static bool UserIsPrivileged(int id) {
    return id == AID_ROOT || id == AID_SYSTEM || id == AID_LOG;
}

// gets a list of supplementary group IDs associated with
// the socket peer.  This is implemented by opening
// /proc/PID/status and look for the "Group:" line.
//
// This function introduces races especially since status
// can change 'shape' while reading, the net result is err
// on lack of permission.
static bool checkSupplementaryGroup(uid_t uid, gid_t gid, pid_t pid, gid_t gidToCheck) {
    char filename[256];
    snprintf(filename, sizeof(filename), "/proc/%u/status", pid);

    bool ret;
    bool foundGroup = false;
    bool foundGid = false;
    bool foundUid = false;

    //
    // Reading /proc/<pid>/status is rife with race conditions. All of /proc
    // suffers from this and its use should be minimized.
    //
    // Notably the content from one 4KB page to the next 4KB page can be from a
    // change in shape even if we are gracious enough to attempt to read
    // atomically. getline can not even guarantee a page read is not split up
    // and in effect can read from different vintages of the content.
    //
    // We are finding out in the field that a 'logcat -c' via adb occasionally
    // is returned with permission denied when we did only one pass and thus
    // breaking scripts. For security we still err on denying access if in
    // doubt, but we expect the falses  should be reduced significantly as
    // three times is a charm.
    //
    for (int retry = 3; !(ret = foundGid && foundUid && foundGroup) && retry; --retry) {
        FILE* file = fopen(filename, "re");
        if (!file) {
            continue;
        }

        char* line = nullptr;
        size_t len = 0;
        while (getline(&line, &len, file) > 0) {
            static const char groups_string[] = "Groups:\t";
            static const char uid_string[] = "Uid:\t";
            static const char gid_string[] = "Gid:\t";

            if (strncmp(groups_string, line, sizeof(groups_string) - 1) == 0) {
                if (checkGroup(line + sizeof(groups_string) - 1, gidToCheck)) {
                    foundGroup = true;
                }
            } else if (strncmp(uid_string, line, sizeof(uid_string) - 1) == 0) {
                uid_t u[4] = { (uid_t)-1, (uid_t)-1, (uid_t)-1, (uid_t)-1 };

                sscanf(line + sizeof(uid_string) - 1, "%u\t%u\t%u\t%u", &u[0],
                       &u[1], &u[2], &u[3]);

                // Protect against PID reuse by checking that UID is the same
                if ((uid == u[0]) && (uid == u[1]) && (uid == u[2]) &&
                    (uid == u[3])) {
                    foundUid = true;
                }
            } else if (strncmp(gid_string, line, sizeof(gid_string) - 1) == 0) {
                gid_t g[4] = { (gid_t)-1, (gid_t)-1, (gid_t)-1, (gid_t)-1 };

                sscanf(line + sizeof(gid_string) - 1, "%u\t%u\t%u\t%u", &g[0],
                       &g[1], &g[2], &g[3]);

                // Protect against PID reuse by checking that GID is the same
                if ((gid == g[0]) && (gid == g[1]) && (gid == g[2]) &&
                    (gid == g[3])) {
                    foundGid = true;
                }
            }
        }
        free(line);
        fclose(file);
    }

    return ret;
}

bool clientCanWriteSecurityLog(uid_t uid, gid_t gid, pid_t pid) {
    if (UserIsPrivileged(uid) || UserIsPrivileged(gid)) {
        return true;
    }
    return checkSupplementaryGroup(uid, gid, pid, AID_SECURITY_LOG_WRITER) ||
           checkSupplementaryGroup(uid, gid, pid, AID_LOG);
}

bool clientHasLogCredentials(uid_t uid, gid_t gid, pid_t pid) {
    if (UserIsPrivileged(uid) || UserIsPrivileged(gid)) {
        return true;
    }
    // FYI We will typically be here for 'adb logcat'
    return checkSupplementaryGroup(uid, gid, pid, AID_LOG);
}

bool clientHasLogCredentials(SocketClient* cli) {
    if (UserIsPrivileged(cli->getUid()) || UserIsPrivileged(cli->getGid())) {
        return true;
    }

    // Kernel version 4.13 added SO_PEERGROUPS to return the supplemental groups of a peer socket,
    // so try that first then fallback to the above racy checking of /proc/<pid>/status if the
    // kernel is too old.  Per
    // https://source.android.com/devices/architecture/kernel/android-common, the fallback can be
    // removed no earlier than 2024.
    auto supplemental_groups = std::vector<gid_t>(16, -1);
    socklen_t groups_size = supplemental_groups.size() * sizeof(gid_t);

    int result = getsockopt(cli->getSocket(), SOL_SOCKET, SO_PEERGROUPS, supplemental_groups.data(),
                            &groups_size);

    if (result != 0) {
        if (errno != ERANGE) {
            return clientHasLogCredentials(cli->getUid(), cli->getGid(), cli->getPid());
        }

        supplemental_groups.resize(groups_size / sizeof(gid_t), -1);
        result = getsockopt(cli->getSocket(), SOL_SOCKET, SO_PEERGROUPS, supplemental_groups.data(),
                            &groups_size);

        // There is still some error after resizing supplemental_groups, fallback.
        if (result != 0) {
            return clientHasLogCredentials(cli->getUid(), cli->getGid(), cli->getPid());
        }
    }

    supplemental_groups.resize(groups_size / sizeof(gid_t), -1);
    for (const auto& gid : supplemental_groups) {
        if (UserIsPrivileged(gid)) {
            return true;
        }
    }

    return false;
}

bool clientIsExemptedFromUserConsent(SocketClient* cli) {
    return cli->getUid() < AID_APP_START;
}
