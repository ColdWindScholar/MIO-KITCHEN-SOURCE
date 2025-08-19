#ifndef _SYS_KEXEC_H
#define _SYS_KEXEC_H

#include <linux/kexec.h>
#include <sys/cdefs.h>
#include <sys/syscall.h>
#include <unistd.h>
#include "kexec.h"

#define KEXEC_SEGMENT_MAX 16

#define KEXEC_TYPE_DEFAULT 0
#define KEXEC_TYPE_CRASH 1

/*
 * Prototypes
 */

static inline long kexec_load(unsigned int entry, unsigned long nr_segments,
                              struct kexec_segment* segment, unsigned long flags) {
    return syscall(__NR_kexec_load, entry, nr_segments, segment, flags);
}

#endif /* _SYS_KEXEC_H */
