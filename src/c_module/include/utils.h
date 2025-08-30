//
// Created by ColdWindScholar on 2025/8/20.
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
    char * part_name;
} extract_args_struct;
typedef struct {
    char * block_list;// a file
    char * basefs_out;// a file
    long int timestamp;
    char * fs_config;
    char * file_contexts;
    char * product_out;// a file
    char * mountpoint;
    char * basefs_in;//a file
    char * src_dir;
    bool android_sparse_file;// e //
    char * uid_mapping;
    char * gid_mapping;
    char * image;
    bool is_share_dup;
} e2fsdroid_args_struct;
#endif //C_MODULE_UTILS_H