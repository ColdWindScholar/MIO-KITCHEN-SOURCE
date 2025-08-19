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


#include <arpa/inet.h>
#include <errno.h>
#include <netdb.h>
#include <netinet/in.h>
#include <string.h>
#include <sys/socket.h>

#include <iostream>
#include <string>

#include <android-base/format.h>
#include <android/multinetwork.h>
#include "common.h"


int main(int argc, const char* argv[]) {
    int rval = -1;

    struct Arguments args;
    if (!args.parseArguments(argc, argv)) { return rval; }

    const struct addrinfo hints = {
            .ai_family = args.family,
            .ai_socktype = SOCK_DGRAM,
    };
    struct addrinfo *result = nullptr;

    time_t t;
    time(&t);
    srand((unsigned long)time);

    for (int i = 0; i < args.attempts; i++) {
        std::string name;

        if (args.random_name) {
            name = fmt::format("{}-{}-ds.metric.gstatic.com", rand(), rand());
        } else {
            name = args.arg1;
        }

        std::cout << "# " << name << " (via nethandle " << args.nethandle << "):" << std::endl;

        switch (args.api_mode) {
            case ApiMode::EXPLICIT:
                rval = android_getaddrinfofornetwork(args.nethandle, name.c_str(), nullptr, &hints,
                                                     &result);
                break;
            case ApiMode::PROCESS:
                if (args.nethandle != NETWORK_UNSPECIFIED) {
                    rval = android_setprocnetwork(args.nethandle);
                    if (rval != 0) {
                        std::cerr << "android_setprocnetwork returned " << rval << std::endl;
                        return rval;
                    }
                }
                rval = getaddrinfo(name.c_str(), nullptr, &hints, &result);
                break;
            default:
                // Unreachable.
                std::cerr << "Unknown api mode." << std::endl;
                return -1;
        }

        if (rval != 0) {
            std::cerr << "DNS resolution failure; gaierror=" << rval << " [" << gai_strerror(rval)
                      << "]" << std::endl;
            return rval;
        }

        for (struct addrinfo* rp = result; rp != nullptr; rp = rp->ai_next) {
            std::cout << inetSockaddrToString(rp->ai_addr) << std::endl;
        }

        freeaddrinfo(result);
    }

    return 0;
}
