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


#include "common.h"

#include <android/api-level.h>
#include <arpa/inet.h>
#include <assert.h>
#include <ctype.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <iostream>


namespace {

bool strEqual(const char *a, const char *b) {
    return strcmp(a, b) == 0;
}

// Allow specifying network handles in decimal and hexadecimal.
bool parseNetworkHandle(const char *arg, net_handle_t *nethandle) {
    if (arg == nullptr || !isdigit(arg[0]) || nethandle == nullptr) {
        return false;
    }

    net_handle_t nh;
    char *end = nullptr;

    nh = strtoull(arg, &end, 0);
    if (end != nullptr && *end == '\0') {
        *nethandle = nh;
        return true;
    }
    return false;
}

}  // namespace


void printUsage(const char *progname) {
    std::cerr << "Usage: " << progname << " [--nethandle <nethandle>]"
              << " [--mode explicit|process]"
              << " [--family unspec|ipv4|ipv6]"
              << " [--attempts <N>]"
              << " --randomname | name" << std::endl
              << std::endl
              << "Learn nethandle values from 'dumpsys connectivity --short' "
              << "or 'dumpsys connectivity --diag'" << std::endl;
}

Arguments::~Arguments() {}

bool Arguments::parseArguments(int argc, const char* argv[]) {
    if (argc < 1 || argv == nullptr) { return false; }

    for (int i = 1; i < argc; i++) {
        if (strEqual(argv[i], "--nethandle")) {
            i++;
            if (argc == i) break;
            if (!parseNetworkHandle(argv[i], &nethandle)) {
                std::cerr << "Failed to parse nethandle: '" << argv[i] << "'"
                          << std::endl;
                break;
            }
        } else if (strEqual(argv[i], "--family")) {
            i++;
            if (argc == i) break;
            if (strEqual(argv[i], "unspec")) {
                family = AF_UNSPEC;
            } else if (strEqual(argv[i], "ipv4")) {
                family = AF_INET;
            } else if (strEqual(argv[i], "ipv6")) {
                family = AF_INET6;
            } else {
                break;
            }
        } else if (strEqual(argv[i], "--mode")) {
            i++;
            if (argc == i) break;
            if (strEqual(argv[i], "explicit")) {
                api_mode = ApiMode::EXPLICIT;
            } else if (strEqual(argv[i], "process")) {
                api_mode = ApiMode::PROCESS;
            } else {
                break;
            }
        } else if (strEqual(argv[i], "--attempts")) {
            i++;
            if (argc == i) break;
            char* endptr;
            attempts = strtoul(argv[i], &endptr, 10);
            if (*endptr != '\0') {
                std::cerr << "Failed to parse arguments: '" << argv[i] << "'" << std::endl;
                break;
            }
        } else if (strEqual(argv[i], "--randomname")) {
            time_t t;
            time(&t);
            srand((unsigned long)time);
            random_name = true;
        } else if (arg1 == nullptr && !random_name) {
            arg1 = argv[i];
        } else {
            arg1 = nullptr;
            break;
        }
    }

    if (random_name || arg1 != nullptr) {
        return true;
    }

    printUsage(argv[0]);
    return false;
}


std::string inetSockaddrToString(const sockaddr* sa) {
    const bool is_ipv6 = (sa->sa_family == AF_INET6);
    char host[INET6_ADDRSTRLEN];
    char port[sizeof("65535")];
    getnameinfo(sa, is_ipv6 ? sizeof(sockaddr_in6) : sizeof(sockaddr_in),
                host, sizeof(host),
                port, sizeof(port),
                NI_NUMERICHOST | NI_NUMERICSERV);

    if (port[0] == '0' || port[0] == '\0') {
        return std::string(host);
    }
    return (is_ipv6 ? "[" : "") + std::string(host) + (is_ipv6 ? "]:" : ":") + std::string(port);
}
