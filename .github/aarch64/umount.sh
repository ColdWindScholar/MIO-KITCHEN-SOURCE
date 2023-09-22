#!/usr/bin/zsh
sudo umount rootfs/dev/pts rootfs/dev rootfs/proc rootfs/sys
sudo find rootfs/dev rootfs/proc rootfs/sys

exit 0
