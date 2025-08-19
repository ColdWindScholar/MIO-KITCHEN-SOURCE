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

#include <string_view>

#include "client/openscreen/mdns_service_info.h"

#include <discovery/public/dns_sd_service_watcher.h>

namespace mdns {

class ServiceReceiver : public ::openscreen::discovery::DnsSdServiceWatcher<ServiceInfo> {
  public:
    explicit ServiceReceiver(
            openscreen::discovery::DnsSdService* service, std::string_view service_name,
            openscreen::discovery::DnsSdServiceWatcher<ServiceInfo>::ServicesUpdatedCallback cb);

    const std::string& service_name() const { return service_name_; }

  private:
    std::string service_name_;
};  // ServiceReceiver

}  // namespace mdns
