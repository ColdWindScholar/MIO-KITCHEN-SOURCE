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

#include <optional>
#include <sstream>

#include <BootControlClient.h>
#include <android/hardware/boot/1.2/IBootControl.h>
#include <sysexits.h>

using android::sp;

using aidl::android::hardware::boot::MergeStatus;

using android::hal::BootControlClient;
using android::hal::BootControlVersion;
using android::hal::CommandResult;

static void usage(FILE* where, BootControlVersion bootVersion, int /* argc */, char* argv[]) {
    fprintf(where,
            "%s - command-line wrapper for the boot HAL.\n"
            "\n"
            "Usage:\n"
            "  %s COMMAND\n"
            "\n"
            "Commands:\n"
            "  hal-info                       - Show info about boot_control HAL used.\n"
            "  get-number-slots               - Prints number of slots.\n"
            "  get-current-slot               - Prints currently running SLOT.\n"
            "  mark-boot-successful           - Mark current slot as GOOD.\n"
            "  get-active-boot-slot           - Prints the SLOT to load on next boot.\n"
            "  set-active-boot-slot SLOT      - On next boot, load and execute SLOT.\n"
            "  set-slot-as-unbootable SLOT    - Mark SLOT as invalid.\n"
            "  is-slot-bootable SLOT          - Returns 0 only if SLOT is bootable.\n"
            "  is-slot-marked-successful SLOT - Returns 0 only if SLOT is marked GOOD.\n"
            "  get-suffix SLOT                - Prints suffix for SLOT.\n",
            argv[0], argv[0]);
    if (bootVersion >= BootControlVersion::BOOTCTL_V1_1) {
        fprintf(where,
                "  set-snapshot-merge-status STAT - Sets whether a snapshot-merge of any dynamic\n"
                "                                   partition is in progress. Valid STAT values\n"
                "                                   are: none, unknown, snapshotted, merging,\n"
                "                                   or cancelled.\n"
                "  get-snapshot-merge-status      - Prints the current snapshot-merge status.\n");
    }
    fprintf(where,
            "\n"
            "SLOT parameter is the zero-based slot-number.\n");
}

static constexpr auto ToString(BootControlVersion ver) {
    switch (ver) {
        case BootControlVersion::BOOTCTL_V1_0:
            return "android.hardware.boot@1.0::IBootControl";
        case BootControlVersion::BOOTCTL_V1_1:
            return "android.hardware.boot@1.1::IBootControl";
        case BootControlVersion::BOOTCTL_V1_2:
            return "android.hardware.boot@1.2::IBootControl";
        case BootControlVersion::BOOTCTL_AIDL:
            return "android.hardware.boot@aidl::IBootControl";
    }
}

static int do_hal_info(const BootControlClient* module) {
    fprintf(stdout, "HAL Version: %s\n", ToString(module->GetVersion()));
    return EX_OK;
}

static int do_get_number_slots(BootControlClient* module) {
    auto numSlots = module->GetNumSlots();
    fprintf(stdout, "%u\n", numSlots);
    return EX_OK;
}

static int do_get_current_slot(BootControlClient* module) {
    auto curSlot = module->GetCurrentSlot();
    fprintf(stdout, "%u\n", curSlot);
    return EX_OK;
}

static int handle_return(CommandResult cr, const char* errStr) {
    if (!cr.IsOk()) {
        fprintf(stderr, errStr, cr.errMsg.c_str());
        return EX_SOFTWARE;
    } else if (!cr.success) {
        fprintf(stderr, errStr, cr.errMsg.c_str());
        return EX_SOFTWARE;
    }
    return EX_OK;
}

static int do_mark_boot_successful(BootControlClient* module) {
    auto ret = module->MarkBootSuccessful();
    return handle_return(ret, "Error marking as having booted successfully: %s\n");
}

static int do_get_active_boot_slot(BootControlClient* module) {
    uint32_t slot = module->GetActiveBootSlot();
    fprintf(stdout, "%u\n", slot);
    return EX_OK;
}

static int do_set_active_boot_slot(BootControlClient* module, int32_t slot_number) {
    const auto cr = module->SetActiveBootSlot(slot_number);
    return handle_return(cr, "Error setting active boot slot: %s\n");
}

static int do_set_slot_as_unbootable(BootControlClient* module, int32_t slot_number) {
    const auto cr = module->MarkSlotUnbootable(slot_number);
    return handle_return(cr, "Error setting slot as unbootable: %s\n");
}

static int handle_return(const std::optional<bool>& ret, const char* errStr) {
    if (!ret.has_value()) {
        fprintf(stderr, errStr, "");
        return EX_SOFTWARE;
    }
    if (ret.value()) {
        printf("%d\n", ret.value());
        return EX_OK;
    }
    printf("%d\n", ret.value());
    return EX_SOFTWARE;
}

static int do_is_slot_bootable(BootControlClient* module, int32_t slot_number) {
    const auto ret = module->IsSlotBootable(slot_number);
    return handle_return(ret, "Error calling isSlotBootable()\n");
}

static int do_is_slot_marked_successful(BootControlClient* module, int32_t slot_number) {
    const auto ret = module->IsSlotMarkedSuccessful(slot_number);
    return handle_return(ret, "Error calling isSlotMarkedSuccessful()\n");
}

