import os


def clink(link: str, target: str):
    with open(link, 'wb') as f:
        f.write(b'!<symlink>')
        f.write(target.encode('utf-16'))
    if os.name == 'nt':
        from ctypes.wintypes import LPCSTR
        from ctypes.wintypes import DWORD
        from stat import FILE_ATTRIBUTE_SYSTEM
        from ctypes import windll
        attrib = windll.kernel32.SetFileAttributesA
        attrib(LPCSTR(link.encode()), DWORD(FILE_ATTRIBUTE_SYSTEM))


class prop_utils(object):
    def __init__(self, file):
        self.prop = file

    def setprop(self, key: str, value: any):
        pass

    def getprop(self, key):
        pass

    def sdk2androidver(self, value: int):
        pass
