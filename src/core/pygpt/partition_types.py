from enum import Enum

import uuid

class PartitionTypes(Enum):
    Unused = uuid.UUID('00000000-0000-0000-0000-000000000000')

    # Microsoft types from https://en.wikipedia.org/wiki/GUID_Partition_Table
    # First three blocks have bytes swapped to conform to little-endian storage
    MicrosoftBasicData = uuid.UUID('a2a0d0eb-e5b9-3344-87c0-68b6b72699c7')
    MicrosoftReserved = uuid.UUID('16e3c9e3-5c0b-b84d-817d-f92df00215ae')
    MicrosoftLdmMetadata = uuid.UUID('aac80858-8f7e-e042-85d2-e1e90434cfb3')
    MicrosoftLDM = uuid.UUID('a0609baf-3114-624f-68bc-3311714a69ad')
    WindowsRecoverEnvrionment = ('a4bb94de-d106-404d-a6a1-bfd50179d6ac')
    MicrosoftIBMGeneralParallel = ('90cfaf37-7def-964e-c391-2d7ae055b174')
    MicrosoftStorageSpace = ('8fafc5e7-80f6-ee4c-a3af-b001e56efc2d')

    # Linux types from https://en.wikipedia.org/wiki/GUID_Partition_Table
    # First three blocks have bytes swapped to conform to little-endian storage
    LinuxFilesystem = uuid.UUID('af3dc60f-8384-7247-8e79-3d69d8477de4')
    LinuxRaidPart = uuid.UUID('0f889da1-fc05-3B4d-06a0-743f0f84911e')
    LinuxRootPart = uuid.UUID('40954744-97f2-b241-f79a-d131d5f0458a')
    LinuxRootPartX86_64 = uuid.UUID('e3bc684f-cde8-b14d-e796-fbcaf984b709')
    LinuxRootPartRootArm32 =     uuid.UUID('10d7da69-e42c-3c4e-6cb1-21a1d49abed3')
    LinuxRootPartArm64 = uuid.UUID('45b021b9-f01d-c341-44af-4c6f280d3fae')
    LinuxSwapPart = uuid.UUID('6dfd5706-aba4-c443-e584-0933c84b4f4f')
    LinuxLVMPart = uuid.UUID('79d3d6e6-07f5-c244-3ca2-238f2a3df928')
    LinuxHomePart = uuid.UUID('e1c73a93-b42e-134f-44b8-0e14e2eef915')
    LinuxServerDataPart = uuid.UUID('25848f3b-e020-3b4f-7f90-1a25a76f98e8')
    LinuxPlainDmCryptPart = uuid.UUID('7FFEC5C9-2D00-49B7-8941-3EA10A5586B7')
    LinuxLUKSPart = uuid.UUID('cb7c7dca-ed63-534c-1c86-1742536059cc')
    LinuxReserved = uuid.UUID('3933a68d-0700-c060-36c4-083ac8230908')

    # Qualcomm types found typically on Android devices
    QualcommRoot = uuid.UUID('11b0d797-da54-3548-b3c4-917ad6e73d74')
    QualcommVbmeta = uuid.UUID('d46c0377-d503-bb42-8ed1-37e5a88baa35')
    # used for TZ, hyp and boot firmware blobs, apparently B partitions
    # all have the same type while A are treated differently
    QualcommFirmware = uuid.UUID('d46c0377-d503-bb42-8ed1-37e5a88baa34')
