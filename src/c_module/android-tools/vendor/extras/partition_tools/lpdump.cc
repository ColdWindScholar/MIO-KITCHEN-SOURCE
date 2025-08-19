/*
 * Copyright (C) 2018 The Android Open Source Project
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

#include <getopt.h>
#include <inttypes.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/types.h>
#include <sysexits.h>
#include <unistd.h>

#include <algorithm>
#include <iostream>
#include <optional>
#include <regex>
#include <string>
#include <vector>

#include <android-base/parseint.h>
#include <android-base/properties.h>
#include <android-base/strings.h>
#ifdef __ANDROID__
#include <cutils/android_get_control_file.h>
#include <fs_mgr.h>
#endif
#include <jsonpb/jsonpb.h>
#include <liblp/builder.h>
#include <liblp/liblp.h>

#include "dynamic_partitions_device_info.pb.h"
using namespace android;
using namespace android::fs_mgr;

static int usage(int /* argc */, char* argv[], std::ostream& cerr) {
    cerr << argv[0]
         << " - command-line tool for dumping Android Logical Partition images.\n"
            "\n"
            "Usage:\n"
            "  "
         << argv[0]
         << " [-s <SLOT#>|--slot=<SLOT#>] [-j|--json] [FILE|DEVICE]\n"
            "\n"
            "Options:\n"
            "  -s, --slot=N     Slot number or suffix.\n"
            "  -j, --json       Print in JSON format.\n"
            "  -d, --dump-metadata-size\n"
            "                   Print the space reserved for metadata to stdout\n"
            "                   in bytes.\n"
            "  -a, --all        Dump all slots (not available in JSON mode).\n";
    return EX_USAGE;
}

static std::string BuildFlagString(const std::vector<std::string>& strings) {
    return strings.empty() ? "none" : android::base::Join(strings, ",");
}

static std::string BuildHeaderFlagString(uint32_t flags) {
    std::vector<std::string> strings;

    if (flags & LP_HEADER_FLAG_VIRTUAL_AB_DEVICE) {
        strings.emplace_back("virtual_ab_device");
        flags &= ~LP_HEADER_FLAG_VIRTUAL_AB_DEVICE;
    }

    for (uint32_t i = 0; i < sizeof(flags) * 8; i++) {
        if (!(flags & (1U << i))) {
            continue;
        }
        strings.emplace_back("unknown_flag_bit_" + std::to_string(i));
    }
    return BuildFlagString(strings);
}

static std::string BuildAttributeString(uint32_t attrs) {
    std::vector<std::string> strings;
    if (attrs & LP_PARTITION_ATTR_READONLY) strings.emplace_back("readonly");
    if (attrs & LP_PARTITION_ATTR_SLOT_SUFFIXED) strings.emplace_back("slot-suffixed");
    if (attrs & LP_PARTITION_ATTR_UPDATED) strings.emplace_back("updated");
    if (attrs & LP_PARTITION_ATTR_DISABLED) strings.emplace_back("disabled");
    return BuildFlagString(strings);
}

static std::string BuildGroupFlagString(uint32_t flags) {
    std::vector<std::string> strings;
    if (flags & LP_GROUP_SLOT_SUFFIXED) strings.emplace_back("slot-suffixed");
    return BuildFlagString(strings);
}

static std::string BuildBlockDeviceFlagString(uint32_t flags) {
    std::vector<std::string> strings;
    if (flags & LP_BLOCK_DEVICE_SLOT_SUFFIXED) strings.emplace_back("slot-suffixed");
    return BuildFlagString(strings);
}

// Reimplementation of fs_mgr_get_slot_suffix() without reading
// kernel commandline.
static std::string GetSlotSuffix() {
    return base::GetProperty("ro.boot.slot_suffix", "");
}

