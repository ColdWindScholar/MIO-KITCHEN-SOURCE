#include <arpa/inet.h>
#include <cutils/sockets.h>
#include <fcntl.h>
#include <hardware/gralloc.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
#include <algorithm>
#include <chrono>
#include <fstream>
#include <iostream>
#include <numeric>
#include <string>
#include <tuple>
#include <vector>

#include <android-base/stringprintf.h>
#include <meminfo/procmeminfo.h>

using namespace std;

#define BUFFER_SIZE (1024 * 1024 * 1024)

int main(int, char**) {
    // waste a bunch of memory
    void* src = malloc(BUFFER_SIZE);
    for (size_t i = 0; i < BUFFER_SIZE; i++) {
        ((char*)src)[i] = (char)i;
    }
    void* dst = malloc(BUFFER_SIZE);
    memcpy(dst, src, BUFFER_SIZE);

    uint64_t pss;
    // should always return true
    std::string pid_path = android::base::StringPrintf("/proc/%d/smaps", getpid());
    while (android::meminfo::SmapsOrRollupPssFromFile(pid_path, &pss))
        ;

    return 0;
}
