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

#define TRACE_TAG MDNS

#include "transport.h"

#ifdef _WIN32
#include <winsock2.h>
#else
#include <arpa/inet.h>
#endif

#include <memory>
#include <thread>
#include <unordered_set>
#include <vector>

#include <android-base/stringprintf.h>
#include <android-base/strings.h>

#include <discovery/common/config.h>
#include <discovery/common/reporting_client.h>
#include <discovery/public/dns_sd_service_factory.h>
#include <platform/api/network_interface.h>
#include <platform/api/serial_delete_ptr.h>
#include <platform/base/error.h>
#include <platform/base/interface_info.h>

#include "adb_client.h"
#include "adb_mdns.h"
#include "adb_trace.h"
#include "adb_utils.h"
#include "adb_wifi.h"
#include "client/mdns_utils.h"
#include "client/openscreen/mdns_service_watcher.h"
#include "client/openscreen/platform/task_runner.h"
#include "fdevent/fdevent.h"
#include "sysdeps.h"

namespace {

using namespace mdns;
using namespace openscreen;
using ServicesUpdatedState = mdns::ServiceReceiver::ServicesUpdatedState;

struct DiscoveryState;
DiscoveryState* g_state = nullptr;
// TODO: remove once openscreen has bonjour client APIs.
bool g_using_bonjour = false;
AdbMdnsResponderFuncs g_adb_mdnsresponder_funcs;

class DiscoveryReportingClient : public discovery::ReportingClient {
  public:
    void OnFatalError(Error error) override {
        // The multicast port 5353 may fail to bind because of another process already binding
        // to it (bonjour). So let's fallback to bonjour client APIs.
        // TODO: Remove this once openscreen implements the bonjour client APIs.
        LOG(ERROR) << "Encountered fatal discovery error: " << error;
        got_fatal_ = true;
    }

    void OnRecoverableError(Error error) override {
        LOG(ERROR) << "Encountered recoverable discovery error: " << error;
    }

    bool GotFatalError() const { return got_fatal_; }

