#include <sys/prctl.h>

constexpr int LOOP_COUNT = 100000000;

void Function1() {
  for (volatile int i = 0; i < LOOP_COUNT; ++i) {
  }
}

int main() {
  // Run the test in an infinite loop, so if we profile the test manually, the process
  // doesn't exit before we attach to it. This scheme also allows simpleperf to control
  // how long to profile.
  while (true) {
    prctl(PR_SET_NAME, reinterpret_cast<unsigned long>("RUN_COMM1"), 0, 0, 0);  // NOLINT
    Function1();
    prctl(PR_SET_NAME, reinterpret_cast<unsigned long>("RUN_COMM2"), 0, 0, 0);  // NOLINT
    Function1();
  }
  return 0;
}
