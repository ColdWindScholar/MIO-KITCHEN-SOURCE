#pragma once

#include <list>
#include "meminspect.h"

struct PinConfigFile {
    std::string filename;

    // File relative offsets
    std::vector<VmaRange> ranges;

    ZipEntryCoverage to_zipfilemem(const ZipEntryInfo& info);
};

struct PinConfig {
    std::list<PinConfigFile> files_;

    int parse(std::string filename, bool verbose = false);
};

/**
 * @brief Generate a pinlist file from a given list of vmas containing a list of 4-byte pairs
 * representing (4-byte offset, 4-byte len) contiguous in memory and they are stored in big endian
 * format.
 *
 * @param output_file Output file to write pinlist
 * @param vmas_to_pin Set of vmas to write into pinlist file.
 * @param write_quota Specifies a maximum amount o bytes to be written to the pinlist file
 * or -1 means no limit.
 * @return 0 on success, non-zero on failure
 */
int write_pinlist_file(const std::string& output_file, const std::vector<VmaRange>& vmas_to_pin,
                       int64_t write_quota = -1);

/**
 * @brief This method is the counter part of @see write_pinlist_file(). It will read an existing
 * pinlist file.
 *
 * @param pinner_file Input pinlist file
 * @param pinranges Vmas read from pinlist file. This is populated on call.
 * @return 0 on success, non-zero on failure
 */
int read_pinlist_file(const std::string& pinner_file, /*out*/ std::vector<VmaRange>& pinranges);

enum ProbeType {
    UNSET,     // No probe setup
    GENERATE,  // Generate a probe
    CUSTOM     // User generated probe
};

class PinTool {
  public:
    enum DumpType { PROBE, FILE_COVERAGE, FILTERED };

  private:
    std::string input_file_;
    std::string custom_probe_file_;
    PinConfig* pinconfig_;
    std::vector<ZipEntryCoverage> filtered_files_;
    bool verbose_;
    ZipMemInspector* zip_inspector_ = nullptr;

  public:
    PinTool(const std::string& input_file) : input_file_(input_file) {
        zip_inspector_ = new ZipMemInspector(input_file_);
    }

    ~PinTool() {
        delete zip_inspector_;
        delete pinconfig_;
    }

    void set_verbose_output(bool verbose);

    // Read |probe_file| which should be a pinlist.meta style
    // file and use it as current probe.
    void read_probe_from_pinlist(std::string probe_file);

    // Compute a resident memory probe for |input_file_|
    int probe_resident();

    // Compute coverage for each zip entry contained within
    // |input_file_|.
    // Note: It only works for zip files
    void compute_zip_entry_coverages();

    /**
     * Filter coverages based on a provided pinconfig style file
     * See README.md for sample structure of pinconfig file.
     *
     * Note: It only works for zip files, for non zip files, this will be
     * a no-op.
     */
    void filter_zip_entry_coverages(const std::string& pinconfig_file);

    void filter_zip_entry_coverages(PinConfig* pinconfig);

    /**
     * Dumps output of existing coverages to console for |type|.
     */
    void dump_coverages(DumpType type);

    /**
     * Writes coverages into a pinlist.meta style file.
     *
     * @param write_quota Maximum bytes allowed to be written to file.
     */
    void write_coverages_as_pinlist(std::string output_pinlist, int64_t write_quota = -1);

    std::vector<ZipEntryCoverage> get_filtered_zip_entries();

    /**
     * Sets a user defined inspector, currently only used for testing.
     */
    void set_custom_zip_inspector(ZipMemInspector* inspector);
};