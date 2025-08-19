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

#define TRACE_TAG TRANSPORT

#include "transport.h"

#ifdef _WIN32
#include <winsock2.h>
#else
#include <arpa/inet.h>
#endif

#include <memory>
#include <thread>
#include <vector>

#include <android-base/stringprintf.h>
#include <android-base/strings.h>
#include <dns_sd.h>

#include "adb_client.h"
#include "adb_mdns.h"
#include "adb_trace.h"
#include "adb_utils.h"
#include "adb_wifi.h"
#include "client/mdns_utils.h"
#include "fdevent/fdevent.h"
#include "sysdeps.h"

// TODO: Remove this file once openscreen has bonjour client APIs implemented.
namespace {

DNSServiceRef g_service_refs[kNumADBDNSServices];
fdevent* g_service_ref_fdes[kNumADBDNSServices];

// Use adb_DNSServiceRefSockFD() instead of calling DNSServiceRefSockFD()
// directly so that the socket is put through the appropriate compatibility
// layers to work with the rest of ADB's internal APIs.
int adb_DNSServiceRefSockFD(DNSServiceRef ref) {
    return adb_register_socket(DNSServiceRefSockFD(ref));
}
#define DNSServiceRefSockFD ___xxx_DNSServiceRefSockFD

void DNSSD_API register_service_ip(DNSServiceRef sdref, DNSServiceFlags flags,
                                   uint32_t interface_index, DNSServiceErrorType error_code,
                                   const char* hostname, const sockaddr* address, uint32_t ttl,
                                   void* context);

void pump_service_ref(int /*fd*/, unsigned ev, void* data) {
    DNSServiceRef* ref = reinterpret_cast<DNSServiceRef*>(data);

    if (ev & FDE_READ) DNSServiceProcessResult(*ref);
}

class AsyncServiceRef {
  public:
    bool Initialized() const { return initialized_; }

    void DestroyServiceRef() {
        if (!initialized_) {
            return;
        }

        // Order matters here! Must destroy the fdevent first since it has a
        // reference to |sdref_|.
        fdevent_destroy(fde_);
        D("DNSServiceRefDeallocate(sdref=%p)", sdref_);
        DNSServiceRefDeallocate(sdref_);
        initialized_ = false;
    }

    virtual ~AsyncServiceRef() { DestroyServiceRef(); }

  protected:
    DNSServiceRef sdref_;

    void Initialize() {
        fde_ = fdevent_create(adb_DNSServiceRefSockFD(sdref_), pump_service_ref, &sdref_);
        if (fde_ == nullptr) {
            D("Unable to create fdevent");
            return;
        }
        fdevent_set(fde_, FDE_READ);
        initialized_ = true;
    }

  private:
    bool initialized_ = false;
    fdevent* fde_;
};

class ResolvedService : public AsyncServiceRef {
  public:
    virtual ~ResolvedService() = default;

    ResolvedService(const std::string& service_name, const std::string& reg_type,
                    uint32_t interface_index, const std::string& host_target, uint16_t port,
                    int version)
        : service_name_(service_name),
          reg_type_(reg_type),
          host_target_(host_target),
          port_(port),
          sa_family_(0),
          service_version_(version) {
        /* TODO: We should be able to get IPv6 support by adding
         * kDNSServiceProtocol_IPv6 to the flags below. However, when we do
         * this, we get served link-local addresses that are usually useless to
         * connect to. What's more, we seem to /only/ get those and nothing else.
         * If we want IPv6 in the future we'll have to figure out why.
         */
        DNSServiceErrorType ret = DNSServiceGetAddrInfo(
                &sdref_, 0, interface_index, kDNSServiceProtocol_IPv4, host_target_.c_str(),
                register_service_ip, reinterpret_cast<void*>(this));

        if (ret != kDNSServiceErr_NoError) {
            D("Got %d from DNSServiceGetAddrInfo.", ret);
        } else {
            D("DNSServiceGetAddrInfo(sdref=%p, host_target=%s)", sdref_, host_target_.c_str());
            Initialize();
        }

        D("Client version: %d Service version: %d", ADB_SECURE_CLIENT_VERSION, service_version_);
    }

