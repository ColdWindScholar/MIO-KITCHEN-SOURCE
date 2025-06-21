#!/bin/bash
fastboot=$(which fastboot)
zstd=$(pwd)/bin/zstd_linux
right_device=$(cat $(pwd)/bin/right_device)
function check_fastboot() {
  if [ -z "$fastboot" ]; then
  if [ $UID == 0 ] && [ "$USER" == root ]; then
    apt install fastboot
    if [ $? != 0 ]; then
      echo -e "\e[1;31mFastboot Install Fail.Please install it by urself.\e[0m"
      exit
    fi
  else
    echo -e "\e[1;31mFastboot Not Installed.Please install it.\e[0m"
  fi
  else
    echo -e "\e[1;32m$($fastboot --version)\e[0m"
fi
}
function flash() {
  $fastboot flash "$1" "$2"
  if [ "$?" == 0 ];then
    echo -e "\e[1;32mFlashing $1 completed\e[0m"
  else
    echo -e "\e[1;31mAn error occurred while flashing $1 \e[0m"
  fi
}
function start_flash() {
    echo -e "\e[1;30mYour phone must be in Bootloader mode, waiting for the device.\e[0m"
    device_code=$($fastboot getvar product 2>&1 | grep "^product: " | sed s/"product: "//g)
    slots=$($fastboot getvar slot-count 2>&1 | grep "^slot-count: " | sed s/"slot-count: "//g)
    echo -e "\e[1;32mDevice detected:[$device_code]; Slots:$slots\e[0m"
    [ "$slots" == '2' ] && isab=true
    if [ "$device_code" != "$right_device" ] && [ ! -z "$right_device" ];then
      echo -e "\e[1;31mThis ROM is made for $right_device, but your device is $device_code\e[0m"
      exit
    fi
    for img in $(ls images)
    do
      [ "$img" == "super.img" ] && continue
      [ "$img" == "cust.img" ] && continue
      [ "$img" == "preloader_raw.img" ] && continue
      part=$(basename "$part" .img)
      echo -e "\e[1;33mFlashing\e[0m \e[1;36m[$part]\e[0m"
      if [ "$isab" == 'true' ];then
        flash "$part"_a "$img"
        flash "$part"_b "$img"
      else
        flash "$part" "$img"
      fi
    done
    [ -e images/cust.img ] && flash cust images/cust.img
    if [ -e images/preloader_raw.img ]; then
      flash preloader_a images/preloader_raw.img
      flash preloader_b images/preloader_raw.img
      flash preloader1 images/preloader_raw.img
      flash preloader2 images/preloader_raw.img
    fi
    """
for /f "delims=" %%a in ('dir /b "images\*.zst"')do (
echo.正在转换 %%~na
!zstd! --rm -d images/%%~nxa -o images/%%~na
echo 开始刷入 %%~na
set name=%%~na
!fastboot! flash !name:~0,-4! images\%%~na
)
if "!xz!" == "1" %e% {0A}已保留全部数据,准备重启！{#}{\n}
if "!xz!" == "2" (echo 正在格式化DATA
!fastboot! erase userdata
!fastboot! erase metadata)
if "!fqlx!"=="AB" (!fastboot! set_active a %sg%)
!fastboot! reboot
    """
}
function home() {
  echo -e "\e[1;34mMio-kitchen Flash Script\e[0m"
  check_fastboot
  echo -e "\e[1;36m[1]\e[0m\e[1;33m Keep all data and flash it in\e[0m"
  echo -e "\e[1;36m[2]\e[0m\e[1;33m Erase Userdata and flash in\e[0m"
  if [ ! -z "$right_device" ]; then
    echo -e "\e[1;31mAttention: This ROM is specifically made for [$right_device!], and cannot be flashed on other models.\e[0m"
  else
    echo -e "\e[1;31mAttention: Please ensure the rom is for your device before flashing.\e[0m"
  fi
  read -p "Please select:" flash_type
  start_flash

}
home