// Reimplementation of fs_mgr_get_super_partition_name() without reading
// kernel commandline. Always return the super partition at current slot.
static std::string GetSuperPartitionName(const std::optional<uint32_t>& slot = {}) {
    std::string super_partition = base::GetProperty("ro.boot.super_partition", "");
    if (super_partition.empty()) {
        return LP_METADATA_DEFAULT_PARTITION_NAME;
    }
    if (slot.has_value()) {
        return super_partition + SlotSuffixForSlotNumber(slot.value());
    }
    return super_partition + GetSlotSuffix();
}

static std::string RemoveSuffix(const std::string& s, const std::string& suffix) {
    if (base::EndsWith(s, suffix)) {
        return s.substr(0, s.length() - suffix.length());
    }
    return s;
}

// Merge proto with information from metadata.
static bool MergeMetadata(const LpMetadata* metadata,
                          DynamicPartitionsDeviceInfoProto* proto) {
    if (!metadata) return false;
    auto builder = MetadataBuilder::New(*metadata);
    if (!builder) return false;

    std::string slot_suffix = GetSlotSuffix();

    for (const auto& group_name : builder->ListGroups()) {
        auto group = builder->FindGroup(group_name);
        if (!group) continue;
        if (!base::EndsWith(group_name, slot_suffix)) continue;
        auto group_proto = proto->add_groups();
        group_proto->set_name(RemoveSuffix(group_name, slot_suffix));
        group_proto->set_maximum_size(group->maximum_size());

        for (auto partition : builder->ListPartitionsInGroup(group_name)) {
            auto partition_name = partition->name();
            if (!base::EndsWith(partition_name, slot_suffix)) continue;
            auto partition_proto = proto->add_partitions();
            partition_proto->set_name(RemoveSuffix(partition_name, slot_suffix));
            partition_proto->set_group_name(RemoveSuffix(group_name, slot_suffix));
            partition_proto->set_size(partition->size());
            partition_proto->set_is_dynamic(true);
        }
    }

    for (const auto& block_device : metadata->block_devices) {
        std::string name = GetBlockDevicePartitionName(block_device);
        BlockDeviceInfo info;
        if (!builder->GetBlockDeviceInfo(name, &info)) {
            continue;
        }
        auto block_device_proto = proto->add_block_devices();
        block_device_proto->set_name(RemoveSuffix(name, slot_suffix));
        block_device_proto->set_size(info.size);
        block_device_proto->set_block_size(info.logical_block_size);
        block_device_proto->set_alignment(info.alignment);
        block_device_proto->set_alignment_offset(info.alignment_offset);
    }

    auto super_device_proto = proto->mutable_super_device();
    super_device_proto->set_name(GetSuperPartitionName());
    super_device_proto->set_used_size(builder->UsedSpace());
    super_device_proto->set_total_size(GetTotalSuperPartitionSize(*metadata));

    return true;
}

#ifdef __ANDROID__
static DynamicPartitionsDeviceInfoProto::Partition* FindPartition(
        DynamicPartitionsDeviceInfoProto* proto, const std::string& partition) {
    for (DynamicPartitionsDeviceInfoProto::Partition& p : *proto->mutable_partitions()) {
        if (p.name() == partition) {
            return &p;
        }
    }
    return nullptr;
}

static std::optional<std::string> GetReadonlyPartitionName(const android::fs_mgr::FstabEntry& entry) {
    // Only report readonly partitions.
    if ((entry.flags & MS_RDONLY) == 0) return std::nullopt;
    std::regex regex("/([a-zA-Z_]*)$");
    std::smatch match;
    if (!std::regex_match(entry.mount_point, match, regex)) return std::nullopt;
    // On system-as-root devices, fstab lists / for system partition.
    std::string partition = match[1];
    return partition.empty() ? "system" : partition;
}

