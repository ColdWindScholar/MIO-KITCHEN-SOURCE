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

#define EIGEN_RUNTIME_NO_MALLOC

#include <Eigen/Dense>

using namespace std;

int main(int, char**) {
    Eigen::MatrixXd a(8192, 8192);
    Eigen::MatrixXd b(8192, 8192);
    Eigen::MatrixXd c(8192, 8192);

    for (int i = 0; i < 8192; i++) {
        for (int j = 0; j < 8192; j++) {
            a(i, j) = 1 + i * j;
            b(i, j) = 2 + i * j;
            c(i, j) = 3 + i * j;
        }
    }

    cout << "starting" << endl;
    while (true) {
        a.noalias() += (b * c);
        b(1, 5) += 5.0;
        c(5, 1) -= 5.0;
    }

    return 0;
}
