#include <stdlib.h>

constexpr int LOOP_COUNT = 100000000;

volatile int a[2];
void Function1() {
  volatile int* p = a + atoi("0");
  for (int i = 0; i < LOOP_COUNT; ++i) {
    *p = i;
  }
}

void Function2() {
  volatile int* p = a + atoi("1");
  for (int i = 0; i < LOOP_COUNT; ++i) {
    *p = i;
  }
}

int main() {
  while (true) {
    Function1();
    Function2();
  }
  return 0;
}
