import os
import shutil

local = os.getcwd()
print("Building...")
os.system("pyinstaller -F run.py --exclude-module=numpy -i icon.ico")
if os.name == 'nt':
    if os.path.exists(local + os.sep + "dist" + os.sep + "run.exe"):
        shutil.move(local + os.sep + "dist" + os.sep + "run.exe", local)
    if os.path.exists(local + os.sep + "bin" + os.sep + "Linux"):
        shutil.rmtree(local + os.sep + "bin" + os.sep + "Linux")
elif os.name == 'posix':
    if os.path.exists(local + os.sep + "dist" + os.sep + "run"):
        shutil.move(local + os.sep + "dist" + os.sep + "run", local)
    if os.path.exists(local + os.sep + "bin" + os.sep + "Windows"):
        shutil.rmtree(local + os.sep + "bin" + os.sep + "Windows")
for i in os.listdir(local):
    if i not in ['run', 'run.exe', 'bin', 'LICENSE']:
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
            print(f"Chmod {os.path.join(root,i)}")
            os.system(f"chmod a+x {os.path.join(root,i)}")
