#!/usr/bin/zsh
if [ "$1" == "build" ];then
uname -a
exit 0
fi
sudo apt-get update
sudo apt-get install docker.io
sudo docker pull arm64v8/ubuntu
sudo docker run -it arm64v8/ubuntu sudo bash ./.github/aarch64/build.sh build
