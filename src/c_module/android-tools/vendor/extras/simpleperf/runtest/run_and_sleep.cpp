#include <inttypes.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#define noinline __attribute__((__noinline__))

static inline uint64_t GetSystemClock() {
  timespec ts;
  // Assume clock_gettime() doesn't fail.
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return ts.tv_sec * 1000000000ULL + ts.tv_nsec;
}

constexpr int LOOP_COUNT = 100000000;
uint64_t noinline RunFunction() {
  uint64_t start_time_in_ns = GetSystemClock();
  for (volatile int i = 0; i < LOOP_COUNT; ++i) {
  }
  return GetSystemClock() - start_time_in_ns;
}

uint64_t noinline SleepFunction(unsigned long long sleep_time_in_ns) {
  uint64_t start_time_in_ns = GetSystemClock();
  struct timespec req;
  req.tv_sec = sleep_time_in_ns / 1000000000;
  req.tv_nsec = sleep_time_in_ns % 1000000000;
  nanosleep(&req, nullptr);
  return GetSystemClock() - start_time_in_ns;
}

void noinline GlobalFunction() {
  uint64_t total_sleep_time_in_ns = 0;
  uint64_t total_run_time_in_ns = 0;
  while (true) {
    total_run_time_in_ns += RunFunction();
    if (total_sleep_time_in_ns < total_run_time_in_ns) {
      total_sleep_time_in_ns += SleepFunction(total_run_time_in_ns - total_sleep_time_in_ns);
    }
  }
}

int main() {
  GlobalFunction();
  return 0;
}
