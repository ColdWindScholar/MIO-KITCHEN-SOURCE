#include <android-base/parseint.h>
#include <fcntl.h>
#include <sys/endian.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#include <iostream>
#include <string>
#include <vector>

#include <meminspect.h>
#include <pin_utils.h>

using namespace std;
using namespace android::base;

enum ToolMode {
    MAPPED_FILE,  // Files that are mapped in memory
    PINLIST,      // pinlist.meta style file
    UNKNOWN
};

void print_pinlist_ranges(const std::vector<VmaRange>& ranges) {
    cout << "--pinlist memory ranges--" << endl;
    for (auto&& range : ranges) {
        cout << "start=" << range.offset << " bytes=" << range.length << endl;
    }
}

void print_pinlist_summary(const std::vector<VmaRange>& ranges) {
    cout << "--pinlist summary--" << endl;
    uint64_t total_bytes = 0;
    for (auto&& range : ranges) {
        total_bytes += range.length;
    }
    cout << "total_bytes_to_pin=" << total_bytes << endl;
}

int perform_file_action(const vector<string>& options) {
    std::string custom_probe_file;
    std::string output_file;
    std::string pinconfig_file;

    bool verbose = false;
    bool is_zip = false;
    bool dump_results = false;
    ProbeType probe_type = UNSET;
    int64_t write_quota = -1;  // unbounded by default

    if (options.empty()) {
        cerr << "Missing filename for file action, see usage for details." << endl;
        return 1;
    }

    std::string input_file = options[0];

    // Validate that the file exists.
    if (get_file_size(input_file) == -1) {
        cerr << "Error: Could not read file: " << input_file << endl;
        return 1;
    }

    if (input_file.empty()) {
        cerr << "Error: Should specify an input file." << endl;
        return 1;
    }

    // Parse flags
    for (int i = 1; i < options.size(); ++i) {
        string option = options[i];
        if (option == "--gen-probe") {
            if (probe_type != ProbeType::UNSET) {
                cerr << "Should only specify one probe treatment. See usage for details." << endl;
                return 1;
            }
            probe_type = ProbeType::GENERATE;
            continue;
        }

        if (option == "--use-probe") {
            if (probe_type != ProbeType::UNSET) {
                cerr << "Should only specify one probe treatment. See usage for details." << endl;
                return 1;
            }
            probe_type = ProbeType::CUSTOM;
            ++i;
            custom_probe_file = options[i];
            continue;
        }
        if (option == "--pinconfig") {
            ++i;
            pinconfig_file = options[i];
            continue;
        }
        if (option == "-o") {
            ++i;
            output_file = options[i];
            continue;
        }
        if (option == "--quota") {
            ++i;
            android::base::ParseInt(options[i], &write_quota);
            continue;
        }
        if (option == "-v") {
            verbose = true;
            continue;
        }
        if (option == "--zip") {
            is_zip = true;
            continue;
        }
        if (option == "--dump") {
            dump_results = true;
            continue;
        }
    }

    if (verbose) {
        cout << "Setting output pinlist file: " << output_file.c_str() << endl;
        cout << "Setting input file: " << input_file.c_str() << endl;
        cout << "Setting pinconfig file: " << pinconfig_file.c_str() << endl;
        cout << "Setting custom probe file: " << custom_probe_file.c_str() << endl;
        cout << "Setting probe type: " << probe_type << endl;
        cout << "Dump enabled: " << dump_results << endl;
        cout << "Is Zip file: " << is_zip << endl;
        if (write_quota != -1) {
            cout << "Set Write quota: " << write_quota << endl;
        }
    }

    PinTool pintool(input_file);

    if (is_zip) {
        pintool.set_verbose_output(verbose);
        if (probe_type == ProbeType::CUSTOM) {
            if (verbose) {
                cout << "Using custom probe file: " << custom_probe_file << endl;
            }
            pintool.read_probe_from_pinlist(custom_probe_file);
        } else if (probe_type == ProbeType::GENERATE) {
            if (verbose) {
                cout << "Generating probe" << endl;
            }
            int res = pintool.probe_resident();
            if (res > 0) {
                cerr << "Failed to generate probe. Error Code: " << res << endl;
                return 1;
            }
        }
        pintool.compute_zip_entry_coverages();

        if (pinconfig_file.length() > 0) {
            // We have provided a pinconfig file so perform filtering
            // of computed coverages based on it.
            pintool.filter_zip_entry_coverages(pinconfig_file);
        }

        if (dump_results) {
            cout << endl << "----Unfiltered file coverages----" << endl << endl;
            pintool.dump_coverages(PinTool::DumpType::FILE_COVERAGE);

            if (pinconfig_file.length() > 0) {
                cout << endl << "----Filtered file coverages----" << endl << endl;
                pintool.dump_coverages(PinTool::DumpType::FILTERED);
            }
        }

        if (output_file.length() > 0) {
            pintool.write_coverages_as_pinlist(output_file, write_quota);
        }

        return 0;
    } else {
        if (probe_type != ProbeType::GENERATE) {
            cerr << "Only generating probes is supported for non-zip files, please include "
                    "--gen-probe on your command"
                 << endl;
            return 1;
        }

        // Generic file probing will just return resident memory and offsets
        // without more contextual information.
        VmaRangeGroup resident;

        int res = pintool.probe_resident();
        if (res > 0) {
            cerr << "Failed to generate probe. Error Code: " << res << endl;
            return 1;
        }

        pintool.dump_coverages(PinTool::DumpType::PROBE);

        if (output_file.length() > 0) {
            res = write_pinlist_file(output_file, resident.ranges, write_quota);
            if (res > 0) {
                cerr << "Failed to write pin file at: " << output_file << endl;
            } else if (verbose) {
                cout << "Finished writing pin file at: " << output_file << endl;
            }
        }
        return res;
    }
    return 0;
}

