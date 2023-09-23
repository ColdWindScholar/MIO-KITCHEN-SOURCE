#!/usr/bin/zsh
uname -a
python3 -m pip install -U --force-reinstall pip
pip3 install -r requirements.txt
sudo apt update -y && sudo apt install python3-tk -y
pyinstaller -Fw tool.py --exclude-module=numpy -i icon.ico --collect-data sv_ttk --hidden-import=tkinter --hidden-import=PIL --hidden-import=PIL._tkinter_finder --splash splash.png
mv dist/* ./
rm -rf .git
rm -rf .github
rm -rf bin/nt_*
rm -rf bin/posix_x86_64
rm -rf *.*
rm -rf build
rm -rf dist
rm -rf splash.png
find . | xargs chmod a+x
chmod a+x ./*
ls
exit 0