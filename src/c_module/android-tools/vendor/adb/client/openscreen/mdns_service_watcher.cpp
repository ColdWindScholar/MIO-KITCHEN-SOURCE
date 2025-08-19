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

#include "client/openscreen/mdns_service_watcher.h"

#include "client/openscreen/mdns_service_info.h"

using namespace openscreen;

namespace mdns {

ServiceReceiver::ServiceReceiver(
        discovery::DnsSdService* service, std::string_view service_name,
        openscreen::discovery::DnsSdServiceWatcher<ServiceInfo>::ServicesUpdatedCallback cb)
    : discovery::DnsSdServiceWatcher<ServiceInfo>(
              service, service_name.data(), DnsSdInstanceEndpointToServiceInfo, std::move(cb)) {
    LOG(VERBOSE) << "Initializing ServiceReceiver service=" << service_name;
}
}  // namespace mdns
