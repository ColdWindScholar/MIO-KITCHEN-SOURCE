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
#define _POSIX 1

#include "libnt.h"

#include <stdint.h>
#include <unistd.h>
#include <assert.h>
#include <io.h>
#include <dos.h>
#include <wchar.h>
#include <signal.h>
#include <windows.h>
#include <imagehlp.h>
#include <pthread.h>

/* Crashing and reporting backtrace. */
#define INV "INVALID"
static const char *signame[] =
    {INV,
     "SIGHUP", "SIGINT", "SIGQUIT", "SIGILL", "SIGTRAP",
     "SIGIOT", "SIGEMT", "SIGFPE", "SIGKILL", "SIGBUS",
     "SIGSEGV", "SIGSYS", "SIGPIPE", "SIGALRM", "SIGTERM",
     INV, INV, INV, INV, INV,
     "SIGBREAK", "SIGABRT", NULL};

static int signal_sig, dl_error = 0;
static LPTOP_LEVEL_EXCEPTION_FILTER prev_exception_handler;

static DWORD except_code;
static PVOID except_addr;

#define BACKTRACE_LIMIT_MAX 62

typedef struct
{
    const char *dli_fname;    /* Pathname of shared object containing address */
    void *dli_fbase;          /* Address at which shared object is loaded */
    const char *dli_sname;    /* Name of nearest symbol with lower address */
    void *dli_saddr;          /* Exact address of symbol named dli_sname */
    const char *dli_sfname;   /* Source file name of the nearest symbol */
    void *dli_sfaddr;         /* Exact address of start of line named dli_sfname */
    unsigned long dli_sfline; /* Line of the Source file */
} Dl_info;

int __NT_DCL map_nt_error(const DWORD err)
{
    switch (err)
    {
    case ERROR_ALREADY_EXISTS:
    case ERROR_FILE_EXISTS:
        return EEXIST;
    case ERROR_INVALID_FUNCTION:
        return ENOSYS;
    case ERROR_FILE_NOT_FOUND:
    case ERROR_PATH_NOT_FOUND:
        return ENOENT;
    case ERROR_TOO_MANY_OPEN_FILES:
        return EMFILE;
    case ERROR_INVALID_HANDLE:
        return EBADF;
    case ERROR_NOT_ENOUGH_MEMORY:
    case ERROR_COMMITMENT_LIMIT:
    case ERROR_OUTOFMEMORY:
    case ERROR_NO_SYSTEM_RESOURCES:
        return ENOMEM;
    case ERROR_ACCESS_DENIED:
    case ERROR_INVALID_ACCESS:
    case ERROR_SHARING_VIOLATION:
    case ERROR_LOCK_VIOLATION:
        return EACCES;
    case ERROR_INVALID_DRIVE:
        return ENXIO;
    case ERROR_NOT_SAME_DEVICE:
        return EXDEV;
    case ERROR_NO_MORE_FILES:
        return ENFILE;
    case ERROR_WRITE_PROTECT:
    case ERROR_CANT_OPEN_ANONYMOUS: /* Can't open anonymous token */
        return EPERM;
    case ERROR_NOT_SUPPORTED:
        return ENOSYS;
    case ERROR_DISK_FULL:
        return ENOSPC;
    case ERROR_BROKEN_PIPE:
    case ERROR_NO_DATA:
        return EPIPE;
    case ERROR_INVALID_NAME:      /* Invalid syntax in filename */
    case ERROR_INVALID_PARAMETER: /* Invalid function parameter */
    case ERROR_BAD_PATHNAME:      /* Invalid pathname */
        return EINVAL;
    case ERROR_DIRECTORY: /* "Directory name is invalid" */
        return ENOTDIR;   /* Seems the closest mapping */
    case WSAENOTSOCK:     /* For fstat() calls */
        return ENOTSOCK;
    case ERROR_INVALID_ADDRESS:
    case ERROR_INVALID_USER_BUFFER:
        return EFAULT;
    case ERROR_IO_PENDING: /* System call "interrupted" by signal */
        return EINTR;
    /*
     * The following remapped because their number is in the POSIX range
     */
    case ERROR_ARENA_TRASHED:
        return EFAULT;
    case ERROR_INVALID_BLOCK:
        return EIO;
    case ERROR_BAD_ENVIRONMENT:
        return EFAULT;
    case ERROR_BAD_FORMAT:
        return EINVAL;
    case ERROR_INVALID_DATA:
        return EIO;
    case ERROR_CURRENT_DIRECTORY:
        return ENOFILE;
    case ERROR_BAD_UNIT:
    case ERROR_BAD_DEVICE:
    case ERROR_NOT_READY: /* No disk "in" the letter drive */
        return ENODEV;
    case ERROR_BAD_COMMAND:
    case ERROR_CRC:
    case ERROR_BAD_LENGTH:
    case ERROR_SEEK:
    case ERROR_NOT_DOS_DISK:
    case ERROR_SECTOR_NOT_FOUND:
    case ERROR_GEN_FAILURE:
    case ERROR_WRONG_DISK:
    case ERROR_SHARING_BUFFER_EXCEEDED:
    case ERROR_DEVICE_REMOVED:
        return EIO;
    case ERROR_OUT_OF_PAPER:
        return ENOSPC;
    case ERROR_WRITE_FAULT:
    case ERROR_READ_FAULT:
    case ERROR_NOACCESS: /* Invalid access to memory location */
        return EFAULT;
    case ERROR_HANDLE_EOF:
        return 0; /* EOF must be treated as a read of 0 bytes */
    case ERROR_HANDLE_DISK_FULL:
        return ENOSPC;
    case ERROR_ENVVAR_NOT_FOUND:
        /* Got this error writing to a closed stdio fd, opened via pipe() */
        return EBADF;
    case ERROR_BAD_EXE_FORMAT:
        return ENOEXEC;
    case ERROR_NETNAME_DELETED:
        return EHOSTUNREACH;
    case ERROR_NO_TOKEN:
        return ESRCH;
    case 0: /* Always indicates success */
        return 0;
    default:
        printf("Windows error code %lu (%s) not remapped to a POSIX one",
               err, strerror(err));
    }

    return err;
}

