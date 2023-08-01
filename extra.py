import os
import subprocess
from platform import machine
from typing import Optional


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


class proputil:
    def __init__(self, propfile: str):
        proppath = os.path.abspath(propfile)
        if os.path.exists(proppath):
            self.propfd = open(propfile, 'r+')
        else:
            raise FileExistsError(f"File {propfile} does not exist!")
        self.prop = self.__loadprop

    @property
    def __loadprop(self) -> list:
        return self.propfd.readlines()

    def getprop(self, key: str) -> Optional[str]:
        """
        recive key and return value or None
        """
        for i in self.prop:
            if key in i: return i.rstrip().split('=')[1]
        return None

    def setprop(self, key, value) -> None:
        flag: bool = False  # maybe there is not only one item
        for index, current in enumerate(self.prop):
            if key in current:
                self.prop[index] = current.split('=')[0] + '=' + value + '\n'
                flag = True
        if not flag:
            self.prop.append(
                key + '=' + value + '\n'
            )

    def save(self):
        self.propfd.seek(0, 0)
        self.propfd.truncate()
        self.propfd.writelines(self.prop)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):  # with proputil('build.prop') as p:
        self.save()
        self.propfd.close()


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