static bool MergeFsUsage(DynamicPartitionsDeviceInfoProto* proto,
                         std::ostream& cerr) {
    using namespace std::string_literals;
    Fstab fstab;
    if (!ReadDefaultFstab(&fstab)) {
        cerr << "Cannot read fstab\n";
        return false;
    }

    for (const auto& entry : fstab) {
        auto partition = GetReadonlyPartitionName(entry);
        if (!partition) {
            continue;
        }

        // system is mounted to "/";
        const char* mount_point = (entry.mount_point == "/system")
            ? "/" : entry.mount_point.c_str();

        struct statvfs vst;
        if (statvfs(mount_point, &vst) == -1) {
            continue;
        }

        auto partition_proto = FindPartition(proto, *partition);
        if (partition_proto == nullptr) {
            partition_proto = proto->add_partitions();
            partition_proto->set_name(*partition);
            partition_proto->set_is_dynamic(false);
        }
        partition_proto->set_fs_size((uint64_t)vst.f_blocks * vst.f_frsize);

        if (!entry.fs_type.empty()) {
            partition_proto->set_fs_type(entry.fs_type);
        } else {
            partition_proto->set_fs_type("UNKNOWN");
        }

        if (vst.f_bavail <= vst.f_blocks) {
            partition_proto->set_fs_used((uint64_t)(vst.f_blocks - vst.f_bavail) * vst.f_frsize);
        }
    }
    return true;
}
#endif

// Print output in JSON format.
// If successful, this function must write a valid JSON string to "cout" and return 0.
static int PrintJson(const LpMetadata* metadata, std::ostream& cout,
                     std::ostream& cerr) {
    DynamicPartitionsDeviceInfoProto proto;

    if (base::GetBoolProperty("ro.boot.dynamic_partitions", false)) {
        proto.set_enabled(true);
    }

    if (base::GetBoolProperty("ro.boot.dynamic_partitions_retrofit", false)) {
        proto.set_retrofit(true);
    }

    if (!MergeMetadata(metadata, &proto)) {
        cerr << "Warning: Failed to read metadata.\n";
    }
#ifdef __ANDROID__
    if (!MergeFsUsage(&proto, cerr)) {
        cerr << "Warning: Failed to read filesystem size and usage.\n";
    }
#endif

    auto error_or_json = jsonpb::MessageToJsonString(proto);
    if (!error_or_json.ok()) {
        cerr << error_or_json.error() << "\n";
        return EX_SOFTWARE;
    }
    cout << *error_or_json;
    return EX_OK;
}

static int DumpMetadataSize(const LpMetadata& metadata, std::ostream& cout) {
    auto super_device = GetMetadataSuperBlockDevice(metadata);
    uint64_t metadata_size = super_device->first_logical_sector * LP_SECTOR_SIZE;
    cout << metadata_size << std::endl;
    return EX_OK;
}

class FileOrBlockDeviceOpener final : public PartitionOpener {
public:
    android::base::unique_fd Open(const std::string& path, int flags) const override {
        // Try a local file first.
        android::base::unique_fd fd;

#ifdef __ANDROID__
        fd.reset(android_get_control_file(path.c_str()));
        if (fd >= 0) return fd;
#endif
        fd.reset(open(path.c_str(), flags));
        if (fd >= 0) return fd;

        return PartitionOpener::Open(path, flags);
    }
};

std::optional<std::tuple<std::string, uint64_t>>
ParseLinearExtentData(const LpMetadata& pt, const LpMetadataExtent& extent) {
    if (extent.target_type != LP_TARGET_TYPE_LINEAR) {
        return std::nullopt;
    }
    const auto& block_device = pt.block_devices[extent.target_source];
    std::string device_name = GetBlockDevicePartitionName(block_device);
    return std::make_tuple(std::move(device_name), extent.target_data);
}