static int inline backtrace(void **buffer, int limit)
{
    return RtlCaptureStackBackTrace(5, min(BACKTRACE_LIMIT_MAX, limit), buffer,
                                    NULL);
}

static int dladdr(void *addr, Dl_info *info)
{
    static unsigned int initialized;

    static pthread_mutex_t dladdr_lk = PTHREAD_MUTEX_INITIALIZER;
    static pthread_spinlock_t dladdr_slk = -1;

    char path[PATH_MAX];
    IMAGEHLP_SYMBOL64 symbolInfo;
    IMAGEHLP_LINE64 symbolLine;

    int error = 0;
    HANDLE process = NULL;
    DWORD64 dldisp = 0;

    /* ZERO info struct before doing anything */
    memset(info, 0, sizeof(Dl_info));

    /* if we FAIL once, we keep FAILLING */
    if (dl_error || !addr)
        return 0;

    process = GetCurrentProcess();

    /*
     * When called during a crash, do not attempt to refresh the symbols via
     * a SymCleanup() / SymInitialize(): use the symbols we already have.
     *
     * However, if we never initialized them, then do so regardless of whether
     * we are crashing.
     */
    if (!initialized)
    {
        static unsigned int first_init;
        static pthread_spinlock_t dladdr_first_slk = -1;
        unsigned int is_first = FALSE;

        pthread_spin_lock(&dladdr_first_slk);
        if (!first_init)
        {
            is_first = TRUE;
            first_init = TRUE;
        }
        pthread_spin_unlock(&dladdr_first_slk);

        if (is_first)
        {
            pthread_mutex_lock(&dladdr_lk);
        }
        else
        {
            if (!pthread_mutex_trylock(&dladdr_lk))
                goto skip_init;
        }

        if (initialized)
            SymCleanup(process);

        SymSetOptions(SymGetOptions() | SYMOPT_LOAD_LINES);

        if (!SymInitialize(process, NULL, TRUE))
        {
            error = dl_error = GetLastError();
            fprintf(stderr, "%s(): SymInitialize() failed: error = %d (%s)", __func__,
                    dl_error, strerror(dl_error));
        }
        else
        {
            pthread_spin_lock(&dladdr_slk);
            initialized = TRUE;
            pthread_spin_unlock(&dladdr_slk);
        }

        pthread_mutex_unlock(&dladdr_lk);
    }

skip_init:
    /* in case of SymInitialize FAILUARE */
    if (error)
        return 0;

    info->dli_fbase = (void *)(SymGetModuleBase(process, (uint64_t)(addr)));

    if (!info->dli_fbase)
    {
        dl_error = GetLastError();
        return 0; /* Unknown, error */
    }

    /*
     * A spinlock is OK to protect the critical section below because we're
     * not expecting any recursion: the routines we call out should not
     * allocate memory nor create assertion failures (which would definitely
     * create recursion to dump the stack!).
     *
     * Note that path or symbol name information are returned in a private
     * buffer so that two threads can concurrently request dladdr() and yet
     * be able to get their own results back.
     */

    pthread_spin_lock(&dladdr_slk); /* Protect access to static vars */

    if (GetModuleFileNameA((HINSTANCE)info->dli_fbase, path, sizeof(path) / sizeof(char)))
    {
        info->dli_fname = strdup(path);
    }

    symbolInfo.SizeOfStruct = sizeof(IMAGEHLP_SYMBOL64);
    symbolInfo.MaxNameLength = PATH_MAX;

    /*
     * The SymGetSymFromAddr() is mono-threaded, as explained on MSDN,
     * but we're running under spinlock protection.
     */

    if (SymGetSymFromAddr64(process, (DWORD64)addr, &dldisp, &symbolInfo))
    {
        info->dli_sname = strdup(symbolInfo.Name);
        info->dli_saddr = (char *)addr - dldisp;
    }

    symbolLine.SizeOfStruct = sizeof(IMAGEHLP_LINE64);

    if (SymGetLineFromAddr64(process, (DWORD64)addr, &dldisp, &symbolLine))
    {
        info->dli_sfname = strdup(symbolLine.FileName);
        info->dli_sfline = symbolLine.LineNumber;
        info->dli_sfaddr = (char *)addr - dldisp;
    }

    pthread_spin_unlock(&dladdr_slk);

    /*
     * Windows offsets the actual loading of the text by MINGW_TEXT_OFFSET
     * bytes, as determined empirically.
     */

    info->dli_fbase = (char *)info->dli_fbase + 0x1000;
    return 1; /* OK */
}