    bool ConnectSecureWifiDevice() {
        if (!adb_wifi_is_known_host(service_name_)) {
            LOG(INFO) << "service_name=" << service_name_ << " not in keystore";
            return false;
        }

        std::string response;
        connect_device(
                android::base::StringPrintf("%s.%s", service_name_.c_str(), reg_type_.c_str()),
                &response);
        D("Secure connect to %s regtype %s (%s:%hu) : %s", service_name_.c_str(), reg_type_.c_str(),
          ip_addr_.c_str(), port_, response.c_str());
        return true;
    }

    bool RegisterIpAddress(const sockaddr* address) {
        sa_family_ = address->sa_family;

        const void* ip_addr_data;
        if (sa_family_ == AF_INET) {
            ip_addr_data = &reinterpret_cast<const sockaddr_in*>(address)->sin_addr;
            addr_format_ = "%s:%hu";
        } else if (sa_family_ == AF_INET6) {
            ip_addr_data = &reinterpret_cast<const sockaddr_in6*>(address)->sin6_addr;
            addr_format_ = "[%s]:%hu";
        } else {  // Should be impossible
            D("mDNS resolved non-IP address.");
            return false;
        }

        // Winsock version requires the const cast mingw defines inet_ntop differently from msvc.
        char ip_addr[INET6_ADDRSTRLEN] = {};
        if (!inet_ntop(sa_family_, const_cast<void*>(ip_addr_data), ip_addr, sizeof(ip_addr))) {
            D("Could not convert IP address to string.");
            return false;
        }
        ip_addr_ = ip_addr;

        return true;
    }

    static void AddToServiceRegistry(std::unique_ptr<ResolvedService> service) {
        // Add to the service registry before trying to auto-connect, since socket_spec_connect will
        // check these registries for the ip address when connecting via mdns instance name.
        auto service_index = service->service_index();
        if (!service_index) {
            return;
        }

        // Remove any services with the same instance name, as it may be a stale registration.
        RemoveDNSService(service->reg_type(), service->service_name());

        ServiceRegistry* services = nullptr;
        switch (*service_index) {
            case kADBTransportServiceRefIndex:
                services = sAdbTransportServices;
                break;
            case kADBSecurePairingServiceRefIndex:
                services = sAdbSecurePairingServices;
                break;
            case kADBSecureConnectServiceRefIndex:
                services = sAdbSecureConnectServices;
                break;
            default:
                LOG(WARNING) << "No registry available for reg_type=[" << service->reg_type()
                             << "]";
                return;
        }

        services->push_back(std::move(service));
        const auto& s = services->back();

        auto reg_type = s->reg_type();
        auto service_name = s->service_name();

        auto ip_addr = s->ip_address();
        auto port = s->port();
        if (adb_DNSServiceShouldAutoConnect(reg_type, service_name)) {
            std::string response;
            D("Attempting to connect service_name=[%s], regtype=[%s] ip_addr=(%s:%hu)",
              service_name.c_str(), reg_type.c_str(), ip_addr.c_str(), port);

            if (*service_index == kADBSecureConnectServiceRefIndex) {
                s->ConnectSecureWifiDevice();
            } else {
                connect_device(android::base::StringPrintf("%s.%s", service_name.c_str(),
                                                           reg_type.c_str()),
                               &response);
                D("Connect to %s regtype %s (%s:%hu) : %s", service_name.c_str(), reg_type.c_str(),
                  ip_addr.c_str(), port, response.c_str());
            }
        } else {
            D("Not immediately connecting to service_name=[%s], regtype=[%s] ip_addr=(%s:%hu)",
              service_name.c_str(), reg_type.c_str(), ip_addr.c_str(), port);
        }
    }

    std::optional<int> service_index() const {
        return adb_DNSServiceIndexByName(reg_type_.c_str());
    }

    const std::string& service_name() const { return service_name_; }

    const std::string& reg_type() const { return reg_type_; }

    const std::string& ip_address() const { return ip_addr_; }

    uint16_t port() const { return port_; }

    using ServiceRegistry = std::vector<std::unique_ptr<ResolvedService>>;

