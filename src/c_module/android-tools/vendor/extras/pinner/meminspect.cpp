#include "meminspect.h"
#include <android-base/unique_fd.h>
#include "ziparchive/zip_archive.h"

using namespace std;
using namespace android::base;
using namespace ::android::base;

const static VmaRange VMA_RANGE_EMPTY = VmaRange(0, 0);

uint32_t VmaRange::end_offset() const {
    return offset + length;
}

uint64_t VmaRangeGroup::compute_total_size() {
    uint64_t total_size = 0;
    for (auto&& range : ranges) {
        total_size += range.length;
    }
    return total_size;
}

void VmaRangeGroup::apply_offset(uint64_t offset) {
    for (auto&& range : ranges) {
        range.offset += offset;
    }
}

void VmaRangeGroup::compute_coverage(const VmaRange& range, VmaRangeGroup& out_memres) const {
    for (auto&& resident_range : ranges) {
        VmaRange intersect_res = resident_range.intersect(range);
        if (!intersect_res.is_empty()) {
            out_memres.ranges.push_back(intersect_res);
        }
    }
}

bool VmaRange::is_empty() const {
    return length == 0;
}

VmaRange VmaRange::intersect(const VmaRange& target) const {
    // First check if the slice is outside our range
    if (target.end_offset() <= this->offset) {
        return VMA_RANGE_EMPTY;
    }
    if (target.offset >= this->end_offset()) {
        return VMA_RANGE_EMPTY;
    }
    VmaRange result;
    // the slice should now be inside the range so compute the intersection.
    result.offset = std::max(target.offset, this->offset);
    uint32_t res_end = std::min(target.end_offset(), end_offset());
    result.length = res_end - result.offset;

    return result;
}

VmaRange VmaRange::union_merge(const VmaRange& target) const {
    VmaRange result = intersect(target);
    if (result.is_empty()) {
        // Disjointed ranges, no merge.
        return VMA_RANGE_EMPTY;
    }

    // Since there is an intersection, merge ranges between lowest
    // and highest value.
    result.offset = std::min(offset, target.offset);
    uint32_t res_end = std::max(target.end_offset(), end_offset());
    result.length = res_end - result.offset;
    return result;
}

void align_ranges(std::vector<VmaRange>& vmas_to_align, unsigned int alignment) {
    for (auto&& vma_to_align : vmas_to_align) {
        uint32_t unaligned_offset = vma_to_align.offset % alignment;
        vma_to_align.offset -= unaligned_offset;
        vma_to_align.length += unaligned_offset;
    }
}

bool compare_range(VmaRange& a, VmaRange& b) {
    return a.offset < b.offset;
}

std::vector<VmaRange> merge_ranges(const std::vector<VmaRange>& ranges) {
    if (ranges.size() <= 1) {
        // Not enough ranges to perform a merge.
        return ranges;
    }

    std::vector<VmaRange> to_merge_ranges = ranges;
    std::vector<VmaRange> merged_ranges;
    // Sort the ranges to make a slightly more efficient merging.
    std::sort(to_merge_ranges.begin(), to_merge_ranges.end(), compare_range);

    // The first element will always start as-is, then start merging with subsequent elements.
    merged_ranges.push_back(to_merge_ranges[0]);
    for (int iMerged = 0, iTarget = 1; iTarget < to_merge_ranges.size(); ++iTarget) {
        VmaRange merged = merged_ranges[iMerged].union_merge(to_merge_ranges[iTarget]);
        if (!merged.is_empty()) {
            // Merge was successful, swallow range.
            merged_ranges[iMerged] = merged;
        } else {
            // Merge failed, add disjointed range.
            merged_ranges.push_back(to_merge_ranges[iTarget]);
            ++iMerged;
        }
    }

    return merged_ranges;
}

int64_t get_file_size(const std::string& file) {
    unique_fd file_ufd(open(file.c_str(), O_RDONLY));
    int fd = file_ufd.get();
    if (fd == -1) {
        return -1;
    }

    struct stat fstat_res;
    int res = fstat(fd, &fstat_res);
    if (res == -1) {
        return -1;
    }

    return fstat_res.st_size;
}

