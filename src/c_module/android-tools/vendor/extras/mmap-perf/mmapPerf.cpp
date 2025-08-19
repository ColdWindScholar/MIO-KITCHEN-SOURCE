#include <benchmark/benchmark.h>

#include <string>
#include <cstring>
#include <cstdlib>
#include <cstdio>
#include <iostream>
#include <vector>
#include <tuple>

#include <unistd.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <sys/mman.h>

using namespace std;
static const size_t pageSize = getpagesize();
static size_t fsize = 1024 * (1ull << 20);
static size_t pagesTotal = fsize / pageSize;

class Fd {
    int m_fd = -1;
public:
    int get() { return m_fd; }
    void set(int fd) { m_fd = fd; }
    Fd() {}
    explicit Fd(int fd) : m_fd{fd} {}
    ~Fd() {
        if (m_fd >= 0)
            close(m_fd);
    }
};

int dummy = 0;

void fillPageJunk(void *ptr)
{
    uint64_t seed = (unsigned long long)rand() | ((unsigned long long)rand() << 32);
    uint64_t *target = (uint64_t*)ptr;
    for (int i = 0; i < pageSize / sizeof(uint64_t); i++) {
        *target = seed ^ (uint64_t)(uintptr_t)target;
        seed = (seed << 1) | ((seed >> 63) & 1);
        target++;
    }
}

class FileMap {
    string m_name;
    size_t m_size;
    void *m_ptr = nullptr;
    Fd m_fileFd;
public:
    enum Hint {
       FILE_MAP_HINT_NONE,
       FILE_MAP_HINT_RAND,
       FILE_MAP_HINT_LINEAR,
    };
    FileMap(const string &name, size_t size, Hint hint = FILE_MAP_HINT_NONE) : m_name{name}, m_size{size} {
        int fd = open(name.c_str(), O_CREAT | O_RDWR, S_IRWXU);
        if (fd < 0) {
            cout << "Error: open failed for " << name << ": " << strerror(errno) << endl;
            exit(1);
        }
        m_fileFd.set(fd);
        fallocate(m_fileFd.get(), 0, 0, size);
        unlink(name.c_str());
        m_ptr = mmap(nullptr, size, PROT_READ | PROT_WRITE, MAP_SHARED, m_fileFd.get(), 0);
        if ((int)(uintptr_t)m_ptr == -1) {
            cout << "Error: mmap failed: " << (int)(uintptr_t)m_ptr << ": " << strerror(errno) << endl;
            exit(1);
        }
        switch (hint) {
        case FILE_MAP_HINT_NONE: break;
        case FILE_MAP_HINT_RAND:
            madvise(m_ptr, m_size, MADV_RANDOM);
            break;
        case FILE_MAP_HINT_LINEAR:
            madvise(m_ptr, m_size, MADV_SEQUENTIAL);
            break;
        }
        for (int i = 0; i < m_size / pageSize; i++) {
            uint8_t *targetPtr = (uint8_t*)m_ptr + 4096ull * i;
            fillPageJunk(targetPtr);
        }
    }
    void benchRandomRead(unsigned int targetPage) {
        uint8_t *targetPtr = (uint8_t*)m_ptr + pageSize * targetPage;
        dummy += *targetPtr;
    }
    void benchRandomWrite(unsigned int targetPage) {
        uint8_t *targetPtr = (uint8_t*)m_ptr + pageSize * targetPage;
        *targetPtr = dummy;
    }
    void benchLinearRead(unsigned int j) {
        uint8_t *targetPtr = (uint8_t*)m_ptr + pageSize * j;
        dummy += *targetPtr;
    }
    void benchLinearWrite(unsigned int j) {
        uint8_t *targetPtr = (uint8_t*)m_ptr + pageSize * j;
        *targetPtr = dummy;
    }
    void dropCache() {
        int ret1 = msync(m_ptr, m_size, MS_SYNC | MS_INVALIDATE);
        madvise(m_ptr, m_size, MADV_DONTNEED);
        (void)ret1;
    }
    ~FileMap() {
        if (m_ptr)
            munmap(m_ptr, m_size);
    }

};

static void benchRandomRead(benchmark::State& state) {
    FileMap file{"/data/local/tmp/mmap_test", fsize};
    while (state.KeepRunning()) {
        unsigned int targetPage = rand() % pagesTotal;
        file.benchRandomRead(targetPage);
    }
    state.SetBytesProcessed(state.iterations() * pageSize);
}
BENCHMARK(benchRandomRead);

static void benchRandomWrite(benchmark::State& state) {
    FileMap file{"/data/local/tmp/mmap_test", fsize};
    while (state.KeepRunning()) {
        unsigned int targetPage = rand() % pagesTotal;
        file.benchRandomWrite(targetPage);
    }
    state.SetBytesProcessed(state.iterations() * pageSize);
}
BENCHMARK(benchRandomWrite);

static void benchLinearRead(benchmark::State& state) {
   FileMap file{"/data/local/tmp/mmap_test", fsize};
   unsigned int j = 0;
   while (state.KeepRunning()) {
       file.benchLinearRead(j);
       j = (j + 1) % pagesTotal;
   }
   state.SetBytesProcessed(state.iterations() * pageSize);
}
BENCHMARK(benchLinearRead);

static void benchLinearWrite(benchmark::State& state) {
   FileMap file{"/data/local/tmp/mmap_test", fsize};
   unsigned int j = 0;
   while (state.KeepRunning()) {
       file.benchLinearWrite(j);
       j = (j + 1) % pagesTotal;
   }
   state.SetBytesProcessed(state.iterations() * pageSize);
}
BENCHMARK(benchLinearWrite);

BENCHMARK_MAIN();
