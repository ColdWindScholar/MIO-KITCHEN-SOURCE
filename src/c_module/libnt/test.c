#include <stdio.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>

#include "libnt.h"

#define MAP_FILE_READ_CONTENTS "MAP_TEST_CASE1"
#define MAP_FILE_WRITE_CONTENTS "MAP_TEST_CASE2"
#define GETDLIM_FILE_READ_CONTENTS "GETDLIM TEST CASE1"

#define GETDLIM_TOKEN1 "GETDLIM"
#define GETDLIM_TOKEN2 "TEST"
#define GETDLIM_TOKEN3 "CASE1"

#define TEST_FILE_MAP "map"
#define TEST_FILE_GETDLIM "getdlim"
#define TEST_FILE_GETLINE "getline"
#define TEST_FILE_SYMLINK "symlink"
#define TEST_FILE_LSTAT "statfile"
#define TEST_FILE_SENDFILE_SIZE (1 << 26)
#define TEST_FILE_SENDFILE_IN "sendfilein"
#define TEST_FILE_SENDFILE_OUT "sendfileout"

#define WRITE_TO_TEST_FILE_IMPL(FILE, SIZE, BUF) { \
        unlink(FILE); \
        int fd = open(FILE, O_TRUNC | O_RDWR | O_CREAT, S_IRUSR | S_IWUSR); \
        write(fd, BUF, SIZE); \
        close(fd); \
    }

#define WRITE_TO_TEST_FILE(FILE, BUF) WRITE_TO_TEST_FILE_IMPL(FILE, sizeof(BUF), BUF)
#define WRITE_TEXT_TO_TEST_FILE(FILE, BUF) WRITE_TO_TEST_FILE_IMPL(FILE, sizeof(BUF) - 1, BUF)

void create_test_files(void) {
    WRITE_TEXT_TO_TEST_FILE(TEST_FILE_MAP, MAP_FILE_READ_CONTENTS)
    WRITE_TEXT_TO_TEST_FILE(TEST_FILE_GETDLIM, GETDLIM_FILE_READ_CONTENTS)
}

int file_map_read(const char *read_str)
{
    mode_t mode = S_IRUSR | S_IWUSR;
    int o = open(TEST_FILE_MAP, O_RDONLY, mode);

    void* map = mmap(NULL, strlen(read_str), PROT_READ, MAP_PRIVATE, o, 0);
    if (map == MAP_FAILED)
    {
        printf("mmap returned unexpected error: %d\n", errno);
        return -1;
    }
    
    if (strncmp((char *)map, read_str, strlen(read_str)))
        return -1;
    
    int result = munmap(map, strlen(read_str));
    if (result != 0)
        printf("munmap returned unexpected error: %d\n", errno);
    
    close(o);
    return result;
}

int test_file_map_read(void) {
    return file_map_read(MAP_FILE_READ_CONTENTS);
}

int test_file_map_write(void) {
    mode_t mode = S_IRUSR | S_IWUSR;
    /* mapping without read? */
    int o = open(TEST_FILE_MAP, O_RDWR, mode);

    void* map = mmap(NULL, strlen(MAP_FILE_READ_CONTENTS), PROT_WRITE, MAP_SHARED, o, 0);
    if (map == MAP_FAILED)
    {
        printf("mmap returned unexpected error: %d\n", errno);
        return -1;
    }

    memcpy(map, MAP_FILE_WRITE_CONTENTS, strlen(MAP_FILE_WRITE_CONTENTS));

    int result = munmap(map, strlen(MAP_FILE_READ_CONTENTS));
    if (result != 0)
        printf("munmap returned unexpected error: %d\n", errno);
    
    close(o);    
    return file_map_read(MAP_FILE_WRITE_CONTENTS);
}

#define CHECK_TOKEN(TOKEN) \
    { \
        ret = getdelim(&buf, &bufsiz, ' ', fp); \
        if (ret == -1) { \
            printf("getdelim failed : %d\n", errno); \
            return ret; \
        } \
        len = strlen(TOKEN); \
        printf("%s:getdelim: \"%.*s\" (sz: %d)", __func__, ret, buf, len); \
        ret = strncmp(buf, TOKEN, len); \
        if (ret) \
            cmp = -1; \
        printf(" == %s\n", cmp ? "fail" : "pass"); \
    }
int file_getdlim(const char *filename)
{
    char *buf;
    size_t bufsiz = 0;
    FILE *fp = fopen(filename, "rb");
    int cmp = 0, len, ret;
    
    CHECK_TOKEN(GETDLIM_TOKEN1)
    CHECK_TOKEN(GETDLIM_TOKEN2)
    CHECK_TOKEN(GETDLIM_TOKEN3)

    fclose(fp);
    return cmp;
}

int test_file_getdlim(void) {
    return file_getdlim(TEST_FILE_GETDLIM);
}

int test_file_symlink(void) {
    int ret = symlink("/etc/fstab", TEST_FILE_SYMLINK);
    if (ret == -1) {
        printf("symlink failed : %s\n", strerror(errno));
        return ret;
    }
    char path[255];
    int sz = readlink(TEST_FILE_SYMLINK, path, 254);
    if (sz == -1) {
        printf("readlink failed: %s\n", strerror(errno));
        return sz;
    }
    struct stat st;
    ret = lstat(TEST_FILE_SYMLINK, &st);
    if (ret == -1) {
        printf("lstat failed : %d\n", errno);
        return ret;
    }
    path[sz] = 0;
    printf("readlink: %s (sz: %d is_lnk: %d stsz: %lld)", path, sz, S_ISLNK(st.st_mode), st.st_size);
    printf(" == %s\n", (!S_ISLNK(st.st_mode) || st.st_size != sz) ? "fail" : "pass");
    return 0;
}

int test_file_sendfile(void) {
    int in_fd, out_fd;
    
    FILE *fp = fopen(TEST_FILE_SENDFILE_IN, "w+");
    if (fp) {
        // provoke a short read
        fseek(fp, TEST_FILE_SENDFILE_SIZE - 2, SEEK_SET);
        fwrite("", 1, sizeof(char), fp);
        fclose(fp);
    } else {
        printf("fopen failed : %d\n", errno);
        return -1;
    }
    
    in_fd = open(TEST_FILE_SENDFILE_IN, O_RDONLY);
    out_fd = open(TEST_FILE_SENDFILE_OUT, O_TRUNC | O_CREAT | O_WRONLY);

    int ret = sendfile(out_fd, in_fd, NULL, TEST_FILE_SENDFILE_SIZE - 1);

    if (ret < 0) {
        printf("sendfile failed: %s\n", strerror(errno));
        return 1;
    }

    close(in_fd);
    close(out_fd);

    return 0;
}

#define EXEC_TEST(name) \
    if (name() != 0) { result = -1; printf( #name ": fail\n"); } \
    else { printf(#name ": pass\n"); }

int main(void)
{
    int result = 0;
    
    create_test_files();

    EXEC_TEST(test_file_map_read);
    EXEC_TEST(test_file_map_write);
    EXEC_TEST(test_file_getdlim);
    EXEC_TEST(test_file_symlink);
    EXEC_TEST(test_file_sendfile);

    return result;
}