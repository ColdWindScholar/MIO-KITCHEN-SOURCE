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


#include <errno.h>
#include <fcntl.h>
#include <netdb.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/uio.h>
#include <iostream>
#include <string>

#include <android/multinetwork.h>
#include <android-base/stringprintf.h>
#include "common.h"

using android::base::StringPrintf;

struct Parameters {
    Parameters() : ss({}), port("80"), path("/") {}

    struct sockaddr_storage ss;
    std::string host;
    std::string hostname;
    std::string port;
    std::string path;
};

bool resolveHostname(const struct Arguments& args, struct Parameters* parameters);

bool parseUrl(const struct Arguments& args, struct Parameters* parameters) {
    if (parameters == nullptr) { return false; }

    if (args.random_name) {
        parameters->host = StringPrintf("%d-%d-ipv6test.ds.metric.gstatic.com", rand(), rand());
        parameters->hostname = parameters->host;
        parameters->path = "/ip.js?fmt=text";
        return resolveHostname(args, parameters);
    }

    static const char HTTP_PREFIX[] = "http://";
    if (strncmp(args.arg1, HTTP_PREFIX, strlen(HTTP_PREFIX)) != 0) {
        std::cerr << "Only " << HTTP_PREFIX << " URLs supported." << std::endl;
        return false;
    }

    parameters->host = std::string(args.arg1).substr(strlen(HTTP_PREFIX));
    const auto first_slash = parameters->host.find_first_of('/');
    if (first_slash != std::string::npos) {
        parameters->path = parameters->host.substr(first_slash);
        parameters->host.erase(first_slash);
    }

    if (parameters->host.size() == 0) {
        std::cerr << "Host portion cannot be empty." << std::endl;
        return false;
    }

    if (parameters->host[0] == '[') {
        const auto closing_bracket = parameters->host.find_first_of(']');
        if (closing_bracket == std::string::npos) {
            std::cerr << "Missing closing bracket." << std::endl;
            return false;
        }
        parameters->hostname = parameters->host.substr(1, closing_bracket - 1);

        const auto colon_port = closing_bracket + 1;
        if (colon_port < parameters->host.size()) {
            if (parameters->host[colon_port] != ':') {
                std::cerr << "Malformed port portion." << std::endl;
                return false;
            }
            parameters->port = parameters->host.substr(closing_bracket + 2);
        }
    } else {
        const auto first_colon = parameters->host.find_first_of(':');
        if (first_colon != std::string::npos) {
            parameters->port = parameters->host.substr(first_colon + 1);
            parameters->hostname = parameters->host.substr(0, first_colon);
        } else {
            parameters->hostname = parameters->host;
        }
    }

    // TODO: find the request portion to send (before '#...').

    return resolveHostname(args, parameters);
}

bool resolveHostname(const struct Arguments& args, struct Parameters* parameters) {
    std::cerr << "Resolving hostname=" << parameters->hostname
              << ", port=" << parameters->port
              << std::endl;

    struct addrinfo hints = {
            .ai_family = args.family,
            .ai_socktype = SOCK_STREAM,
    };
    struct addrinfo *result = nullptr;

    int rval = -1;
    switch (args.api_mode) {
        case ApiMode::EXPLICIT:
            rval = android_getaddrinfofornetwork(args.nethandle,
                                                 parameters->hostname.c_str(),
                                                 parameters->port.c_str(),
                                                 &hints, &result);
            break;
        case ApiMode::PROCESS:
            rval = getaddrinfo(parameters->hostname.c_str(),
                               parameters->port.c_str(),
                               &hints, &result);
            break;
        default:
            // Unreachable.
            std::cerr << "Unknown api mode." << std::endl;
            return false;
    }

    if (rval != 0) {
        std::cerr << "DNS resolution failure; gaierror=" << rval
                  << " [" << gai_strerror(rval) << "]"
                  << std::endl;
        return rval;
    }

    memcpy(&(parameters->ss), result[0].ai_addr, result[0].ai_addrlen);
    std::cerr << "Connecting to: "
              << inetSockaddrToString(result[0].ai_addr)
              << std::endl;

    freeaddrinfo(result);
    return true;
}

