#include <fcntl.h>
#include <linux/fs.h>
#include <sys/stat.h>
#include <sys/swap.h>
#include <sys/types.h>
#include <unistd.h>
#include <chrono>
#include <iostream>
#include <numeric>
#include <vector>

using namespace std;

static const size_t kPageSize = sysconf(_SC_PAGESIZE);
static constexpr char kZramBlkdevPath[] = "/dev/block/zram0";
static constexpr size_t kPatternSize = 4;
static constexpr size_t kSectorSize = 512;

void fillPageRand(uint32_t *page) {
    uint32_t start = rand();
    for (int i = 0; i < kPageSize / sizeof(start); i++) {
        page[i] = start+i;
    }
}
void fillPageCompressible(void* page) {
    uint32_t val = rand() & 0xfff;
    auto page_ptr = reinterpret_cast<typeof(val)*>(page);
    std::vector<typeof(val)> pattern(kPatternSize, 0);

    for (auto i = 0u; i < kPatternSize; i++) {
        pattern[i] = val + i;
    }
    // fill in ABCD... pattern
    for (int i = 0; i < kPageSize / sizeof(val); i += kPatternSize) {
        std::copy_n(pattern.data(), kPatternSize, (page_ptr + i));
    }
}

class AlignedAlloc {
    void *m_ptr;
public:
    AlignedAlloc(size_t size, size_t align) {
        posix_memalign(&m_ptr, align, size);
    }
    ~AlignedAlloc() {
        free(m_ptr);
    }
    void *ptr() {
        return m_ptr;
    }
};

class BlockFd {
    int m_fd = -1;
public:
    BlockFd(const char *path, bool direct) {
        m_fd = open(path, O_RDWR | (direct ? O_DIRECT : 0));
    }
    size_t getSize() {
        size_t blockSize = 0;
        int result = ioctl(m_fd, BLKGETSIZE, &blockSize);
        if (result < 0) {
            cout << "ioctl block size failed" << endl;
        }
        return blockSize * kSectorSize;
    }
    ~BlockFd() {
        if (m_fd >= 0) {
            close(m_fd);
        }
    }
    void fillWithCompressible() {
        size_t devSize = getSize();
        AlignedAlloc page(kPageSize, kPageSize);
        for (uint64_t offset = 0; offset < devSize; offset += kPageSize) {
            fillPageCompressible((uint32_t*)page.ptr());
            ssize_t ret = write(m_fd, page.ptr(), kPageSize);
            if (ret != kPageSize) {
                cout << "write() failed" << endl;
            }
        }
    }
    void benchSequentialRead() {
        chrono::time_point<chrono::high_resolution_clock> start, end;
        size_t devSize = getSize();
        size_t passes = 4;
        AlignedAlloc page(kPageSize, kPageSize);

        start = chrono::high_resolution_clock::now();
        for (int i = 0; i < passes; i++) {
            for (uint64_t offset = 0; offset < devSize; offset += kPageSize) {
                if (offset == 0)
                    lseek(m_fd, offset, SEEK_SET);
                ssize_t ret = read(m_fd, page.ptr(), kPageSize);
                if (ret != kPageSize) {
                    cout << "read() failed" << endl;
                }
            }
        }
        end = chrono::high_resolution_clock::now();
        size_t duration = chrono::duration_cast<chrono::microseconds>(end - start).count();
        cout << "read: " << (double)devSize * passes / 1024.0 / 1024.0 / (duration / 1000.0 / 1000.0) << "MB/s" << endl;
    }
    void benchSequentialWrite() {
        chrono::time_point<chrono::high_resolution_clock> start, end;
        size_t devSize = getSize();
        size_t passes = 4;
        AlignedAlloc page(kPageSize, kPageSize);

        start = chrono::high_resolution_clock::now();
        for (int i = 0; i < passes; i++) {
            for (uint64_t offset = 0; offset < devSize; offset += kPageSize) {
                fillPageCompressible((uint32_t*)page.ptr());
                if (offset == 0)
                    lseek(m_fd, offset, SEEK_SET);
                ssize_t ret = write(m_fd, page.ptr(), kPageSize);
                if (ret != kPageSize) {
                    cout << "write() failed" << endl;
                }
            }
        }
        end = chrono::high_resolution_clock::now();
        size_t duration = chrono::duration_cast<chrono::microseconds>(end - start).count();
        cout << "write: " << (double)devSize * passes / 1024.0 / 1024.0 / (duration / 1000.0 / 1000.0) << "MB/s" << endl;

    }
};

int bench(bool direct)
{
    BlockFd zramDev{kZramBlkdevPath, direct};

    zramDev.fillWithCompressible();
    zramDev.benchSequentialRead();
    zramDev.benchSequentialWrite();
    return 0;
}

int main(int argc, char *argv[])
{
    int result = swapoff(kZramBlkdevPath);
    if (result < 0) {
        cout << "swapoff failed: " << strerror(errno) << endl;
    }

    bench(1);

    result = system((string("mkswap ") + string(kZramBlkdevPath)).c_str());
    if (result < 0) {
        cout << "mkswap failed: " <<  strerror(errno) << endl;
        return -1;
    }

    result = swapon(kZramBlkdevPath, 0);
    if (result < 0) {
        cout << "swapon failed: " <<  strerror(errno) << endl;
        return -1;
    }
    return 0;
}
