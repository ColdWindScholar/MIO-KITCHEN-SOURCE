#pragma once

#include <android-base/stringprintf.h>
#include <fcntl.h>
#include <sys/endian.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#include <iostream>
#include <string>
#include <vector>
#include "ziparchive/zip_archive.h"

#define MEMINSPECT_FAIL_OPEN 1
#define MEMINSPECT_FAIL_FSTAT 2
#define MEMINSPECT_FAIL_MINCORE 3

#define DEFAULT_PAGES_PER_MINCORE 1

/**
 * This class stores an offset defined vma which exists
 * relative to another memory address.
 */
class VmaRange {
  public:
    uint32_t offset;
    uint32_t length;

    VmaRange() {}
    VmaRange(uint32_t off, uint32_t len) : offset(off), length(len) {}

    bool is_empty() const;

    /**
     * @brief Compute the intersection of this range with another range
     *
     * Intersection Operation:
     *
     * Example 1:
     * [   Range A    ]
     *          [   Range B   ]
     * Intersection:
     *          [  C  ]
     *
     * Example 2:
     * [   Range A    ]    [   Range B   ]
     * No Intersection
     *
     * @param target range to test against
     * @return the intersection range, if none is found, empty range is returned.
     */
    VmaRange intersect(const VmaRange& target) const;

    /**
     * @brief Merges the current range with a target range using a union operation
     * that is only successful when overlapping ranges occur.
     * A visual explanation can be seen as:
     *
     * Union-merge Operation:
     *
     * Example 1:
     * [   Range A    ]
     *          [   Range B   ]
     * Merged:
     * [       Range C        ]
     *
     * Example 2:
     * [   Range A    ]    [   Range B   ]
     * Fails, no merge available.
     *
     * @param target The range to test against.
     * @param result Upon successfully merging, contains the resulting range.
     * @return the merged range, if none is found, empty range is returned.
     */
    VmaRange union_merge(const VmaRange& target) const;

    uint32_t end_offset() const;
};

/**
 * Represents a set of memory ranges
 */
struct VmaRangeGroup {
    std::vector<VmaRange> ranges;

    /**
     * Compute intersection coverage between |range| and |this->ranges|
     * and append it to |out_memres|
     */
    void compute_coverage(const VmaRange& range, VmaRangeGroup& out_memres) const;

    /**
     * Apply an offset to all existing |ranges|.
     */
    void apply_offset(uint64_t offset);

    /**
     * Computes total resident bytes from existing set of memory ranges.
     */
    uint64_t compute_total_size();
};

/**
 * Represents useful immutable metadata for zip entry
 */
struct ZipEntryInfo {
    std::string name;
    uint64_t offset_in_zip;
    uint64_t file_size_bytes;
    uint64_t uncompressed_size;
};

/**
 * Represents the resident memory coverage for a zip entry within a zip file.
 */
struct ZipEntryCoverage {
    ZipEntryInfo info;

    /**
     * Contains all the coverage ranges if any have been computed with |compute_coverage|
     * and their offsets will be the absolute global offset from the zip file start.
     */
    VmaRangeGroup coverage;

    /**
     * Computes the intersection coverage for the current zip file entry
     * resident memory against a provided |probe| representing another set
     * of ranges.
     */
    ZipEntryCoverage compute_coverage(const VmaRangeGroup& probe) const;
};

// Class used for inspecting resident memory for entries within a zip file
class ZipMemInspector {
    /**
     * Stored probe of resident ranges either computed or provided by user.
     */
    VmaRangeGroup* probe_resident_ = nullptr;

    /**
     * List of file entries within zip file.
     */
    std::vector<ZipEntryInfo> entry_infos_;

    /**
     * Path to zip file.
     */
    std::string filename_;

    /**
     * Result of computing coverage operations.
     */
    std::vector<ZipEntryCoverage> entry_coverages_;

    /**
     * Handle that allows reading the zip entries.
     */
    ZipArchiveHandle handle_;

  public:
    ZipMemInspector(std::string filename) : filename_(filename) {}
    ~ZipMemInspector();

    /**
     * Reads zip file and computes resident memory coverage per zip entry if
     * a probe is provided, if no probe is provided, then whole file coverage
     * will be assumed.
     *
     * Note: If any zip entries have been manually added via |add_file_info|
     * then coverage will be only computed against manually added entries.
     *
     * @return 0 on success and 1 on error
     */
    int compute_per_file_coverage();

    /**
     * Computes resident memory for the entire zip file.
     *
     * @return 0 on success, 1 on failure
     */
    int probe_resident();

    /**
     * Retrieves the currently set probe if any exists.
     */
    VmaRangeGroup* get_probe();

    /**
     * Sets probe data in case you decide to pass a previously taken probe instead of a live taken
     * one.
     */
    void set_existing_probe(VmaRangeGroup* probe);

    /**
     * Returns the result of memory coverage of each file if any has been computed via
     * |compute_per_file_coverage|.
     */
    std::vector<ZipEntryCoverage>& get_file_coverages();

    /**
     * Returns the file information for each zip entry.
     */
    std::vector<ZipEntryInfo>& get_file_infos();

    /**
     * Add a zip entry manually.
     *
     * Note: Zip entries are usually retrieved by reading the |filename_| so
     * this method is mostly used for cases where client wants control of
     * zip file reading or for testing.
     */
    void add_file_info(ZipEntryInfo& file);

    /**
     * Computes the intersection coverage between provided |files| and |probe|.
     *
     * @return result of coverage computation
     */
    static std::vector<ZipEntryCoverage> compute_coverage(
            const std::vector<ZipEntryCoverage>& files, VmaRangeGroup* probe);

  private:
    /**
     * Read files and zip relative offsets for them.
     *
     * @return 0 on success, 1 on failure.
     */
    int read_files_and_offsets();
};

/**
 * Retrieve file size in bytes for |file|
 *
 * @return positive value with file size on success, otherwise, returns -1 on error.
 */
int64_t get_file_size(const std::string& file);

/**
 * @brief Probe resident memory for a currently opened file in the system.
 *
 * @param probed_file File to probe as defined by its path.
 * @param out_resident_mem Inspection result. This is populated when called.
 * @param pages_per_mincore Size of mincore window used, bigger means more memory used
 * during operation but slightly faster.
 * @return 0 on success or on failure a non-zero error code from the following list:
 * MEMINSPECT_FAIL_OPEN, MEMINSPECT_FAIL_FSTAT, MEMINSPECT_FAIL_MINCORE
 */
int probe_resident_memory(std::string probed_file, VmaRangeGroup& out_resident_mem,
                          int pages_per_mincore = DEFAULT_PAGES_PER_MINCORE);

/**
 * @brief Align vma ranges to a certain page size
 *
 * @param ranges vma ranges that have to be aligned
 * @param alignment Desired alignment, this is usually the page size.
 */
void align_ranges(std::vector<VmaRange>& ranges, unsigned int alignment);

/**
 * @brief Merges a list of ranges following a union-like merge which
 * means that two ranges that overlap will avoid double accounting for
 * overlaps.
 *
 * @param ranges vma ranges that need to be merged.
 * @return new vector with ranges merged.
 */
std::vector<VmaRange> merge_ranges(const std::vector<VmaRange>& ranges);