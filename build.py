import os
import shutil
from platform import system

ostype = system()

local = os.getcwd()
print("Building...")
if ostype == 'Darwin':
    os.system("pyinstaller -Fw tool.py --exclude-module=numpy -i icon.ico --collect-data sv_ttk --hidden-import=tkinter --hidden-import=PIL --hidden-import=PIL._tkinter_finder")
elif os.name == 'posix':
    os.system(
        "pyinstaller -Fw tool.py --exclude-module=numpy -i icon.ico --collect-data sv_ttk --hidden-import=tkinter --hidden-import=PIL --hidden-import=PIL._tkinter_finder --splash splash.png")
elif os.name == 'nt':
    os.system("pyinstaller -Fw tool.py --exclude-module=numpy -i icon.ico --collect-data sv_ttk --splash splash.png")
if os.name == 'nt':
    if os.path.exists(local + os.sep + "dist" + os.sep + "tool.exe"):
        shutil.move(local + os.sep + "dist" + os.sep + "tool.exe", local)
else:
    if os.path.exists(local + os.sep + "dist" + os.sep + "tool"):
        shutil.move(local + os.sep + "dist" + os.sep + "tool", local)
pclist = ['images', 'languages', 'licenses', 'module', 'temp', 'extra_flash.zip', 'setting.ini', ostype]
for i in os.listdir(local + os.sep + "bin"):
    if i in pclist:
        continue
    else:
        if os.path.isdir(local + os.sep + "bin" + os.sep + i):
            shutil.rmtree(local + os.sep + "bin" + os.sep + i)
        else:
            os.remove(local + os.sep + "bin" + os.sep + i)
for i in os.listdir(local):
    if i not in ['tool', 'tool.exe', 'bin', 'LICENSE']:
        print(f"Removing {i}")
        if os.path.isdir(local + os.sep + i):
            try:
                shutil.rmtree(local + os.sep + i)
            except Exception or OSError as e:
                print(e)
        elif os.path.isfile(local + os.sep + i):
            try:
                os.remove(local + os.sep + i)
            except Exception or OSError as e:
                print(e)
    else:
        print(i)
if os.name == 'posix':
    for root, dirs, files in os.walk(local, topdown=True):
        for i in files:
            print(f"Chmod {os.path.join(root, i)}")
            os.system(f"chmod a+x {os.path.join(root, i)}")
