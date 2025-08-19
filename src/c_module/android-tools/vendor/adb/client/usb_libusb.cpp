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

#include "sysdeps.h"

#include "client/usb.h"

#include <stdint.h>
#include <stdlib.h>

#if defined(__linux__)
#include <sys/inotify.h>
#include <unistd.h>
#endif

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

#ifdef ANDROID_TOOLS_USE_BUNDLED_LIBUSB
#include <libusb/libusb.h>
#else
#include <libusb-1.0/libusb.h>
#endif

#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/stringprintf.h>
#include <android-base/strings.h>
#include <android-base/thread_annotations.h>

#include "adb.h"
#include "adb_utils.h"
#include "fdevent/fdevent.h"
#include "transfer_id.h"
#include "transport.h"

using namespace std::chrono_literals;

using android::base::ScopedLockAssertion;
using android::base::StringPrintf;

#define LOG_ERR(out, fmt, ...)                                               \
    do {                                                                     \
        std::string __err = android::base::StringPrintf(fmt, ##__VA_ARGS__); \
        LOG(ERROR) << __err;                                                 \
        *out = std::move(__err);                                             \
    } while (0)

// RAII wrappers for libusb.
struct ConfigDescriptorDeleter {
    void operator()(libusb_config_descriptor* desc) { libusb_free_config_descriptor(desc); }
};

using unique_config_descriptor = std::unique_ptr<libusb_config_descriptor, ConfigDescriptorDeleter>;

struct DeviceDeleter {
    void operator()(libusb_device* d) { libusb_unref_device(d); }
};

using unique_device = std::unique_ptr<libusb_device, DeviceDeleter>;

struct DeviceHandleDeleter {
    void operator()(libusb_device_handle* h) { libusb_close(h); }
};

using unique_device_handle = std::unique_ptr<libusb_device_handle, DeviceHandleDeleter>;

static void process_device(libusb_device* device_raw);

static std::string get_device_address(libusb_device* device) {
    uint8_t ports[7];
    int port_count = libusb_get_port_numbers(device, ports, 7);
    if (port_count < 0) return "";

    std::string address = StringPrintf("%d-%d", libusb_get_bus_number(device), ports[0]);
    for (int port = 1; port < port_count; ++port) {
        address += StringPrintf(".%d", ports[port]);
    }

    return address;
}

#if defined(__linux__)
static std::string get_device_serial_path(libusb_device* device) {
    std::string address = get_device_address(device);
    std::string path = StringPrintf("/sys/bus/usb/devices/%s/serial", address.c_str());
    return path;
}
#endif

static bool endpoint_is_output(uint8_t endpoint) {
    return (endpoint & LIBUSB_ENDPOINT_DIR_MASK) == LIBUSB_ENDPOINT_OUT;
}

static bool should_perform_zero_transfer(size_t write_length, uint16_t zero_mask) {
    return write_length != 0 && zero_mask != 0 && (write_length & zero_mask) == 0;
}

struct LibusbConnection : public Connection {
    struct ReadBlock {
        LibusbConnection* self = nullptr;
        libusb_transfer* transfer = nullptr;
        Block block;
        bool active = false;
    };

    struct WriteBlock {
        LibusbConnection* self;
        libusb_transfer* transfer;
        Block block;
        TransferId id;
    };

    explicit LibusbConnection(unique_device device)
        : device_(std::move(device)), device_address_(get_device_address(device_.get())) {}

    ~LibusbConnection() { Stop(); }

    void HandlePacket(amessage& msg, std::optional<Block> payload) {
        auto packet = std::make_unique<apacket>();
        packet->msg = msg;
        if (payload) {
            packet->payload = std::move(*payload);
        }
        transport_->HandleRead(std::move(packet));
    }

    void Cleanup(ReadBlock* read_block) REQUIRES(read_mutex_) {
        libusb_free_transfer(read_block->transfer);
        read_block->active = false;
        read_block->transfer = nullptr;
        if (terminated_) {
            destruction_cv_.notify_one();
        }
    }

    bool MaybeCleanup(ReadBlock* read_block) REQUIRES(read_mutex_) {
        CHECK(read_block);
        CHECK(read_block->transfer);

        if (terminated_) {
            Cleanup(read_block);
            return true;
        }

        return false;
    }

    static void LIBUSB_CALL header_read_cb(libusb_transfer* transfer) {
        auto read_block = static_cast<ReadBlock*>(transfer->user_data);
        auto self = read_block->self;

        std::lock_guard<std::mutex> lock(self->read_mutex_);
        CHECK_EQ(read_block, &self->header_read_);
        if (self->MaybeCleanup(read_block)) {
            return;
        }

        if (transfer->status != LIBUSB_TRANSFER_COMPLETED) {
            std::string msg = StringPrintf("usb read failed: status = %d", transfer->status);
            LOG(ERROR) << msg;
            if (!self->detached_) {
                self->OnError(msg);
            }
            self->Cleanup(read_block);
            return;
        }

        if (transfer->actual_length != sizeof(amessage)) {
            std::string msg = StringPrintf("usb read: invalid length for header: %d",
                                           transfer->actual_length);
            LOG(ERROR) << msg;
            self->OnError(msg);
            self->Cleanup(read_block);
            return;
        }

        CHECK(!self->incoming_header_);
        amessage& amsg = self->incoming_header_.emplace();
        memcpy(&amsg, transfer->buffer, sizeof(amsg));

        if (amsg.data_length > MAX_PAYLOAD) {
            std::string msg =
                    StringPrintf("usb read: payload length too long: %d", amsg.data_length);
            LOG(ERROR) << msg;
            self->OnError(msg);
            self->Cleanup(&self->header_read_);
            return;
        } else if (amsg.data_length == 0) {
            self->HandlePacket(amsg, std::nullopt);
            self->incoming_header_.reset();
            self->SubmitRead(read_block, sizeof(amessage));
        } else {
            read_block->active = false;
            self->SubmitRead(&self->payload_read_, amsg.data_length);
        }
    }

    static void LIBUSB_CALL payload_read_cb(libusb_transfer* transfer) {
        auto read_block = static_cast<ReadBlock*>(transfer->user_data);
        auto self = read_block->self;
        std::lock_guard<std::mutex> lock(self->read_mutex_);

        if (self->MaybeCleanup(&self->payload_read_)) {
            return;
        }

        if (transfer->status != LIBUSB_TRANSFER_COMPLETED) {
            std::string msg = StringPrintf("usb read failed: status = %d", transfer->status);
            LOG(ERROR) << msg;
            if (!self->detached_) {
                self->OnError(msg);
            }
            self->Cleanup(&self->payload_read_);
            return;
        }

        if (transfer->actual_length != transfer->length) {
            std::string msg =
                    StringPrintf("usb read: unexpected length for payload: wanted %d, got %d",
                                 transfer->length, transfer->actual_length);
            LOG(ERROR) << msg;
            self->OnError(msg);
            self->Cleanup(&self->payload_read_);
            return;
        }

        CHECK(self->incoming_header_.has_value());
        self->HandlePacket(*self->incoming_header_, std::move(read_block->block));
        self->incoming_header_.reset();

        read_block->active = false;
        self->SubmitRead(&self->header_read_, sizeof(amessage));
    }

    static void LIBUSB_CALL write_cb(libusb_transfer* transfer) {
        auto write_block = static_cast<WriteBlock*>(transfer->user_data);
        auto self = write_block->self;

        bool succeeded = transfer->status == LIBUSB_TRANSFER_COMPLETED;

        {
            std::lock_guard<std::mutex> lock(self->write_mutex_);
            libusb_free_transfer(transfer);
            self->writes_.erase(write_block->id);

            if (self->terminated_ && self->writes_.empty()) {
                self->destruction_cv_.notify_one();
            }
        }

        if (!succeeded && !self->detached_) {
            self->OnError("libusb write failed");
        }
    }

    bool DoTlsHandshake(RSA*, std::string*) final {
        LOG(FATAL) << "tls not supported";
        return false;
    }

    void CreateRead(ReadBlock* read, bool header) {
        read->self = this;
        read->transfer = libusb_alloc_transfer(0);
        if (!read->transfer) {
            LOG(FATAL) << "failed to allocate libusb_transfer for read";
        }
        libusb_fill_bulk_transfer(read->transfer, device_handle_.get(), read_endpoint_, nullptr, 0,
                                  header ? header_read_cb : payload_read_cb, read, 0);
    }

    void SubmitRead(ReadBlock* read, size_t length) {
        read->block.resize(length);
        read->transfer->buffer = reinterpret_cast<unsigned char*>(read->block.data());
        read->transfer->length = length;
        read->active = true;
        int rc = libusb_submit_transfer(read->transfer);
        if (rc != 0) {
            LOG(ERROR) << "libusb_submit_transfer failed: " << libusb_strerror(static_cast<libusb_error>(rc));
        }
    }

    void SubmitWrite(Block&& block) REQUIRES(write_mutex_) {
        // TODO: Reuse write blocks.
        auto write = std::make_unique<WriteBlock>();

        write->self = this;
        write->id = TransferId::write(next_write_id_++);
        write->block = std::move(block);
        write->transfer = libusb_alloc_transfer(0);
        if (!write->transfer) {
            LOG(FATAL) << "failed to allocate libusb_transfer for write";
        }

        libusb_fill_bulk_transfer(write->transfer, device_handle_.get(), write_endpoint_,
                                  reinterpret_cast<unsigned char*>(write->block.data()),
                                  write->block.size(), &write_cb, write.get(), 0);
        int rc = libusb_submit_transfer(write->transfer);
        if (rc == 0) {
            writes_[write->id] = std::move(write);
        } else {
            LOG(ERROR) << "libusb_submit_transfer failed: " << libusb_strerror(static_cast<libusb_error>(rc));
            libusb_free_transfer(write->transfer);
        }
    }

    bool Write(std::unique_ptr<apacket> packet) final {
        VLOG(USB) << "USB write: " << dump_header(&packet->msg);
        Block header;
        header.resize(sizeof(packet->msg));
        memcpy(header.data(), &packet->msg, sizeof(packet->msg));

        std::lock_guard<std::mutex> lock(write_mutex_);
        if (terminated_) {
            return false;
        }

        if (detached_) {
            return true;
        }

        SubmitWrite(std::move(header));
        if (!packet->payload.empty()) {
            size_t payload_length = packet->payload.size();
            SubmitWrite(std::move(packet->payload));

            // If the payload is a multiple of the endpoint packet size, we
            // need an explicit zero-sized transfer.
            if (should_perform_zero_transfer(payload_length, zero_mask_)) {
                VLOG(USB) << "submitting zero transfer for payload length " << payload_length;
                Block empty;
                SubmitWrite(std::move(empty));
            }
        }

        return true;
    }

    std::optional<libusb_device_descriptor> GetDeviceDescriptor() {
        libusb_device_descriptor device_desc;
        int rc = libusb_get_device_descriptor(device_.get(), &device_desc);
        if (rc != 0) {
            LOG(WARNING) << "failed to get device descriptor for device at " << device_address_
                         << ": " << libusb_error_name(rc);
            return {};
        }
        return device_desc;
    }

    bool FindInterface(libusb_device_descriptor* device_desc) {
        if (device_desc->bDeviceClass != LIBUSB_CLASS_PER_INTERFACE) {
            // Assume that all Android devices have the device class set to per interface.
            // TODO: Is this assumption valid?
            VLOG(USB) << "skipping device with incorrect class at " << device_address_;
            return false;
        }

        libusb_config_descriptor* config_raw;
        int rc = libusb_get_active_config_descriptor(device_.get(), &config_raw);
        if (rc != 0) {
            LOG(WARNING) << "failed to get active config descriptor for device at "
                         << device_address_ << ": " << libusb_error_name(rc);
            return false;
        }
        const unique_config_descriptor config(config_raw);

        // Use size_t for interface_num so <iostream>s don't mangle it.
        size_t interface_num;
        uint16_t zero_mask = 0;
        uint8_t bulk_in = 0, bulk_out = 0;
        size_t packet_size = 0;
        bool found_adb = false;

        for (interface_num = 0; interface_num < config->bNumInterfaces; ++interface_num) {
            const libusb_interface& interface = config->interface[interface_num];

            if (interface.num_altsetting == 0) {
                continue;
            }

            const libusb_interface_descriptor& interface_desc = interface.altsetting[0];
            if (!is_adb_interface(interface_desc.bInterfaceClass, interface_desc.bInterfaceSubClass,
                                  interface_desc.bInterfaceProtocol)) {
                VLOG(USB) << "skipping non-adb interface at " << device_address_ << " (interface "
                          << interface_num << ")";
                continue;
            }

            if (interface.num_altsetting != 1) {
                // Assume that interfaces with alternate settings aren't adb interfaces.
                // TODO: Is this assumption valid?
                LOG(WARNING) << "skipping interface with unexpected num_altsetting at "
                             << device_address_ << " (interface " << interface_num << ")";
                continue;
            }

            VLOG(USB) << "found potential adb interface at " << device_address_ << " (interface "
                      << interface_num << ")";

            bool found_in = false;
            bool found_out = false;
            for (size_t endpoint_num = 0; endpoint_num < interface_desc.bNumEndpoints;
                 ++endpoint_num) {
                const auto& endpoint_desc = interface_desc.endpoint[endpoint_num];
                const uint8_t endpoint_addr = endpoint_desc.bEndpointAddress;
                const uint8_t endpoint_attr = endpoint_desc.bmAttributes;

                const uint8_t transfer_type = endpoint_attr & LIBUSB_TRANSFER_TYPE_MASK;

                if (transfer_type != LIBUSB_TRANSFER_TYPE_BULK) {
                    continue;
                }

                if (endpoint_is_output(endpoint_addr) && !found_out) {
                    found_out = true;
                    bulk_out = endpoint_addr;
                    zero_mask = endpoint_desc.wMaxPacketSize - 1;
                } else if (!endpoint_is_output(endpoint_addr) && !found_in) {
                    found_in = true;
                    bulk_in = endpoint_addr;
                }

                size_t endpoint_packet_size = endpoint_desc.wMaxPacketSize;
                CHECK(endpoint_packet_size != 0);
                if (packet_size == 0) {
                    packet_size = endpoint_packet_size;
                } else {
                    CHECK(packet_size == endpoint_packet_size);
                }
            }

            if (found_in && found_out) {
                found_adb = true;
                break;
            } else {
                VLOG(USB) << "rejecting potential adb interface at " << device_address_
                          << "(interface " << interface_num << "): missing bulk endpoints "
                          << "(found_in = " << found_in << ", found_out = " << found_out << ")";
            }
        }

        if (!found_adb) {
            return false;
        }

        interface_num_ = interface_num;
        write_endpoint_ = bulk_out;
        read_endpoint_ = bulk_in;
        zero_mask_ = zero_mask;
        return true;
    }

    std::string GetUsbDeviceAddress() const { return std::string("usb:") + device_address_; }

    std::string GetSerial() {
        std::string serial;

        auto device_desc = GetDeviceDescriptor();

        serial.resize(255);
        int rc = libusb_get_string_descriptor_ascii(
                device_handle_.get(), device_desc->iSerialNumber,
                reinterpret_cast<unsigned char*>(&serial[0]), serial.length());
        if (rc == 0) {
            LOG(WARNING) << "received empty serial from device at " << device_address_;
            return {};
        } else if (rc < 0) {
            LOG(WARNING) << "failed to get serial from device at " << device_address_
                         << libusb_error_name(rc);
            return {};
        }
        serial.resize(rc);

        return serial;
    }

    // libusb gives us an int which is a value from 'enum libusb_speed'
    static uint64_t ToConnectionSpeed(int speed) {
        switch (speed) {
            case LIBUSB_SPEED_LOW:
                return 1;
            case LIBUSB_SPEED_FULL:
                return 12;
            case LIBUSB_SPEED_HIGH:
                return 480;
            case LIBUSB_SPEED_SUPER:
                return 5000;
            case LIBUSB_SPEED_SUPER_PLUS:
                return 10000;
            case LIBUSB_SPEED_SUPER_PLUS_X2:
                return 20000;
            case LIBUSB_SPEED_UNKNOWN:
            default:
                return 0;
        }
    }

    // libusb gives us a bitfield made of 'enum libusb_supported_speed' values
    static uint64_t ExtractMaxSuperSpeed(uint16_t wSpeedSupported) {
        if (wSpeedSupported == 0) {
            return 0;
        }

        int msb = 0;
        while (wSpeedSupported >>= 1) {
            msb++;
        }

        switch (1 << msb) {
            case LIBUSB_LOW_SPEED_OPERATION:
                return 1;
            case LIBUSB_FULL_SPEED_OPERATION:
                return 12;
            case LIBUSB_HIGH_SPEED_OPERATION:
                return 480;
            case LIBUSB_SUPER_SPEED_OPERATION:
                return 5000;
            default:
                return 0;
        }
    }

    static uint64_t ExtractMaxSuperSpeedPlus(libusb_ssplus_usb_device_capability_descriptor* cap) {
        // The exponents is one of {bytes, kB, MB, or GB}. We express speed in MB so we use a 0
        // multiplier for value which would result in 0MB anyway.
        static uint64_t exponent[] = {0, 0, 1, 1000};
        uint64_t max_speed = 0;
        for (uint8_t i = 0; i < cap->numSublinkSpeedAttributes; i++) {
            libusb_ssplus_sublink_attribute* attr = &cap->sublinkSpeedAttributes[i];
            uint64_t speed = attr->mantissa * exponent[attr->exponent];
            max_speed = std::max(max_speed, speed);
        }
        return max_speed;
    }

    void RetrieveSpeeds() {
        negotiated_speed_ = ToConnectionSpeed(libusb_get_device_speed(device_.get()));

        // To discover the maximum speed supported by an USB device, we walk its capability
        // descriptors.
        struct libusb_bos_descriptor* bos = nullptr;
        if (libusb_get_bos_descriptor(device_handle_.get(), &bos)) {
            return;
        }

        for (int i = 0; i < bos->bNumDeviceCaps; i++) {
            switch (bos->dev_capability[i]->bDevCapabilityType) {
                case LIBUSB_BT_SS_USB_DEVICE_CAPABILITY: {
                    libusb_ss_usb_device_capability_descriptor* cap = nullptr;
                    if (!libusb_get_ss_usb_device_capability_descriptor(
                                nullptr, bos->dev_capability[i], &cap)) {
                        max_speed_ =
                                std::max(max_speed_, ExtractMaxSuperSpeed(cap->wSpeedSupported));
                        libusb_free_ss_usb_device_capability_descriptor(cap);
                    }
                } break;
                case LIBUSB_BT_SUPERSPEED_PLUS_CAPABILITY: {
                    libusb_ssplus_usb_device_capability_descriptor* cap = nullptr;
                    if (!libusb_get_ssplus_usb_device_capability_descriptor(
                                nullptr, bos->dev_capability[i], &cap)) {
                        max_speed_ = std::max(max_speed_, ExtractMaxSuperSpeedPlus(cap));
                        libusb_free_ssplus_usb_device_capability_descriptor(cap);
                    }
                } break;
                default:
                    break;
            }
        }
        libusb_free_bos_descriptor(bos);
    }

    bool OpenDevice(std::string* error) {
        if (device_handle_) {
            LOG_ERR(error, "device already open");
            return false;
        }

        libusb_device_handle* handle_raw;
        int rc = libusb_open(device_.get(), &handle_raw);
        if (rc != 0) {
            // TODO: Handle no permissions.
            LOG_ERR(error, "failed to open device: %s", libusb_strerror(static_cast<libusb_error>(rc)));
            return false;
        }

        unique_device_handle handle(handle_raw);
        device_handle_ = std::move(handle);

        auto device_desc = GetDeviceDescriptor();
        if (!device_desc) {
            LOG_ERR(error, "failed to get device descriptor");
            device_handle_.reset();
            return false;
        }

        if (!FindInterface(&device_desc.value())) {
            LOG_ERR(error, "failed to find adb interface");
            device_handle_.reset();
            return false;
        }

        serial_ = GetSerial();

        VLOG(USB) << "successfully opened adb device at " << device_address_ << ", "
                  << StringPrintf("bulk_in = %#x, bulk_out = %#x", read_endpoint_, write_endpoint_);

        // WARNING: this isn't released via RAII.
        rc = libusb_claim_interface(device_handle_.get(), interface_num_);
        if (rc != 0) {
            LOG_ERR(error, "failed to claim adb interface for device '%s': %s", serial_.c_str(),
                    libusb_error_name(rc));
            device_handle_.reset();
            return false;
        }

        for (uint8_t endpoint : {read_endpoint_, write_endpoint_}) {
            rc = libusb_clear_halt(device_handle_.get(), endpoint);
            if (rc != 0) {
                LOG_ERR(error, "failed to clear halt on device '%s' endpoint %#02x: %s",
                        serial_.c_str(), endpoint, libusb_error_name(rc));
                libusb_release_interface(device_handle_.get(), interface_num_);
                device_handle_.reset();
                return false;
            }
        }

        RetrieveSpeeds();
        return true;
    }

    void CancelReadTransfer(ReadBlock* read_block) REQUIRES(read_mutex_) {
        if (!read_block->transfer) {
            return;
        }

        if (!read_block->active) {
            // There is no read_cb pending. Clean it up right now.
            Cleanup(read_block);
            return;
        }

        int rc = libusb_cancel_transfer(read_block->transfer);
        if (rc != 0) {
            LOG(WARNING) << "libusb_cancel_transfer failed: " << libusb_error_name(rc);
            // There is no read_cb pending. Clean it up right now.
            Cleanup(read_block);
            return;
        }
    }

    void CloseDevice() {
        // This is rather messy, because of the lifecyle of libusb_transfers.
        //
        // We can't call libusb_free_transfer for a submitted transfer, we have to cancel it
        // and free it in the callback. Complicating things more, it's possible for us to be in
        // the callback for a transfer as the destructor is being called, at which point cancelling
        // the transfer won't do anything (and it's possible that we'll submit the transfer again
        // in the callback).
        //
        // Resolve this by setting an atomic flag before we lock to cancel transfers, and take the
        // lock in the callbacks before checking the flag.

        if (terminated_) {
            return;
        }

        terminated_ = true;

        {
            std::unique_lock<std::mutex> lock(write_mutex_);
            ScopedLockAssertion assumed_locked(write_mutex_);

            std::erase_if(writes_, [](const auto& write_item) {
                auto const& [id, write_block] = write_item;
                int rc = libusb_cancel_transfer(write_block->transfer);
                if (rc != 0) {
                    // libusb_cancel_transfer failed for some reason. We will
                    // never get a callback for this transfer. So we need to
                    // remove it from the list or we will hang below.
                    LOG(INFO) << "libusb_cancel_transfer failed: " << libusb_error_name(rc);
                    libusb_free_transfer(write_block->transfer);
                    return true;
                }
                // Wait for the write_cb to fire before removing.
                return false;
            });

            // Wait here until the write callbacks have all fired and removed
            // the remaining writes_.
            destruction_cv_.wait(lock, [this]() {
                ScopedLockAssertion assumed_locked(write_mutex_);
                return writes_.empty();
            });
        }

        {
            std::unique_lock<std::mutex> lock(read_mutex_);
            ScopedLockAssertion assumed_locked(read_mutex_);

            CancelReadTransfer(&header_read_);
            CancelReadTransfer(&payload_read_);

            destruction_cv_.wait(lock, [this]() {
                ScopedLockAssertion assumed_locked(read_mutex_);
                return !header_read_.active && !payload_read_.active;
            });

            incoming_header_.reset();
            incoming_payload_.clear();
        }

        if (device_handle_) {
            int rc = libusb_release_interface(device_handle_.get(), interface_num_);
            if (rc != 0) {
                LOG(WARNING) << "libusb_release_interface failed: " << libusb_error_name(rc);
            }
            device_handle_.reset();
        }
    }

    bool StartImpl(std::string* error) {
        if (!device_handle_) {
            *error = "device not opened";
            return false;
        }

        VLOG(USB) << "registered new usb device '" << serial_ << "'";
        std::lock_guard lock(read_mutex_);
        CreateRead(&header_read_, true);
        CreateRead(&payload_read_, false);
        SubmitRead(&header_read_, sizeof(amessage));

        return true;
    }

    void OnError(const std::string& error) {
        std::call_once(error_flag_, [this, &error]() {
            if (transport_) {
                transport_->HandleError(error);
            }
        });
    }

    virtual bool Attach(std::string* error) override final {
        terminated_ = false;
        detached_ = false;

        if (!OpenDevice(error)) {
            return false;
        }

        if (!StartImpl(error)) {
            CloseDevice();
            return false;
        }

        return true;
    }

    virtual bool Detach(std::string* error) override final {
        detached_ = true;
        CloseDevice();
        return true;
    }

    virtual void Reset() override final {
        VLOG(USB) << "resetting " << transport_->serial_name();
        int rc = libusb_reset_device(device_handle_.get());
        if (rc == 0) {
            libusb_device* device = libusb_ref_device(device_.get());

            Stop();

            fdevent_run_on_looper([device]() {
                process_device(device);
                libusb_unref_device(device);
            });
        } else {
            LOG(ERROR) << "libusb_reset_device failed: " << libusb_error_name(rc);
        }
    }

    virtual void Start() override final {
        std::string error;
        if (!Attach(&error)) {
            OnError(error);
        }
    }

    virtual void Stop() override final {
        CloseDevice();
        OnError("requested stop");
    }

    static std::optional<std::shared_ptr<LibusbConnection>> Create(unique_device device) {
        auto connection = std::make_unique<LibusbConnection>(std::move(device));
        if (!connection) {
            LOG(FATAL) << "failed to construct LibusbConnection";
        }

        auto device_desc = connection->GetDeviceDescriptor();
        if (!device_desc) {
            VLOG(USB) << "ignoring device " << connection->GetUsbDeviceAddress()
                      << ": not an adb interface. (GetDeviceDescriptor)";
            return {};
        }

        if (!connection->FindInterface(&device_desc.value())) {
            VLOG(USB) << "ignoring device " << connection->GetUsbDeviceAddress()
                      << ": not an adb interface. (FindInterface)";
            return {};
        }

#if defined(__linux__)
        std::string device_serial;
        if (android::base::ReadFileToString(get_device_serial_path(connection->device_.get()),
                                            &device_serial)) {
            connection->serial_ = android::base::Trim(device_serial);
        } else {
            // We don't actually want to treat an unknown serial as an error because
            // devices aren't able to communicate a serial number in early bringup.
            // http://b/20883914
            connection->serial_ = "<unknown>";
        }
#else
        // We need to open the device to get its serial on Windows and OS X.
        std::string error;
        if (!connection->OpenDevice(&error)) {
            VLOG(USB) << "ignoring device " << connection->GetUsbDeviceAddress()
                      << ": not an adb interface. (OpenDevice)";
            return {};
        }
        connection->serial_ = connection->GetSerial();
        connection->CloseDevice();
#endif
        if (!transport_server_owns_device(connection->GetUsbDeviceAddress(), connection->serial_)) {
            VLOG(USB) << "ignoring device " << connection->GetUsbDeviceAddress() << " serial "
                      << connection->serial_ << ": this server owns '" << transport_get_one_device()
                      << "'";
            return {};
        }

        return connection;
    }

    virtual uint64_t MaxSpeedMbps() override final { return max_speed_; }

    virtual uint64_t NegotiatedSpeedMbps() override final { return negotiated_speed_; }

    unique_device device_;
    unique_device_handle device_handle_;
    std::string device_address_;
    std::string serial_ = "<unknown>";

    uint32_t interface_num_;
    uint8_t write_endpoint_;
    uint8_t read_endpoint_;

    std::mutex read_mutex_;
    ReadBlock header_read_ GUARDED_BY(read_mutex_);
    ReadBlock payload_read_ GUARDED_BY(read_mutex_);
    std::optional<amessage> incoming_header_ GUARDED_BY(read_mutex_);
    IOVector incoming_payload_ GUARDED_BY(read_mutex_);

    std::mutex write_mutex_;
    std::unordered_map<TransferId, std::unique_ptr<WriteBlock>> writes_ GUARDED_BY(write_mutex_);
    std::atomic<size_t> next_write_id_ = 0;

    std::once_flag error_flag_;
    std::atomic<bool> terminated_ = false;
    std::atomic<bool> detached_ = false;
    std::condition_variable destruction_cv_;

    size_t zero_mask_ = 0;

    uint64_t negotiated_speed_ = 0;
    uint64_t max_speed_ = 0;
};

static std::mutex usb_handles_mutex [[clang::no_destroy]];
static std::unordered_map<libusb_device*, std::weak_ptr<LibusbConnection>> usb_handles
        [[clang::no_destroy]] GUARDED_BY(usb_handles_mutex);
static std::atomic<int> connecting_devices(0);

static void process_device(libusb_device* device_raw) {
    std::string device_address = "usb:" + get_device_address(device_raw);
    VLOG(USB) << "device connected: " << device_address;

    unique_device device(libusb_ref_device(device_raw));
    auto connection_opt = LibusbConnection::Create(std::move(device));
    if (!connection_opt) {
        return;
    }

    auto connection = *connection_opt;

    {
        std::lock_guard<std::mutex> lock(usb_handles_mutex);
        usb_handles.emplace(libusb_ref_device(device_raw), connection);
    }

    VLOG(USB) << "constructed LibusbConnection for device " << connection->serial_ << " ("
              << device_address << ")";

    register_usb_transport(connection, connection->serial_.c_str(), device_address.c_str(), true);
}

static void device_connected(libusb_device* device) {
#if defined(__linux__)
    // Android's host linux libusb uses netlink instead of udev for device hotplug notification,
    // which means we can get hotplug notifications before udev has updated ownership/perms on the
    // device. Since we're not going to be able to link against the system's libudev any time soon,
    // poll for accessibility changes with inotify until a timeout expires.
    libusb_ref_device(device);
    auto thread = std::thread([device]() {
        std::string bus_path = StringPrintf("/dev/bus/usb/%03d/", libusb_get_bus_number(device));
        std::string device_path =
                StringPrintf("%s/%03d", bus_path.c_str(), libusb_get_device_address(device));
        auto deadline = std::chrono::steady_clock::now() + 1s;
        unique_fd infd(inotify_init1(IN_CLOEXEC | IN_NONBLOCK));
        if (infd == -1) {
            PLOG(FATAL) << "failed to create inotify fd";
        }

        // Register the watch first, and then check for accessibility, to avoid a race.
        // We can't watch the device file itself, as that requires us to be able to access it.
        if (inotify_add_watch(infd.get(), bus_path.c_str(), IN_ATTRIB) == -1) {
            PLOG(ERROR) << "failed to register inotify watch on '" << bus_path
                        << "', falling back to sleep";
            std::this_thread::sleep_for(std::chrono::seconds(1));
        } else {
            adb_pollfd pfd = {.fd = infd.get(), .events = POLLIN, .revents = 0};

            while (access(device_path.c_str(), R_OK | W_OK) == -1) {
                auto timeout = deadline - std::chrono::steady_clock::now();
                if (timeout < 0s) {
                    break;
                }

                uint64_t ms = timeout / 1ms;
                int rc = adb_poll(&pfd, 1, ms);
                if (rc == -1) {
                    if (errno == EINTR) {
                        continue;
                    } else {
                        LOG(WARNING) << "timeout expired while waiting for device accessibility";
                        break;
                    }
                }

                union {
                    struct inotify_event ev;
                    char bytes[sizeof(struct inotify_event) + NAME_MAX + 1];
                } buf;

                rc = adb_read(infd.get(), &buf, sizeof(buf));
                if (rc == -1) {
                    break;
                }

                // We don't actually care about the data: we might get spurious events for
                // other devices on the bus, but we'll double check in the loop condition.
                continue;
            }
        }

        process_device(device);
        if (--connecting_devices == 0) {
            adb_notify_device_scan_complete();
        }
        libusb_unref_device(device);
    });
    thread.detach();
#else
    process_device(device);
#endif
}

static void device_disconnected(libusb_device* device) {
    usb_handles_mutex.lock();
    auto it = usb_handles.find(device);
    if (it != usb_handles.end()) {
        // We need to ensure that we don't destroy the LibusbConnection on this thread,
        // as we're in a context with internal libusb mutexes held.
        libusb_device* device = it->first;
        std::weak_ptr<LibusbConnection> connection_weak = it->second;
        usb_handles.erase(it);
        fdevent_run_on_looper([connection_weak]() {
            auto connection = connection_weak.lock();
            if (connection) {
                connection->Stop();
                VLOG(USB) << "libusb_hotplug: device disconnected: " << connection->serial_;
            } else {
                VLOG(USB) << "libusb_hotplug: device disconnected: (destroyed)";
            }
        });
        libusb_unref_device(device);
    }
    usb_handles_mutex.unlock();
}

static auto& hotplug_queue = *new BlockingQueue<std::pair<libusb_hotplug_event, libusb_device*>>();
static void hotplug_thread() {
    VLOG(USB) << "libusb hotplug thread started";
    adb_thread_setname("libusb hotplug");
    while (true) {
        hotplug_queue.PopAll([](std::pair<libusb_hotplug_event, libusb_device*> pair) {
            libusb_hotplug_event event = pair.first;
            libusb_device* device = pair.second;
            if (event == LIBUSB_HOTPLUG_EVENT_DEVICE_ARRIVED) {
                VLOG(USB) << "libusb hotplug: device arrived";
                device_connected(device);
            } else if (event == LIBUSB_HOTPLUG_EVENT_DEVICE_LEFT) {
                VLOG(USB) << "libusb hotplug: device left";
                device_disconnected(device);
            } else {
                LOG(WARNING) << "unknown libusb hotplug event: " << event;
            }
        });
    }
}

static LIBUSB_CALL int hotplug_callback(libusb_context*, libusb_device* device,
                                        libusb_hotplug_event event, void*) {
    // We're called with the libusb lock taken. Call these on a separate thread outside of this
    // function so that the usb_handle mutex is always taken before the libusb mutex.
    static std::once_flag once;
    std::call_once(once, []() { std::thread(hotplug_thread).detach(); });

    if (event == LIBUSB_HOTPLUG_EVENT_DEVICE_ARRIVED) {
        ++connecting_devices;
    }
    hotplug_queue.Push({event, device});
    return 0;
}

namespace libusb {

void usb_init() {
    VLOG(USB) << "initializing libusb...";
    int rc = libusb_init(nullptr);
    if (rc != 0) {
        LOG(WARNING) << "failed to initialize libusb: " << libusb_error_name(rc);
        return;
    }

    // Register the hotplug callback.
    rc = libusb_hotplug_register_callback(
            nullptr,
            static_cast<libusb_hotplug_event>(LIBUSB_HOTPLUG_EVENT_DEVICE_ARRIVED |
                                              LIBUSB_HOTPLUG_EVENT_DEVICE_LEFT),
            LIBUSB_HOTPLUG_ENUMERATE, LIBUSB_HOTPLUG_MATCH_ANY, LIBUSB_HOTPLUG_MATCH_ANY,
            LIBUSB_CLASS_PER_INTERFACE, hotplug_callback, nullptr, nullptr);

    if (rc != LIBUSB_SUCCESS) {
        LOG(FATAL) << "failed to register libusb hotplug callback";
    }

    // Spawn a thread for libusb_handle_events.
    std::thread([]() {
        adb_thread_setname("libusb");
        while (true) {
            libusb_handle_events(nullptr);
        }
    }).detach();
}

}  // namespace libusb