    // unencrypted tcp connections
    static ServiceRegistry* sAdbTransportServices;

    static ServiceRegistry* sAdbSecurePairingServices;
    static ServiceRegistry* sAdbSecureConnectServices;

    static void InitAdbServiceRegistries();

    static void ForEachService(const ServiceRegistry& services, const std::string& hostname,
                               adb_secure_foreach_service_callback cb);

    static bool ConnectByServiceName(const ServiceRegistry& services,
                                     const std::string& service_name);

    static void RemoveDNSService(const std::string& reg_type, const std::string& service_name);

  private:
    std::string addr_format_;
    std::string service_name_;
    std::string reg_type_;
    std::string host_target_;
    const uint16_t port_;
    int sa_family_;
    std::string ip_addr_;
    int service_version_;
};

// static
ResolvedService::ServiceRegistry* ResolvedService::sAdbTransportServices = NULL;

// static
ResolvedService::ServiceRegistry* ResolvedService::sAdbSecurePairingServices = NULL;

// static
ResolvedService::ServiceRegistry* ResolvedService::sAdbSecureConnectServices = NULL;

// static
void ResolvedService::InitAdbServiceRegistries() {
    if (!sAdbTransportServices) {
        sAdbTransportServices = new ServiceRegistry;
    }
    if (!sAdbSecurePairingServices) {
        sAdbSecurePairingServices = new ServiceRegistry;
    }
    if (!sAdbSecureConnectServices) {
        sAdbSecureConnectServices = new ServiceRegistry;
    }
}

// static
void ResolvedService::ForEachService(const ServiceRegistry& services,
                                     const std::string& wanted_service_name,
                                     adb_secure_foreach_service_callback cb) {
    InitAdbServiceRegistries();

    for (const auto& service : services) {
        auto service_name = service->service_name();
        auto reg_type = service->reg_type();
        auto ip = service->ip_address();
        auto port = service->port();

        if (wanted_service_name.empty()) {
            cb(service_name.c_str(), reg_type.c_str(), ip.c_str(), port);
        } else if (service_name == wanted_service_name) {
            cb(service_name.c_str(), reg_type.c_str(), ip.c_str(), port);
        }
    }
}

// static
bool ResolvedService::ConnectByServiceName(const ServiceRegistry& services,
                                           const std::string& service_name) {
    InitAdbServiceRegistries();
    for (const auto& service : services) {
        auto wanted_name = service->service_name();
        if (wanted_name == service_name) {
            D("Got service_name match [%s]", wanted_name.c_str());
            return service->ConnectSecureWifiDevice();
        }
    }
    D("No registered service_names matched [%s]", service_name.c_str());
    return false;
}

// static
void ResolvedService::RemoveDNSService(const std::string& reg_type,
                                       const std::string& service_name) {
    D("%s: reg_type=[%s] service_name=[%s]", __func__, reg_type.c_str(), service_name.c_str());
    auto index = adb_DNSServiceIndexByName(reg_type);
    if (!index) {
        return;
    }
    ServiceRegistry* services;
    switch (*index) {
        case kADBTransportServiceRefIndex:
            services = sAdbTransportServices;
            break;
        case kADBSecurePairingServiceRefIndex:
            services = sAdbSecurePairingServices;
            break;
        case kADBSecureConnectServiceRefIndex:
            services = sAdbSecureConnectServices;
            break;
        default:
            return;
    }

    if (services->empty()) {
        return;
    }

    services->erase(std::remove_if(services->begin(), services->end(),
                                   [&service_name](std::unique_ptr<ResolvedService>& service) {
                                       return (service_name == service->service_name());
                                   }),
                    services->end());
}

void DNSSD_API register_service_ip(DNSServiceRef sdref, DNSServiceFlags flags,
                                   uint32_t /*interface_index*/, DNSServiceErrorType error_code,
                                   const char* hostname, const sockaddr* address, uint32_t ttl,
                                   void* context) {
    D("%s: sdref=%p flags=0x%08x error_code=%u ttl=%u", __func__, sdref, flags, error_code, ttl);
    std::unique_ptr<ResolvedService> data(static_cast<ResolvedService*>(context));
    // Only resolve the address once. If the address or port changes, we'll just get another
    // registration.
    data->DestroyServiceRef();

    if (error_code != kDNSServiceErr_NoError) {
        D("Got error while looking up ip_addr [%u]", error_code);
        return;
    }

    if (flags & kDNSServiceFlagsAdd) {
        if (data->RegisterIpAddress(address)) {
            D("Resolved IP address for [%s]. Adding to service registry.", hostname);
            ResolvedService::AddToServiceRegistry(std::move(data));
        }
    }
}

void DNSSD_API register_resolved_mdns_service(DNSServiceRef sdref, DNSServiceFlags flags,
                                              uint32_t interface_index,
                                              DNSServiceErrorType error_code, const char* fullname,
                                              const char* host_target, uint16_t port,
                                              uint16_t txt_len, const unsigned char* txt_record,
                                              void* context);

class DiscoveredService : public AsyncServiceRef {
  public:
    DiscoveredService(uint32_t interface_index, const char* service_name, const char* regtype,
                      const char* domain)
        : service_name_(service_name), reg_type_(regtype) {
        DNSServiceErrorType ret =
                DNSServiceResolve(&sdref_, 0, interface_index, service_name, regtype, domain,
                                  register_resolved_mdns_service, reinterpret_cast<void*>(this));

        D("DNSServiceResolve for "
          "interface_index %u "
          "service_name %s "
          "regtype %s "
          "domain %s "
          ": %d",
          interface_index, service_name, regtype, domain, ret);

        if (ret == kDNSServiceErr_NoError) {
            Initialize();
        }
    }