int probe_resident_memory(string probed_file,
                          /*out*/ VmaRangeGroup& resident_ranges, int pages_per_mincore) {
    unique_fd probed_file_ufd(open(probed_file.c_str(), O_RDONLY));
    int probe_fd = probed_file_ufd.get();
    if (probe_fd == -1) {
        return MEMINSPECT_FAIL_OPEN;
    }

    int64_t total_bytes = get_file_size(probed_file);
    if (total_bytes < 0) {
        return MEMINSPECT_FAIL_FSTAT;
    }

    char* base_address =
            (char*)mmap(0, (uint64_t)total_bytes, PROT_READ, MAP_SHARED, probe_fd, /*offset*/ 0);

    // this determines how many pages to inspect per mincore syscall
    unsigned char* window = new unsigned char[pages_per_mincore];

    unsigned int page_size = sysconf(_SC_PAGESIZE);
    unsigned long bytes_inspected = 0;

    // total bytes in inspection window
    unsigned long window_bytes = page_size * pages_per_mincore;

    char* window_base;
    bool started_vma_range = false;
    uint32_t resident_vma_start_offset = 0;
    for (window_base = base_address; bytes_inspected < total_bytes;
         window_base += window_bytes, bytes_inspected += window_bytes) {
        int res = mincore(window_base, window_bytes, window);
        if (res != 0) {
            if (errno == ENOMEM) {
                // Did not find page, maybe it's a hole.
                continue;
            }
            return MEMINSPECT_FAIL_MINCORE;
        }
        // Inspect the provided mincore window result sequentially
        // and as soon as a change in residency happens a range is
        // created or finished.
        for (int iWin = 0; iWin < pages_per_mincore; ++iWin) {
            if ((window[iWin] & (unsigned char)1) != 0) {
                // Page is resident
                if (!started_vma_range) {
                    // End of range
                    started_vma_range = true;
                    uint32_t window_offset = iWin * page_size;
                    resident_vma_start_offset = window_base + window_offset - base_address;
                }
            } else {
                // Page is not resident
                if (started_vma_range) {
                    // Start of range
                    started_vma_range = false;
                    uint32_t window_offset = iWin * page_size;
                    uint32_t resident_vma_end_offset = window_base + window_offset - base_address;
                    uint32_t resident_len = resident_vma_end_offset - resident_vma_start_offset;
                    VmaRange vma_range(resident_vma_start_offset, resident_len);
                    resident_ranges.ranges.push_back(vma_range);
                }
            }
        }
    }
    // This was the last window, so close any opened vma range
    if (started_vma_range) {
        started_vma_range = false;
        uint32_t in_memory_vma_end = window_base - base_address;
        uint32_t resident_len = in_memory_vma_end - resident_vma_start_offset;
        VmaRange vma_range(resident_vma_start_offset, resident_len);
        resident_ranges.ranges.push_back(vma_range);
    }

    return 0;
}

ZipMemInspector::~ZipMemInspector() {
    CloseArchive(handle_);
    delete probe_resident_;
}

ZipEntryCoverage ZipEntryCoverage::compute_coverage(const VmaRangeGroup& probe) const {
    ZipEntryCoverage file_coverage;
    file_coverage.info = info;

    // Compute coverage for each range in file against probe which represents a set of ranges.
    for (auto&& range : coverage.ranges) {
        probe.compute_coverage(range, file_coverage.coverage);
    }

    return file_coverage;
}

std::vector<ZipEntryCoverage> ZipMemInspector::compute_coverage(
        const std::vector<ZipEntryCoverage>& files, VmaRangeGroup* probe) {
    if (probe == nullptr) {
        // No probe to calculate coverage against, so coverage is zero.
        return std::vector<ZipEntryCoverage>();
    }

    std::vector<ZipEntryCoverage> file_coverages;
    // Find the file coverage against provided probe.
    for (auto&& file : files) {
        // For each file, compute coverage against the probe which represents a list of ranges.
        ZipEntryCoverage file_coverage = file.compute_coverage(*probe);
        file_coverages.push_back(file_coverage);
    }

    return file_coverages;
}

void ZipMemInspector::add_file_info(ZipEntryInfo& file) {
    entry_infos_.push_back(file);
}

int ZipMemInspector::compute_per_file_coverage() {
    if (entry_infos_.empty()) {
        // We haven't read the file information yet, so do it now.
        if (read_files_and_offsets()) {
            cerr << "Could not read zip entries to compute coverages." << endl;
            return 1;
        }
    }

    // All existing files should consider their whole memory as present by default.
    std::vector<ZipEntryCoverage> entry_coverages;
    for (auto&& entry_info : entry_infos_) {
        ZipEntryCoverage entry_coverage;
        entry_coverage.info = entry_info;
        VmaRange file_vma_range(entry_info.offset_in_zip, entry_info.file_size_bytes);
        entry_coverage.coverage.ranges.push_back(file_vma_range);
        entry_coverage.coverage.compute_total_size();
        entry_coverages.push_back(entry_coverage);
    }

    if (probe_resident_ != nullptr) {
        // We decided to compute coverage based on a probe
        entry_coverages_ = compute_coverage(entry_coverages, probe_resident_);
    } else {
        // No probe means whole file coverage
        entry_coverages_ = entry_coverages;
    }

    return 0;
}

VmaRangeGroup* ZipMemInspector::get_probe() {
    return probe_resident_;
}

void ZipMemInspector::set_existing_probe(VmaRangeGroup* probe) {
    this->probe_resident_ = probe;
}

std::vector<ZipEntryCoverage>& ZipMemInspector::get_file_coverages() {
    return entry_coverages_;
}

int ZipMemInspector::probe_resident() {
    probe_resident_ = new VmaRangeGroup();
    int res = probe_resident_memory(filename_, *probe_resident_);
    if (res != 0) {
        // Failed to probe
        return res;
    }

    return 0;
}

std::vector<ZipEntryInfo>& ZipMemInspector::get_file_infos() {
    return entry_infos_;
}

int ZipMemInspector::read_files_and_offsets() {
    if (OpenArchive(filename_.c_str(), &handle_) < 0) {
        return 1;
    }
    void* cookie;
    int res = StartIteration(handle_, &cookie);
    if (res != 0) {
        return 1;
    }

    ZipEntry64 entry;
    string name;
    while (Next(cookie, &entry, &name) == 0) {
        ZipEntryInfo file;
        file.name = name;
        file.offset_in_zip = entry.offset;
        file.file_size_bytes = entry.compressed_length;
        file.uncompressed_size = entry.uncompressed_length;
        entry_infos_.push_back(file);
    }
    return 0;
}
