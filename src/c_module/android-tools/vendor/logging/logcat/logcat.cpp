/*
 * Copyright (C) 2006 The Android Open Source Project
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

#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <error.h>
#include <fcntl.h>
#include <getopt.h>
#include <linux/f2fs.h>
#include <linux/fs.h>
#include <malloc.h>
#include <math.h>
#include <sched.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#include <memory>
#include <regex>
#include <set>
#include <string>
#include <utility>
#include <vector>

#include <android-base/file.h>
#include <android-base/macros.h>
#include <android-base/parseint.h>
#include <android-base/properties.h>
#include <android-base/stringprintf.h>
#include <android-base/strings.h>
#include <android-base/unique_fd.h>
#include <android/log.h>
#include <log/event_tag_map.h>
#include <log/log_id.h>
#include <log/log_read.h>
#include <log/logprint.h>
#include <private/android_logger.h>
#include <processgroup/sched_policy.h>
#include <system/thread_defs.h>
#include "logcat.pb.h"
#include "process_names.h"

using com::android::logcat::proto::LogcatEntryProto;
using com::android::logcat::proto::LogcatPriorityProto;

#define DEFAULT_MAX_ROTATED_LOGS 4

using android::base::Join;
using android::base::ParseByteCount;
using android::base::ParseUint;
using android::base::Split;
using android::base::StringPrintf;
using android::base::WaitForProperty;
using android::base::WriteFully;

namespace {
enum OutputType {
    TEXT,    // Human-readable formatted
    BINARY,  // Raw struct log_msg as obtained from logd
    PROTO    // Protobuffer format. See logcat.proto for details. Each message is prefixed with
             // 8 bytes (little endian) size of the message.
};
}  // namespace

class Logcat {
  public:
    int Run(int argc, char** argv);

  private:
    FILE* OpenLogFile(const char* path);
    void RotateLogs();
    void ProcessBuffer(struct log_msg* buf);
    LogcatPriorityProto GetProtoPriority(const AndroidLogEntry& entry);
    uint64_t PrintToProto(const AndroidLogEntry& entry);
    void PrintDividers(log_id_t log_id, bool print_dividers);
    void SetupOutputAndSchedulingPolicy(bool blocking);
    int SetLogFormat(const char* format_string);
    void WriteFully(const void* p, size_t n) {
        if (fwrite(p, 1, n, output_file_) != n) {
            error(EXIT_FAILURE, errno, "Write to output file failed");
        }
    }

    const bool kCompressLogcat = android::base::GetBoolProperty("ro.logcat.compress", false);

    // Used for all options
    std::unique_ptr<AndroidLogFormat, decltype(&android_log_format_free)> logformat_{
            android_log_format_new(), &android_log_format_free};
    // This isn't a unique_ptr because it's usually stdout;
    // stdio's atexit handler ensures we flush on exit.
    FILE* output_file_ = stdout;

    // For logging to a file and log rotation
    const char* output_file_name_ = nullptr;
    size_t log_rotate_size_kb_ = 0;                       // 0 means "no log rotation"
    size_t max_rotated_logs_ = DEFAULT_MAX_ROTATED_LOGS;  // 0 means "unbounded"
    uint64_t out_byte_count_ = 0;

    enum OutputType output_type_ = TEXT;

    // For binary log buffers
    std::unique_ptr<EventTagMap, decltype(&android_closeEventTagMap)> event_tag_map_{
            nullptr, &android_closeEventTagMap};
    bool has_opened_event_tag_map_ = false;

    // For the related --regex, --max-count, --print
    std::unique_ptr<std::regex> regex_;
    size_t max_count_ = 0;  // 0 means "infinite"
    size_t print_count_ = 0;
    bool print_it_anyway_ = false;

    // For PrintDividers()
    bool print_dividers_ = false;
    log_id_t last_printed_id_ = LOG_ID_MAX;
    bool printed_start_[LOG_ID_MAX] = {};

    bool debug_ = false;

    ProcessNames process_names_;
};

static void startCompMode(int fd) {
    // Ignore errors.
    long flag = FS_COMPR_FL;
    ioctl(fd, FS_IOC_SETFLAGS, &flag);
}

static void releaseCompBlocks(const char* pathname) {
    int fd = open(pathname, O_RDONLY);
    if (fd != -1) {
        // Ignore errors.
        unsigned long long blkcnt;
        ioctl(fd, F2FS_IOC_RELEASE_COMPRESS_BLOCKS, &blkcnt);
        close(fd);
    }
}

FILE* Logcat::OpenLogFile(const char* path) {
    int fd = open(path, O_WRONLY | O_APPEND | O_CREAT | O_CLOEXEC, S_IRUSR | S_IWUSR | S_IRGRP);
    if (fd == -1) {
        error(EXIT_FAILURE, errno, "couldn't open output file '%s'", path);
    }
    if (kCompressLogcat) {
        startCompMode(fd);
    }
    return fdopen(fd, "w");
}

void Logcat::RotateLogs() {
    // Can't rotate logs if we're not outputting to a file
    if (!output_file_name_) return;

    fclose(output_file_);
    output_file_ = nullptr;

    if (kCompressLogcat) {
        releaseCompBlocks(output_file_name_);
    }

    // Compute the maximum number of digits needed to count up to
    // maxRotatedLogs in decimal.  eg:
    // maxRotatedLogs == 30
    //   -> log10(30) == 1.477
    //   -> maxRotationCountDigits == 2
    int max_rotation_count_digits =
            max_rotated_logs_ > 0 ? (int)(floor(log10(max_rotated_logs_) + 1)) : 0;

    for (int i = max_rotated_logs_; i > 0; i--) {
        std::string file1 =
                StringPrintf("%s.%.*d", output_file_name_, max_rotation_count_digits, i);

        std::string file0;
        if (!(i - 1)) {
            file0 = output_file_name_;
        } else {
            file0 = StringPrintf("%s.%.*d", output_file_name_, max_rotation_count_digits, i - 1);
        }

        if (!file0.length() || !file1.length()) {
            perror("while rotating log files");
            break;
        }

        if (rename(file0.c_str(), file1.c_str()) == -1 && errno != ENOENT) {
            error(0, errno, "rename('%s', '%s') failed while rotating log files", file0.c_str(),
                  file1.c_str());
        }
    }

    output_file_ = OpenLogFile(output_file_name_);
    out_byte_count_ = 0;
}

void Logcat::ProcessBuffer(struct log_msg* buf) {
    AndroidLogEntry entry;
    char binaryMsgBuf[1024] __attribute__((__uninitialized__));

    bool is_binary =
            buf->id() == LOG_ID_EVENTS || buf->id() == LOG_ID_STATS || buf->id() == LOG_ID_SECURITY;
    int err;
    if (is_binary) {
        if (!event_tag_map_ && !has_opened_event_tag_map_) {
            event_tag_map_.reset(android_openEventTagMap(nullptr));
            has_opened_event_tag_map_ = true;
        }
        // This causes entry to point to binaryMsgBuf!
        err = android_log_processBinaryLogBuffer(&buf->entry, &entry, event_tag_map_.get(),
                                                 binaryMsgBuf, sizeof(binaryMsgBuf));

        // printf(">>> pri=%d len=%d msg='%s'\n",
        //    entry.priority, entry.messageLen, entry.message);
    } else {
        err = android_log_processLogBuffer(&buf->entry, &entry);
    }
    if (err < 0 && !debug_) return;

    if (android_log_shouldPrintLine(logformat_.get(), std::string(entry.tag, entry.tagLen).c_str(),
                                    entry.priority)) {
        bool match = !regex_ ||
                     std::regex_search(entry.message, entry.message + entry.messageLen, *regex_);

        print_count_ += match;
        if (match || print_it_anyway_) {
            switch (output_type_) {
                case TEXT: {
                    PrintDividers(buf->id(), print_dividers_);
                    out_byte_count_ +=
                            android_log_printLogLine(logformat_.get(), output_file_, &entry);
                    break;
                }
                case PROTO: {
                    out_byte_count_ += PrintToProto(entry);
                    break;
                }
                case BINARY: {
                    error(EXIT_FAILURE, errno, "Binary output reached ProcessBuffer");
                }
            }
        }
    }

    if (log_rotate_size_kb_ > 0 && (out_byte_count_ / 1024) >= log_rotate_size_kb_) {
        RotateLogs();
    }
}

LogcatPriorityProto Logcat::GetProtoPriority(const AndroidLogEntry& entry) {
    switch (entry.priority) {
        case ANDROID_LOG_UNKNOWN:
            return com::android::logcat::proto::UNKNOWN;
        case ANDROID_LOG_DEFAULT:
            return com::android::logcat::proto::DEFAULT;
        case ANDROID_LOG_VERBOSE:
            return com::android::logcat::proto::VERBOSE;
        case ANDROID_LOG_DEBUG:
            return com::android::logcat::proto::DEBUG;
        case ANDROID_LOG_INFO:
            return com::android::logcat::proto::INFO;
        case ANDROID_LOG_WARN:
            return com::android::logcat::proto::WARN;
        case ANDROID_LOG_ERROR:
            return com::android::logcat::proto::ERROR;
        case ANDROID_LOG_FATAL:
            return com::android::logcat::proto::FATAL;
        case ANDROID_LOG_SILENT:
            return com::android::logcat::proto::SILENT;
    }
    return com::android::logcat::proto::UNKNOWN;
}
uint64_t Logcat::PrintToProto(const AndroidLogEntry& entry) {
    // Convert AndroidLogEntry to LogcatEntryProto
    LogcatEntryProto proto;
    proto.set_time_sec(entry.tv_sec);
    proto.set_time_nsec(entry.tv_nsec);
    proto.set_priority(GetProtoPriority(entry));
    proto.set_uid(entry.uid);
    proto.set_pid(entry.pid);
    proto.set_tid(entry.tid);
    proto.set_tag(entry.tag, entry.tagLen);
    proto.set_message(entry.message, entry.messageLen);
    const std::string name = process_names_.Get(entry.pid);
    if (!name.empty()) {
        proto.set_process_name(name);
    }

    // Serialize
    std::string data;
    proto.SerializeToString(&data);

    uint64_t size = data.length();
    WriteFully(&size, sizeof(size));

    // Write proto
    WriteFully(data.data(), data.length());

    // Return how many bytes we wrote so log file rotation can happen
    return sizeof(size) + sizeof(data.length());
}

void Logcat::PrintDividers(log_id_t log_id, bool print_dividers) {
    if (log_id == last_printed_id_) {
        return;
    }
    if (!printed_start_[log_id] || print_dividers) {
        if (fprintf(output_file_, "--------- %s %s\n",
                    printed_start_[log_id] ? "switch to" : "beginning of",
                    android_log_id_to_name(log_id)) < 0) {
            error(EXIT_FAILURE, errno, "Output error");
        }
    }
    last_printed_id_ = log_id;
    printed_start_[log_id] = true;
}

void Logcat::SetupOutputAndSchedulingPolicy(bool blocking) {
    if (!output_file_name_) return;

    if (blocking) {
        // Lower priority and set to batch scheduling if we are saving
        // the logs into files and taking continuous content.
        if (set_sched_policy(0, SP_BACKGROUND) < 0) {
            fprintf(stderr, "failed to set background scheduling policy\n");
        }

        struct sched_param param = {};
        if (sched_setscheduler((pid_t)0, SCHED_BATCH, &param) < 0) {
            fprintf(stderr, "failed to set to batch scheduler\n");
        }

        if (setpriority(PRIO_PROCESS, 0, ANDROID_PRIORITY_BACKGROUND) < 0) {
            fprintf(stderr, "failed set to priority\n");
        }
    }

    output_file_ = OpenLogFile(output_file_name_);

    struct stat sb;
    if (fstat(fileno(output_file_), &sb) == -1) {
        error(EXIT_FAILURE, errno, "Couldn't stat output file");
    }
    out_byte_count_ = sb.st_size;
}

// clang-format off
static void show_help() {
    printf(R"logcat(
  Usage: logcat [OPTION]... [FILTERSPEC]...

  General options:

  -b BUFFER, --buffer=BUFFER
      Request alternate ring buffer(s). Options are:
          main system radio events crash default all
      Additionally, 'kernel' for userdebug and eng builds, and 'security' for
      Device Owner installations.
      Multiple -b parameters or comma separated list of buffers are
      allowed. Buffers are interleaved.
      Default is "main,system,crash,kernel".
  -c, --clear
      Clear (flush) the entire log and exit. With -f, clear the specified file
      and its related rotated log files instead. With -L, clear pstore instead.
  -d            Dump the log and then exit (don't block).
  -L, --last    Dump logs from prior to last reboot from pstore.
  --pid=PID     Only print logs from the given pid.
  --wrap
      Sleep for 2 hours or until buffer about to wrap (whichever comes first).
      Improves efficiency of polling by providing an about-to-wrap wakeup.

  Formatting:

  -v, --format=FORMAT         Sets log print format. See FORMAT below.
  -D, --dividers              Print dividers between each log buffer.
  -B, --binary                Output the log in binary.
      --proto                 Output the log in protobuffer.

  Output files:

  -f, --file=FILE             Log to FILE instead of stdout.
  -r, --rotate-kbytes=N       Rotate log every N KiB. Requires -f.
  -n, --rotate-count=N        Sets max number of rotated logs, default 4.
  --id=<id>
      Clears the associated files if the signature <id> for logging to file
      changes.

  Logd control:

  These options send a control message to the logd daemon on device, print its
  return message if applicable, then exit. They are incompatible with -L
  because these attributes do not apply to pstore.

  -g, --buffer-size
      Get size of the ring buffers within logd.
  -G, --buffer-size=SIZE
      Set size of a ring buffer in logd. May suffix with K or M.
      This can individually control each buffer's size with -b.
  -p, --prune
      Get prune rules. Each rule is specified as UID, UID/PID or /PID. A
      '~' prefix indicates that elements matching the rule should be pruned
      with higher priority otherwise they're pruned with lower priority. All
      other pruning activity is oldest first. Special case ~! represents an
      automatic pruning for the noisiest UID as determined by the current
      statistics. Special case ~1000/! represents pruning of the worst PID
      within AID_SYSTEM when AID_SYSTEM is the noisiest UID.
  -P, --prune='LIST ...'
      Set prune rules, using same format as listed above. Must be quoted.
  -S, --statistics
      Output statistics. With --pid provides pid-specific stats.

  Filtering:

  -s                   Set default filter to silent (like filterspec '*:S').
  -e, --regex=EXPR     Only print lines matching ECMAScript regex.
  -m, --max-count=N    Exit after printing <count> lines.
  --print              With --regex and --max-count, prints all messages
                       even if they do not match the regex, but exits after
                       printing max-count matching lines.
  -t N                 Print most recent <count> lines (implies -d).
  -T N                 Print most recent <count> lines (does not imply -d).
  -t TIME              Print lines since specified time (implies -d).
  -T TIME              Print lines since specified time (not imply -d).
                       Time format is 'MM-DD hh:mm:ss.mmm...',
                       'YYYY-MM-DD hh:mm:ss.mmm...', or 'sssss.mmm...'.
  --uid=UIDS
      Only display log messages from UIDs in the comma-separated list UIDS.
      UIDs must be numeric because no name lookup is performed.
      Note that only root/log/system users can view logs from other users.

  FILTERSPEC:

  Filter specifications are a series of

    <tag>[:priority]

  where <tag> is a log component tag (or * for all) and priority is:

    V    Verbose (default for <tag>)
    D    Debug (default for '*')
    I    Info
    W    Warn
    E    Error
    F    Fatal
    S    Silent (suppress all output)

  '*' by itself means '*:D' and <tag> by itself means <tag>:V.
  If no '*' filterspec or -s on command line, all filter defaults to '*:V'.
  '*:S <tag>' prints only <tag>, '<tag>:S' suppresses all <tag> log messages.

  If not specified on the command line, FILTERSPEC is $ANDROID_LOG_TAGS.

  FORMAT:

  Formats are a comma-separated sequence of verbs and adverbs.

  Single format verbs:

    brief      Show priority, tag, and PID of the process issuing the message.
    long       Show all metadata fields and separate messages with blank lines.
    process    Show PID only.
    raw        Show the raw log message with no other metadata fields.
    tag        Show the priority and tag only.
    thread     Show priority, PID, and TID of the thread issuing the message.
    threadtime Show the date, invocation time, priority, tag, PID, and TID of
               the thread issuing the message. (This is the default.)
    time       Show the date, invocation time, priority, tag, and PID of the
               process issuing the message.

  Adverb modifiers can be used in combination:

    color       Show each priority with a different color.
    descriptive Show event descriptions from event-log-tags database.
    epoch       Show time as seconds since 1970-01-01 (Unix epoch).
    monotonic   Show time as CPU seconds since boot.
    printable   Ensure that any binary logging content is escaped.
    uid         Show UID or Android ID of logged process (if permitted).
    usec        Show time with microsecond precision.
    UTC         Show time as UTC.
    year        Add the year to the displayed time.
    zone        Add the local timezone to the displayed time.
    \"<ZONE>\"  Print using this named timezone (experimental).

  If not specified with -v on command line, FORMAT is $ANDROID_PRINTF_LOG or
  defaults to "threadtime".
)logcat");
}
// clang-format on

int Logcat::SetLogFormat(const char* format_string) {
    AndroidLogPrintFormat format = android_log_formatFromString(format_string);

    // invalid string?
    if (format == FORMAT_OFF) return -1;

    return android_log_setPrintFormat(logformat_.get(), format);
}

static std::pair<unsigned long, const char*> format_of_size(unsigned long value) {
    static const char multipliers[][3] = {{""}, {"Ki"}, {"Mi"}, {"Gi"}};
    size_t i;
    for (i = 0;
         (i < sizeof(multipliers) / sizeof(multipliers[0])) && (value >= 1024);
         value /= 1024, ++i)
        ;
    return std::make_pair(value, multipliers[i]);
}

static char* parseTime(log_time& t, const char* cp) {
    char* ep = t.strptime(cp, "%m-%d %H:%M:%S.%q");
    if (ep) return ep;
    ep = t.strptime(cp, "%Y-%m-%d %H:%M:%S.%q");
    if (ep) return ep;
    return t.strptime(cp, "%s.%q");
}

// Find last logged line in <outputFileName>, or <outputFileName>.1
static log_time lastLogTime(const char* outputFileName) {
    log_time retval(log_time::EPOCH);
    if (!outputFileName) return retval;

    std::string directory;
    const char* file = strrchr(outputFileName, '/');
    if (!file) {
        directory = ".";
        file = outputFileName;
    } else {
        directory = std::string(outputFileName, file - outputFileName);
        ++file;
    }

    std::unique_ptr<DIR, int (*)(DIR*)> dir(opendir(directory.c_str()),
                                            closedir);
    if (!dir.get()) return retval;

    log_time now(CLOCK_REALTIME);

    size_t len = strlen(file);
    log_time modulo(0, NS_PER_SEC);
    struct dirent* dp;

    while (!!(dp = readdir(dir.get()))) {
        if ((dp->d_type != DT_REG) || !!strncmp(dp->d_name, file, len) ||
            (dp->d_name[len] && ((dp->d_name[len] != '.') ||
                                 (strtoll(dp->d_name + 1, nullptr, 10) != 1)))) {
            continue;
        }

        std::string file_name = directory;
        file_name += "/";
        file_name += dp->d_name;
        std::string file;
        if (!android::base::ReadFileToString(file_name, &file)) continue;

        bool found = false;
        for (const auto& line : android::base::Split(file, "\n")) {
            log_time t(log_time::EPOCH);
            char* ep = parseTime(t, line.c_str());
            if (!ep || (*ep != ' ')) continue;
            // determine the time precision of the logs (eg: msec or usec)
            for (unsigned long mod = 1UL; mod < modulo.tv_nsec; mod *= 10) {
                if (t.tv_nsec % (mod * 10)) {
                    modulo.tv_nsec = mod;
                    break;
                }
            }
            // We filter any times later than current as we may not have the
            // year stored with each log entry. Also, since it is possible for
            // entries to be recorded out of order (very rare) we select the
            // maximum we find just in case.
            if ((t < now) && (t > retval)) {
                retval = t;
                found = true;
            }
        }
        // We count on the basename file to be the definitive end, so stop here.
        if (!dp->d_name[len] && found) break;
    }
    if (retval == log_time::EPOCH) return retval;
    // tail_time prints matching or higher, round up by the modulo to prevent
    // a replay of the last entry we have just checked.
    retval += modulo;
    return retval;
}

void ReportErrorName(const std::string& name, bool allow_security,
                     std::vector<std::string>* errors) {
    if (allow_security || name != "security") {
        errors->emplace_back(name);
    }
}

int Logcat::Run(int argc, char** argv) {
    bool hasSetLogFormat = false;
    bool clearLog = false;
    bool security_buffer_selected =
            false;  // Do not report errors on the security buffer unless it is explicitly named.
    bool getLogSize = false;
    bool getPruneList = false;
    bool printStatistics = false;
    unsigned long setLogSize = 0;
    const char* setPruneList = nullptr;
    const char* setId = nullptr;
    int mode = 0;
    std::string forceFilters;
    size_t tail_lines = 0;
    log_time tail_time(log_time::EPOCH);
    size_t pid = 0;
    bool got_t = false;
    unsigned id_mask = 0;
    std::set<uid_t> uids;

    if (argc == 2 && !strcmp(argv[1], "--help")) {
        show_help();
        return EXIT_SUCCESS;
    }

    // meant to catch comma-delimited values, but cast a wider
    // net for stability dealing with possible mistaken inputs.
    static const char delimiters[] = ",:; \t\n\r\f";

    optind = 0;
    while (true) {
        int option_index = 0;
        // list of long-argument only strings for later comparison
        static const char pid_str[] = "pid";
        static const char debug_str[] = "debug";
        static const char id_str[] = "id";
        static const char wrap_str[] = "wrap";
        static const char print_str[] = "print";
        static const char uid_str[] = "uid";
        static const char proto_str[] = "proto";
        // clang-format off
        static const struct option long_options[] = {
          { "binary",        no_argument,       nullptr, 'B' },
          { "buffer",        required_argument, nullptr, 'b' },
          { "buffer-size",   optional_argument, nullptr, 'g' },
          { "clear",         no_argument,       nullptr, 'c' },
          { debug_str,       no_argument,       nullptr, 0 },
          { "dividers",      no_argument,       nullptr, 'D' },
          { "file",          required_argument, nullptr, 'f' },
          { "format",        required_argument, nullptr, 'v' },
          // hidden and undocumented reserved alias for --regex
          { "grep",          required_argument, nullptr, 'e' },
          // hidden and undocumented reserved alias for --max-count
          { "head",          required_argument, nullptr, 'm' },
          { "help",          no_argument,       nullptr, 'h' },
          { id_str,          required_argument, nullptr, 0 },
          { "last",          no_argument,       nullptr, 'L' },
          { "max-count",     required_argument, nullptr, 'm' },
          { pid_str,         required_argument, nullptr, 0 },
          { print_str,       no_argument,       nullptr, 0 },
          { "prune",         optional_argument, nullptr, 'p' },
          { proto_str,         no_argument,       nullptr, 0 },
          { "regex",         required_argument, nullptr, 'e' },
          { "rotate-count",  required_argument, nullptr, 'n' },
          { "rotate-kbytes", required_argument, nullptr, 'r' },
          { "statistics",    no_argument,       nullptr, 'S' },
          // hidden and undocumented reserved alias for -t
          { "tail",          required_argument, nullptr, 't' },
          { uid_str,         required_argument, nullptr, 0 },
          // support, but ignore and do not document, the optional argument
          { wrap_str,        optional_argument, nullptr, 0 },
          { nullptr,         0,                 nullptr, 0 }
        };
        // clang-format on

        int c = getopt_long(argc, argv, ":cdDhLt:T:gG:sQf:r:n:v:b:BSpP:m:e:", long_options,
                            &option_index);
        if (c == -1) break;

        switch (c) {
            case 0:
                // only long options
                if (long_options[option_index].name == pid_str) {
                    if (pid != 0) {
                        error(EXIT_FAILURE, 0, "Only one --pid argument can be provided.");
                    }

                    if (!ParseUint(optarg, &pid) || pid < 1) {
                        error(EXIT_FAILURE, 0, "pid '%s' out of range.", optarg);
                    }
                    break;
                }
                if (long_options[option_index].name == wrap_str) {
                    mode |= ANDROID_LOG_WRAP | ANDROID_LOG_NONBLOCK;
                    // ToDo: implement API that supports setting a wrap timeout
                    size_t timeout = ANDROID_LOG_WRAP_DEFAULT_TIMEOUT;
                    if (optarg && (!ParseUint(optarg, &timeout) || timeout < 1)) {
                        error(EXIT_FAILURE, 0, "wrap timeout '%s' out of range.", optarg);
                    }
                    if (timeout != ANDROID_LOG_WRAP_DEFAULT_TIMEOUT) {
                        fprintf(stderr, "WARNING: wrap timeout %zus, not default %us\n", timeout,
                                ANDROID_LOG_WRAP_DEFAULT_TIMEOUT);
                    }
                    break;
                }
                if (long_options[option_index].name == print_str) {
                    print_it_anyway_ = true;
                    break;
                }
                if (long_options[option_index].name == debug_str) {
                    debug_ = true;
                    break;
                }
                if (long_options[option_index].name == id_str) {
                    setId = (optarg && optarg[0]) ? optarg : nullptr;
                }
                if (long_options[option_index].name == uid_str) {
                    auto uid_strings = Split(optarg, delimiters);
                    for (const auto& uid_string : uid_strings) {
                        uid_t uid;
                        if (!ParseUint(uid_string, &uid)) {
                            error(EXIT_FAILURE, 0, "Unable to parse UID '%s'", uid_string.c_str());
                        }
                        uids.emplace(uid);
                    }
                    break;
                }
                if (long_options[option_index].name == proto_str) {
                    output_type_ = PROTO;
                    break;
                }
                break;

            case 's':
                // default to all silent
                android_log_addFilterRule(logformat_.get(), "*:s");
                break;

            case 'c':
                clearLog = true;
                break;

            case 'L':
                mode |= ANDROID_LOG_PSTORE | ANDROID_LOG_NONBLOCK;
                break;

            case 'd':
                mode |= ANDROID_LOG_NONBLOCK;
                break;

            case 't':
                got_t = true;
                mode |= ANDROID_LOG_NONBLOCK;
                FALLTHROUGH_INTENDED;
            case 'T':
                if (strspn(optarg, "0123456789") != strlen(optarg)) {
                    char* cp = parseTime(tail_time, optarg);
                    if (!cp) {
                        error(EXIT_FAILURE, 0, "-%c '%s' not in time format.", c, optarg);
                    }
                    if (*cp) {
                        char ch = *cp;
                        *cp = '\0';
                        fprintf(stderr, "WARNING: -%c '%s' '%c%s' time truncated\n", c, optarg, ch,
                                cp + 1);
                        *cp = ch;
                    }
                } else {
                    if (!ParseUint(optarg, &tail_lines) || tail_lines < 1) {
                        fprintf(stderr, "WARNING: -%c %s invalid, setting to 1\n", c, optarg);
                        tail_lines = 1;
                    }
                }
                break;

            case 'D':
                print_dividers_ = true;
                break;

            case 'e':
                regex_.reset(new std::regex(optarg));
                break;

            case 'm': {
                if (!ParseUint(optarg, &max_count_) || max_count_ < 1) {
                    error(EXIT_FAILURE, 0, "-%c '%s' isn't an integer greater than zero.", c,
                          optarg);
                }
            } break;

            case 'g':
                if (!optarg) {
                    getLogSize = true;
                    break;
                }
                FALLTHROUGH_INTENDED;

            case 'G': {
                if (!ParseByteCount(optarg, &setLogSize) || setLogSize < 1) {
                    error(EXIT_FAILURE, 0, "-G must be specified as <num><multiplier>.");
                }
            } break;

            case 'p':
                if (!optarg) {
                    getPruneList = true;
                    break;
                }
                FALLTHROUGH_INTENDED;

            case 'P':
                setPruneList = optarg;
                break;

            case 'b':
                for (const auto& buffer : Split(optarg, delimiters)) {
                    if (buffer == "default") {
                        id_mask |= (1 << LOG_ID_MAIN) | (1 << LOG_ID_SYSTEM) | (1 << LOG_ID_CRASH);
                    } else if (buffer == "all") {
                        id_mask = -1;
                    } else {
                        log_id_t log_id = android_name_to_log_id(buffer.c_str());
                        if (log_id >= LOG_ID_MAX) {
                            error(EXIT_FAILURE, 0, "Unknown -b buffer '%s'.", buffer.c_str());
                        }
                        if (log_id == LOG_ID_SECURITY) {
                            security_buffer_selected = true;
                        }
                        id_mask |= (1 << log_id);
                    }
                }
                break;

            case 'B':
                output_type_ = BINARY;
                break;

            case 'f':
                if ((tail_time == log_time::EPOCH) && !tail_lines) {
                    tail_time = lastLogTime(optarg);
                }
                // redirect output to a file
                output_file_name_ = optarg;
                break;

            case 'r':
                if (!ParseUint(optarg, &log_rotate_size_kb_) || log_rotate_size_kb_ < 1) {
                    error(EXIT_FAILURE, 0, "Invalid -r '%s'.", optarg);
                }
                break;

            case 'n':
                if (!ParseUint(optarg, &max_rotated_logs_) || max_rotated_logs_ < 1) {
                    error(EXIT_FAILURE, 0, "Invalid -n '%s'.", optarg);
                }
                break;

            case 'v':
                for (const auto& arg : Split(optarg, delimiters)) {
                    int err = SetLogFormat(arg.c_str());
                    if (err < 0) {
                        error(EXIT_FAILURE, 0, "Invalid -v '%s'.", arg.c_str());
                    }
                    if (err) hasSetLogFormat = true;
                }
                break;

            case 'S':
                printStatistics = true;
                break;

            case ':':
                error(EXIT_FAILURE, 0, "Option '%s' needs an argument.", argv[optind - 1]);
                break;

            case 'h':
                show_help();
                return EXIT_SUCCESS;

            case '?':
                error(EXIT_FAILURE, 0, "Unknown option '%s'.", argv[optind]);
                break;

            default:
                error(EXIT_FAILURE, 0, "Unknown getopt_long() result '%c'.", c);
        }
    }

    if (max_count_ && got_t) {
        error(EXIT_FAILURE, 0, "Cannot use -m (--max-count) and -t together.");
    }
    if (print_it_anyway_ && (!regex_ || !max_count_)) {
        // One day it would be nice if --print -v color and --regex <expr>
        // could play with each other and show regex highlighted content.
        fprintf(stderr,
                "WARNING: "
                "--print ignored, to be used in combination with\n"
                "         "
                "--regex <expr> and --max-count <N>\n");
        print_it_anyway_ = false;
    }

    // If no buffers are specified, default to using these buffers.
    if (id_mask == 0) {
        id_mask = (1 << LOG_ID_MAIN) | (1 << LOG_ID_SYSTEM) | (1 << LOG_ID_CRASH) |
                  (1 << LOG_ID_KERNEL);
    }

    if (log_rotate_size_kb_ != 0 && !output_file_name_) {
        error(EXIT_FAILURE, 0, "-r requires -f as well.");
    }

    if (setId != 0) {
        if (!output_file_name_) {
            error(EXIT_FAILURE, 0, "--id='%s' requires -f as well.", setId);
        }

        std::string file_name = StringPrintf("%s.id", output_file_name_);
        std::string file;
        bool file_ok = android::base::ReadFileToString(file_name, &file);
        android::base::WriteStringToFile(setId, file_name, S_IRUSR | S_IWUSR,
                                         getuid(), getgid());
        if (!file_ok || !file.compare(setId)) setId = nullptr;
    }

    if (!hasSetLogFormat) {
        const char* logFormat = getenv("ANDROID_PRINTF_LOG");

        if (!!logFormat) {
            for (const auto& arg : Split(logFormat, delimiters)) {
                int err = SetLogFormat(arg.c_str());
                // environment should not cause crash of logcat
                if (err < 0) {
                    fprintf(stderr, "invalid format in ANDROID_PRINTF_LOG '%s'\n", arg.c_str());
                }
                if (err > 0) hasSetLogFormat = true;
            }
        }
        if (!hasSetLogFormat) {
            SetLogFormat("threadtime");
        }
    }

    if (forceFilters.size()) {
        int err = android_log_addFilterString(logformat_.get(), forceFilters.c_str());
        if (err < 0) {
            error(EXIT_FAILURE, 0, "Invalid filter expression '%s' in logcat args.",
                  forceFilters.c_str());
        }
    } else if (argc == optind) {
        // Add from environment variable
        const char* env_tags_orig = getenv("ANDROID_LOG_TAGS");

        if (!!env_tags_orig) {
            int err = android_log_addFilterString(logformat_.get(), env_tags_orig);

            if (err < 0) {
                error(EXIT_FAILURE, 0, "Invalid filter expression '%s' in ANDROID_LOG_TAGS.",
                      env_tags_orig);
            }
        }
    } else {
        // Add from commandline
        for (int i = optind ; i < argc ; i++) {
            int err = android_log_addFilterString(logformat_.get(), argv[i]);
            if (err < 0) {
                error(EXIT_FAILURE, 0, "Invalid filter expression '%s'.", argv[i]);
            }
        }
    }

    if (mode & ANDROID_LOG_PSTORE) {
        if (setLogSize || getLogSize || printStatistics || getPruneList || setPruneList) {
            error(EXIT_FAILURE, 0, "-L is incompatible with -g/-G, -S, and -p/-P.");
        }
        if (clearLog) {
            if (output_file_name_) {
                error(EXIT_FAILURE, 0, "-c is ambiguous with both -f and -L specified.");
            }
            unlink("/sys/fs/pstore/pmsg-ramoops-0");
            return EXIT_SUCCESS;
        }
    }

    if (output_file_name_) {
        if (setLogSize || getLogSize || printStatistics || getPruneList || setPruneList) {
            error(EXIT_FAILURE, 0, "-f is incompatible with -g/-G, -S, and -p/-P.");
        }

        if (clearLog || setId) {
            int max_rotation_count_digits =
                    max_rotated_logs_ > 0 ? (int)(floor(log10(max_rotated_logs_) + 1)) : 0;

            for (int i = max_rotated_logs_; i >= 0; --i) {
                std::string file;

                if (!i) {
                    file = output_file_name_;
                } else {
                    file = StringPrintf("%s.%.*d", output_file_name_, max_rotation_count_digits, i);
                }

                int err = unlink(file.c_str());

                if (err < 0 && errno != ENOENT) {
                    fprintf(stderr, "failed to delete log file '%s': %s\n", file.c_str(),
                            strerror(errno));
                }
            }
        }

        if (clearLog) {
            return EXIT_SUCCESS;
        }
    }

    std::unique_ptr<logger_list, decltype(&android_logger_list_free)> logger_list{
            nullptr, &android_logger_list_free};
    if (tail_time != log_time::EPOCH) {
        logger_list.reset(android_logger_list_alloc_time(mode, tail_time, pid));
    } else {
        logger_list.reset(android_logger_list_alloc(mode, tail_lines, pid));
    }
    // We have three orthogonal actions below to clear, set log size and
    // get log size. All sharing the same iteration loop.
    std::vector<std::string> open_device_failures;
    std::vector<std::string> clear_failures;
    std::vector<std::string> set_size_failures;
    std::vector<std::string> get_size_failures;

    for (int i = LOG_ID_MIN; i < LOG_ID_MAX; ++i) {
        if (!(id_mask & (1 << i))) continue;
        const char* buffer_name = android_log_id_to_name(static_cast<log_id_t>(i));

        auto logger = android_logger_open(logger_list.get(), static_cast<log_id_t>(i));
        if (logger == nullptr) {
            ReportErrorName(buffer_name, security_buffer_selected, &open_device_failures);
            continue;
        }

        if (clearLog) {
            if (android_logger_clear(logger)) {
                ReportErrorName(buffer_name, security_buffer_selected, &clear_failures);
            }
        }

        if (setLogSize) {
            if (android_logger_set_log_size(logger, setLogSize)) {
                ReportErrorName(buffer_name, security_buffer_selected, &set_size_failures);
            }
        }

        if (getLogSize) {
            long size = android_logger_get_log_size(logger);
            long readable = android_logger_get_log_readable_size(logger);
            long consumed = android_logger_get_log_consumed_size(logger);

            if (size < 0 || readable < 0) {
                ReportErrorName(buffer_name, security_buffer_selected, &get_size_failures);
            } else {
                auto size_format = format_of_size(size);
                auto readable_format = format_of_size(readable);
                auto consumed_format = format_of_size(consumed);
                std::string str = android::base::StringPrintf(
                        "%s: ring buffer is %lu %sB (%lu %sB consumed, %lu %sB readable),"
                        " max entry is %d B, max payload is %d B\n",
                        buffer_name, size_format.first, size_format.second, consumed_format.first,
                        consumed_format.second, readable_format.first, readable_format.second,
                        (int)LOGGER_ENTRY_MAX_LEN, (int)LOGGER_ENTRY_MAX_PAYLOAD);
                WriteFully(str.data(), str.length());
            }
        }
    }

    // report any errors in the above loop and exit
    if (!open_device_failures.empty()) {
        error(EXIT_FAILURE, 0, "Unable to open log device%s '%s'.",
              open_device_failures.size() > 1 ? "s" : "", Join(open_device_failures, ",").c_str());
    }
    if (!clear_failures.empty()) {
        error(EXIT_FAILURE, 0, "failed to clear the '%s' log%s.", Join(clear_failures, ",").c_str(),
              clear_failures.size() > 1 ? "s" : "");
    }
    if (!set_size_failures.empty()) {
        error(EXIT_FAILURE, 0, "failed to set the '%s' log size%s.",
              Join(set_size_failures, ",").c_str(), set_size_failures.size() > 1 ? "s" : "");
    }
    if (!get_size_failures.empty()) {
        error(EXIT_FAILURE, 0, "failed to get the readable '%s' log size%s.",
              Join(get_size_failures, ",").c_str(), get_size_failures.size() > 1 ? "s" : "");
    }

    if (setPruneList) {
        size_t len = strlen(setPruneList);
        if (android_logger_set_prune_list(logger_list.get(), setPruneList, len)) {
            error(EXIT_FAILURE, 0, "Failed to set the prune list to '%s'.", setPruneList);
        }
        return EXIT_SUCCESS;
    }

    if (printStatistics || getPruneList) {
        std::string buf(8192, '\0');
        size_t ret_length = 0;
        int retry = 32;

        for (; retry >= 0; --retry) {
            if (getPruneList) {
                android_logger_get_prune_list(logger_list.get(), buf.data(), buf.size());
            } else {
                android_logger_get_statistics(logger_list.get(), buf.data(), buf.size());
            }

            ret_length = atol(buf.c_str());
            if (ret_length < 3) {
                error(EXIT_FAILURE, 0, "Failed to read data.");
            }

            if (ret_length < buf.size()) {
                break;
            }

            buf.resize(ret_length + 1);
        }

        if (retry < 0) {
            error(EXIT_FAILURE, 0, "Failed to read data.");
        }

        buf.resize(ret_length);
        if (buf.back() == '\f') {
            buf.pop_back();
        }

        // Remove the byte count prefix
        const char* cp = buf.c_str();
        while (isdigit(*cp)) ++cp;
        if (*cp == '\n') ++cp;

        WriteFully(cp, strlen(cp));
        return EXIT_SUCCESS;
    }

    if (getLogSize || setLogSize || clearLog) return EXIT_SUCCESS;

    bool blocking = !(mode & ANDROID_LOG_NONBLOCK);
    SetupOutputAndSchedulingPolicy(blocking);

    // Purge as much memory as possible before going into the log reading loop.
    // Do this before checking if logd is ready just in case logd isn't
    // ready and this call can be done without penalizing start up.
    mallopt(M_PURGE_ALL, 0);

    if (!WaitForProperty("logd.ready", "true", std::chrono::seconds(1))) {
        error(EXIT_FAILURE, 0, "Failed to wait for logd.ready to become true. logd not running?");
    }

    while (!max_count_ || print_count_ < max_count_) {
        struct log_msg log_msg;
        int ret = android_logger_list_read(logger_list.get(), &log_msg);
        if (!ret) {
            error(EXIT_FAILURE, 0, R"init(Unexpected EOF!

This means that either the device shut down, logd crashed, or this instance of logcat was unable to read log
messages as quickly as they were being produced.

If you have enabled significant logging, look into using the -G option to increase log buffer sizes.)init");
        }

        if (ret < 0) {
            if (ret == -EAGAIN || ret == -EWOULDBLOCK || ret == -ETIMEDOUT) {
                // For non-blocking mode, a socket with a 2s timeout is used to read logs.
                // Either recv returned -EAGAIN or -EWOULDBLOCK (see man recv)
                // or connect returned -EAGAIN or -ETIMEOUT.
                // In either case, the caller should call logcat again at a later time.
                break;
            }
            if (ret == -EIO) {
                error(EXIT_FAILURE, 0, "Unexpected EOF!");
            }
            if (ret == -EINVAL) {
                error(EXIT_FAILURE, 0, "Unexpected length.");
            }
            error(EXIT_FAILURE, errno, "Logcat read failure");
        }

        if (log_msg.id() > LOG_ID_MAX) {
            error(EXIT_FAILURE, 0, "Unexpected log id (%d) over LOG_ID_MAX (%d).", log_msg.id(),
                  LOG_ID_MAX);
        }

        if (!uids.empty() && uids.count(log_msg.entry.uid) == 0) {
            continue;
        }

        switch (output_type_) {
            case BINARY:
                WriteFully(&log_msg, log_msg.len());
                break;
            case TEXT:
            case PROTO:
                ProcessBuffer(&log_msg);
                break;
        }
        if (blocking && output_file_ == stdout) fflush(stdout);
    }
    return EXIT_SUCCESS;
}

int main(int argc, char** argv) {
    Logcat logcat;
    return logcat.Run(argc, argv);
}