    const std::string& service_name() { return service_name_; }

    const std::string& reg_type() { return reg_type_; }

  private:
    std::string service_name_;
    std::string reg_type_;
};

// Returns the version the device wanted to advertise,
// or -1 if parsing fails.
int ParseVersionFromTxtRecord(uint16_t txt_len, const unsigned char* txt_record) {
    if (!txt_len) return -1;
    if (!txt_record) return -1;

    // https://tools.ietf.org/html/rfc6763
    // """
    // 6.1.  General Format Rules for DNS TXT Records
    //
    // A DNS TXT record can be up to 65535 (0xFFFF) bytes long.  The total
    // length is indicated by the length given in the resource record header
    // in the DNS message.  There is no way to tell directly from the data
    // alone how long it is (e.g., there is no length count at the start, or
    // terminating NULL byte at the end).
    //
    // The format of the data within a DNS TXT record is zero or more strings,
    // packed together in memory without any intervening gaps or padding bytes
    // for word alignment. The format of each constituent string within the DNS
    // TXT record is a single length byte, followed by 0-255 bytes of text data.
    // """

    // We only parse the first string in the record.
    // Let's not trust the length byte (txt_record[0]).
    // Worst case, it wastes 65,535 bytes.
    std::vector<char> record_str(txt_len + 1, '\0');
    char* str = record_str.data();

    memcpy(str, txt_record + 1 /* skip the length byte */, txt_len - 1);

    // Check if it's the version key
    static const char* version_key = "v=";
    size_t version_key_len = strlen(version_key);

    if (strncmp(version_key, str, version_key_len)) return -1;

    auto value_start = str + version_key_len;

    long parsed_number = strtol(value_start, 0, 10);

    // No valid conversion. Also, 0
    // is not a valid version.
    if (!parsed_number) return -1;

    // Outside bounds of int.
    if (parsed_number < INT_MIN || parsed_number > INT_MAX) return -1;

    // Possibly valid version
    return static_cast<int>(parsed_number);
}

void DNSSD_API register_resolved_mdns_service(DNSServiceRef sdref, DNSServiceFlags flags,
                                              uint32_t interface_index,
                                              DNSServiceErrorType error_code, const char* fullname,
                                              const char* host_target, uint16_t port,
                                              uint16_t txt_len, const unsigned char* txt_record,
                                              void* context) {
    D("Resolved a service.");
    std::unique_ptr<DiscoveredService> discovered(reinterpret_cast<DiscoveredService*>(context));

    if (error_code != kDNSServiceErr_NoError) {
        D("Got error %d resolving service.", error_code);
        return;
    }

    // TODO: Reject certain combinations of invalid or mismatched client and
    // service versions here before creating anything.
    // At the moment, there is nothing to reject, so accept everything
    // as an optimistic default.
    auto service_version = ParseVersionFromTxtRecord(txt_len, txt_record);

    auto resolved = new ResolvedService(discovered->service_name(), discovered->reg_type(),
                                        interface_index, host_target, ntohs(port), service_version);

    if (!resolved->Initialized()) {
        D("Unable to init resolved service");
        delete resolved;
    }

    if (flags) { /* Only ever equals MoreComing or 0 */
        D("releasing discovered service");
        discovered.release();
    }
}

void DNSSD_API on_service_browsed(DNSServiceRef sdref, DNSServiceFlags flags,
                                  uint32_t interface_index, DNSServiceErrorType error_code,
                                  const char* service_name, const char* regtype, const char* domain,
                                  void* /*context*/) {
    if (error_code != kDNSServiceErr_NoError) {
        D("Got error %d during mDNS browse.", error_code);
        DNSServiceRefDeallocate(sdref);
        auto service_index = adb_DNSServiceIndexByName(regtype);
        if (service_index) {
            fdevent_destroy(g_service_ref_fdes[*service_index]);
        }
        return;
    }

    if (flags & kDNSServiceFlagsAdd) {
        D("%s: Discover found new service_name=[%s] regtype=[%s] domain=[%s]", __func__,
          service_name, regtype, domain);
        auto discovered = new DiscoveredService(interface_index, service_name, regtype, domain);
        if (!discovered->Initialized()) {
            delete discovered;
        }
    } else {
        D("%s: Discover lost service_name=[%s] regtype=[%s] domain=[%s]", __func__, service_name,
          regtype, domain);
        ResolvedService::RemoveDNSService(regtype, service_name);
    }
}

void init_mdns_transport_discovery_thread() {
    int error_codes[kNumADBDNSServices];
    for (int i = 0; i < kNumADBDNSServices; ++i) {
        error_codes[i] = DNSServiceBrowse(&g_service_refs[i], 0, 0, kADBDNSServices[i], nullptr,
                                          on_service_browsed, nullptr);

        if (error_codes[i] != kDNSServiceErr_NoError) {
            D("Got %d browsing for mDNS service %s.", error_codes[i], kADBDNSServices[i]);
        } else {
            fdevent_run_on_looper([i]() {
                g_service_ref_fdes[i] = fdevent_create(adb_DNSServiceRefSockFD(g_service_refs[i]),
                                                       pump_service_ref, &g_service_refs[i]);
                fdevent_set(g_service_ref_fdes[i], FDE_READ);
            });
        }
    }
}

namespace MdnsResponder {

bool adb_secure_connect_by_service_name(const std::string& instance_name) {
    return ResolvedService::ConnectByServiceName(*ResolvedService::sAdbSecureConnectServices,
                                                 instance_name);
}

std::string mdns_check() {
    uint32_t daemon_version;
    uint32_t sz = sizeof(daemon_version);

    auto dnserr = DNSServiceGetProperty(kDNSServiceProperty_DaemonVersion, &daemon_version, &sz);
    if (dnserr != kDNSServiceErr_NoError) {
        return "ERROR: mdns daemon unavailable";
    }

    return android::base::StringPrintf("mdns daemon version [%u]", daemon_version);
}

std::string mdns_list_discovered_services() {
    std::string result;
    auto cb = [&](const std::string& service_name, const std::string& reg_type,
                  const std::string& ip_addr, uint16_t port) {
        result += android::base::StringPrintf("%s\t%s\t%s:%u\n", service_name.c_str(),
                                              reg_type.c_str(), ip_addr.c_str(), port);
    };

    ResolvedService::ForEachService(*ResolvedService::sAdbTransportServices, "", cb);
    ResolvedService::ForEachService(*ResolvedService::sAdbSecureConnectServices, "", cb);
    ResolvedService::ForEachService(*ResolvedService::sAdbSecurePairingServices, "", cb);
    return result;
}

std::optional<MdnsInfo> mdns_get_connect_service_info(const std::string& name) {
    CHECK(!name.empty());

    // only adb server creates these registries
    if (!ResolvedService::sAdbTransportServices && !ResolvedService::sAdbSecureConnectServices) {
        return std::nullopt;
    }
    CHECK(ResolvedService::sAdbTransportServices);
    CHECK(ResolvedService::sAdbSecureConnectServices);

    auto mdns_instance = mdns::mdns_parse_instance_name(name);
    if (!mdns_instance.has_value()) {
        D("Failed to parse mDNS name [%s]", name.c_str());
        return std::nullopt;
    }

    std::optional<MdnsInfo> info;
    auto cb = [&](const std::string& service_name, const std::string& reg_type,
                  const std::string& ip_addr,
                  uint16_t port) { info.emplace(service_name, reg_type, ip_addr, port); };

    std::string reg_type;
    if (!mdns_instance->service_name.empty()) {
        reg_type = android::base::StringPrintf("%s.%s", mdns_instance->service_name.c_str(),
                                               mdns_instance->transport_type.c_str());
        auto index = adb_DNSServiceIndexByName(reg_type);
        if (!index) {
            return std::nullopt;
        }
        switch (*index) {
            case kADBTransportServiceRefIndex:
                ResolvedService::ForEachService(*ResolvedService::sAdbTransportServices,
                                                mdns_instance->instance_name, cb);
                break;
            case kADBSecureConnectServiceRefIndex:
                ResolvedService::ForEachService(*ResolvedService::sAdbSecureConnectServices,
                                                mdns_instance->instance_name, cb);
                break;
            default:
                D("Unknown reg_type [%s]", reg_type.c_str());
                return std::nullopt;
        }
        return info;
    }

    for (const auto& service :
         {ResolvedService::sAdbTransportServices, ResolvedService::sAdbSecureConnectServices}) {
        ResolvedService::ForEachService(*service, name, cb);
        if (info.has_value()) {
            return info;
        }
    }

    return std::nullopt;
}

std::optional<MdnsInfo> mdns_get_pairing_service_info(const std::string& name) {
    CHECK(!name.empty());

    auto mdns_instance = mdns::mdns_parse_instance_name(name);
    if (!mdns_instance.has_value()) {
        D("Failed to parse mDNS pairing name [%s]", name.c_str());
        return std::nullopt;
    }

    std::optional<MdnsInfo> info;
    auto cb = [&](const std::string& service_name, const std::string& reg_type,
                  const std::string& ip_addr,
                  uint16_t port) { info.emplace(service_name, reg_type, ip_addr, port); };

    // Verify it's a pairing service if user explicitly inputs it.
    if (!mdns_instance->service_name.empty()) {
        auto reg_type = android::base::StringPrintf("%s.%s", mdns_instance->service_name.c_str(),
                                                    mdns_instance->transport_type.c_str());
        auto index = adb_DNSServiceIndexByName(reg_type);
        if (!index) {
            return std::nullopt;
        }
        switch (*index) {
            case kADBSecurePairingServiceRefIndex:
                break;
            default:
                D("Not an adb pairing reg_type [%s]", reg_type.c_str());
                return std::nullopt;
        }
    }

    ResolvedService::ForEachService(*ResolvedService::sAdbSecurePairingServices, name, cb);
    return info;
}

void mdns_cleanup() {}

}  // namespace MdnsResponder
}  // namespace

AdbMdnsResponderFuncs StartMdnsResponderDiscovery() {
    ResolvedService::InitAdbServiceRegistries();
    std::thread(init_mdns_transport_discovery_thread).detach();
    AdbMdnsResponderFuncs f = {
            .mdns_check = MdnsResponder::mdns_check,
            .mdns_list_discovered_services = MdnsResponder::mdns_list_discovered_services,
            .mdns_get_connect_service_info = MdnsResponder::mdns_get_connect_service_info,
            .mdns_get_pairing_service_info = MdnsResponder::mdns_get_pairing_service_info,
            .mdns_cleanup = MdnsResponder::mdns_cleanup,
            .adb_secure_connect_by_service_name = MdnsResponder::adb_secure_connect_by_service_name,
    };
    return f;
}
