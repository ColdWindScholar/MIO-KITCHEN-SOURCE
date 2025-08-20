/*
 * svoboda18 MINGW POSIX functions library
 * @copyright (c) 2022, SaMad SegMane.
 * @link https://svoboda18.tk/
 * All rights reserved.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
 * DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
 * SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
 * CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
 * OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
*/

#ifndef _LIB_NT_H
#define _LIB_NT_H

#include <stdlib.h>
#include <fcntl.h>
#include <errno.h>
#include <dirent.h>
#include <stdio.h>
#include <sys/stat.h>
#include <wtypesbase.h>

#ifdef SVB_DEBUG
#define NT_DEBUG_IMPL(__backtace, __fmt, ...) \
    { \
        if (__backtace) \
            fprintf(stderr, __fmt __VA_OPT__(,) __VA_ARGS__); \
        else \
            fprintf(stderr, "%s:%d:%s: " __fmt "\n", __FILE__, __LINE__, __func__ __VA_OPT__(,) __VA_ARGS__); \
    }
#else
#define NT_DEBUG_IMPL(__backtace, __fmt, ...) \
    { \
		if (!__trace) __trace = orig_fopen(__dname, "ab"); \
		if (__trace) { \
			if (__backtace) \
				fprintf(__trace, __fmt __VA_OPT__(,) ##__VA_ARGS__); \
			else \
				fprintf(__trace, "%s:%d:%s: " __fmt "\n", __FILE__, __LINE__, __func__ __VA_OPT__(,) ##__VA_ARGS__); \
            fflush(__trace); \
		} \
    }
#endif

#define NT_DEBUG(...) NT_DEBUG_IMPL(0, __VA_ARGS__)
#define NT_BACKTRACE(...) NT_DEBUG_IMPL(1, __VA_ARGS__)

#if !defined(O_CLOEXEC) && defined(O_NOINHERIT)
#define O_CLOEXEC O_NOINHERIT
#endif

#define S_ISUID 0
#define S_ISGID 0
#define S_ISVTX 0

#undef S_ISLNK
#define S_IFLNK 0xA000
#define S_ISLNK(m) (((m) & S_IFMT) == S_IFLNK)

#ifdef __cplusplus
extern "C" {
#endif

struct nt_mode_t
{
    char mode[8]; // GNU fopen limts mode to 7 chars
    unsigned int direction;
    unsigned int flags;
};

typedef struct nt_iovec
{
    void *iov_base;
    size_t iov_len;
} iovec;

#ifdef __cplusplus
};
#endif

#ifdef __cplusplus
#define __NT_ATTRIB __attribute__((__always_inline__))
#define __NT_EXTERN extern "C"
#else
#define __NT_ATTRIB __attribute__((__gnu_inline__, __always_inline__))
#define __NT_EXTERN extern
#endif

#define __NT_CON static __attribute__((constructor))
#define __NT_INLINE static inline __NT_ATTRIB
#define __NT_DCL __cdecl

#ifndef SVB_DEBUG
static FILE *__trace;
static char __dname[PATH_MAX];
#endif

__NT_INLINE FILE *__NT_DCL orig_fdopen(int fd, const char *mode)
{
    return fdopen(fd, mode);
}

__NT_INLINE FILE *__NT_DCL orig_fopen(const char *path, const char *mode)
{
    return fopen(path, mode);
}

#define strlcpy strncpy
#define fopen fopen2
#define fdopen fdopen2

__NT_EXTERN int map_nt_error(const DWORD err);

__NT_EXTERN int __NT_DCL set_path_timestamp(const char* path, time_t atime, time_t mtime, time_t ctime);

__NT_EXTERN int __NT_DCL scandir(const char *dir_name, struct dirent ***name_list, int (*filter)(const struct dirent *), int (*compar)(const struct dirent **, const struct dirent **));
__NT_EXTERN int __NT_DCL alphasort(const struct dirent **a, const struct dirent **b);

__NT_EXTERN FILE *__NT_DCL fopen2(const char *filename, const char *mode);
__NT_EXTERN FILE *__NT_DCL fdopen2(int fd, const char *mode);
__NT_EXTERN ssize_t __NT_DCL sendfile(int out_fd, int in_fd, off_t *offset, size_t count);

__NT_EXTERN int __NT_DCL lstat_t(const char *pathname, stat_t *statbuf);
__NT_INLINE int __NT_DCL lstat(const char *__path, struct stat *__buf) {
    stat_t __st;
    /* set all __buf members to 0 as some memebers of stat_t
       does not have same type as/exist in struct stat */
    memset(__buf, 0, sizeof(struct stat));

    int __ret = lstat_t(__path, &__st);
    if (__ret)
        return __ret;
#define C(x) __buf->st_##x = __st.st_##x;
    C(dev)
    C(mode)
    C(nlink)
    C(uid)
    C(gid)
    C(rdev)
    C(size)
    C(atime)
    C(mtime)
    C(ctime)
#undef C
    return __ret;
}
__NT_EXTERN ssize_t __NT_DCL readlink(const char *pathname, char *buf, size_t bufsiz);
__NT_EXTERN int __NT_DCL symlink(const char *target, const char *file);

__NT_EXTERN ssize_t __NT_DCL getdelim(char **buf, size_t *bufsiz, int delimiter, FILE *fp);
__NT_EXTERN ssize_t __NT_DCL getline(char **buf, size_t *bufsiz, FILE *fp);

__NT_EXTERN void *__NT_DCL memmem(const void *haystack, size_t haystack_len, const void *const needle, const size_t needle_len);

__NT_EXTERN ssize_t __NT_DCL readv(int fd, const iovec *iov, int iov_cnt);
__NT_EXTERN ssize_t __NT_DCL writev(int fd, const iovec *iov, int iov_cnt);
#endif /* _LIB_NT_H */