  private:
    std::atomic<bool> got_fatal_{false};
};

struct DiscoveryState {
    std::optional<discovery::Config> config;
    SerialDeletePtr<discovery::DnsSdService> service;
    std::unique_ptr<DiscoveryReportingClient> reporting_client;
    std::unique_ptr<AdbOspTaskRunner> task_runner;
    std::vector<std::unique_ptr<ServiceReceiver>> receivers;
    InterfaceInfo interface_info;
};

// Callback provided to service receiver for updates.
void OnServiceReceiverResult(std::vector<std::reference_wrapper<const ServiceInfo>> infos,
                             std::reference_wrapper<const ServiceInfo> info,
                             ServicesUpdatedState state) {
    VLOG(MDNS) << "Endpoint state=" << static_cast<int>(state)
               << " instance_name=" << info.get().instance_name
               << " service_name=" << info.get().service_name << " addr=" << info.get().v4_address
               << " addrv6=" << info.get().v6_address << " total_serv=" << infos.size();

    switch (state) {
        case ServicesUpdatedState::EndpointCreated:
        case ServicesUpdatedState::EndpointUpdated:
            if (adb_DNSServiceShouldAutoConnect(info.get().service_name,
                                                info.get().instance_name) &&
                info.get().v4_address) {
                auto index = adb_DNSServiceIndexByName(info.get().service_name);
                if (!index) {
                    return;
                }

                // Don't try to auto-connect if not in the keystore.
                if (*index == kADBSecureConnectServiceRefIndex &&
                    !adb_wifi_is_known_host(info.get().instance_name)) {
                    VLOG(MDNS) << "instance_name=" << info.get().instance_name
                               << " not in keystore";
                    return;
                }
                std::string response;
                VLOG(MDNS) << "Attempting to auto-connect to instance=" << info.get().instance_name
                           << " service=" << info.get().service_name << " addr4=%s"
                           << info.get().v4_address << ":" << info.get().port;
                connect_device(
                        android::base::StringPrintf("%s.%s", info.get().instance_name.c_str(),
                                                    info.get().service_name.c_str()),
                        &response);
            }
            break;
        default:
            break;
    }
}

std::optional<discovery::Config> GetConfigForAllInterfaces() {
    auto interface_infos = GetNetworkInterfaces();

    discovery::Config config;

    // The host only consumes mDNS traffic. It doesn't publish anything.
    // Avoid creating an mDNSResponder that will listen with authority
    // to answer over no domain.
    config.enable_publication = false;

    for (const auto interface : interface_infos) {
        if (interface.GetIpAddressV4() || interface.GetIpAddressV6()) {
            config.network_info.push_back({interface});
            VLOG(MDNS) << "Listening on interface [" << interface << "]";
        }
    }

    if (config.network_info.empty()) {
        VLOG(MDNS) << "No available network interfaces for mDNS discovery";
        return std::nullopt;
    }

    return config;
}

void StartDiscovery() {
    CHECK(!g_state);
    g_state = new DiscoveryState();
    g_state->task_runner = std::make_unique<AdbOspTaskRunner>();
    g_state->reporting_client = std::make_unique<DiscoveryReportingClient>();

    g_state->task_runner->PostTask([]() {
        g_state->config = GetConfigForAllInterfaces();
        if (!g_state->config) {
            VLOG(MDNS) << "No mDNS config. Aborting StartDiscovery()";
            return;
        }

        VLOG(MDNS) << "Starting discovery on " << (*g_state->config).network_info.size()
                   << " interfaces";

        g_state->service = discovery::CreateDnsSdService(
                g_state->task_runner.get(), g_state->reporting_client.get(), *g_state->config);
        // Register a receiver for each service type
        for (int i = 0; i < kNumADBDNSServices; ++i) {
            auto receiver = std::make_unique<ServiceReceiver>(
                    g_state->service.get(), kADBDNSServices[i], OnServiceReceiverResult);
            receiver->StartDiscovery();
            g_state->receivers.push_back(std::move(receiver));

            if (g_state->reporting_client->GotFatalError()) {
                for (auto& r : g_state->receivers) {
                    if (r->is_running()) {
                        r->StopDiscovery();
                    }
                }
                g_using_bonjour = true;
                break;
            }
        }

        if (g_using_bonjour) {
            VLOG(MDNS) << "Fallback to MdnsResponder client for discovery";
            g_adb_mdnsresponder_funcs = StartMdnsResponderDiscovery();
        }
    });
}

void ForEachService(const std::unique_ptr<ServiceReceiver>& receiver,
                    std::string_view wanted_instance_name, adb_secure_foreach_service_callback cb) {
    if (!receiver->is_running()) {
        return;
    }
    auto services = receiver->GetServices();
    for (const auto& s : services) {
        if (wanted_instance_name.empty() || s.get().instance_name == wanted_instance_name) {
            std::stringstream ss;
            ss << s.get().v4_address;
            cb(s.get().instance_name.c_str(), s.get().service_name.c_str(), ss.str().c_str(),
               s.get().port);
        }
    }
}

bool ConnectAdbSecureDevice(const MdnsInfo& info) {
    if (!adb_wifi_is_known_host(info.service_name)) {
        VLOG(MDNS) << "serviceName=" << info.service_name << " not in keystore";
        return false;
    }

    std::string response;
    connect_device(android::base::StringPrintf("%s.%s", info.service_name.c_str(),
                                               info.service_type.c_str()),
                   &response);
    D("Secure connect to %s regtype %s (%s:%hu) : %s", info.service_name.c_str(),
      info.service_type.c_str(), info.addr.c_str(), info.port, response.c_str());
    return true;
}

}  // namespace

/////////////////////////////////////////////////////////////////////////////////

bool using_bonjour(void) {
    return g_using_bonjour;
}

void mdns_cleanup() {
    if (g_using_bonjour) {
        return g_adb_mdnsresponder_funcs.mdns_cleanup();
    }
}

void init_mdns_transport_discovery() {
    const char* mdns_osp = getenv("ADB_MDNS_OPENSCREEN");
    if (mdns_osp && strcmp(mdns_osp, "0") == 0) {
        g_using_bonjour = true;
        g_adb_mdnsresponder_funcs = StartMdnsResponderDiscovery();
    } else {
        VLOG(MDNS) << "Openscreen mdns discovery enabled";
        StartDiscovery();
    }
}

bool adb_secure_connect_by_service_name(const std::string& instance_name) {
    if (g_using_bonjour) {
        return g_adb_mdnsresponder_funcs.adb_secure_connect_by_service_name(instance_name);
    }

    if (!g_state || g_state->receivers.empty()) {
        VLOG(MDNS) << "Mdns not enabled";
        return false;
    }

    std::optional<MdnsInfo> info;
    auto cb = [&](const std::string& instance_name, const std::string& service_name,
                  const std::string& ip_addr,
                  uint16_t port) { info.emplace(instance_name, service_name, ip_addr, port); };
    ForEachService(g_state->receivers[kADBSecureConnectServiceRefIndex], instance_name, cb);
    if (info.has_value()) {
        return ConnectAdbSecureDevice(*info);
    }
    return false;
}

