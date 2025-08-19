/*
 * Copyright (C) 2008 The Android Open Source Project
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
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define MAX_LINE 512
#define MAX_FILENAME 64

const char* EXPECTED_VERSION = "Latency Top version : v0.1\n";
const char* SYSCTL_FILE = "/proc/sys/kernel/latencytop";
const char* GLOBAL_STATS_FILE = "/proc/latency_stats";
const char* THREAD_STATS_FILE_FORMAT = "/proc/%d/task/%d/latency";

struct latency_entry {
    struct latency_entry* next;
    unsigned long count;
    unsigned long max;
    unsigned long total;
    char reason[MAX_LINE];
};

static inline void check_latencytop() {}

static struct latency_entry* read_global_stats(struct latency_entry* list, int erase);
static struct latency_entry* read_process_stats(struct latency_entry* list, int erase, int pid);
static struct latency_entry* read_thread_stats(struct latency_entry* list, int erase, int pid,
                                               int tid, int fatal);

static struct latency_entry* alloc_latency_entry(void);

static void set_latencytop(int on);
static struct latency_entry* read_latency_file(FILE* f, struct latency_entry* list);

static struct latency_entry* find_latency_entry(struct latency_entry* e, char* reason);
static void print_latency_entries(struct latency_entry* head);

static void signal_handler(int sig);
static void disable_latencytop(void);

static int numcmp(const long long a, const long long b);
static int lat_cmp(const void* a, const void* b);

static void clear_screen(void);
static void usage(const char* cmd);

struct latency_entry* free_entries;

int main(int argc, char* argv[]) {
    struct latency_entry* e;
    int delay, iterations;
    int pid, tid;
    int count, erase;
    int i;

    delay = 1;
    iterations = 0;
    pid = tid = 0;

    for (i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-d")) {
            if (i >= argc - 1) {
                fprintf(stderr, "Option -d expects an argument.\n");
                exit(EXIT_FAILURE);
            }
            delay = atoi(argv[++i]);
            continue;
        }
        if (!strcmp(argv[i], "-n")) {
            if (i >= argc - 1) {
                fprintf(stderr, "Option -n expects an argument.\n");
                exit(EXIT_FAILURE);
            }
            iterations = atoi(argv[++i]);
            continue;
        }
        if (!strcmp(argv[i], "-h")) {
            usage(argv[0]);
            exit(EXIT_SUCCESS);
        }
        if (!strcmp(argv[i], "-p")) {
            if (i >= argc - 1) {
                fprintf(stderr, "Option -p expects an argument.\n");
                exit(EXIT_FAILURE);
            }
            pid = atoi(argv[++i]);
            continue;
        }
        if (!strcmp(argv[i], "-t")) {
            if (i >= argc - 1) {
                fprintf(stderr, "Option -t expects an argument.\n");
                exit(EXIT_FAILURE);
            }
            tid = atoi(argv[++i]);
            continue;
        }
        fprintf(stderr, "Invalid argument \"%s\".\n", argv[i]);
        usage(argv[0]);
        exit(EXIT_FAILURE);
    }

    if (tid && !pid) {
        fprintf(stderr,
                "If you provide a thread ID with -t, you must provide a process ID with -p.\n");
        exit(EXIT_FAILURE);
    }

    check_latencytop();

    free_entries = NULL;

    signal(SIGINT, &signal_handler);
    signal(SIGTERM, &signal_handler);

    atexit(&disable_latencytop);

    set_latencytop(1);

    count = 0;
    erase = 1;

    while ((iterations == 0) || (count++ < iterations)) {
        sleep(delay);

        e = NULL;
        if (pid) {
            if (tid) {
                e = read_thread_stats(e, erase, pid, tid, 1);
            } else {
                e = read_process_stats(e, erase, pid);
            }
        } else {
            e = read_global_stats(e, erase);
        }
        erase = 0;

        clear_screen();
        if (pid) {
            if (tid) {
                printf("Latencies for thread %d in process %d:\n", tid, pid);
            } else {
                printf("Latencies for process %d:\n", pid);
            }
        } else {
            printf("Latencies across all processes:\n");
        }
        print_latency_entries(e);
    }

    set_latencytop(0);

    return 0;
}

static struct latency_entry* read_global_stats(struct latency_entry* list, int erase) {
    FILE* f;
    struct latency_entry* e;

    if (erase) {
        f = fopen(GLOBAL_STATS_FILE, "w");
        if (!f) {
            fprintf(stderr, "Could not open global latency stats file: %s\n", strerror(errno));
            exit(EXIT_FAILURE);
        }
        fprintf(f, "erase\n");
        fclose(f);
    }

    f = fopen(GLOBAL_STATS_FILE, "r");
    if (!f) {
        fprintf(stderr, "Could not open global latency stats file: %s\n", strerror(errno));
        exit(EXIT_FAILURE);
    }

    e = read_latency_file(f, list);

    fclose(f);

    return e;
}

static struct latency_entry* read_process_stats(struct latency_entry* list, int erase, int pid) {
    char dirname[MAX_FILENAME];
    DIR* dir;
    struct dirent* ent;
    struct latency_entry* e;
    int tid;

    sprintf(dirname, "/proc/%d/task", pid);
    dir = opendir(dirname);
    if (!dir) {
        fprintf(stderr, "Could not open task dir for process %d.\n", pid);
        fprintf(stderr, "Perhaps the process has terminated?\n");
        exit(EXIT_FAILURE);
    }

    e = list;
    while ((ent = readdir(dir))) {
        if (!isdigit(ent->d_name[0])) continue;

        tid = atoi(ent->d_name);

        e = read_thread_stats(e, erase, pid, tid, 0);
    }

    closedir(dir);

    return e;
}

static struct latency_entry* read_thread_stats(struct latency_entry* list, int erase, int pid,
                                               int tid, int fatal) {
    char filename[MAX_FILENAME];
    FILE* f;
    struct latency_entry* e;

    sprintf(filename, THREAD_STATS_FILE_FORMAT, pid, tid);

    if (erase) {
        f = fopen(filename, "w");
        if (!f) {
            if (fatal) {
                fprintf(stderr, "Could not open %s: %s\n", filename, strerror(errno));
                fprintf(stderr, "Perhaps the process or thread has terminated?\n");
                exit(EXIT_FAILURE);
            } else {
                return list;
            }
        }
        fprintf(f, "erase\n");
        fclose(f);
    }

    f = fopen(GLOBAL_STATS_FILE, "r");
    if (!f) {
        if (fatal) {
            fprintf(stderr, "Could not open %s: %s\n", filename, strerror(errno));
            fprintf(stderr, "Perhaps the process or thread has terminated?\n");
            exit(EXIT_FAILURE);
        } else {
            return list;
        }
    }

    e = read_latency_file(f, list);

    fclose(f);

    return e;
}

static struct latency_entry* alloc_latency_entry(void) {
    struct latency_entry* e;

    if (free_entries) {
        e = free_entries;
        free_entries = free_entries->next;
    } else {
        e = calloc(1, sizeof(struct latency_entry));
        if (!e) {
            fprintf(stderr, "Could not allocate latency entry: %s\n", strerror(errno));
            exit(EXIT_FAILURE);
        }
    }

    return e;
}

static struct latency_entry* find_latency_entry(struct latency_entry* head, char* reason) {
    struct latency_entry* e;

    e = head;

    while (e) {
        if (!strcmp(e->reason, reason)) return e;
        e = e->next;
    }

    return NULL;
}

static void set_latencytop(int on) {
    FILE* f;

    f = fopen(SYSCTL_FILE, "w");
    if (!f) {
        fprintf(stderr, "Could not open %s: %s\n", SYSCTL_FILE, strerror(errno));
        exit(EXIT_FAILURE);
    }

    fprintf(f, "%d\n", on);

    fclose(f);
}

static struct latency_entry* read_latency_file(FILE* f, struct latency_entry* list) {
    struct latency_entry *e, *head;
    char line[MAX_LINE];
    unsigned long count, max, total;
    char reason[MAX_LINE];

    head = list;

    if (!fgets(line, MAX_LINE, f)) {
        fprintf(stderr, "Could not read latency file version: %s\n", strerror(errno));
        exit(EXIT_FAILURE);
    }

    if (strcmp(line, EXPECTED_VERSION) != 0) {
        fprintf(stderr, "Expected version: %s\n", EXPECTED_VERSION);
        fprintf(stderr, "But got version: %s", line);
        exit(EXIT_FAILURE);
    }

    while (fgets(line, MAX_LINE, f)) {
        sscanf(line, "%ld %ld %ld %s", &count, &total, &max, reason);
        if (max > 0 || total > 0) {
            e = find_latency_entry(head, reason);
            if (e) {
                e->count += count;
                if (max > e->max) e->max = max;
                e->total += total;
            } else {
                e = alloc_latency_entry();
                e->count = count;
                e->max = max;
                e->total = total;
                strcpy(e->reason, reason);
                e->next = head;
                head = e;
            }
        }
    }

    return head;
}

static void print_latency_entries(struct latency_entry* head) {
    struct latency_entry *e, **array;
    unsigned long average;
    int i, count;

    e = head;
    count = 0;
    while (e) {
        count++;
        e = e->next;
    }

    e = head;
    array = calloc(count, sizeof(struct latency_entry*));
    if (!array) {
        fprintf(stderr, "Error allocating array: %s\n", strerror(errno));
        exit(EXIT_FAILURE);
    }
    for (i = 0; i < count; i++) {
        array[i] = e;
        e = e->next;
    }

    qsort(array, count, sizeof(struct latency_entry*), &lat_cmp);

    printf("%10s  %10s  %7s  %s\n", "Maximum", "Average", "Count", "Reason");
    for (i = 0; i < count; i++) {
        e = array[i];
        average = e->total / e->count;
        printf("%4lu.%02lu ms  %4lu.%02lu ms  %7ld  %s\n", e->max / 1000, (e->max % 1000) / 10,
               average / 1000, (average % 1000) / 10, e->count, e->reason);
    }

    free(array);
}

static void signal_handler(int sig) {
    exit(EXIT_SUCCESS);
}

static void disable_latencytop(void) {
    set_latencytop(0);
}

static void clear_screen(void) {
    printf("\n\n");
}

static void usage(const char* cmd) {
    fprintf(stderr,
            "Usage: %s [ -d delay ] [ -n iterations ] [ -p pid [ -t tid ] ] [ -h ]\n"
            "    -d delay       Time to sleep between updates.\n"
            "    -n iterations  Number of updates to show (0 = infinite).\n"
            "    -p pid         Process to monitor (default is all).\n"
            "    -t tid         Thread (within specified process) to monitor (default is all).\n"
            "    -h             Display this help screen.\n",
            cmd);
}

static int numcmp(const long long a, const long long b) {
    if (a < b) return -1;
    if (a > b) return 1;
    return 0;
}

static int lat_cmp(const void* a, const void* b) {
    const struct latency_entry *pa, *pb;

    pa = (*((struct latency_entry**)a));
    pb = (*((struct latency_entry**)b));

    return numcmp(pb->max, pa->max);
}
