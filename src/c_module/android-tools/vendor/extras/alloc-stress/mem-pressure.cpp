#include <errno.h>
#include <fcntl.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <unistd.h>

void* alloc_set(size_t size) {
    void* addr = NULL;

    addr = malloc(size);
    if (!addr) {
        printf("Allocating %zd MB failed\n", size / 1024 / 1024);
    } else {
        memset(addr, 0, size);
    }
    return addr;
}

void add_pressure(size_t* shared, size_t size, size_t step_size, size_t duration,
                  const char* oom_score) {
    int fd, ret;

    fd = open("/proc/self/oom_score_adj", O_WRONLY);
    ret = write(fd, oom_score, strlen(oom_score));
    if (ret < 0) {
        printf("Writing oom_score_adj failed with err %s\n", strerror(errno));
    }
    close(fd);

    if (alloc_set(size)) {
        *shared = size;
    }

    while (alloc_set(step_size)) {
        size += step_size;
        *shared = size;
        usleep(duration);
    }
}

void usage() {
    printf("Usage: [OPTIONS]\n\n"
           "  -d N: Duration in microsecond to sleep between each allocation.\n"
           "  -i N: Number of iterations to run the alloc process.\n"
           "  -o N: The oom_score to set the child process to before alloc.\n"
           "  -s N: Number of bytes to allocate in an alloc process loop.\n");
}

int main(int argc, char* argv[]) {
    pid_t pid;
    size_t* shared;
    int c, i = 0;

    size_t duration = 1000;
    int iterations = 0;
    const char* oom_score = "899";
    size_t step_size = 2 * 1024 * 1024;  // 2 MB
    size_t size = step_size;

    while ((c = getopt(argc, argv, "hi:d:o:s:")) != -1) {
        switch (c) {
            case 'i':
                iterations = atoi(optarg);
                break;
            case 'd':
                duration = atoi(optarg);
                break;
            case 'o':
                oom_score = optarg;
                break;
            case 's':
                step_size = atoi(optarg);
                break;
            case 'h':
                usage();
                abort();
            default:
                abort();
        }
    }

    shared = (size_t*)mmap(NULL, sizeof(size_t), PROT_READ | PROT_WRITE, MAP_ANONYMOUS | MAP_SHARED,
                           0, 0);

    while (iterations == 0 || i < iterations) {
        *shared = 0;
        pid = fork();
        if (!pid) {
            /* Child */
            add_pressure(shared, size, step_size, duration, oom_score);
            /* Shoud not get here */
            exit(0);
        } else {
            wait(NULL);
            printf("Child %d allocated %zd MB\n", i, *shared / 1024 / 1024);
            size = *shared / 2;
        }
        i++;
    }
}
