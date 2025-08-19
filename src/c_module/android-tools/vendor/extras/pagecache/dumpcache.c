#include <ftw.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <fcntl.h>

#include <ctype.h>
#include <stddef.h>
#include <mntent.h>
#include <sys/mman.h>
#include <sys/stat.h>

// Initial size of the array holding struct file_info
#define INITIAL_NUM_FILES 512

// Max number of file descriptors to use for ntfw
#define MAX_NUM_FD 1

struct file_info {
    char *name;
    size_t file_size;
    size_t num_cached_pages;
};

// Size of pages on this system
static int g_page_size;

// Total number of cached pages found so far
static size_t g_total_cached = 0;

// Total number of files scanned so far
static size_t g_num_files = 0;

// Scanned files and their associated cached page counts
static struct file_info **g_files;

// Current size of files array
size_t g_files_size;

static struct file_info *get_file_info(const char* fpath, size_t file_size) {
    struct file_info *info;
    if (g_num_files >= g_files_size) {
        g_files = realloc(g_files, 2 * g_files_size * sizeof(struct file_info*));
        if (!g_files) {
            fprintf(stderr, "Couldn't allocate space for files array: %s\n", strerror(errno));
            exit(EXIT_FAILURE);
        }
        g_files_size = 2 * g_files_size;
    }

    info = calloc(1, sizeof(*info));
    if (!info) {
        fprintf(stderr, "Couldn't allocate space for file struct: %s\n", strerror(errno));
        exit(EXIT_FAILURE);
    }

    info->name = malloc(strlen(fpath) + 1);
    if (!info->name) {
        fprintf(stderr, "Couldn't allocate space for file struct: %s\n", strerror(errno));
        exit(EXIT_FAILURE);
    }
    strcpy(info->name, fpath);

    info->num_cached_pages = 0;
    info->file_size = file_size;

    g_files[g_num_files++] = info;

    return info;
}

static int store_num_cached(const char* fpath, const struct stat *sb) {
    int fd, ret = -1;
    fd = open (fpath, O_RDONLY);

    if (fd == -1) {
        fprintf(stderr, "Could not open file: %s\n", fpath);
        return ret;
    }

    void* mapped_addr = mmap(NULL, sb->st_size, PROT_NONE, MAP_SHARED, fd, 0);

    if (mapped_addr != MAP_FAILED) {
        // Calculate bit-vector size
        size_t num_file_pages = (sb->st_size + g_page_size - 1) / g_page_size;
        unsigned char* mincore_data = calloc(1, num_file_pages);
        ret = mincore(mapped_addr, sb->st_size, mincore_data);
        if (!ret) {
            int num_cached = 0;
            unsigned int page = 0;
            for (page = 0; page < num_file_pages; page++) {
                if (mincore_data[page]) num_cached++;
            }
            if (num_cached > 0) {
                struct file_info *info = get_file_info(fpath, sb->st_size);
                info->num_cached_pages += num_cached;
                g_total_cached += num_cached;
            }
        }
        munmap(mapped_addr, sb->st_size);
    }

    close(fd);
    return ret;
}

static int scan_entry(const char *fpath, const struct stat *sb, int typeflag,
                      struct FTW * __attribute__((unused))ftwbuf) {
    if (typeflag == FTW_F) {
        store_num_cached(fpath, sb);
    }
    return 0;
}

static int cmpsize(size_t a, size_t b) {
    if (a < b) return -1;
    if (a > b) return 1;
    return 0;
}

static int cmpfiles(const void *a, const void *b) {
    return cmpsize((*((struct file_info**)a))->num_cached_pages,
            (*((struct file_info**)b))->num_cached_pages);
}

int main()
{
    size_t i;
    g_page_size = getpagesize();

    g_files = malloc(INITIAL_NUM_FILES * sizeof(struct file_info*));
    g_files_size = INITIAL_NUM_FILES;

    // Walk filesystem trees through procfs except rootfs/devfs/sysfs/procfs
    FILE* fp = setmntent("/proc/mounts", "r");
    if (fp == NULL) {
        fprintf(stderr, "Error opening /proc/mounts\n");
        return -errno;
    }
    struct mntent* mentry;
    while ((mentry = getmntent(fp)) != NULL) {
        if (strcmp(mentry->mnt_type, "rootfs") != 0 &&
            strncmp("/dev", mentry->mnt_dir, strlen("/dev")) != 0 &&
            strncmp("/sys", mentry->mnt_dir, strlen("/sys")) != 0 &&
            strncmp("/proc", mentry->mnt_dir, strlen("/proc")) != 0) {
            nftw(mentry->mnt_dir, &scan_entry, MAX_NUM_FD, FTW_MOUNT | FTW_PHYS | FTW_DEPTH);
        }
    }
    endmntent(fp);

    // Sort entries
    qsort(g_files, g_num_files, sizeof(g_files[0]), &cmpfiles);

    // Dump entries
    for (i = 0; i < g_num_files; i++) {
        struct file_info *info = g_files[i];
        fprintf(stdout, "%s: %zu cached pages (%.2f MB, %zu%% of total file size.)\n", info->name,
                info->num_cached_pages,
                (float) (info->num_cached_pages * g_page_size) / 1024 / 1024,
                (100 * info->num_cached_pages * g_page_size) / info->file_size);
    }

    fprintf(stdout, "TOTAL CACHED: %zu pages (%f MB)\n", g_total_cached,
            (float) (g_total_cached * 4096) / 1024 / 1024);
    return 0;
}
