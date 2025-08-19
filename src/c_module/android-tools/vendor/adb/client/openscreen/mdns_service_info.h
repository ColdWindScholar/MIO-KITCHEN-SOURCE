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

#pragma once

#include <string>

#include <discovery/dnssd/public/dns_sd_instance_endpoint.h>
#include <platform/base/ip_address.h>

#include "client/mdns_utils.h"

namespace mdns {

struct ServiceInfo {
    std::string instance_name;
    std::string service_name;
    openscreen::IPAddress v4_address;
    openscreen::IPAddress v6_address;
    uint16_t port;
};  // ServiceInfo

openscreen::ErrorOr<ServiceInfo> DnsSdInstanceEndpointToServiceInfo(
        const openscreen::discovery::DnsSdInstanceEndpoint& endpoint);

}  // namespace mdns