static void write_backtrace(void)
{
    void *stack[BACKTRACE_LIMIT_MAX] = {NULL};

    if (!backtrace(stack, BACKTRACE_LIMIT_MAX))
        return;

    if (except_addr)
    {
        NT_BACKTRACE("Exception 0x%x at this address: %p\n",
                     (unsigned int)except_code, except_addr);
    }
    else if (signal_sig)
    {
        fprintf(stderr, "Recieved %s (%d) signal at 0x%p\n", signame[signal_sig],
                signal_sig, stack[0]);
        NT_BACKTRACE("Recieved %s (%d) signal at 0x%p\n", signame[signal_sig], signal_sig, stack[0]);
    }

    NT_BACKTRACE("\nBacktrace:\n");
    for (int i = 0; stack[i]; ++i)
    {
        Dl_info info;
#define NODATA "<nodata>"
        int ret = dladdr(stack[i], &info);
        if (!ret || dl_error)
        {
            NT_BACKTRACE("%d:%-*sat %p\n", i, i > 9 ? 1 : 2, "", stack[i]);
            continue;
        }

        const char *srcfile = info.dli_sfname ?: NODATA;
        char *srcfilename = strrchr(srcfile, '\\');
        if (srcfilename)
        {
            srcfile = srcfilename + 1;
        }
        NT_BACKTRACE("%d:%-*sin %s(%p): at %s<%lu> in %s (at %p starts at: %p)\n",
                     i, i > 9 ? 1 : 2, "",
                     info.dli_fname ? strrchr(info.dli_fname, '\\') + 1 : NODATA,
                     info.dli_fbase, info.dli_sname ?: NODATA, info.dli_sfline,
                     srcfile,
                     info.dli_sfaddr,
                     info.dli_saddr);
    }
}

static void signal_handler(int sig)
{
    static pthread_mutex_t sig_lk = PTHREAD_MUTEX_INITIALIZER;

    pthread_mutex_lock(&sig_lk);
    signal_sig = sig;
    write_backtrace();
    pthread_mutex_unlock(&sig_lk);
    exit(sig);
}

