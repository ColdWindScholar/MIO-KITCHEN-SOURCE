#include "pin_utils.h"
#include <android-base/parseint.h>
#include <algorithm>
#include <fstream>
#include <map>
#include <string_view>
#include <utility>
#include <vector>

using namespace std;
using namespace android::base;

int write_pinlist_file(const std::string& output_file,
                       const std::vector<ZipEntryCoverage>& files_to_write, int64_t write_quota) {
    std::vector<VmaRange> ranges;
    for (auto&& file : files_to_write) {
        ranges.insert(ranges.end(), file.coverage.ranges.begin(), file.coverage.ranges.end());
    }
    return write_pinlist_file(output_file, ranges, write_quota);
}

int write_pinlist_file(const std::string& output_file, const std::vector<VmaRange>& vmas_to_write,
                       int64_t write_quota) {
    ofstream pinlist_file(output_file);
    if (pinlist_file.fail()) {
        return 1;
    }
    int64_t total_written = 0;
    unsigned int page_size = sysconf(_SC_PAGESIZE);
    const bool has_quota = write_quota > 0;
    bool reached_quota = false;

    // The PinnerService does not require aligned offsets, however, aligning
    // allows our summary results to be accurate and avoids over-accounting
    // of pinning in PinnerService.
    std::vector<VmaRange> processed_vmas_to_write = vmas_to_write;
    align_ranges(processed_vmas_to_write, page_size);

    // When we page-align the ranges, we may cause overlaps between ranges
    // as we elongate the begin offset to match the page the previous
    // range may end up overlapping the current one.
    processed_vmas_to_write = merge_ranges(processed_vmas_to_write);

    for (auto&& processed_vma_to_write : processed_vmas_to_write) {
        uint32_t vma_start_offset = processed_vma_to_write.offset;
        uint32_t vma_length = processed_vma_to_write.length;
        if (has_quota && (total_written + vma_length > write_quota)) {
            // We would go beyond quota, set the maximum allowed write and exit.
            vma_length = write_quota - total_written;
            reached_quota = true;
        }
        // Transform to BigEndian as PinnerService requires that endianness for reading.
        uint32_t vma_start_offset_be = htobe32(vma_start_offset);
        uint32_t vma_length_be = htobe32(vma_length);
        cout << "Pinlist Writing start=" << vma_start_offset << " bytes=" << vma_length << endl;
        pinlist_file.write(reinterpret_cast<char*>(&vma_start_offset_be),
                           sizeof(vma_start_offset_be));
        if (pinlist_file.fail()) {
            return 1;
        }
        pinlist_file.write(reinterpret_cast<char*>(&vma_length_be), sizeof(vma_length_be));
        total_written += vma_length;
        if (pinlist_file.fail()) {
            return 1;
        }

        if (reached_quota) {
            break;
        }
    }
    return 0;
}

int read_pinlist_file(const std::string& pinner_file, /*out*/ std::vector<VmaRange>& pinranges) {
    ifstream pinlist_file(pinner_file);
    if (pinlist_file.fail()) {
        return 1;
    }

    uint32_t vma_start;
    uint32_t vma_length;
    while (!pinlist_file.eof()) {
        pinlist_file.read(reinterpret_cast<char*>(&vma_start), sizeof(vma_start));
        pinlist_file.read(reinterpret_cast<char*>(&vma_length), sizeof(vma_length));
        if (pinlist_file.fail()) {
            return 1;
        }
        vma_start = betoh32(vma_start);
        vma_length = betoh32(vma_length);
        pinranges.push_back(VmaRange(vma_start, vma_length));
    }

    return 0;
}

ZipEntryCoverage PinConfigFile::to_zipfilemem(const ZipEntryInfo& info) {
    ZipEntryCoverage file;
    file.info = info;

    if (ranges.empty()) {
        cout << "No ranges found for file " << info.name << " creating entire file range" << endl;
        // Any file coming from pinconfig without explicit
        // ranges will be assumed to be wanted in its entirety
        ranges.push_back(VmaRange(0, info.file_size_bytes));
    }

    file.coverage.ranges = ranges;

    // Offsets specified in pinconfig file are relative to the file
    // so transform to zip global offsets which are used for coverage
    // computations.
    file.coverage.apply_offset(info.offset_in_zip);

    file.coverage.compute_total_size();
    return file;
}

