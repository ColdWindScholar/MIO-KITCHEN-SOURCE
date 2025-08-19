
void f1() {
  for (volatile int i = 0; i < 100; i++) {
  }
}

void f2() {
  for (volatile int i = 0; i < 1000; i++) {
  }
}

int main() {
  for (volatile int i = 0; i < 10; i++) {
    if (i * 3 < 6) {
      f1();
    } else {
      f2();
    }
  }
}
