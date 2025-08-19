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

using namespace std;

#define BUFFER_SIZE (1024 * 1024 * 1024)

int main(int, char**) {
    volatile void* src = malloc(BUFFER_SIZE);
    for (size_t i = 0; i < BUFFER_SIZE; i++) {
        ((char*)src)[i] = (char)i;
    }
    volatile void* dst = malloc(BUFFER_SIZE);
    while (true) {
        for (size_t i = 0; i < BUFFER_SIZE; i++) {
            ((char*)dst)[i] = ((char*)src)[i];
        }
    }
    return 0;
}
