import os

if os.name == 'nt':
    from ctypes.wintypes import LPCSTR, DWORD
    from stat import FILE_ATTRIBUTE_SYSTEM
    from ctypes import windll


def symlink(link_target, target):
    if os.name == 'posix':
        os.symlink(link_target, target)
    elif os.name == 'nt':
        with open(target.replace('/', os.sep), 'wb') as out:
            out.write(b'!<symlink>' + link_target.encode('utf-16') + b'\x00\x00')
            try:
                windll.kernel32.SetFileAttributesA(LPCSTR(target.encode()),
                                                   DWORD(FILE_ATTRIBUTE_SYSTEM))
            except Exception as e:
                print(e.__str__())


def readlink(path):
    if os.name == 'nt':
        if not os.path.isdir(path):
            with open(path, 'rb') as f:
                if f.read(10) == b'!<symlink>':
                    return f.read().decode("utf-16")[:-1]
                else:
                    return ''
    else:
        if os.path.islink(path):
            return os.readlink(path)
        else:
            return ''


if os.name == 'nt':
    # TODO: Add Case Sensitive
    pass
