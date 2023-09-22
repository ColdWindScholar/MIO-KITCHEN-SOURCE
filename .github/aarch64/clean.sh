#!/usr/bin/zsh

set -e

echo "Are you sure?"
./umount.sh
sudo find rootfs/dev rootfs/proc rootfs/sys || true
read 1
sudo rm -rf rootfs
sudo find .
echo "bruh"
