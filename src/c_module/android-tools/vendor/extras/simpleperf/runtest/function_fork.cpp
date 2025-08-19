#include <stdlib.h>
#include <sys/wait.h>
#include <unistd.h>

constexpr int LOOP_COUNT = 100000000;

volatile int a[2];
void ParentFunction() {
  volatile int* p = a + atoi("0");
  for (int i = 0; i < LOOP_COUNT; ++i) {
    *p = i;
  }
}

void ChildFunction() {
  volatile int* p = a + atoi("1");
  for (int i = 0; i < LOOP_COUNT; ++i) {
    *p = i;
  }
}

int main() {
  while (true) {
    pid_t pid = fork();
    if (pid == 0) {
      ChildFunction();
      return 0;
    } else {
      ParentFunction();
      waitpid(pid, nullptr, 0);
    }
  }
  return 0;
}
