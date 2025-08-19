/*
** Copyright 2010 The Android Open Source Project
**
** Licensed under the Apache License, Version 2.0 (the "License");
** you may not use this file except in compliance with the License.
** You may obtain a copy of the License at
**
**     http://www.apache.org/licenses/LICENSE-2.0
**
** Unless required by applicable law or agreed to in writing, software
** distributed under the License is distributed on an "AS IS" BASIS,
** WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
** See the License for the specific language governing permissions and
** limitations under the License.
*/


/* Opens /proc/sched_stat and diff's the counters.
   Currently support version 15, modify parse() to support other
   versions
*/

#include <stdlib.h>
#include <stdio.h>
#include <errno.h>
#include <sys/uio.h>
#include <unistd.h>
#include <sys/time.h>
#include <fcntl.h>

#define MAX_CPU 2

struct cpu_stat {
    /* sched_yield() stats */
    unsigned int yld_count;  /* sched_yield() called */

    /* schedule() stats */
    unsigned int sched_switch;  /* switched to expired queue and reused it */
    unsigned int sched_count;  /* schedule() called */
    unsigned int sched_goidle;  /* schedule() left the cpu idle */

    /* try_to_wake_up() stats */
    unsigned int ttwu_count;  /* try_to_wake_up() called */
    /* try_to_wake_up() called and found the process being awakened last ran on
     * the waking cpu */
    unsigned int ttwu_local;

    /* latency stats */
    unsigned long long cpu_time;  /* time spent running by tasks (ms) */
    unsigned long long run_delay; /* time spent waiting to run by tasks (ms) */
    unsigned long pcount;  /* number of tasks (not necessarily unique) given */
};

struct cpu_stat cpu_prev[MAX_CPU];
struct cpu_stat cpu_delta[MAX_CPU];
struct cpu_stat tmp;

static const char *next_line(const char *b) {
    while (1) {
        switch (*b) {
        case '\n':
            return b + 1;
        case '\0':
            return NULL;
        }
        b++;
    }
}
static int print() {
    int i;

    printf("CPU  yield() schedule() switch idle   ttwu() local  cpu_time wait_time timeslices\n");
    for (i=0; i<MAX_CPU; i++) {
        printf(" %2d  %7u %10u %6u %4u %8u %5u %9llu %9llu %10lu\n",
            i,
            cpu_delta[i].yld_count,
            cpu_delta[i].sched_count, cpu_delta[i].sched_switch, cpu_delta[i].sched_goidle,
            cpu_delta[i].ttwu_count, cpu_delta[i].ttwu_local,
            cpu_delta[i].cpu_time / 1000000, cpu_delta[i].run_delay / 1000000, cpu_delta[i].pcount);
    }
    return 0;
}

static int parse_cpu_v15(const char *b) {
    int cpu;

    if (sscanf(b, "cpu%d %u %u %u %u %u %u %llu %llu %lu\n",
            &cpu, &tmp.yld_count,
            &tmp.sched_switch, &tmp.sched_count, &tmp.sched_goidle,
            &tmp.ttwu_count, &tmp.ttwu_local,
            &tmp.cpu_time, &tmp.run_delay, &tmp.pcount) != 10) {
        printf("Could not parse %s\n", b);
        return -1;
    }

    cpu_delta[cpu].yld_count = tmp.yld_count - cpu_prev[cpu].yld_count;
    cpu_delta[cpu].sched_switch = tmp.sched_switch - cpu_prev[cpu].sched_switch;
    cpu_delta[cpu].sched_count = tmp.sched_count - cpu_prev[cpu].sched_count;
    cpu_delta[cpu].sched_goidle = tmp.sched_goidle - cpu_prev[cpu].sched_goidle;
    cpu_delta[cpu].ttwu_count = tmp.ttwu_count - cpu_prev[cpu].ttwu_count;
    cpu_delta[cpu].ttwu_local = tmp.ttwu_local - cpu_prev[cpu].ttwu_local;
    cpu_delta[cpu].cpu_time = tmp.cpu_time - cpu_prev[cpu].cpu_time;
    cpu_delta[cpu].run_delay = tmp.run_delay - cpu_prev[cpu].run_delay;
    cpu_delta[cpu].pcount = tmp.pcount - cpu_prev[cpu].pcount;

    cpu_prev[cpu] = tmp;
    return 0;
}


static int parse(const char *b) {
    unsigned int version;
    unsigned long long ts;

    if (sscanf(b, "version %u\n", &version) != 1) {
        printf("Could not parse version\n");
        return -1;
    }
    switch (version) {
    case 15:
        b = next_line(b);
        if (!b || sscanf(b, "timestamp %llu\n", &ts) != 1) {
            printf("Could not parse timestamp\n");
            return -1;
        }
        while (1) {
            b = next_line(b);
            if (!b) break;
            if (b[0] == 'c') {
                if (parse_cpu_v15(b)) return -1;
            }
        }
        break;
    default:
        printf("Can not handle version %u\n", version);
        return -1;
    }
    return 0;
}

int main(int argc, char **argv) {
    int i;
    int fd;
    char buf[4096];

    while (1) {
        fd = open("/proc/schedstat", O_RDONLY);
        if (fd < 0) return -1;
        i = read(fd, buf, sizeof(buf) - 1);
        close(fd);
        buf[i] = '\0';
        if (parse(buf)) return -1;
        print();
        sleep(1);
    }
    return 0;
}