static LONG CALLBACK exception_handler(EXCEPTION_POINTERS *exception_data)
{
    except_code = exception_data->ExceptionRecord->ExceptionCode;
    except_addr = exception_data->ExceptionRecord->ExceptionAddress;

    write_backtrace();

    if (prev_exception_handler)
    {
        return prev_exception_handler(exception_data);
    }
    return EXCEPTION_EXECUTE_HANDLER;
}

static inline void WINAPI invalid_parameter_handler(const wchar_t *expression,
                                                    const wchar_t *function,
                                                    const wchar_t *file,
                                                    unsigned int line,
                                                    uintptr_t pReserved)
{
    (void)pReserved;

    wprintf(L"libnt:invalid_parameter %s in %s %s:%d\r\n", expression, function, file, line);
    abort();
}

static void EnableCrashingOnCrashes(void)
{
#ifndef EXCEPTION_SWALLOWING
#define EXCEPTION_SWALLOWING (0x1)
#endif
    typedef BOOL(WINAPI * tGetPolicy)(LPDWORD lpFlags);
    typedef BOOL(WINAPI * tSetPolicy)(DWORD dwFlags);

    const HMODULE kernel32 = LoadLibraryA("kernel32.dll");
    const tGetPolicy pGetPolicy = (tGetPolicy)GetProcAddress(kernel32, "GetProcessUserModeExceptionPolicy");
    const tSetPolicy pSetPolicy = (tSetPolicy)GetProcAddress(kernel32, "SetProcessUserModeExceptionPolicy");

    if (!pGetPolicy || !pSetPolicy)
        return;

    DWORD dwFlags;
    if (pGetPolicy(&dwFlags))
        pSetPolicy(dwFlags & ~EXCEPTION_SWALLOWING);
}

static BOOL PreventSetUnhandledExceptionFilter(void)
{
    unsigned char buf[sizeof(void *) + 1] = {0xE9};

    int64_t ptrRelativeAddr = (int64_t)&exception_handler -
                              (int64_t)&SetUnhandledExceptionFilter + 5;

    memcpy(&buf[1], &ptrRelativeAddr, sizeof(void *));
    return WriteProcessMemory(GetCurrentProcess(), (void *)&SetUnhandledExceptionFilter, buf,
                              sizeof(void *) + 1, NULL);
}

#ifndef SVB_DEBUG
static void __NT_DCL nt_late_exit(void)
{
    fclose(__trace);
}
#endif