int PinConfig::parse(std::string config_file, bool verbose) {
    ifstream file(config_file);
    string file_in_zip;
    if (verbose) {
        cout << "Parsing file: " << config_file << endl;
    }
    string token;
    file >> token;
    while (!file.eof()) {
        if (token == "file") {
            file >> file_in_zip;
            PinConfigFile pin_config_file;
            pin_config_file.filename = file_in_zip;
            file >> token;
            while (token != "file" && !file.eof()) {
                VmaRange range;
                // Inner parsing loop for per file config.
                if (token == "offset") {
                    file >> token;
                    android::base::ParseUint(token, &range.offset);
                    file >> token;
                    if (token != "len") {
                        cerr << "Malformed file, expected 'len' after offset" << endl;
                        return 1;
                    }
                    file >> token;
                    android::base::ParseUint(token, &range.length);
                    pin_config_file.ranges.push_back(range);
                }
                file >> token;
            }
            files_.push_back(pin_config_file);
        } else {
            cerr << "Unexpected token: " << token << ". Exit read" << endl;
            return 1;
        }
    }

    if (files_.empty()) {
        cerr << "Failed parsing pinconfig file, no entries found." << endl;
        return 1;
    }

    if (verbose) {
        cout << "Finished parsing Pinconfig file" << endl;
        for (auto&& pin_file : files_) {
            cout << "file=" << pin_file.filename << endl;
            for (auto&& range : pin_file.ranges) {
                cout << "offset=" << range.offset << " bytes=" << range.length << endl;
            }
        }
    }

    return 0;
}

void PinTool::set_custom_zip_inspector(ZipMemInspector* inspector) {
    delete zip_inspector_;
    zip_inspector_ = inspector;
}

void PinTool::set_verbose_output(bool verbose) {
    verbose_ = verbose;
}

void PinTool::read_probe_from_pinlist(std::string custom_probe_file) {
    custom_probe_file_ = custom_probe_file;
    VmaRangeGroup* custom_probe = new VmaRangeGroup();
    read_pinlist_file(custom_probe_file_, custom_probe->ranges);
    custom_probe->compute_total_size();
    if (custom_probe->ranges.empty()) {
        cerr << "Did not find any memory range in " << custom_probe_file_ << endl;
        delete custom_probe;
        return;
    }
    zip_inspector_->set_existing_probe(custom_probe);
}

int PinTool::probe_resident() {
    return zip_inspector_->probe_resident();
}

void PinTool::compute_zip_entry_coverages() {
    zip_inspector_->compute_per_file_coverage();
    if (verbose_) {
        std::vector<ZipEntryInfo> files = zip_inspector_->get_file_infos();
        for (auto&& file : files) {
            cout << "file found. name=" << file.name << " offset=" << file.offset_in_zip
                 << " uncompressed=" << file.uncompressed_size
                 << " compressed=" << file.file_size_bytes << endl
                 << endl;
        }
    }
}

void PinTool::dump_coverages(PinTool::DumpType dump_type) {
    std::vector<ZipEntryCoverage>* file_coverages;
    if (dump_type == PinTool::DumpType::FILTERED) {
        file_coverages = &filtered_files_;
    } else if (dump_type == PinTool::DumpType::FILE_COVERAGE) {
        file_coverages = &(zip_inspector_->get_file_coverages());
    } else {  // PinTool::DumpType::PROBE
        VmaRangeGroup* probe = zip_inspector_->get_probe();
        file_coverages = new vector<ZipEntryCoverage>();
        ZipEntryCoverage file;
        file.coverage = *probe;
        file.info.name = input_file_;
        file.info.offset_in_zip = 0;
        uint64_t file_size_bytes = get_file_size(input_file_);
        if (file_size_bytes == -1) {
            cerr << "Failed to dump, cannot fstat file: " << input_file_ << endl;
            delete file_coverages;
            return;
        }
        file.info.file_size_bytes = file_size_bytes;
        file_coverages->push_back(file);
    }

    for (auto&& file : *file_coverages) {
        uint64_t total_size = file.coverage.compute_total_size();
        cout << file.info.name << " size(B)=" << file.info.file_size_bytes
             << " resident(B)=" << total_size
             << " resident(%)=" << (double)(total_size) / file.info.file_size_bytes * 100.0 << endl;
        if (verbose_) {
            cout << "file_base_zip_offset=" << file.info.offset_in_zip << endl;
        }
        cout << "file resident ranges" << endl;
        if (dump_type != DumpType::PROBE) {
            for (auto&& range : file.coverage.ranges) {
                // The offset in the range represents the absolute absolute offset relative to the
                // zip so substract the file base offset to get the relative offset within the file
                // which may be what is worth for a user to specify in pinconfig.txt files.
                uint64_t offset_in_file = range.offset - file.info.offset_in_zip;

                cout << "zip_offset=" << range.offset << " file_offset=" << offset_in_file
                     << " total_bytes=" << range.length << endl;
            }
        } else {
            for (auto&& range : file.coverage.ranges) {
                cout << "file_offset=" << range.offset << " total_bytes=" << range.length << endl;
            }
        }
        cout << endl;
    }
    cout << endl;
    if (dump_type == DumpType::PROBE) {
        // For other dump types we do not create memory, we reuse from class.
        delete file_coverages;
    }
}

