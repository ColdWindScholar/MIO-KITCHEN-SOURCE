constexpr int LOOP_COUNT = 5000000;

void FunctionRecursiveTwo(int loop);

void FunctionRecursiveOne(int loop) {
  for (volatile int i = 0; i < LOOP_COUNT; ++i) {
  }
  if (loop >= 0) {
    FunctionRecursiveTwo(loop);
  }
}

void FunctionRecursiveTwo(int loop) {
  for (volatile int i = 0; i < LOOP_COUNT; ++i) {
  }
  if (loop > 0) {
    FunctionRecursiveOne(loop - 1);
  }
}

int main() {
  while (true) {
    FunctionRecursiveOne(10);
  }
  return 0;
}
