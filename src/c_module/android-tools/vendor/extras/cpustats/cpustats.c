/*
 * Copyright (c) 2012, The Android Open Source Project
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 *  * Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 *  * Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in
 *    the documentation and/or other materials provided with the
 *    distribution.
 *  * Neither the name of Google, Inc. nor the names of its contributors
 *    may be used to endorse or promote products derived from this
 *    software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
 * FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
 * COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
 * INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
 * BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS
 * OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
 * AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
 * OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT
 * OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
 * SUCH DAMAGE.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define MAX_BUF_SIZE 64

struct freq_info {
    unsigned freq;
    long unsigned time;
};

struct cpu_info {
    long unsigned utime, ntime, stime, itime, iowtime, irqtime, sirqtime;
    struct freq_info* freqs;
    int freq_count;
};

#define die(...)                      \
    {                                 \
        fprintf(stderr, __VA_ARGS__); \
        exit(EXIT_FAILURE);           \
    }

static struct cpu_info old_total_cpu, new_total_cpu, *old_cpus, *new_cpus;
static int cpu_count, delay, iterations;
static char minimal, aggregate_freq_stats;

static int get_cpu_count();
static int get_cpu_count_from_file(char* filename);
static long unsigned get_cpu_total_time(struct cpu_info* cpu);
static int get_freq_scales_count(int cpu);
static void print_stats();
static void print_cpu_stats(char* label, struct cpu_info* new_cpu, struct cpu_info* old_cpu,
                            char print_freq);
static void print_freq_stats(struct cpu_info* new_cpu, struct cpu_info* old_cpu);
static void read_stats();
static void read_freq_stats(int cpu);
static char should_aggregate_freq_stats();
static char should_print_freq_stats();
static void usage(char* cmd);

int main(int argc, char* argv[]) {
    struct cpu_info *tmp_cpus, tmp_total_cpu;
    int i, freq_count;

    delay = 3;
    iterations = -1;
    minimal = 0;
    aggregate_freq_stats = 0;

    for (i = 0; i < argc; i++) {
        if (!strcmp(argv[i], "-n")) {
            if (i + 1 >= argc) {
                fprintf(stderr, "Option -n expects an argument.\n");
                usage(argv[0]);
                exit(EXIT_FAILURE);
            }
            iterations = atoi(argv[++i]);
            continue;
        }
        if (!strcmp(argv[i], "-d")) {
            if (i + 1 >= argc) {
                fprintf(stderr, "Option -d expects an argument.\n");
                usage(argv[0]);
                exit(EXIT_FAILURE);
            }
            delay = atoi(argv[++i]);
            continue;
        }
        if (!strcmp(argv[i], "-m")) {
            minimal = 1;
        }
        if (!strcmp(argv[i], "-h")) {
            usage(argv[0]);
            exit(EXIT_SUCCESS);
        }
    }

    cpu_count = get_cpu_count();
    if (cpu_count < 1) die("Unexpected cpu count\n");

    old_cpus = malloc(sizeof(struct cpu_info) * cpu_count);
    if (!old_cpus) die("Could not allocate struct cpu_info\n");
    new_cpus = malloc(sizeof(struct cpu_info) * cpu_count);
    if (!new_cpus) die("Could not allocate struct cpu_info\n");

    for (i = 0; i < cpu_count; i++) {
        freq_count = get_freq_scales_count(i);
        if (freq_count < 1) die("Unexpected frequency scale count\n");
        old_cpus[i].freq_count = new_cpus[i].freq_count = freq_count;
        new_cpus[i].freqs = malloc(sizeof(struct freq_info) * new_cpus[i].freq_count);
        if (!new_cpus[i].freqs) die("Could not allocate struct freq_info\n");
        old_cpus[i].freqs = malloc(sizeof(struct freq_info) * old_cpus[i].freq_count);
        if (!old_cpus[i].freqs) die("Could not allocate struct freq_info\n");
    }

    // Read stats without aggregating freq stats in the total cpu
    read_stats();

    aggregate_freq_stats = should_aggregate_freq_stats();
    if (aggregate_freq_stats) {
        old_total_cpu.freq_count = new_total_cpu.freq_count = new_cpus[0].freq_count;
        new_total_cpu.freqs = malloc(sizeof(struct freq_info) * new_total_cpu.freq_count);
        if (!new_total_cpu.freqs) die("Could not allocate struct freq_info\n");
        old_total_cpu.freqs = malloc(sizeof(struct freq_info) * old_total_cpu.freq_count);
        if (!old_total_cpu.freqs) die("Could not allocate struct freq_info\n");

        // Read stats again with aggregating freq stats in the total cpu
        read_stats();
    }

    while ((iterations == -1) || (iterations-- > 0)) {
        // Swap new and old cpu buffers;
        tmp_total_cpu = old_total_cpu;
        old_total_cpu = new_total_cpu;
        new_total_cpu = tmp_total_cpu;

        tmp_cpus = old_cpus;
        old_cpus = new_cpus;
        new_cpus = tmp_cpus;

        sleep(delay);
        read_stats();
        print_stats();
    }

    // Clean up
    if (aggregate_freq_stats) {
        free(new_total_cpu.freqs);
        free(old_total_cpu.freqs);
    }
    for (i = 0; i < cpu_count; i++) {
        free(new_cpus[i].freqs);
        free(old_cpus[i].freqs);
    }
    free(new_cpus);
    free(old_cpus);

    return 0;
}

/*
 * Get the number of CPUs of the system.
 *
 * Uses the two files /sys/devices/system/cpu/present and
 * /sys/devices/system/cpu/online to determine the number of CPUs. Expects the
 * format of both files to be either 0 or 0-N where N+1 is the number of CPUs.
 *
 * Exits if the present CPUs is not equal to the online CPUs
 */