std::optional<MergeStatus> stringToMergeStatus(const std::string& status) {
    if (status == "cancelled") return MergeStatus::CANCELLED;
    if (status == "merging") return MergeStatus::MERGING;
    if (status == "none") return MergeStatus::NONE;
    if (status == "snapshotted") return MergeStatus::SNAPSHOTTED;
    if (status == "unknown") return MergeStatus::UNKNOWN;
    return {};
}

static int do_set_snapshot_merge_status(BootControlClient* module, BootControlVersion bootVersion,
                                        int argc, char* argv[]) {
    if (argc != 3) {
        usage(stderr, bootVersion, argc, argv);
        exit(EX_USAGE);
        return -1;
    }

    auto status = stringToMergeStatus(argv[2]);
    if (!status.has_value()) {
        usage(stderr, bootVersion, argc, argv);
        exit(EX_USAGE);
        return -1;
    }

    const auto ret = module->SetSnapshotMergeStatus(status.value());
    return handle_return(ret, "Failed to set snapshot merge status: %s\n");
}

std::ostream& operator<<(std::ostream& os, MergeStatus state) {
    switch (state) {
        case MergeStatus::CANCELLED:
            return os << "cancelled";
        case MergeStatus::MERGING:
            return os << "merging";
        case MergeStatus::NONE:
            return os << "none";
        case MergeStatus::SNAPSHOTTED:
            return os << "snapshotted";
        case MergeStatus::UNKNOWN:
            return os << "unknown";
        default:
            return os;
    }
}

static int do_get_snapshot_merge_status(BootControlClient* module) {
    MergeStatus ret = module->getSnapshotMergeStatus();
    std::stringstream ss;
    ss << ret;
    fprintf(stdout, "%s\n", ss.str().c_str());
    return EX_OK;
}

static int do_get_suffix(BootControlClient* module, int32_t slot_number) {
    const auto ret = module->GetSuffix(slot_number);
    if (ret.empty()) {
        fprintf(stderr, "Error calling getSuffix()\n");
        return EX_SOFTWARE;
    }
    printf("%s\n", ret.c_str());
    return EX_OK;
}

static uint32_t parse_slot(BootControlVersion bootVersion, int pos, int argc, char* argv[]) {
    if (pos > argc - 1) {
        usage(stderr, bootVersion, argc, argv);
        exit(EX_USAGE);
        return -1;
    }
    errno = 0;
    uint64_t ret = strtoul(argv[pos], NULL, 10);
    if (errno != 0 || ret > UINT_MAX) {
        usage(stderr, bootVersion, argc, argv);
        exit(EX_USAGE);
        return -1;
    }
    return (uint32_t)ret;
}

int main(int argc, char* argv[]) {
    const auto client = android::hal::BootControlClient::WaitForService();
    if (client == nullptr) {
        fprintf(stderr, "Failed to get bootctl module.\n");
        return EX_SOFTWARE;
    }
    const auto bootVersion = client->GetVersion();

    if (argc < 2) {
        usage(stderr, bootVersion, argc, argv);
        return EX_USAGE;
    }

    // Functions present from version 1.0
    if (strcmp(argv[1], "hal-info") == 0) {
        return do_hal_info(client.get());
    } else if (strcmp(argv[1], "get-number-slots") == 0) {
        return do_get_number_slots(client.get());
    } else if (strcmp(argv[1], "get-current-slot") == 0) {
        return do_get_current_slot(client.get());
    } else if (strcmp(argv[1], "mark-boot-successful") == 0) {
        return do_mark_boot_successful(client.get());
    } else if (strcmp(argv[1], "set-active-boot-slot") == 0) {
        return do_set_active_boot_slot(client.get(), parse_slot(bootVersion, 2, argc, argv));
    } else if (strcmp(argv[1], "set-slot-as-unbootable") == 0) {
        return do_set_slot_as_unbootable(client.get(), parse_slot(bootVersion, 2, argc, argv));
    } else if (strcmp(argv[1], "is-slot-bootable") == 0) {
        return do_is_slot_bootable(client.get(), parse_slot(bootVersion, 2, argc, argv));
    } else if (strcmp(argv[1], "is-slot-marked-successful") == 0) {
        return do_is_slot_marked_successful(client.get(), parse_slot(bootVersion, 2, argc, argv));
    } else if (strcmp(argv[1], "get-suffix") == 0) {
        return do_get_suffix(client.get(), parse_slot(bootVersion, 2, argc, argv));
    }

    // Functions present from version 1.1
    if (strcmp(argv[1], "set-snapshot-merge-status") == 0 ||
        strcmp(argv[1], "get-snapshot-merge-status") == 0) {
        if (bootVersion < BootControlVersion::BOOTCTL_V1_1) {
            fprintf(stderr, "Error getting bootctrl v1.1 module.\n");
            return EX_SOFTWARE;
        }
        if (strcmp(argv[1], "set-snapshot-merge-status") == 0) {
            return do_set_snapshot_merge_status(client.get(), bootVersion, argc, argv);
        } else if (strcmp(argv[1], "get-snapshot-merge-status") == 0) {
            return do_get_snapshot_merge_status(client.get());
        }
    }

    if (strcmp(argv[1], "get-active-boot-slot") == 0) {
        if (bootVersion < BootControlVersion::BOOTCTL_V1_2) {
            fprintf(stderr, "Error getting bootctrl v1.2 module.\n");
            return EX_SOFTWARE;
        }

        return do_get_active_boot_slot(client.get());
    }

    // Parameter not matched, print usage
    usage(stderr, bootVersion, argc, argv);
    return EX_USAGE;
}
