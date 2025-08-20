//
// Created by xzz on 2025/8/20.
//
#pragma once
#include <stdbool.h>
#ifndef C_MODULE_UTILS_H
#define C_MODULE_UTILS_H
typedef struct {
    char * config_dir;
    char * mountpoint;
    char * filename;
    char * directory;
    char * image_type;
    int blocksize;
    bool android_configure_only;
} extract_args_struct;
#endif //C_MODULE_UTILS_H