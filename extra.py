import os
import subprocess
from platform import machine


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


def returnoutput(cmd, elocal, kz=1):
    if kz == 1:
        comd = elocal + os.sep + "bin" + os.sep + os.name + '_' + machine() + os.sep + cmd
    else:
        comd = cmd
    if os.name == 'posix':
        comd = comd.split()
    else:
        comd = cmd
    try:
        ret = subprocess.check_output(comd, shell=False, stderr=subprocess.STDOUT)
        return ret.decode()
    except subprocess.CalledProcessError as e:
        return e.decode()


class prop_utils(object):
    def __init__(self, file):
        self.prop = file

    def setprop(self, key: str, value: any):
        pass

    def getprop(self, key):
        pass

    def sdk2androidver(self, value: int):
        pass
