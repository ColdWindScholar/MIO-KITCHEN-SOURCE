/*
 * sys/mman.h
 * mman-win32
 */

#ifndef _SYS_MMAN_H_
#define _SYS_MMAN_H_

#include <sys/types.h>

#include "libnt.h"

#ifdef __cplusplus
extern "C" {
#endif

#define PROT_NONE       0
#define PROT_READ       1
#define PROT_WRITE      2
#define PROT_EXEC       4

#define MAP_FILE        0
#define MAP_SHARED      1
#define MAP_PRIVATE     2
#define MAP_TYPE        0xf
#define MAP_FIXED       0x10
#define MAP_ANONYMOUS   0x20
#define MAP_ANON        MAP_ANONYMOUS

#define MAP_FAILED      ((void *)-1)

__NT_EXTERN void* __NT_DCL mmap(void *addr, size_t len, int prot, int flags, int fildes, off64_t off);
__NT_EXTERN int __NT_DCL munmap(void *addr, size_t len);

#ifdef __cplusplus
}
#endif

#endif /*  _SYS_MMAN_H_ */