int makeTcpSocket(sa_family_t address_family, net_handle_t nethandle) {
    int fd = socket(address_family, SOCK_STREAM, IPPROTO_TCP);
    if (fd < 0) {
        std::cerr << "failed to create TCP socket" << std::endl;
        return -1;
    }

    // Don't let reads or writes block indefinitely. We cannot control
    // connect() timeouts without nonblocking sockets and select/poll/epoll.
    const struct timeval timeo = { 5, 0 };  // 5 seconds
    setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeo, sizeof(timeo));
    setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeo, sizeof(timeo));

    if (nethandle != NETWORK_UNSPECIFIED) {
        if (android_setsocknetwork(nethandle, fd) != 0) {
            int errnum = errno;
            std::cerr << "android_setsocknetwork() failed;"
                      << " errno: " << errnum << " [" << strerror(errnum) << "]"
                      << std::endl;
            close(fd);
            return -1;
        }
    }
    return fd;
}


int doHttpQuery(int fd, const struct Parameters& parameters) {
    int rval = -1;
    if (connect(fd,
                reinterpret_cast<const struct sockaddr *>(&(parameters.ss)),
                (parameters.ss.ss_family == AF_INET6)
                        ? sizeof(struct sockaddr_in6)
                        : sizeof(struct sockaddr_in)) != 0) {
        int errnum = errno;
        std::cerr << "Failed to connect; errno=" << errnum
                  << " [" << strerror(errnum) << "]"
                  << std::endl;
        return -1;
    }

    const std::string request(android::base::StringPrintf(
            "GET %s HTTP/1.1\r\n"
            "Host: %s\r\n"
            "Accept: */*\r\n"
            "Connection: close\r\n"
            "User-Agent: httpurl/0.0\r\n"
            "\r\n",
            parameters.path.c_str(), parameters.host.c_str()));
    const ssize_t sent = write(fd, request.c_str(), request.size());
    if (sent != static_cast<ssize_t>(request.size())) {
        std::cerr << "Sent only " << sent << "/" << request.size() << " bytes"
                  << std::endl;
        return -1;
    }

    char buf[4*1024];
    do {
        rval = recv(fd, buf, sizeof(buf), 0);

        if (rval < 0) {
            const int saved_errno = errno;
            std::cerr << "Failed to recv; errno=" << saved_errno
                      << " [" << strerror(saved_errno) << "]"
                      << std::endl;
        } else if (rval > 0) {
            std::cout.write(buf, rval);
            std::cout.flush();
        }
    } while (rval > 0);
    std::cout << std::endl;

    return 0;
}


int main(int argc, const char* argv[]) {
    int rval = -1;

    struct Arguments args;
    if (!args.parseArguments(argc, argv)) { return rval; }

    if (args.api_mode == ApiMode::PROCESS) {
        rval = android_setprocnetwork(args.nethandle);
        if (rval != 0) {
            int errnum = errno;
            std::cerr << "android_setprocnetwork(" << args.nethandle << ") failed;"
                      << " errno: " << errnum << " [" << strerror(errnum) << "]"
                      << std::endl;
            return rval;
        }
    }

    struct Parameters parameters;
    if (!parseUrl(args, &parameters)) { return -1; }

    int ret = 0;

    for (int i = 0; i < args.attempts; i++) {
        // TODO: Fall back from IPv6 to IPv4 if ss.ss_family is AF_UNSPEC.
        // This will involve changes to parseUrl() as well.
        struct FdAutoCloser closer = makeTcpSocket(
                parameters.ss.ss_family,
                (args.api_mode == ApiMode::EXPLICIT) ? args.nethandle : NETWORK_UNSPECIFIED);
        if (closer.fd < 0) {
            return closer.fd;
        }

        ret |= doHttpQuery(closer.fd, parameters);
    }

    return ret;
}