static void PrintMetadata(const LpMetadata& pt, std::ostream& cout) {
    cout << "Metadata version: " << pt.header.major_version << "." << pt.header.minor_version
         << "\n";
    cout << "Metadata size: " << (pt.header.header_size + pt.header.tables_size) << " bytes\n";
    cout << "Metadata max size: " << pt.geometry.metadata_max_size << " bytes\n";
    cout << "Metadata slot count: " << pt.geometry.metadata_slot_count << "\n";
    cout << "Header flags: " << BuildHeaderFlagString(pt.header.flags) << "\n";
    cout << "Partition table:\n";
    cout << "------------------------\n";

    std::vector<std::tuple<std::string, const LpMetadataExtent*>> extents;

    for (const auto& partition : pt.partitions) {
        std::string name = GetPartitionName(partition);
        std::string group_name = GetPartitionGroupName(pt.groups[partition.group_index]);
        cout << "  Name: " << name << "\n";
        cout << "  Group: " << group_name << "\n";
        cout << "  Attributes: " << BuildAttributeString(partition.attributes) << "\n";
        cout << "  Extents:\n";
        uint64_t first_sector = 0;
        for (size_t i = 0; i < partition.num_extents; i++) {
            const LpMetadataExtent& extent = pt.extents[partition.first_extent_index + i];
            cout << "    " << first_sector << " .. " << (first_sector + extent.num_sectors - 1)
                 << " ";
            first_sector += extent.num_sectors;
            if (extent.target_type == LP_TARGET_TYPE_LINEAR) {
                const auto& block_device = pt.block_devices[extent.target_source];
                std::string device_name = GetBlockDevicePartitionName(block_device);
                cout << "linear " << device_name.c_str() << " " << extent.target_data;
            } else if (extent.target_type == LP_TARGET_TYPE_ZERO) {
                cout << "zero";
            }
            extents.push_back(std::make_tuple(name, &extent));
            cout << "\n";
        }
        cout << "------------------------\n";
    }

    std::sort(extents.begin(), extents.end(), [&](const auto& x, const auto& y) {
        auto x_data = ParseLinearExtentData(pt, *std::get<1>(x));
        auto y_data = ParseLinearExtentData(pt, *std::get<1>(y));
        return x_data < y_data;
    });

    cout << "Super partition layout:\n";
    cout << "------------------------\n";
    for (auto&& [name, extent] : extents) {
        auto data = ParseLinearExtentData(pt, *extent);
        if (!data) continue;
        auto&& [block_device, offset] = *data;
        cout << block_device << ": " << offset << " .. " << (offset + extent->num_sectors)
             << ": " << name << " (" << extent->num_sectors << " sectors)\n";
    }
    cout << "------------------------\n";

    cout << "Block device table:\n";
    cout << "------------------------\n";
    for (const auto& block_device : pt.block_devices) {
        std::string partition_name = GetBlockDevicePartitionName(block_device);
        cout << "  Partition name: " << partition_name << "\n";
        cout << "  First sector: " << block_device.first_logical_sector << "\n";
        cout << "  Size: " << block_device.size << " bytes\n";
        cout << "  Flags: " << BuildBlockDeviceFlagString(block_device.flags) << "\n";
        cout << "------------------------\n";
    }

    cout << "Group table:\n";
    cout << "------------------------\n";
    for (const auto& group : pt.groups) {
        std::string group_name = GetPartitionGroupName(group);
        cout << "  Name: " << group_name << "\n";
        cout << "  Maximum size: " << group.maximum_size << " bytes\n";
        cout << "  Flags: " << BuildGroupFlagString(group.flags) << "\n";
        cout << "------------------------\n";
    }
}

static std::unique_ptr<LpMetadata> ReadDeviceOrFile(const std::string& path, uint32_t slot) {
    if (IsEmptySuperImage(path)) {
        return ReadFromImageFile(path);
    }
    return ReadMetadata(path, slot);
}

