/*
 * Copyright (C) 2019 The Android Open Source Project
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
#include <sysexits.h>

#include <libvbmeta/libvbmeta.h>

using android::fs_mgr::WriteToSuperVBMetaFile;

/* Prints program usage to |where|. */
static int usage(int /* argc */, char* argv[]) {
    fprintf(stderr,
            "%s - command-line tool for creating Super VBMeta Image.\n"
            "\n"
            "Usage:\n"
            "  %s [options]\n"
            "\n"
            "Required options:\n"
            "  -o,--output=FILE              Output file.\n"
            "\n"
            "Optional:\n"
            "  -i,--image=VBMETA_NAME=FILE   include the given vbmeta file as\n"
            "                                initial data for the super vbmeta.\n",
            argv[0], argv[0]);
    return EX_USAGE;
}

int main(int argc, char* argv[]) {
    struct option options[] = {
        { "help", no_argument, nullptr, 'h' },
        { "image", required_argument, nullptr, 'i' },
        { "output", required_argument, nullptr, 'o' },
        { nullptr, 0, nullptr, 0 },
    };

    std::string output_path;
    std::map<std::string, std::string> images;

    int rv;
    while ((rv = getopt_long_only(argc, argv, "i:o:", options, NULL)) != -1) {
        switch (rv) {
            case 'h':
                return usage(argc, argv);
            case 'i':
            {
                char* separator = strchr(optarg, '=');
                if (!separator || separator == optarg || !strlen(separator + 1)) {
                    fprintf(stderr, "Expected VBMETA_NAME=FILE.\n");
                    return EX_USAGE;
                }
                *separator = '\0';

                std::string vbmeta_name(optarg);
                std::string file(separator + 1);
                images[vbmeta_name] = file;
                break;
            }
            case 'o':
                output_path = optarg;
                break;
            default:
                break;
        }
    }

    // Check for empty arguments so we can print a more helpful message rather
    // than error on each individual missing argument.
    if (optind == 1) {
        return usage(argc, argv);
    }

    if (output_path.empty()) {
        fprintf(stderr, "--output must specify a valid path.\n");
        return EX_USAGE;
    }

    if (!WriteToSuperVBMetaFile(output_path.c_str(), images)) {
        return EX_CANTCREAT;
    }

    return EX_OK;
}
