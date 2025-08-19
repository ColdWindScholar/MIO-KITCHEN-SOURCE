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

#include <inttypes.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <fec.h>

#define FEC_RSM 255
#define FEC_ROOTS 16
#define FEC_RSN (FEC_RSM - FEC_ROOTS)
#define FEC_PARAMS(roots) \
    8, 0x11d, 0, 1, (roots), 0

int main()
{
    uint8_t data[FEC_RSM];
    uint8_t dupl[FEC_RSM];
    uint8_t corr[FEC_RSM];
    int i, rc, neras, errors;
    int erasures[FEC_RSM];
    void *rs;

    memset(data, 0x00, sizeof(data));
    memset(corr, 0x00, sizeof(corr));

    rs = init_rs_char(FEC_PARAMS(FEC_ROOTS));

    if (!rs) {
        perror("init_rs_char");
        exit(1);
    }

    encode_rs_char(rs, data, &corr[FEC_RSN]);

    for (neras = 1; neras <= FEC_ROOTS; ++neras) {
        printf("%d errors\n", neras);

        for (i = 0; i < neras; ++i) {
            corr[i] = 0xFD;
            erasures[i] = i;
        }

        memcpy(dupl, corr, sizeof(corr));

        rc = decode_rs_char(rs, corr, NULL, 0);

        printf("\tno erasures: %d\n", rc);

        errors = 0;
        for (i = 0; i < FEC_RSN; ++i) {
            if (corr[i] != 0x00) {
                printf("\t\terror at %d (%02x)\n", i, corr[i]);
                ++errors;
            }
        }
        printf("\t\t%d errors in output\n", errors);

        rc = decode_rs_char(rs, dupl, erasures, neras);

        printf("\terasures: %d\n", rc);

        errors = 0;
        for (i = 0; i < FEC_RSN; ++i) {
            if (dupl[i] != 0x00) {
                printf("\t\terror at %d (%02x)\n", i, dupl[i]);
                ++errors;
            }
        }
        printf("\t\t%d errors in output\n", errors);
    }

    exit(0);
}
