#!/usr/bin/env python3
"""
set directory case sensitive on Windows directly with ctypes

**requires WSL to be enabled**
BASED ON CODE FROM https://github.com/microsoft/WSL/issues/2954 !!!
thus for Windows 10 1903 and up
"""

from ctypes import (
    WinDLL,
    c_void_p,
    get_last_error,
    WinError,
    c_int,
    Structure,
    sizeof,
    byref
)
from ctypes.wintypes import (
    HANDLE,
    LPCSTR,
    DWORD,
    BOOL,
    LPVOID,
    ULONG
)
try:
    from enum import IntEnum
except ImportError:
    IntEnum = int
import os.path

# ==================================================================
# ======================== WinApi Bindings =========================
# ==================================================================

# https://stackoverflow.com/questions/29847679/get-error-message-from-ctypes-windll
kernel32 = WinDLL('kernel32', use_last_error=True)


def _check_handle(h, *_):
    if h == INVALID_HANDLE_VALUE:
        raise WinError(get_last_error())

    return h


def _expect_nonzero(res, *_):
    if not res:
        raise WinError(get_last_error())


# https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilea
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FILE_FLAG_POSIX_SEMANTICS = 0x01000000

OPEN_EXISTING = 3

FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_SHARE_DELETE = 0x00000004
FILE_SHARE_VALID_FLAGS = FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE

"""
    HANDLE CreateFileA(
    [in]           LPCSTR                lpFileName,
    [in]           DWORD                 dwDesiredAccess,
    [in]           DWORD                 dwShareMode,
    [in, optional] LPSECURITY_ATTRIBUTES lpSecurityAttributes,
    [in]           DWORD                 dwCreationDisposition,
    [in]           DWORD                 dwFlagsAndAttributes,
    [in, optional] HANDLE                hTemplateFile
    );
"""
_CreateFileA = kernel32.CreateFileA
_CreateFileA.argtypes = [
    LPCSTR, DWORD, DWORD, c_void_p, DWORD, DWORD, HANDLE
]
_CreateFileA.restype = HANDLE
_CreateFileA.errcheck = _check_handle

# https://learn.microsoft.com/en-us/windows/win32/secauthz/generic-access-rights
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000

# https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-findfirstfilenamew
INVALID_HANDLE_VALUE = HANDLE(-1).value

# https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-closehandle
"""
    BOOL CloseHandle(
    [in] HANDLE hObject
    );
"""
_CloseHandle = kernel32.CloseHandle
_CloseHandle.argtypes = [HANDLE]
_CloseHandle.restype = BOOL
_CloseHandle.errcheck = _expect_nonzero

# https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfileinformationbyhandleex
"""
    BOOL GetFileInformationByHandleEx(
    [in]  HANDLE                    hFile,
    [in]  FILE_INFO_BY_HANDLE_CLASS FileInformationClass,
    [out] LPVOID                    lpFileInformation,
    [in]  DWORD                     dwBufferSize
    );
"""
_GetFileInformationByHandleEx = kernel32.GetFileInformationByHandleEx
_GetFileInformationByHandleEx.argtypes = [HANDLE, c_int, LPVOID, DWORD]
_GetFileInformationByHandleEx.restype = BOOL
_GetFileInformationByHandleEx.errcheck = _expect_nonzero


# ===== The start of the undocumented craps... =====

# /mingw64/include/winbase.h
class FILE_CASE_SENSITIVE_INFO(Structure):
    _fields_ = [
        ('Flags', ULONG)
    ]


FILE_INFO_BY_HANDLE = FILE_CASE_SENSITIVE_INFO


# https://learn.microsoft.com/en-us/windows/win32/api/minwinbase/ne-minwinbase-file_info_by_handle_class
class FILE_INFO_BY_HANDLE_CLASS(IntEnum):
    FileCaseSensitiveInfo = 23


# /mingw64/include/winnt.h
# https://github.com/DDoSolitary/LxRunOffline/blob/bdc6d7d77f886c6dcdab3b4c9c136557ca6694c4/src/lib/fs.cpp#L89
FILE_CS_FLAG_CASE_SENSITIVE_DIR = 0x00000001

# https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle
"""
    BOOL SetFileInformationByHandle(
    [in] HANDLE                    hFile,
    [in] FILE_INFO_BY_HANDLE_CLASS FileInformationClass,
    [in] LPVOID                    lpFileInformation,
    [in] DWORD                     dwBufferSize
    );
"""
_SetFileInformationByHandle = kernel32.SetFileInformationByHandle
_SetFileInformationByHandle.argtypes = [HANDLE, c_int, LPVOID, DWORD]
_SetFileInformationByHandle.restype = BOOL
_SetFileInformationByHandle.errcheck = _expect_nonzero


# ==================================================================
# ======================= Wrappers functions =======================
# ==================================================================

def CreateFileA(path: str, access: int, share: int,
                oflag: int, flags: int) -> HANDLE:
    return _CreateFileA(
        path.encode(encoding='utf-8'),
        access, share,
        None,  # default
        oflag, flags,
        None  # unused
    )


def CloseHandle(h: HANDLE):
    _CloseHandle(h)


def GetFileInformationByHandleEx(
        h: HANDLE,
        kind: FILE_INFO_BY_HANDLE_CLASS
) -> FILE_INFO_BY_HANDLE:
    if kind == FILE_INFO_BY_HANDLE_CLASS.FileCaseSensitiveInfo:
        dtype = FILE_CASE_SENSITIVE_INFO
    else:
        raise ValueError('Invalid file info class')

    data = dtype()

    _GetFileInformationByHandleEx(h, kind,
                                  byref(data), sizeof(dtype))

    return data


def SetFileInformationByHandle(
        h: HANDLE,
        kind: FILE_INFO_BY_HANDLE_CLASS,
        data: FILE_INFO_BY_HANDLE
):
    if kind == FILE_INFO_BY_HANDLE_CLASS.FileCaseSensitiveInfo:
        dtype = FILE_CASE_SENSITIVE_INFO
    else:
        raise ValueError('Invalid file info class')

    _SetFileInformationByHandle(h, kind,
                                byref(data), sizeof(dtype))


# ==================================================================
# ======================== Helper functions ========================
# ==================================================================

def open_dir_handle(path: str, access: int) -> HANDLE:
    return CreateFileA(
        path, access,
        FILE_SHARE_VALID_FLAGS, OPEN_EXISTING,
        FILE_FLAG_POSIX_SEMANTICS | FILE_FLAG_BACKUP_SEMANTICS
    )


# ==================================================================
# ======================= Exported functions ========================
# ==================================================================

def ensure_dir_case_sensitive(path: str):
    if not os.path.isdir(path):
        raise NotADirectoryError(
            f'Cannot set case sensitive for non-directory: {path}'
        )

    h = open_dir_handle(path, GENERIC_READ)
    try:
        info: FILE_CASE_SENSITIVE_INFO = GetFileInformationByHandleEx(
            h, FILE_INFO_BY_HANDLE_CLASS.FileCaseSensitiveInfo
        )

        if info.Flags & FILE_CS_FLAG_CASE_SENSITIVE_DIR:
            print(f'{path!r} is already case sensitive')
        else:
            h2 = open_dir_handle(path, GENERIC_WRITE)

            try:
                info.Flags |= FILE_CS_FLAG_CASE_SENSITIVE_DIR

                SetFileInformationByHandle(
                    h2,
                    FILE_INFO_BY_HANDLE_CLASS.FileCaseSensitiveInfo,
                    info
                )

                print(f'set case sensitive state for {path!r}')
            finally:
                CloseHandle(h2)
    finally:
        CloseHandle(h)

