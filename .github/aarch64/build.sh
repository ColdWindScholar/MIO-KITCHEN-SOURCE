#!/usr/bin/zsh
clean (){
echo "Are you sure?"
umount
sudo find rootfs/dev rootfs/proc rootfs/sys || true
read 1
sudo rm -rf rootfs
sudo find .
echo "bruh"
}

umount (){
sudo umount rootfs/dev/pts rootfs/dev rootfs/proc rootfs/sys
sudo find rootfs/dev rootfs/proc rootfs/sys
exit 0
}
set -e
echo "clean!!"
clean
echo "cleanned"
sudo ./apk -X http://cmcc.mirrors.ustc.edu.cn/alpine/edge/main -X http://cmcc.mirrors.ustc.edu.cn/alpine/edge/community -U --allow-untrusted -p rootfs --initdb add --no-cache alpine-base coreutils bash bash-completion shadow patchelf

cd rootfs

sudo su -c "echo 'https://cmcc.mirrors.ustc.edu.cn/alpine/edge/main' > etc/apk/repositories"
sudo su -c "echo 'https://cmcc.mirrors.ustc.edu.cn/alpine/edge/community' >> etc/apk/repositories"
sudo cp /etc/resolv.conf etc/resolv.conf

sudo mount -o bind /dev dev
sudo mount -o bind /dev/pts dev/pts
sudo mount -t proc none proc
sudo mount -o bind /sys sys

sudo env -i /usr/sbin/chroot . /usr/bin/env -i PATH=/sbin:/usr/sbin:/bin:/usr/bin TMPDIR=/tmp USER=root HOME=/root chsh -s /bin/bash
sudo cp ./.github/aarch64/build_inside.sh tmp/build.sh
sudo chmod +x tmp/build.sh
sudo env -i /usr/sbin/chroot . /usr/bin/env -i PATH=/sbin:/usr/sbin:/bin:/usr/bin TMPDIR=/tmp USER=root HOME=/root bash /tmp/build.sh

sudo cp -avf root/appstatic/appstatic ..
sudo cp -avf etc/ssl/certs/ca-certificates.crt ..

sudo umount dev/pts dev proc sys
sudo find dev proc sys

cd ..
sudo chown yurri:yurri appstatic ca-certificates.crt