int perform_pinlist_action(const vector<string>& options) {
    string pinner_file;
    bool verbose = false;
    bool dump = false;
    bool summary = false;

    if (options.size() < 1) {
        cerr << "Missing arguments for pinlist mode. See usage for details << endl";
        return 1;
    }
    pinner_file = options[0];
    for (int i = 1; i < options.size(); ++i) {
        string option = options[i];

        if (option == "-v") {
            verbose = true;
        }

        if (option == "--dump") {
            dump = true;
        }

        if (option == "--summary") {
            summary = true;
        }
    }

    if (pinner_file.empty()) {
        cerr << "Error: Pinlist file to dump is missing. Specify it with '-p <file>'" << endl;
        return 1;
    }

    if (verbose) {
        cout << "Setting file to dump: " << pinner_file.c_str() << endl;
    }

    vector<VmaRange> vma_ranges;
    if (read_pinlist_file(pinner_file, vma_ranges) == 1) {
        cerr << "Failed reading pinlist file" << endl;
    }

    if (dump) {
        print_pinlist_ranges(vma_ranges);
    }

    if (summary) {
        print_pinlist_summary(vma_ranges);
    }

    return 0;
}

void print_usage() {
    const string usage = R"(
    Expected usage: pintool <mode> <required> [option]
    where:
    ./pintool <MODE>
    <MODE>
        file <filename> [option]
            [option]
                --gen-probe
                    Generate a probe from current resident memory based on provided "file"
                --use-probe <path_to_input_pinlist.meta>
                    Use a previously generated pinlist.meta style file as the probe to match against.
                --dump
                    Dump output contents to console.
                --zip
                    Treat the file as a zip/apk file required for doing per-file coverage analysis and generation.
                --pinconfig <path_to_pinconfig.txt>
                    Filter output coverage ranges using a provided pinconfig.txt style file. See README.md for samples
                    on the format of that file.
                -v
                    Enable verbose output.

        pinlist <pinlist_file> [option]
            <pinlist_file>
                this is the file that will be used for reading and it should follow the pinlist.meta format.
            [option]
                --dump
                    Dump <pinlist_file> contents to console output.
                -v
                    Enable verbose output.
                --summary
                    Summary results for the pinlist.meta file
    )";
    cout << usage.c_str();
}

int main(int argc, char** argv) {
    if (argc == 1) {
        print_usage();
        return 0;
    }

    if (argc < 2) {
        cerr << "<mode> is missing";
        return 1;
    }

    if (strcmp(argv[1], "--help") == 0) {
        print_usage();
        return 0;
    }

    ToolMode mode = ToolMode::UNKNOWN;
    if (strcmp(argv[1], "file") == 0) {
        mode = ToolMode::MAPPED_FILE;
    } else if (strcmp(argv[1], "pinlist") == 0) {
        mode = ToolMode::PINLIST;
    }

    if (mode == ToolMode::UNKNOWN) {
        cerr << "Failed to find mode: " << argv[1] << ". See usage for available modes." << endl;
        return 1;
    }

    vector<string> options;
    for (int i = 2; i < argc; ++i) {
        options.push_back(argv[i]);
    }

    int res;
    switch (mode) {
        case ToolMode::MAPPED_FILE:
            res = perform_file_action(options);
            break;
        case ToolMode::PINLIST:
            res = perform_pinlist_action(options);
            break;
        case ToolMode::UNKNOWN:
            cerr << "Unknown <MODE> see usage for details." << endl;
            return 1;
    }

    return res;
}
