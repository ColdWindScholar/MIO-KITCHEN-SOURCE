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

#include "bootio_collector.h"

#include <android-base/file.h>
#include <android-base/logging.h>
#include <dirent.h>
#include <inttypes.h>
#include <log/log.h>

#include <map>
#include <memory>
#include <string>
#include <unordered_map>

#include "protos.pb.h"
#include "time.h"

namespace android {

#define CPU_STAT_FILE "/proc/stat"
#define SAMPLES_FILE "/samples"
#define PID_STAT_FILE "/proc/%d/stat"
#define PID_CMDLINE_FILE "/proc/%d/cmdline"
#define PID_IO_FILE "/proc/%d/io"
#define PROC_DIR "/proc"

static const int MAX_LINE = 256;

#define die(...) { LOG(ERROR) << (__VA_ARGS__); exit(EXIT_FAILURE); }

void PopulateCpu(CpuData& cpu) {
    long unsigned utime, ntime, stime, itime;
    long unsigned iowtime, irqtime, sirqtime;
    FILE *file;
    file = fopen(CPU_STAT_FILE, "r");
    if (!file) die("Could not open /proc/stat.\n");
    fscanf(file, "cpu  %lu %lu %lu %lu %lu %lu %lu", &utime, &ntime, &stime,
           &itime, &iowtime, &irqtime, &sirqtime);
    fclose(file);
    cpu.set_utime(utime);
    cpu.set_ntime(ntime);
    cpu.set_stime(stime);
    cpu.set_itime(itime);
    cpu.set_iowtime(iowtime);
    cpu.set_irqtime(irqtime);
    cpu.set_sirqtime(sirqtime);
}

void ClearPreviousResults(std::string path) {
    std::string err;
    if (!android::base::RemoveFileIfExists(path, &err)) {
        LOG(ERROR) << "failed to remove the file " << path << " " << err;
        return;
    }
}

int ReadIo(char *filename, AppSample *sample) {
    FILE *file;
    char line[MAX_LINE];
    unsigned int rchar = 0;
    unsigned int wchar = 0;
    unsigned int syscr = 0;
    unsigned int syscw = 0;
    unsigned int readbytes = 0;
    unsigned int writebytes = 0;

    file = fopen(filename, "r");
    if (!file) return 1;
    while (fgets(line, MAX_LINE, file)) {
        sscanf(line, "rchar: %u", &rchar);
        sscanf(line, "wchar: %u", &wchar);
        sscanf(line, "syscr: %u", &syscr);
        sscanf(line, "syscw: %u", &syscw);
        sscanf(line, "read_bytes: %u", &readbytes);
        sscanf(line, "write_bytes: %u", &writebytes);
    }
    fclose(file);
    sample->set_rchar(rchar);
    sample->set_wchar(wchar);
    sample->set_syscr(syscr);
    sample->set_syscw(syscw);
    sample->set_readbytes(readbytes);
    sample->set_writebytes(writebytes);
    return 0;
}

int ReadStatForName(char *filename, AppData *app) {
    FILE *file;
    char buf[MAX_LINE], *open_paren, *close_paren;

    file = fopen(filename, "r");
    if (!file) return 1;
    fgets(buf, MAX_LINE, file);
    fclose(file);

    /* Split at first '(' and last ')' to get process name. */
    open_paren = strchr(buf, '(');
    close_paren = strrchr(buf, ')');
    if (!open_paren || !close_paren) return 1;

    *open_paren = *close_paren = '\0';
    if (!app->has_tname()) {
        app->set_tname(open_paren + 1, close_paren - open_paren - 1);
    }
    return 0;
}

int ReadStat(char *filename, AppSample *sample) {
    FILE *file;
    char buf[MAX_LINE], *open_paren, *close_paren;

    file = fopen(filename, "r");
    if (!file) return 1;
    fgets(buf, MAX_LINE, file);
    fclose(file);

    /* Split at first '(' and last ')' to get process name. */
    open_paren = strchr(buf, '(');
    close_paren = strrchr(buf, ')');
    if (!open_paren || !close_paren) return 1;

    uint64_t utime;
    uint64_t stime;
    uint64_t rss;

    /* Scan rest of string. */
    sscanf(close_paren + 1,
           " %*c " "%*d %*d %*d %*d %*d %*d %*d %*d %*d %*d "
                   "%" PRIu64 /*SCNu64*/
                   "%" PRIu64 /*SCNu64*/ "%*d %*d %*d %*d %*d %*d %*d %*d "
                   "%" PRIu64 /*SCNu64*/ "%*d %*d %*d %*d %*d %*d %*d %*d %*d %*d %*d %*d %*d %*d %*d",
           &utime,
           &stime,
           &rss);
    sample->set_utime(utime);
    sample->set_stime(stime);
    sample->set_rss(rss);

    return 0;
}

int ReadCmdline(char *filename, AppData *app) {
    FILE *file;
    char line[MAX_LINE];

    line[0] = '\0';
    file = fopen(filename, "r");
    if (!file) return 1;
    fgets(line, MAX_LINE, file);
    fclose(file);
    if (strlen(line) > 0) {
        app->set_name(line, strlen(line));
    } else {
        app->set_name("N/A");
    }
    return 0;
};

void ReadProcData(std::unordered_map<int, AppData*>& pidDataMap, DataContainer& dataContainer,
                  time_t currentTimeUtc, time_t currentUptime) {
    DIR *procDir;
    struct dirent *pidDir;
    pid_t pid;
    char filename[64];
    procDir = opendir(PROC_DIR);
    if (!procDir) die("Could not open /proc.\n");
    while ((pidDir = readdir(procDir))) {
        if (!isdigit(pidDir->d_name[0])) {
            continue;
        }
        pid = atoi(pidDir->d_name);
        AppData *data;

        // TODO: in theory same pid can be shared for multiple processes,
        // might need add extra check.
        if (pidDataMap.count(pid) == 0) {
            data = dataContainer.add_app();
            data->set_pid(pid);
            sprintf(filename, PID_STAT_FILE, pid);
            ReadStatForName(filename, data);
            sprintf(filename, PID_CMDLINE_FILE, pid);
            ReadCmdline(filename, data);
            pidDataMap[pid] = data;
        } else {
            data = pidDataMap[pid];
        }
        AppSample *sample = data->add_samples();
        sample->set_timestamp(currentTimeUtc);
        sample->set_uptime(currentUptime);

        sprintf(filename, PID_STAT_FILE, pid);
        ReadStat(filename, sample);

        sprintf(filename, PID_IO_FILE, pid);
        ReadIo(filename, sample);
    }
}

uint64_t SumCpuValues(CpuData& cpu) {
    return cpu.utime() + cpu.ntime() + cpu.stime() + cpu.itime() + cpu.iowtime() +
           cpu.irqtime() + cpu.sirqtime();
}

time_t GetUptime() {
    std::string uptime_str;
    if (!android::base::ReadFileToString("/proc/uptime", &uptime_str)) {
        LOG(ERROR) << "Failed to read /proc/uptime";
        return -1;
    }

    // Cast intentionally rounds down.
    return static_cast<time_t>(strtod(uptime_str.c_str(), NULL));
}

struct Stats {
    int uptime;
    float cpu;
    uint64_t rbytes;
    uint64_t wbytes;
};

void PrintPids(DataContainer& data, std::unordered_map<int, uint64_t>& cpuDataMap) {
    printf("rchar: number of bytes the process read, using any read-like system call "
                   "(from files, pipes, tty...).\n");
    printf("wchar: number of bytes the process wrote using any write-like system call.\n");
    printf("wchar: number of bytes the process wrote using any write-like system call.\n");
    printf("syscr: number of write-like system call invocations that the process performed.\n");
    printf("rbytes: number of bytes the process directly read from disk.\n");
    printf("wbytes: number of bytes the process originally dirtied in the page-cache "
                   "(assuming they will go to disk later).\n\n");

    std::unique_ptr<AppSample> bootZeroSample(new AppSample());
    std::map<int, Stats> statsMap;
    // Init stats map
    Stats emptyStat {0, 0., 0, 0};
    for (auto it = cpuDataMap.begin(); it != cpuDataMap.end(); it++) {
        statsMap[it->first] = emptyStat;
    }
    for (int i = 0; i < data.app_size(); i++) {
        const AppData appData = data.app(i);
        printf("\n-----------------------------------------------------------------------------\n");
        printf("PID:\t%u\n", appData.pid());
        printf("Name:\t%s\n", appData.name().c_str());
        printf("ThName:\t%s\n", appData.tname().c_str());
        printf("%-15s%-13s%-13s%-13s%-13s%-13s%-13s%-13s\n", "Uptime inter.", "rchar", "wchar",
               "syscr", "syscw", "rbytes", "wbytes", "cpu%");
        const AppSample *olderSample = NULL;
        const AppSample *newerSample = NULL;
        bool isFirstSample = true;
        for (int j = 0; j < appData.samples_size(); j++) {
            olderSample = newerSample;
            newerSample = &(appData.samples(j));
            if (olderSample == NULL) {
                olderSample = bootZeroSample.get();
            }
            float cpuLoad = 0.;
            uint64_t cpuDelta;
            if (isFirstSample) {
                cpuDelta = cpuDataMap[newerSample->timestamp()];
            } else {
                cpuDelta = cpuDataMap[newerSample->timestamp()] -
                        cpuDataMap[olderSample->timestamp()];
            }
            if (cpuDelta != 0) {
                cpuLoad = (newerSample->utime() - olderSample->utime() +
                           newerSample->stime() - olderSample->stime()) * 100. / cpuDelta;
            }
            Stats& stats = statsMap[newerSample->timestamp()];
            stats.uptime = newerSample->uptime();
            stats.cpu += cpuLoad;
            stats.rbytes += (newerSample->readbytes() - olderSample->readbytes());
            stats.wbytes += (newerSample->writebytes() - olderSample->writebytes());

#define NUMBER "%-13" PRId64
            printf("%5" PRId64 " - %-5" PRId64 "  " NUMBER NUMBER NUMBER NUMBER NUMBER NUMBER "%-9.2f\n",
#undef NUMBER
                   olderSample->uptime(),
                   newerSample->uptime(),
                   newerSample->rchar() - olderSample->rchar(),
                   newerSample->wchar() - olderSample->wchar(),
                   newerSample->syscr() - olderSample->syscr(),
                   newerSample->syscw() - olderSample->syscw(),
                   newerSample->readbytes() - olderSample->readbytes(),
                   newerSample->writebytes() - olderSample->writebytes(),
                   cpuLoad);
            isFirstSample = false;
        }
        if (!newerSample) {
            LOG(ERROR) << "newerSample is null";
        } else {
            printf("-----------------------------------------------------------------------------"
                   "\n");
#define NUMBER "%-13" PRId64
            printf("%-15s" NUMBER NUMBER NUMBER NUMBER NUMBER NUMBER "\n",
#undef NUMBER
                   "Total", newerSample->rchar(), newerSample->wchar(), newerSample->syscr(),
                   newerSample->syscw(), newerSample->readbytes(), newerSample->writebytes());
        }
    }
    printf("\nAggregations\n%-10s%-13s%-13s%-13s\n",
           "Total",
           "rbytes",
           "wbytes",
           "cpu%");

    for (auto it = statsMap.begin(); it != statsMap.end(); it++) {
        printf("%-10u%-13" PRIu64 "%-13" PRIu64 "%-9.2f\n",
               it->second.uptime,
               it->second.rbytes,
               it->second.wbytes,
               it->second.cpu);
    }
}

}

