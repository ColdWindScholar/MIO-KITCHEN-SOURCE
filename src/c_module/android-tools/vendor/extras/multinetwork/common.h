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


#ifndef SYSTEM_EXTRAS_MULTINETWORK_COMMON_H_
#define SYSTEM_EXTRAS_MULTINETWORK_COMMON_H_

#include <sys/cdefs.h>
#include <sys/socket.h>
#include <unistd.h>
#include <string>
#include <android/multinetwork.h>

enum class ApiMode {
    EXPLICIT,
    PROCESS,
};


struct Arguments {
    Arguments()
        : nethandle(NETWORK_UNSPECIFIED),
          api_mode(ApiMode::EXPLICIT),
          family(AF_UNSPEC),
          attempts(1),
          random_name(false),
          arg1(nullptr) {}
    ~Arguments();

    bool parseArguments(int argc, const char* argv[]);

    net_handle_t nethandle;
    ApiMode api_mode;
    sa_family_t family;
    unsigned attempts;
    bool random_name;
    const char* arg1;
};


void printUsage(const char *progname);

// If port is non-zero returns strings of the form "192.0.2.1:port" or
// "[2001:db8::1]:port", else it returns the bare IP string literal.
std::string inetSockaddrToString(const sockaddr* sa);


struct FdAutoCloser {
    FdAutoCloser() : fd(-1) {}
    /* not explicit */ FdAutoCloser(int fd) : fd(fd) {}
    ~FdAutoCloser() {
        if (fd > -1) {
            close(fd);
        }
        fd = -1;
    }

    int fd;
};

#endif  // SYSTEM_EXTRAS_MULTINETWORK_COMMON_H_
