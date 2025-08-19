/*
 * Copyright (C) 2022 The Android Open Source Project
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

#include <err.h>
#include <inttypes.h>
#include <stdio.h>

#include "AllocParser.h"

#include <iostream>

void AllocGetData(const std::string& line, AllocEntry* entry) {
    int op_prefix_pos = 0;
    char name[128];
    // All lines have this format:
    //   TID: ALLOCATION_TYPE POINTER
    // where
    //   TID is the thread id of the thread doing the operation.
    //   ALLOCATION_TYPE is one of malloc, calloc, memalign, realloc, free, thread_done
    //   POINTER is the hex value of the actual pointer
    if (sscanf(line.c_str(), "%d: %127s %" SCNx64 " %n", &entry->tid, name, &entry->ptr,
               &op_prefix_pos) != 3) {
        errx(1, "File Error: Failed to process %s", line.c_str());
    }
    std::string type(name);
    if (type == "thread_done") {
        entry->type = THREAD_DONE;
    } else {
        int args_offset = 0;
        const char* args_beg = &line[op_prefix_pos];
        if (type == "malloc") {
            // Format:
            //   TID: malloc POINTER SIZE_OF_ALLOCATION
            if (sscanf(args_beg, "%zu%n", &entry->size, &args_offset) != 1) {
                errx(1, "File Error: Failed to read malloc data %s", line.c_str());
            }
            entry->type = MALLOC;
        } else if (type == "free") {
            // Format:
            //   TID: free POINTER
            entry->type = FREE;
        } else if (type == "calloc") {
            // Format:
            //   TID: calloc POINTER ITEM_COUNT ITEM_SIZE
            if (sscanf(args_beg, "%" SCNd64 " %zu%n", &entry->u.n_elements, &entry->size,
                       &args_offset) != 2) {
                errx(1, "File Error: Failed to read calloc data %s", line.c_str());
            }
            entry->type = CALLOC;
        } else if (type == "realloc") {
            // Format:
            //   TID: realloc POINTER OLD_POINTER NEW_SIZE
            if (sscanf(args_beg, "%" SCNx64 " %zu%n", &entry->u.old_ptr, &entry->size,
                       &args_offset) != 2) {
                errx(1, "File Error: Failed to read realloc data %s", line.c_str());
            }
            entry->type = REALLOC;
        } else if (type == "memalign") {
            // Format:
            //   TID: memalign POINTER ALIGNMENT SIZE
            if (sscanf(args_beg, "%" SCNd64 " %zu%n", &entry->u.align, &entry->size,
                       &args_offset) != 2) {
                errx(1, "File Error: Failed to read memalign data %s", line.c_str());
            }
            entry->type = MEMALIGN;
        } else {
            errx(1, "File Error: Unknown type %s", type.c_str());
        }

        const char* timestamps_beg = &args_beg[args_offset];

        // Timestamps come after the alloc args if present, for example,
        //   TID: malloc POINTER SIZE_OF_ALLOCATION START_TIME END_TIME
        int n_match = sscanf(timestamps_beg, "%" SCNd64 " %" SCNd64, &entry->st, &entry->et);
        if (n_match != EOF && n_match != 2) {
            errx(1, "File Error: Failed to read timestamps %s", line.c_str());
        }
    }
}