int LpdumpMain(int argc, char* argv[], std::ostream& cout, std::ostream& cerr) {
    // clang-format off
    struct option options[] = {
        { "all", no_argument, nullptr, 'a' },
        { "slot", required_argument, nullptr, 's' },
        { "help", no_argument, nullptr, 'h' },
        { "json", no_argument, nullptr, 'j' },
        { "dump-metadata-size", no_argument, nullptr, 'd' },
        { "is-super-empty", no_argument, nullptr, 'e' },
        { nullptr, 0, nullptr, 0 },
    };
    // clang-format on

    // Allow this function to be invoked by lpdumpd multiple times.
    optind = 1;

    int rv;
    int index;
    bool json = false;
    bool dump_metadata_size = false;
    bool dump_all = false;
    std::optional<uint32_t> slot;
    while ((rv = getopt_long_only(argc, argv, "s:jhde", options, &index)) != -1) {
        switch (rv) {
            case 'a':
                dump_all = true;
                break;
            case 'h':
                usage(argc, argv, cout);
                return EX_OK;
            case 's': {
                uint32_t slot_arg;
                if (android::base::ParseUint(optarg, &slot_arg)) {
                    slot = slot_arg;
                } else {
                    slot = SlotNumberForSlotSuffix(optarg);
                }
                break;
            }
            case 'e':
                // This is ignored, we now derive whether it's empty automatically.
                break;
            case 'd':
                dump_metadata_size = true;
                break;
            case 'j':
                json = true;
                break;
            case '?':
            case ':':
                return usage(argc, argv, cerr);
        }
    }

    if (dump_all) {
        if (slot.has_value()) {
            cerr << "Cannot specify both --all and --slot.\n";
            return usage(argc, argv, cerr);
        }
        if (json) {
            cerr << "Cannot specify both --all and --json.\n";
            return usage(argc, argv, cerr);
        }

        // When dumping everything always start from the first slot.
        slot = 0;
    }

#ifdef __ANDROID__
    // Use the current slot as a default for A/B devices.
    auto current_slot_suffix = GetSlotSuffix();
    if (!slot.has_value() && !current_slot_suffix.empty()) {
        slot = SlotNumberForSlotSuffix(current_slot_suffix);
    }
#endif

    // If we still haven't determined a slot yet, use the first one.
    if (!slot.has_value()) {
        slot = 0;
    }

    // Determine the path to the super partition (or image). If an explicit
    // path is given, we use it for everything. Otherwise, we will infer it
    // at the time we need to read metadata.
    std::string super_path;
    bool override_super_name = (optind < argc);
    if (override_super_name) {
        super_path = argv[optind++];
    } else {
#ifdef __ANDROID__
        super_path = GetSuperPartitionName(slot);
#else
        cerr << "Must specify a super partition image.\n";
        return usage(argc, argv, cerr);
#endif
    }

    auto pt = ReadDeviceOrFile(super_path, slot.value());

    // --json option doesn't require metadata to be present.
    if (json) {
        return PrintJson(pt.get(), cout, cerr);
    }

    if (!pt) {
        cerr << "Failed to read metadata.\n";
        return EX_NOINPUT;
    }

    if (dump_metadata_size) {
        return DumpMetadataSize(*pt.get(), cout);
    }

    // When running on the device, we can check the slot count. Otherwise we
    // use the # of metadata slots. (There is an extra slot we don't want to
    // dump because it is currently unused.)
#ifdef __ANDROID__
    uint32_t num_slots = current_slot_suffix.empty() ? 1 : 2;
    if (dump_all && num_slots > 1) {
        cout << "Current slot: " << current_slot_suffix << "\n";
    }
#else
    uint32_t num_slots = pt->geometry.metadata_slot_count;
#endif
    // Empty images only have one slot.
    if (IsEmptySuperImage(super_path)) {
        num_slots = 1;
    }

    if (num_slots > 1) {
        cout << "Slot " << slot.value() << ":\n";
    }
    PrintMetadata(*pt.get(), cout);

    if (dump_all) {
        for (uint32_t i = 1; i < num_slots; i++) {
            if (!override_super_name) {
                super_path = GetSuperPartitionName(i);
            }

            pt = ReadDeviceOrFile(super_path, i);
            if (!pt) {
                continue;
            }

            cout << "\nSlot " << i << ":\n";
            PrintMetadata(*pt.get(), cout);
        }
    }
    return EX_OK;
}

int LpdumpMain(int argc, char* argv[]) {
    return LpdumpMain(argc, argv, std::cout, std::cerr);
}