void PinTool::filter_zip_entry_coverages(const std::string& pinconfig_filename) {
    if (pinconfig_filename.length() == 0) {
        // Nothing to do.
        return;
    }

    PinConfig* pinconfig = new PinConfig();
    if (pinconfig->parse(pinconfig_filename, verbose_) > 0) {
        cerr << "Failed parsing pinconfig file " << pinconfig_filename << ". Skip filtering";
        delete pinconfig;
        return;
    }

    filter_zip_entry_coverages(pinconfig);
}

void PinTool::filter_zip_entry_coverages(PinConfig* pinconfig) {
    pinconfig_ = pinconfig;

    // Filter based on the per file configuration.
    vector<ZipEntryCoverage> file_coverages = zip_inspector_->get_file_coverages();
    vector<ZipEntryCoverage>& filtered_files = filtered_files_;

    for (auto&& file_coverage : file_coverages) {
        for (auto&& pinconfig_file : pinconfig_->files_) {
            // Match each zip entry against every pattern in filter file.
            std::string_view file_coverage_view(file_coverage.info.name.c_str());
            std::string_view pinconfig_view(pinconfig_file.filename.c_str());
            if (file_coverage_view.find(pinconfig_view) != std::string_view::npos) {
                // Now that we found a match, create a file with offsets that are global to zip file
                ZipEntryCoverage file_in_config = pinconfig_file.to_zipfilemem(file_coverage.info);
                if (verbose_) {
                    cout << "Found a match: file=" << file_coverage.info.name
                         << " matching filter=" << pinconfig_file.filename << endl;
                    for (auto&& range : file_in_config.coverage.ranges) {
                        cout << "zip_offset=" << range.offset << " bytes=" << range.length << endl;
                    }
                }
                ZipEntryCoverage filtered_file =
                        file_coverage.compute_coverage(file_in_config.coverage);
                filtered_files.push_back(filtered_file);
                break;
            }
        }
    }
}

std::vector<ZipEntryCoverage> PinTool::get_filtered_zip_entries() {
    return filtered_files_;
}

void PinTool::write_coverages_as_pinlist(std::string output_pinlist, int64_t write_quota) {
    std::vector<ZipEntryCoverage>* pinlist_coverages = nullptr;
    if (!filtered_files_.empty()) {
        // Highest preference is writing filtered files if they exist
        if (verbose_) {
            cout << "Writing pinconfig filtered file coverages" << endl;
        }
        pinlist_coverages = &filtered_files_;
    } else if (!zip_inspector_->get_file_coverages().empty()) {
        // Fallback to looking for file coverage computation
        pinlist_coverages = &zip_inspector_->get_file_coverages();
        if (verbose_) {
            cout << "Writing regular file coverages." << endl;
        }
    }
    if (pinlist_coverages == nullptr) {
        cerr << "Failed to find coverage to write to: " << output_pinlist << endl;
        return;
    }
    int res = write_pinlist_file(output_pinlist, *pinlist_coverages, write_quota);
    if (res > 0) {
        cerr << "Failed to write pin file at: " << output_pinlist << endl;
    } else {
        if (verbose_) {
            cout << "Finished writing pin file at: " << output_pinlist << endl;
        }
    }
}