std::string mdns_check() {
    if (!g_state && !g_using_bonjour) {
        return "ERROR: mdns discovery disabled";
    }

    if (g_using_bonjour) {
        return g_adb_mdnsresponder_funcs.mdns_check();
    }

    return "mdns daemon version [Openscreen discovery 0.0.0]";
}

std::string mdns_list_discovered_services() {
    if (g_using_bonjour) {
        return g_adb_mdnsresponder_funcs.mdns_list_discovered_services();
    }

    if (!g_state || g_state->receivers.empty()) {
        return "";
    }

    std::string result;
    auto cb = [&](const std::string& instance_name, const std::string& service_name,
                  const std::string& ip_addr, uint16_t port) {
        result += android::base::StringPrintf("%s\t%s\t%s:%u\n", instance_name.data(),
                                              service_name.data(), ip_addr.data(), port);
    };

    for (const auto& receiver : g_state->receivers) {
        ForEachService(receiver, "", cb);
    }
    return result;
}

std::optional<MdnsInfo> mdns_get_connect_service_info(const std::string& name) {
    CHECK(!name.empty());

    if (g_using_bonjour) {
        return g_adb_mdnsresponder_funcs.mdns_get_connect_service_info(name);
    }

    if (!g_state || g_state->receivers.empty()) {
        return std::nullopt;
    }

    auto mdns_instance = mdns::mdns_parse_instance_name(name);
    if (!mdns_instance.has_value()) {
        D("Failed to parse mDNS name [%s]", name.data());
        return std::nullopt;
    }

    std::optional<MdnsInfo> info;
    auto cb = [&](const std::string& instance_name, const std::string& service_name,
                  const std::string& ip_addr,
                  uint16_t port) { info.emplace(instance_name, service_name, ip_addr, port); };

    std::string reg_type;
    // Service name was provided.
    if (!mdns_instance->service_name.empty()) {
        reg_type = android::base::StringPrintf("%s.%s", mdns_instance->service_name.data(),
                                               mdns_instance->transport_type.data());
        const auto index = adb_DNSServiceIndexByName(reg_type);
        if (!index) {
            return std::nullopt;
        }
        switch (*index) {
            case kADBTransportServiceRefIndex:
            case kADBSecureConnectServiceRefIndex:
                ForEachService(g_state->receivers[*index], mdns_instance->instance_name, cb);
                break;
            default:
                D("Not a connectable service name [%s]", reg_type.data());
                return std::nullopt;
        }
        return info;
    }

    // No mdns service name provided. Just search for the instance name in all adb connect services.
    // Prefer the secured connect service over the other.
    ForEachService(g_state->receivers[kADBSecureConnectServiceRefIndex], name, cb);
    if (!info.has_value()) {
        ForEachService(g_state->receivers[kADBTransportServiceRefIndex], name, cb);
    }

    return info;
}

std::optional<MdnsInfo> mdns_get_pairing_service_info(const std::string& name) {
    CHECK(!name.empty());

    if (g_using_bonjour) {
        return g_adb_mdnsresponder_funcs.mdns_get_pairing_service_info(name);
    }

    if (!g_state || g_state->receivers.empty()) {
        return std::nullopt;
    }

    auto mdns_instance = mdns::mdns_parse_instance_name(name);
    if (!mdns_instance.has_value()) {
        D("Failed to parse mDNS name [%s]", name.data());
        return std::nullopt;
    }

    std::optional<MdnsInfo> info;
    auto cb = [&](const std::string& instance_name, const std::string& service_name,
                  const std::string& ip_addr,
                  uint16_t port) { info.emplace(instance_name, service_name, ip_addr, port); };

    std::string reg_type;
    // Verify it's a pairing service if user explicitly inputs it.
    if (!mdns_instance->service_name.empty()) {
        reg_type = android::base::StringPrintf("%s.%s", mdns_instance->service_name.data(),
                                               mdns_instance->transport_type.data());
        const auto index = adb_DNSServiceIndexByName(reg_type);
        if (!index) {
            return std::nullopt;
        }
        switch (*index) {
            case kADBSecurePairingServiceRefIndex:
                break;
            default:
                D("Not an adb pairing reg_type [%s]", reg_type.data());
                return std::nullopt;
        }
        return info;
    }

    ForEachService(g_state->receivers[kADBSecurePairingServiceRefIndex], name, cb);

    return info;
}
