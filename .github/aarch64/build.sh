#!/usr/bin/zsh
sudo apt-get update
sudo apt-get install docker.io
sudo docker pull arm64v8/ubuntu
sudo docker run -it arm64v8/ubuntu /bin/bash
uname