static int get_cpu_count() {
    int cpu_count = get_cpu_count_from_file("/sys/devices/system/cpu/present");
    if (cpu_count != get_cpu_count_from_file("/sys/devices/system/cpu/online")) {
        die("present cpus != online cpus\n");
    }
    return cpu_count;
}

/*
 * Get the number of CPUs from a given filename.
 */
static int get_cpu_count_from_file(char* filename) {
    FILE* file;
    char line[MAX_BUF_SIZE];
    int cpu_count;

    file = fopen(filename, "r");
    if (!file) die("Could not open %s\n", filename);
    if (!fgets(line, MAX_BUF_SIZE, file)) die("Could not get %s contents\n", filename);
    fclose(file);

    if (strcmp(line, "0\n") == 0) {
        return 1;
    }

    if (1 == sscanf(line, "0-%d\n", &cpu_count)) {
        return cpu_count + 1;
    }

    die("Unexpected input in file %s (%s).\n", filename, line);
    return -1;
}

/*
 * Get the number of frequency states a given CPU can be scaled to.
 */
static int get_freq_scales_count(int cpu) {
    FILE* file;
    char filename[MAX_BUF_SIZE];
    long unsigned freq;
    int count = 0;

    sprintf(filename, "/sys/devices/system/cpu/cpu%d/cpufreq/stats/time_in_state", cpu);
    file = fopen(filename, "r");
    if (!file) die("Could not open %s\n", filename);
    do {
        freq = 0;
        fscanf(file, "%lu %*d\n", &freq);
        if (freq) count++;
    } while (freq);
    fclose(file);

    return count;
}

/*
 * Read the CPU and frequency stats for all cpus.
 */
static void read_stats() {
    FILE* file;
    char scanline[MAX_BUF_SIZE];
    int i;

    file = fopen("/proc/stat", "r");
    if (!file) die("Could not open /proc/stat.\n");
    fscanf(file, "cpu  %lu %lu %lu %lu %lu %lu %lu %*d %*d %*d\n", &new_total_cpu.utime,
           &new_total_cpu.ntime, &new_total_cpu.stime, &new_total_cpu.itime, &new_total_cpu.iowtime,
           &new_total_cpu.irqtime, &new_total_cpu.sirqtime);
    if (aggregate_freq_stats) {
        for (i = 0; i < new_total_cpu.freq_count; i++) {
            new_total_cpu.freqs[i].time = 0;
        }
    }

    for (i = 0; i < cpu_count; i++) {
        sprintf(scanline, "cpu%d %%lu %%lu %%lu %%lu %%lu %%lu %%lu %%*d %%*d %%*d\n", i);
        fscanf(file, scanline, &new_cpus[i].utime, &new_cpus[i].ntime, &new_cpus[i].stime,
               &new_cpus[i].itime, &new_cpus[i].iowtime, &new_cpus[i].irqtime,
               &new_cpus[i].sirqtime);
        read_freq_stats(i);
    }
    fclose(file);
}

/*
 * Read the frequency stats for a given cpu.
 */
static void read_freq_stats(int cpu) {
    FILE* file;
    char filename[MAX_BUF_SIZE];
    int i;

    sprintf(filename, "/sys/devices/system/cpu/cpu%d/cpufreq/stats/time_in_state", cpu);
    file = fopen(filename, "r");
    for (i = 0; i < new_cpus[cpu].freq_count; i++) {
        if (file) {
            fscanf(file, "%u %lu\n", &new_cpus[cpu].freqs[i].freq, &new_cpus[cpu].freqs[i].time);
        } else {
            /* The CPU has been off lined for some reason */
            new_cpus[cpu].freqs[i].freq = old_cpus[cpu].freqs[i].freq;
            new_cpus[cpu].freqs[i].time = old_cpus[cpu].freqs[i].time;
        }
        if (aggregate_freq_stats) {
            new_total_cpu.freqs[i].freq = new_cpus[cpu].freqs[i].freq;
            new_total_cpu.freqs[i].time += new_cpus[cpu].freqs[i].time;
        }
    }
    if (file) fclose(file);
}

/*
 * Get the sum of the cpu time from all categories.
 */