__NT_CON void __NT_DCL nt_early_init(void)
{
    int fmode;
#ifndef SVB_DEBUG
    snprintf(__dname, PATH_MAX - 1, "%s\\debug_nt", getenv("TEMP") ?: ".");
    unlink(__dname);
    atexit(&nt_late_exit);
    NT_DEBUG("Configured debug file: %s", __dname);
#endif

    // always use BINARY mode as TEXT mode will report incorrect file length and it will
    // append an extra byte 0x0D (\r) to every 0x0A (\n) read/write, which may result in corrupted I/O operations
    NT_DEBUG("Set I/O mode to BINARY");
    _set_fmode(O_BINARY);

    _get_fmode(&fmode);
    NT_DEBUG("I/O mode: %s", fmode == O_BINARY ? "BINARY" : "TEXT");
#define BINARY_MODE(FILE)                            \
    {                                                \
        if (_setmode(_fileno(FILE), O_BINARY) != -1) \
            NT_DEBUG("Set BINARY I/O: %s", #FILE);    \
    }

    BINARY_MODE(stdin)
    BINARY_MODE(stdout)
    BINARY_MODE(stderr)
#undef BINARY_MODE
    // Disable any Windows pop-up on crash or file access error
    NT_DEBUG("Disable Windows crash pop-up");
    SetErrorMode(SEM_NOOPENFILEERRORBOX | SEM_NOGPFAULTERRORBOX |
                 SEM_FAILCRITICALERRORS);

    NT_DEBUG("Enable Crash notify");
    EnableCrashingOnCrashes();

    NT_DEBUG("Configure invalid parameter handler");
    _set_invalid_parameter_handler(invalid_parameter_handler);

    NT_DEBUG("Configure abort behavior");
    _set_abort_behavior(0, 0);

    NT_DEBUG("Configure exception handler");
    SetUnhandledExceptionFilter(exception_handler);

    if (PreventSetUnhandledExceptionFilter())
        NT_DEBUG("Locked exception handler");

    NT_DEBUG("Configure signal handler");
    signal(SIGSEGV, signal_handler);
    signal(SIGTRAP, signal_handler);
}

void UnixTimeToFileTime(time_t t, FILETIME *ft)
{
    // Convert Unix time to Windows FILETIME
    LONGLONG ll = Int32x32To64(t, 10000000) + 116444736000000000;
    ft->dwLowDateTime = (DWORD)ll;
    ft->dwHighDateTime = ll >> 32;
}

int __NT_DCL set_path_timestamp(const char *path, time_t atime, time_t mtime, time_t ctime)
{
    FILETIME ftCreate, ftAccess, ftWrite;
    HANDLE hFile = CreateFileA(path, GENERIC_WRITE, 0, NULL, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, NULL);
    if (hFile == INVALID_HANDLE_VALUE)
    {
        errno = map_nt_error(GetLastError());
        return 1;
    }

    UnixTimeToFileTime(ctime, &ftCreate);
    UnixTimeToFileTime(atime, &ftAccess);
    UnixTimeToFileTime(mtime, &ftWrite);

    if (!SetFileTime(hFile, &ftCreate, &ftAccess, &ftWrite))
    {
        errno = map_nt_error(GetLastError());
        return 1;
    }

    CloseHandle(hFile);
    return 0;
}

int __NT_DCL scandir(const char *dir_name, struct dirent ***name_list, int (*filter)(const struct dirent *), int (*compar)(const struct dirent **, const struct dirent **))
{
    struct dirent **dent_list = NULL;
    size_t dent_num = 0;

    assert(dir_name);

    DIR *dir = opendir(dir_name);
    if (!dir)
    {
        return -1;
    }

    for (struct dirent *dent; (dent = readdir(dir));)
    {
        if (filter && !(*filter)(dent))
            continue;

        // re-allocate the list
        struct dirent **old_list = dent_list;
        dent_list = realloc(dent_list, (dent_num + 1) * sizeof(struct dirent *));
        if (!dent_list)
        {
            dent_list = old_list;
            goto out;
        }

        // add the copy of dirent to the list, using d_reclen as dent size
        // but since Mingw defines struct dirent as follows:
        //
        //  long            d_ino;          /* Always zero. */
        //  unsigned short  d_reclen;       /* Always zero. */
        //  unsigned short  d_namlen;       /* Length of name in d_name. */
        //  char            d_name[260];    /* [FILENAME_MAX] */ /* File name. */
        //
        // we cant use d_reclen as it is always zero and sizeof(struct dirent) is no-use, so
        // we use d_namlen for length of d_name, hence d_reclen is calculated by this way:
#define D_RECLEN (sizeof(struct dirent) - FILENAME_MAX + dent->d_namlen + 1)
        dent_list[dent_num] = malloc(D_RECLEN);
        if (!dent_list[dent_num])
        {
            goto out;
        }
        memcpy(dent_list[dent_num], dent, D_RECLEN);
        ++dent_num;
#undef D_RECLEN
    }

    if (compar)
    {
        qsort(dent_list, dent_num, sizeof(struct dirent *),
              (int (*)(const void *, const void *))compar);
    }

    // release the dent list
    *name_list = dent_list;
    dent_list = NULL;
out:
    if (dent_list)
    {
        while (dent_num > 0)
        {
            free(dent_list[--dent_num]);
        }
        free(dent_list);
        dent_num = -1;
    }
    closedir(dir);
    return dent_num;
}

int __NT_DCL alphasort(const struct dirent **a, const struct dirent **b)
{
    return strcoll((*a)->d_name, (*b)->d_name);
}

static struct nt_mode_t parse_fopen_mode(const char *mode)
{
    struct nt_mode_t mode_st;
    unsigned int open_direction, open_flags = O_SEQUENTIAL;
    char *ptr = mode_st.mode;

    /* parse mode */
    for (; *mode != '\0'; ++mode)
        switch (*mode)
        {
        case 'r':
            open_direction = O_RDONLY;
            *ptr++ = *mode;
            continue;
        case 'w':
            open_direction = O_WRONLY;
            open_flags |= O_CREAT | O_TRUNC;
            *ptr++ = *mode;
            continue;
        case 'a':
            open_direction = O_WRONLY;
            open_flags |= O_CREAT | O_APPEND;
            *ptr++ = *mode;
            continue;
        case 'b':
            open_flags = (open_flags & ~O_TEXT) | O_BINARY;
            *ptr++ = *mode;
            continue;
        case 't':
            open_flags = (open_flags & ~O_BINARY) | O_TEXT;
            *ptr++ = *mode;
            continue;
        case '+':
            open_direction = O_RDWR;
            *ptr++ = *mode;
            continue;
        case 'x':
            open_flags |= O_EXCL;
            continue;
        case 'e':
            open_flags |= O_NOINHERIT;
            continue;
        default:
            break;
        }
    *ptr = '\0';

    NT_DEBUG("mode: %s", mode_st.mode);
    mode_st.direction = open_direction;
    mode_st.flags = open_flags;

    return mode_st;
}

FILE *__NT_DCL fopen2(const char *filename, const char *mode)
{
    struct nt_mode_t p_mode = parse_fopen_mode(mode);
    size_t end = strlen(filename) - 1;
    char *filepath = strdup(!strncmp(filename, "/dev/null", 9) ? "NUL" : filename);

    if (filepath[end] == '/' ||
        filepath[end] == '\\')
    {
        struct _stat64 st;

        filepath[end] = '\0'; // assume as it is just a file
        NT_DEBUG("filename: %s -> %s", filename, filepath);

        if (_stat64(filepath, &st) || !S_ISREG(st.st_mode))
        {
            free(filepath);
            errno = EINVAL;
            return NULL;
        }
    }

    int fd = _open(filepath, p_mode.direction | p_mode.flags, S_IREAD | S_IWRITE);
    if (fd < 0)
    {
        free(filepath);
        return NULL;
    }

    FILE *fp = orig_fdopen(fd, p_mode.mode);
    if (fp == NULL)
    {
        int saved_errno = errno;
        close(fd);
        errno = saved_errno;
    }

    free(filepath);
    return fp;
}

FILE *__NT_DCL fdopen2(int fd, const char *mode)
{
    struct nt_mode_t p_mode = parse_fopen_mode(mode);
    return orig_fdopen(fd, p_mode.mode);
}

#define FILE_IO_BUF_SIZE 65536 /* 64kb */
ssize_t __NT_DCL sendfile(int out_fd, int in_fd, off_t *offset, size_t count)
{
    ssize_t bytes = 0;
    off_t orig_pos;

    if (out_fd < 0 || in_fd < 0)
    {
        errno = EBADF;
        return -1;
    }

    if (count < 0)
    {
        errno = EINVAL;
        return -1;
    }
    else if (count == 0)
    {
        return 0;
    }

    if (offset)
    {
        orig_pos = lseek(in_fd, 0, SEEK_CUR);
        NT_DEBUG("original file pos %lld", orig_pos);
        if (orig_pos == (off_t)-1)
        {
            return -1;
        }
        off_t pos = lseek(in_fd, *offset, SEEK_SET);
        NT_DEBUG("changed pos to %lld", pos);
        if (pos == (off_t)-1)
        {
            return -1;
        }
    }

    while (count)
    {
        char buf[FILE_IO_BUF_SIZE];
        ssize_t rd = read(in_fd, buf, FILE_IO_BUF_SIZE);
        // since we have already treated zero count case, mark it as error at this stage
        if (rd <= 0)
        {
            bytes = -1;
            break;
        }
        ssize_t we = write(out_fd, buf, rd);
        if (we <= 0 || rd != we)
        {
            bytes = -1;
            break;
        }
        bytes += we;
        if (offset)
            *offset += rd;
        count -= rd;
        if (rd < FILE_IO_BUF_SIZE) // short read
            break;
    }

    if (offset)
    {
        assert(lseek(in_fd, orig_pos, SEEK_SET) == orig_pos);
    }

    // here count should be 0 else we have failed
    if (count)
    {
        errno = EIO;
        return -1;
    }

    return bytes;
}

/* support only unicode symlinks for simplicity
   and cygwin inspired symlinks for comptability */
#define SYMLINK_COOKIE "!<symlink>"
#define SYMLINK_COOKIE_LEN 10
#define SYMLINK_MAXSIZE 1024
static int fix_stat(const char *pathname,
                    const struct _stati64 nbuf,
                    stat_t *buf)
{
    BY_HANDLE_FILE_INFORMATION fi;
    HANDLE hd;

#define C(x) buf->st_##x = nbuf.st_##x
    C(dev);
    C(ino);
    C(mode);
    C(nlink);
    C(uid);
    C(gid);
    C(rdev);
    C(size);
    C(atime);
    C(mtime);
    C(ctime);
#undef C

    buf->st_blksize = 131072;           /* magic "random" number */
    buf->st_blocks = nbuf.st_size >> 9; /* # of 512B blocks allocated */
    if (nbuf.st_size & ((1 << 9) - 1))  /* partial trailing block? */
        buf->st_blocks++;

    hd = CreateFileA(pathname, FILE_READ_ATTRIBUTES,
                     FILE_SHARE_DELETE | FILE_SHARE_READ | FILE_SHARE_WRITE,
                     NULL, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, NULL);

    if (INVALID_HANDLE_VALUE == hd)
    {
        NT_DEBUG("CreateFileA");
        return 0;
    }

    if (GetFileType(hd) != FILE_TYPE_DISK ||
        !GetFileInformationByHandle(hd, &fi))
    {
        NT_DEBUG("GetFileInformationByHandle");
        return 0; /* Don't let the stat() call fail, but complain loudly */
    }

    buf->st_dev = (dev_t)fi.dwVolumeSerialNumber;
    buf->st_ino = fi.nFileIndexHigh;
    buf->st_ino <<= 32;
    buf->st_ino |= fi.nFileIndexLow;

    return 0;
}

int __NT_DCL lstat_t(const char *pathname, stat_t *statbuf)
{
    int rc;
    char buf[SYMLINK_MAXSIZE];
    struct _stat64 st;

    assert(statbuf);
    assert(pathname);

    rc = _stat64(pathname, &st);
    if (rc)
        return rc;

    rc = fix_stat(pathname, st, statbuf);
    if (rc || statbuf->st_size > SYMLINK_MAXSIZE || !S_ISREG(statbuf->st_mode))
        return rc;

    rc = readlink(pathname, buf, SYMLINK_MAXSIZE);
    if (rc == -1)
        return 0;

    statbuf->st_mode = S_IFLNK | 0644;
    statbuf->st_size = rc; /* use readlink returned sz */

    return 0;
}

ssize_t __NT_DCL readlink(const char *pathname, char *buf, size_t bufsiz)
{
    int fd, sz, at;
    char wbuf[SYMLINK_MAXSIZE];

    assert(pathname);
    assert(buf);
    assert(wbuf);

    at = GetFileAttributesA(pathname);
    if ((unsigned long)at == INVALID_FILE_ATTRIBUTES || !(at & _A_SYSTEM))
    {
        errno = EINVAL;
        return -1;
    }

    fd = _open(pathname, O_RDONLY | O_BINARY);
    if (fd < 0)
        return -1;

    sz = read(fd, wbuf, SYMLINK_COOKIE_LEN + 2);
    if (sz < 0)
    {
        sz = -1;
        goto err;
    }

    if ((size_t)sz < SYMLINK_COOKIE_LEN ||
        memcmp(wbuf, SYMLINK_COOKIE, SYMLINK_COOKIE_LEN) ||
        *(PWCHAR)(wbuf + SYMLINK_COOKIE_LEN) != 0xfeff)
    {
        errno = EINVAL;
        sz = -1;
        goto err;
    }

    if (lseek(fd, SYMLINK_COOKIE_LEN + 2, SEEK_SET) < 0 ||
        read(fd, wbuf, sizeof(wbuf)) < 0)
    {
        sz = -1;
        goto err;
    }

    sz = WideCharToMultiByte(CP_UTF8, 0, (LPWSTR)wbuf, -1, NULL, 0, NULL, NULL);
    if (sz < 2 || sz > SYMLINK_MAXSIZE)
    {
        errno = EINVAL;
        sz = -1;
        goto err;
    }

    /* POSIX readlink buf does not include NULL character */
    sz -= 1;
    /* POSIX readlink truncates target sz to bufsiz */
    if ((size_t)sz > bufsiz)
        sz = bufsiz;

    if (WideCharToMultiByte(CP_UTF8, 0, (LPWSTR)wbuf,
                            sz, buf, bufsiz, NULL, NULL) != sz)
    {
        errno = EINVAL;
        sz = -1;
    }

err:
    close(fd);
    return sz;
}

int __NT_DCL symlink(const char *target, const char *file)
{
    int sz = strlen(target) + 1;
    const ssize_t len = sz * sizeof(wchar_t) + SYMLINK_COOKIE_LEN + 2;
    char *data = malloc(len);

    assert(data);
    assert(target);
    assert(file);

    char *p = data;
    strncpy(p, SYMLINK_COOKIE, SYMLINK_COOKIE_LEN);
    p += SYMLINK_COOKIE_LEN;
    *(PWCHAR)p = 0xfeff;
    p += 2;

    int fd = _open(file, O_RDWR | O_CREAT | O_BINARY, S_IREAD | S_IWRITE);
    if (fd == -1)
    {
        free(data);
        return -1;
    }

    if (MultiByteToWideChar(CP_UTF8, 0, target, sz, (LPWSTR)p, sz) != sz)
    {
        errno = EINVAL;
        sz = -1;
        goto err;
    }

    if (write(fd, data, len) != len ||
        !SetFileAttributesA(file, FILE_ATTRIBUTE_SYSTEM))
    {
        sz = -1;
        goto err;
    }

    /* POSIX symlink returns 0 on success */
    sz = 0;
err:
    free(data);
    close(fd);
    return sz;
}

ssize_t __NT_DCL getdelim(char **buf, size_t *bufsiz, int delimiter, FILE *fp)
{
    char *ptr, *eptr;

    assert(fp);

    if (*buf == NULL || *bufsiz == 0)
    {
        *bufsiz = BUFSIZ;
        if ((*buf = malloc(*bufsiz)) == NULL)
            return -1;
    }

    for (ptr = *buf, eptr = *buf + *bufsiz;;)
    {
        int c = fgetc(fp);
        if (c == -1)
        {
            if (feof(fp))
                return ptr == *buf ? -1 : ptr - *buf;
            else
                return -1;
        }
        *ptr++ = c;
        if (c == delimiter)
        {
            *ptr = '\0';
            return ptr - *buf;
        }
        if (ptr + 2 >= eptr)
        {
            char *nbuf;
            size_t nbufsiz = *bufsiz * 2;
            ssize_t d = ptr - *buf;
            if ((nbuf = (char *)realloc(*buf, nbufsiz)) == NULL)
                return -1;
            *buf = nbuf;
            *bufsiz = nbufsiz;
            eptr = nbuf + nbufsiz;
            ptr = nbuf + d;
        }
    }
}

ssize_t __NT_DCL getline(char **buf, size_t *bufsiz, FILE *fp)
{
    return getdelim(buf, bufsiz, '\n', fp);
}

void *__NT_DCL memmem(const void *haystack, size_t haystack_len, const void *const needle, const size_t needle_len)
{
    const char *begin;
    const char *const last_possible = (const char *)haystack + haystack_len - needle_len;

    if (needle_len == 0)
        /* The first occurrence of the empty string is deemed to occur at
        the beginning of the string.  */
        return (void *)haystack;

    /* Sanity check, otherwise the loop might search through the whole
        memory.  */
    if (haystack_len < needle_len)
        return NULL;

    for (begin = (const char *)haystack; begin <= last_possible; ++begin)
        if (begin[0] == ((const char *)needle)[0] &&
            !memcmp((const void *)&begin[1],
                    (const void *)((const char *)needle + 1),
                    needle_len - 1))
            return (void *)begin;

    return NULL;
}

ssize_t __NT_DCL readv(int fd, const iovec *iov, int iov_cnt)
{
    int i;
    ssize_t total_read = 0;

    assert(iov);

    for (i = 0; i < iov_cnt; i++)
    {
        ssize_t c = iov[i].iov_len;
        while (c)
        {
            ssize_t r = read(fd, iov[i].iov_base, c);

            if (r < 0)
            {
                return -1;
            }
            c -= r;
            total_read += r;
        }
    }

    return total_read;
}

ssize_t __NT_DCL writev(int fd, const iovec *iov, int iov_cnt)
{
    int i;
    ssize_t total_written = 0;

    assert(iov);

    for (i = 0; i < iov_cnt; i++)
    {
        ssize_t c = iov[i].iov_len;
        while (c)
        {
            ssize_t w = write(fd, iov[i].iov_base, c);

            if (w < 0)
            {
                return -1;
            }
            c -= w;
            total_written += w;
        }
    }

    return total_written;
}
