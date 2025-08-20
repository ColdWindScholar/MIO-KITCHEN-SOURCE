#include_next <io.h>

#undef creat

#define creat(path, mode) _open(path, O_TRUNC | O_RDWR | O_CREAT, mode)
