/*
 * Copyright (C) 2020 The Android Open Source Project
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

#include <errno.h>
#include <pthread.h>
#include <sys/inotify.h>
#include <sys/prctl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#include <atomic>
#include <map>
#include <mutex>
#include <string>
#include <thread>

#include <android-base/logging.h>
#include <android-base/unique_fd.h>
#include <packagelistparser/packagelistparser.h>

#include "LogUtils.h"

using android::base::unique_fd;

#define PACKAGES_LIST_FILE "/data/system/packages.list"

struct PkgIdMap {
    bool active = false;
    std::mutex lock;
    std::atomic<bool> running = false;
    std::map<uid_t, std::string> appid_to_package;
    std::unique_ptr<std::thread> pklp_thread;
};

static PkgIdMap* gPkgIdMap = new PkgIdMap;

static bool PackageParseCallback(pkg_info* info, void* userdata) {
    struct PkgIdMap* global = static_cast<struct PkgIdMap*>(userdata);
    if (info->name != NULL && info->name[0] != '\0') {
        global->appid_to_package.emplace(info->uid, info->name);
    }
    packagelist_free(info);
    return true;
}

static bool ReadPackageList(struct PkgIdMap* global) {
    std::lock_guard<std::mutex> guard(global->lock);
    global->appid_to_package.clear();
    bool rc = packagelist_parse(PackageParseCallback, global);
    LOG(INFO) << "ReadPackageList, total packages: " << global->appid_to_package.size();
    return rc;
}

static void WatchPackageList(struct PkgIdMap* global) {
    struct inotify_event* event;
    char event_buf[512];

    unique_fd nfd(inotify_init1(IN_CLOEXEC));
    if (nfd == -1) {
        LOG(FATAL) << "inotify_init failed";
        return;
    }

    global->active = false;
    while (1) {
        if (!global->active) {
            LOG(INFO) << "start watching " PACKAGES_LIST_FILE " ...";
            int ret = inotify_add_watch(nfd, PACKAGES_LIST_FILE, IN_DELETE_SELF);
            if (ret == -1) {
                if (errno == ENOENT || errno == EACCES) {
                    LOG(INFO) << "missing " PACKAGES_LIST_FILE "; retrying...";
                    return;
                } else {
                    PLOG(ERROR) << "inotify_add_watch failed";
                    return;
                }
            }

            if (ReadPackageList(global) == false) {
                LOG(ERROR) << "ReadPackageList failed";
                return;
            }
            global->active = true;
        }

        int event_pos = 0;
        ssize_t res = TEMP_FAILURE_RETRY(read(nfd, event_buf, sizeof(event_buf)));
        if (res == -1 || static_cast<size_t>(res) < sizeof(*event)) {
            LOG(ERROR) << "failed to read inotify event, res: " << res;
            global->active = false;
            continue;
        }

        while (res >= static_cast<ssize_t>(sizeof(*event))) {
            int event_size;
            event = reinterpret_cast<struct inotify_event*>(event_buf + event_pos);

            if ((event->mask & IN_IGNORED) == IN_IGNORED) {
                global->active = false;
            }

            event_size = sizeof(*event) + event->len;
            res -= event_size;
            event_pos += event_size;
        }
    }
}

static void StartHandler(struct PkgIdMap* global) {
    prctl(PR_SET_NAME, "logd.pkglist");
    WatchPackageList(global);
    global->running = false;
}

void StartPkgMonitor() {
    std::lock_guard<std::mutex> guard(gPkgIdMap->lock);
    if (gPkgIdMap->pklp_thread.get() == nullptr) {
        gPkgIdMap->running = true;
        gPkgIdMap->pklp_thread = std::make_unique<std::thread>(StartHandler, gPkgIdMap);
    } else if (!gPkgIdMap->running) {
        gPkgIdMap->pklp_thread->join();
        gPkgIdMap->running = true;
        gPkgIdMap->pklp_thread.reset(new std::thread(StartHandler, gPkgIdMap));
    }
}

char* android::uidToName(uid_t u) {
    {
        std::lock_guard<std::mutex> guard(gPkgIdMap->lock);
        if (gPkgIdMap->active) {
            const auto& iter = gPkgIdMap->appid_to_package.find(u);
            if (iter != gPkgIdMap->appid_to_package.end()) {
                return strdup(iter->second.c_str());
            }
        }
    }

    struct Userdata {
        uid_t uid;
        char* name;
    } userdata = {
            .uid = u,
            .name = nullptr,
    };

    packagelist_parse(
            [](pkg_info* info, void* callback_parameter) {
                auto userdata = reinterpret_cast<Userdata*>(callback_parameter);
                bool result = true;
                if (info->uid == userdata->uid) {
                    userdata->name = strdup(info->name);
                    // false to stop processing
                    result = false;
                }
                packagelist_free(info);
                return result;
            },
            &userdata);

    if (userdata.name != nullptr) {
        StartPkgMonitor();
    }
    return userdata.name;
}