static long unsigned get_cpu_total_time(struct cpu_info* cpu) {
    return (cpu->utime + cpu->ntime + cpu->stime + cpu->itime + cpu->iowtime + cpu->irqtime +
            cpu->sirqtime);
}

/*
 * Print the stats for all CPUs.
 */
static void print_stats() {
    char label[8];
    int i;
    char print_freq;

    print_freq = should_print_freq_stats();

    print_cpu_stats("Total", &new_total_cpu, &old_total_cpu, 1);
    for (i = 0; i < cpu_count; i++) {
        sprintf(label, "cpu%d", i);
        print_cpu_stats(label, &new_cpus[i], &old_cpus[i], print_freq);
    }
    printf("\n");
}

/*
 * Print the stats for a single CPU.
 */
static void print_cpu_stats(char* label, struct cpu_info* new_cpu, struct cpu_info* old_cpu,
                            char print_freq) {
    long int total_delta_time;

    if (!minimal) {
        total_delta_time = get_cpu_total_time(new_cpu) - get_cpu_total_time(old_cpu);
        printf("%s: User %ld + Nice %ld + Sys %ld + Idle %ld + IOW %ld + IRQ %ld + SIRQ %ld = "
               "%ld\n",
               label, new_cpu->utime - old_cpu->utime, new_cpu->ntime - old_cpu->ntime,
               new_cpu->stime - old_cpu->stime, new_cpu->itime - old_cpu->itime,
               new_cpu->iowtime - old_cpu->iowtime, new_cpu->irqtime - old_cpu->irqtime,
               new_cpu->sirqtime - old_cpu->sirqtime, total_delta_time);
        if (print_freq) {
            print_freq_stats(new_cpu, old_cpu);
        }
    } else {
        printf("%s,%ld,%ld,%ld,%ld,%ld,%ld,%ld", label, new_cpu->utime - old_cpu->utime,
               new_cpu->ntime - old_cpu->ntime, new_cpu->stime - old_cpu->stime,
               new_cpu->itime - old_cpu->itime, new_cpu->iowtime - old_cpu->iowtime,
               new_cpu->irqtime - old_cpu->irqtime, new_cpu->sirqtime - old_cpu->sirqtime);
        print_freq_stats(new_cpu, old_cpu);
        printf("\n");
    }
}

/*
 * Print the CPU stats for a single CPU.
 */
static void print_freq_stats(struct cpu_info* new_cpu, struct cpu_info* old_cpu) {
    long int delta_time, total_delta_time;
    int i;

    if (new_cpu->freq_count > 0) {
        if (!minimal) {
            total_delta_time = 0;
            printf("  ");
            for (i = 0; i < new_cpu->freq_count; i++) {
                delta_time = new_cpu->freqs[i].time - old_cpu->freqs[i].time;
                total_delta_time += delta_time;
                printf("%ukHz %ld", new_cpu->freqs[i].freq, delta_time);
                if (i + 1 != new_cpu->freq_count) {
                    printf(" + \n  ");
                } else {
                    printf(" = ");
                }
            }
            printf("%ld\n", total_delta_time);
        } else {
            for (i = 0; i < new_cpu->freq_count; i++) {
                printf(",%u,%ld", new_cpu->freqs[i].freq,
                       new_cpu->freqs[i].time - old_cpu->freqs[i].time);
            }
        }
    }
}

/*
 * Determine if frequency stats should be printed.
 *
 * If the frequency stats are different between CPUs, the stats should be
 * printed for each CPU, else only the aggregate frequency stats should be
 * printed.
 */
static char should_print_freq_stats() {
    int i, j;

    for (i = 1; i < cpu_count; i++) {
        for (j = 0; j < new_cpus[i].freq_count; j++) {
            if (new_cpus[i].freqs[j].time - old_cpus[i].freqs[j].time !=
                new_cpus[0].freqs[j].time - old_cpus[0].freqs[j].time) {
                return 1;
            }
        }
    }
    return 0;
}

/*
 * Determine if the frequency stats should be aggregated.
 *
 * Only aggregate the frequency stats in the total cpu stats if the frequencies
 * reported by all CPUs are identical.  Must be called after read_stats() has
 * been called once.
 */
static char should_aggregate_freq_stats() {
    int i, j;

    for (i = 1; i < cpu_count; i++) {
        if (new_cpus[i].freq_count != new_cpus[0].freq_count) {
            return 0;
        }
        for (j = 0; j < new_cpus[i].freq_count; j++) {
            if (new_cpus[i].freqs[j].freq != new_cpus[0].freqs[j].freq) {
                return 0;
            }
        }
    }

    return 1;
}

/*
 * Print the usage message.
 */
static void usage(char* cmd) {
    fprintf(stderr,
            "Usage %s [ -n iterations ] [ -d delay ] [ -c cpu ] [ -m ] [ -h ]\n"
            "    -n num  Updates to show before exiting.\n"
            "    -d num  Seconds to wait between updates.\n"
            "    -m      Display minimal output.\n"
            "    -h      Display this help screen.\n",
            cmd);
}
