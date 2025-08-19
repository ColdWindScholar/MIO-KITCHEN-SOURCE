#include <errno.h>
#include <fcntl.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#include "kexec.h"

// Offsets same as in kernel asm/kexec.h
#define KEXEC_ARM_ATAGS_OFFSET 0x1000
#define KEXEC_ARM_ZIMAGE_OFFSET 0x8000

#define MEMORY_SIZE 0x0800000
// Physical buffer address cannot overlap with other regions
#define START_ADDRESS 0x44000000

#define ROUND_TO_PAGE(address, pagesize) (((address) + (pagesize)-1) & (~((pagesize)-1)))

/*
 * Gives file position and resets current position to begining of file
 */
int get_file_size(int f) {
    struct stat st;
    fstat(f, &st);
    return st.st_size;
}

int test_kexeccall() {
    int rv;

    rv = kexec_load(0, 0, NULL, KEXEC_ARCH_DEFAULT);

    if (rv != 0) {
        printf("ERROR: kexec_load: %d \n", errno);
        return 1;
    }

    printf("Kexec test: Success \n");

    return 0;
}

void usage(void) {
    fprintf(stderr,
            "usage: kexecload [ <option> ] <atags path> <kernel path>\n"
            "\n"
            "options:\n"
            "  -t                                       tests syscall\n"
            "  -s <start address>                       specify start address of kernel\n");
}

/*
 * Loads kexec into the kernel and sets kexec on crash
 */
int main(int argc, char* argv[]) {
    int rv;
    int atag_file, zimage_file;
    int atag_size, zimage_size;
    void* atag_buffer;
    void* zimage_buffer;
    struct kexec_segment segment[2];
    int page_size = getpagesize();
    void* start_address = (void*)START_ADDRESS;
    int c;

    const struct option longopts[] = {{"start_address", required_argument, 0, 's'},
                                      {"test", 0, 0, 't'},
                                      {"help", 0, 0, 'h'},
                                      {0, 0, 0, 0}};

    while (1) {
        c = getopt_long(argc, argv, "s:th", longopts, NULL);
        if (c < 0) {
            break;
        }
        /* Alphabetical cases */
        switch (c) {
            case 's':
                start_address = (void*)strtoul(optarg, 0, 16);
                break;
            case 'h':
                usage();
                return 1;
            case 't':
                test_kexeccall();
                return 1;
            case '?':
                return 1;
            default:
                abort();
        }
    }

    argc -= optind;
    argv += optind;

    if (argc < 2) {
        usage();
        return 1;
    }

    atag_file = open(argv[0], O_RDONLY);
    zimage_file = open(argv[1], O_RDONLY);

    if (atag_file < 0 || zimage_file < 0) {
        fprintf(stderr, "Error during opening of atag file or the zImage file %s\n",
                strerror(errno));
        return 1;
    }

    atag_size = ROUND_TO_PAGE(get_file_size(atag_file), page_size);
    zimage_size = ROUND_TO_PAGE(get_file_size(zimage_file), page_size);

    if (atag_size >= KEXEC_ARM_ZIMAGE_OFFSET - KEXEC_ARM_ATAGS_OFFSET) {
        fprintf(stderr, "Atag file is too large\n");
        return 1;
    }

    atag_buffer = (char*)mmap(NULL, atag_size, PROT_READ, MAP_POPULATE | MAP_PRIVATE, atag_file, 0);
    zimage_buffer =
            (char*)mmap(NULL, zimage_size, PROT_READ, MAP_POPULATE | MAP_PRIVATE, zimage_file, 0);

    if (atag_buffer == MAP_FAILED || zimage_buffer == MAP_FAILED) {
        fprintf(stderr, "Unable to map files into memory");
        return 1;
    }

    segment[0].buf = zimage_buffer;
    segment[0].bufsz = zimage_size;
    segment[0].mem = (void*)((uintptr_t)start_address + KEXEC_ARM_ZIMAGE_OFFSET);
    segment[0].memsz = zimage_size;

    segment[1].buf = atag_buffer;
    segment[1].bufsz = atag_size;
    segment[1].mem = (void*)((uintptr_t)start_address + KEXEC_ARM_ATAGS_OFFSET);
    segment[1].memsz = atag_size;

    rv = kexec_load(((uintptr_t)start_address + KEXEC_ARM_ZIMAGE_OFFSET), 2, (void*)segment,
                    KEXEC_ARCH_DEFAULT | KEXEC_ON_CRASH);

    if (rv != 0) {
        fprintf(stderr, "Kexec_load returned non-zero exit code: %d with errno %d\n", rv, errno);
        return 1;
    }

    printf("Done! Kexec loaded\n");
    printf("New kernel should start at 0x%08x\n", START_ADDRESS + KEXEC_ARM_ZIMAGE_OFFSET);

    return 0;
}
