/*
 * Copyright (C) 2015 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include <new>
#include <memory>
#include <fstream>
#include <iostream>
#include <fec/io.h>

using namespace std;
const unsigned bufsize = 2 * 1024 * FEC_BLOCKSIZE;

int main(int argc, char **argv)
{
    if (argc != 3) {
        cerr << "usage: " << argv[0] << " input output" << endl;
        return 1;
    }

    unique_ptr<uint8_t[]> buffer(new (nothrow) uint8_t[bufsize]);

    if (!buffer) {
        cerr << "failed to allocate buffer" << endl;
        return 1;
    }

    fec::io input(argv[1]);

    if (!input) {
        return 1;
    }

    ofstream output(argv[2], ios::binary | ios::trunc);

    if (!output) {
        cerr << "failed to open " << argv[2] << endl;
        return 1;
    }

    ssize_t count;

    do {
        count = input.read(buffer.get(), bufsize);

        if (count == -1) {
            return 1;
        } else if (count > 0) {
            output.write(reinterpret_cast<const char *>(buffer.get()), count);

            if (!output) {
                cerr << "write" << endl;
                return 1;
            }
        }
    } while (count > 0);

    return 0;
}
