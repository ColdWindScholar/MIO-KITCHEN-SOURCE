#!/usr/bin/zsh
if [ "$1" == "build" ];then
uname -a
python3 -m pip install -U --force-reinstall pip
pip3 install -r requirements.txt
sudo apt update -y && sudo apt install python3-tk -y
pyinstaller -Fw tool.py --exclude-module=numpy -i icon.ico --collect-data sv_ttk --hidden-import=tkinter --hidden-import=PIL --hidden-import=PIL._tkinter_finder --splash splash.png
mv dist/* ./
exit 0
fi
sudo apt-get update
sudo apt-get install docker.io
sudo docker pull arm64v8/ubuntu
sudo docker run arm64v8/ubuntu ./.github/aarch64/build.sh build