BootioCollector::BootioCollector(std::string path) {
    DCHECK_EQ('/', path.back());
    path_ = path;
}

void BootioCollector::StartDataCollection(int timeout, int samples) {
    android::ClearPreviousResults(getStoragePath());
    int remaining = samples + 1;
    int delayS = timeout / samples;

    std::unordered_map < int, AppData * > pidDataMap;
    std::unique_ptr <DataContainer> data(new DataContainer());
    while (remaining > 0) {
        time_t currentTimeUtc = time(nullptr);
        time_t currentUptime = android::GetUptime();
        CpuData *cpu = data->add_cpu();
        cpu->set_timestamp(currentTimeUtc);
        cpu->set_uptime(currentUptime);
        android::PopulateCpu(*cpu);
        android::ReadProcData(pidDataMap, *data.get(), currentTimeUtc, currentUptime);
        remaining--;
        if (remaining == 0) {
            continue;
        }
        sleep(delayS);
    }
    std::string file_data;
    if (!data->SerializeToString(&file_data)) {
        LOG(ERROR) << "Failed to serialize";
        return;
    }
    if (!android::base::WriteStringToFile(file_data, getStoragePath())) {
        LOG(ERROR) << "Failed to write samples";
    }
}

void BootioCollector::Print() {
    std::string file_data;
    if (!android::base::ReadFileToString(getStoragePath(), &file_data)) {
        printf("Failed to read data from file.\n");
        return;
    }
    std::unique_ptr <DataContainer> data(new DataContainer());
    if (!data->ParsePartialFromString(file_data)) {
        printf("Failed to parse data.\n");
        return;
    }
    std::unordered_map<int, uint64_t> cpuDataMap;
    for (int i = 0; i < data->cpu_size(); i++) {
        CpuData cpu_data = data->cpu(i);
        cpuDataMap[cpu_data.timestamp()] = android::SumCpuValues(cpu_data);
    }
    android::PrintPids(*data.get(), cpuDataMap);
}


std::string BootioCollector::getStoragePath() {
    return path_ + SAMPLES_FILE;
}
