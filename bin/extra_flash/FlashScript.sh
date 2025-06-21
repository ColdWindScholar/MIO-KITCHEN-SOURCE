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
  echo -e "\e[1;33mFlashing\e[0m \e[1;36m[$1]\e[0m"
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
      if [ "$(basename "$img" .img.zst)" != "$(basename "$img")" ];then
        echo "Uncompressing $(basename "$img")"
        $zstd --rm -d images/"$img" -o images/"$(basename "$img" .zst)"
        img=$(basename "$img" .zst)
      fi
      part=$(basename "$img" .img)
      [ "$part" == "super" ] && continue
      [ "$part" == "cust" ] && continue
      [ "$part" == "preloader_raw" ] && continue
      if [ "$isab" == 'true' ];then
        flash "$part"_a images/"$img"
        flash "$part"_b images/"$img"
      else
        flash "$part" images/"$img"
      fi
    done
    [ -e images/cust.img ] && flash cust images/cust.img
    [ -e images/super.img ] && flash super images/super.img
    if [ -e images/preloader_raw.img ]; then
      flash preloader_a images/preloader_raw.img
      flash preloader_b images/preloader_raw.img
      flash preloader1 images/preloader_raw.img
      flash preloader2 images/preloader_raw.img
    fi
    [ "$isab" == 'true' ]&& $fastboot set_active a
}
function home() {
  echo -e "\e[1;34mMio-kitchen Flash Script\e[0m"
  check_fastboot
  echo -e "\e[1;36m[1]\e[0m\e[1;33m Keep all data and flash it in\e[0m"
  echo -e "\e[1;36m[2]\e[0m\e[1;33m Erase Userdata and flash in\e[0m"
  if [ ! -z "$right_device" ]; then
    echo -e "\e[1;31mAttention: This ROM is specifically made for [$right_device], and cannot be flashed on other models.\e[0m"
  else
    echo -e "\e[1;31mAttention: Please ensure the rom is for your device before flashing.\e[0m"
  fi
  read -p "Please select:" flash_type
  start_flash
  if [ "$flash_type" == "2" ]; then
    echo "Formatting Userdata"
    $fastboot erase userdata
    $fastboot erase metadata
  fi
  echo  -e "\e[1;32mFlash completed\e[0m"
  read -p "Reboot The Device?[y/n]" if_reboot
  [ "$if_reboot" == "y" ] && $fastboot reboot
}
home