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

#include <stdio.h>
#include <sysexits.h>

#include <string>

#include <liblp/liblp.h>

using namespace android;
using namespace android::fs_mgr;

/* Prints program usage to |where|. */
static int usage(int /* argc */, char* argv[]) {
    fprintf(stderr,
            "%s - command-line tool for dumping Android Logical Partition images.\n"
            "\n"
            "Usage:\n"
            "  %s [block-device] [img-file]\n",
            argv[0], argv[0]);
    return EX_USAGE;
}

int main(int argc, char* argv[]) {
    if (argc != 3) {
        return usage(argc, argv);
    }

    std::unique_ptr<LpMetadata> pt = ReadFromImageFile(argv[2]);
    if (!pt) {
        printf("Failed to read image file.\n");
        return EX_NOINPUT;
    }

    if (!FlashPartitionTable(argv[1], *pt.get())) {
        printf("Failed to flash partition table.\n");
        return EX_SOFTWARE;
    }
    printf("Successfully flashed partition table.\n");
    return EX_OK;
}
