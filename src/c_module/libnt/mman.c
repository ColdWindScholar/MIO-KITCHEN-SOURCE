#include <windows.h>
#include <errno.h>
#include <io.h>
#include <stdio.h>
#include <sys/mman.h>

#ifndef FILE_MAP_EXECUTE
#define FILE_MAP_EXECUTE    0x0020
#endif /* FILE_MAP_EXECUTE */

static DWORD __map_mmap_prot_page(const int prot) {
    DWORD protect;
    
    if (prot == PROT_NONE)
        return 0;
        
    if ((prot & PROT_EXEC) != 0)
        protect = ((prot & PROT_WRITE) != 0) ? 
                    PAGE_EXECUTE_READWRITE : PAGE_EXECUTE_READ;
    else
        protect = ((prot & PROT_WRITE) != 0) ?
                    PAGE_READWRITE : PAGE_READONLY;
    
    return protect;
}

static DWORD __map_mmap_prot_file(const int prot) {
    DWORD desiredAccess = 0;
    
    if (prot == PROT_NONE)
        return desiredAccess;
        
    if ((prot & PROT_READ) != 0)
        desiredAccess |= FILE_MAP_READ;
    if ((prot & PROT_WRITE) != 0)
        desiredAccess |= FILE_MAP_WRITE;
    if ((prot & PROT_EXEC) != 0)
        desiredAccess |= FILE_MAP_EXECUTE;
    
    return desiredAccess;
}

void* __NT_DCL mmap(void *addr, size_t len, int prot, int flags, int fildes, off64_t off) {
    HANDLE fm, h = INVALID_HANDLE_VALUE;
    void *map = MAP_FAILED;

    const DWORD dwFileOffsetLow = off & 0xFFFFFFFFL;
    const DWORD dwFileOffsetHigh = off >> 32;
    const DWORD protect = __map_mmap_prot_page(prot);
    const DWORD desiredAccess = __map_mmap_prot_file(prot);

    const off64_t maxSize = off + len;

    const DWORD dwMaxSizeLow = maxSize & 0xFFFFFFFFL;
    const DWORD dwMaxSizeHigh = maxSize >> 32;

    if (len == 0 || prot == PROT_EXEC) {
        errno = EINVAL;
        return MAP_FAILED;
    }

    if ((flags & MAP_ANONYMOUS) == 0 &&
	    (h = (HANDLE)_get_osfhandle(fildes)) == INVALID_HANDLE_VALUE) {
        errno = EBADF;
        NT_DEBUG("failed with %d (%s)", errno, strerror(errno));
        return MAP_FAILED;
    }

    fm = CreateFileMappingA(h, NULL, protect, dwMaxSizeHigh, dwMaxSizeLow, NULL);
    if (!fm) {
		errno = map_nt_error(GetLastError());
        NT_DEBUG("failed with %d (%s)", errno, strerror(errno));
        return MAP_FAILED;
    }
  
    if ((flags & MAP_FIXED) == 0)
        map = MapViewOfFile(fm, desiredAccess, dwFileOffsetHigh, dwFileOffsetLow, len);
    else
        map = MapViewOfFileEx(fm, desiredAccess, dwFileOffsetHigh, dwFileOffsetLow, len, addr);

    /* maybe dont close handle? */ 
    CloseHandle(fm);
  
    if (!map){
		errno = map_nt_error(GetLastError());
        NT_DEBUG("failed with %d (%s)", errno, strerror(errno));
        return MAP_FAILED;
    }

    return map;
}

int __NT_DCL munmap(void *addr, size_t len) {
    (void)len;

    if (UnmapViewOfFile(addr))
        return 0;
        
    errno =  map_nt_error(GetLastError());
    return -1;
}