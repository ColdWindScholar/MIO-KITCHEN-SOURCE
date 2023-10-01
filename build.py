import os
import shutil
import platform

local = os.getcwd()
print("Building...")
if os.name == 'posix':
    os.system(
        "pyinstaller -Fw tool.py --exclude-module=numpy -i icon.ico --collect-data sv_ttk --hidden-import=tkinter --hidden-import=PIL --hidden-import=PIL._tkinter_finder --splash splash.png")
elif os.name == 'nt':
    os.system("pyinstaller -Fw tool.py --exclude-module=numpy -i icon.ico --collect-data sv_ttk --splash splash.png")
if os.name == 'nt':
    if os.path.exists(local + os.sep + "dist" + os.sep + "tool.exe"):
        shutil.move(local + os.sep + "dist" + os.sep + "tool.exe", local)
    if os.path.exists(local + os.sep + "bin" + os.sep + "Linux"):
        shutil.rmtree(local + os.sep + "bin" + os.sep + "Linux")
elif os.name == 'posix':
    if os.path.exists(local + os.sep + "dist" + os.sep + "tool"):
        shutil.move(local + os.sep + "dist" + os.sep + "tool", local)
    pclist = ['images', 'languages', 'licenses', 'module', 'temp', 'extra_flash.zip', 'setting.ini',platform.system()]:

    if os.path.exists(local + os.sep + "bin" + os.sep + "Windows"):
        shutil.rmtree(local + os.sep + "bin" + os.sep + "Windows")
for i in os.listdir(local):
    if i not in ['run', 'tool.exe', 'bin', 'LICENSE']:
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
