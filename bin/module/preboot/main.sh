#!/usr/bin/env sh
find "$project" -name "header" | while read i;do
  echo "> 开始修补：$i"
  sed -i "s/androidboot.selinux=enforcing/androidboot.selinux=permissive/" $i
  sed -i "s/androidboot.selinux=permissive//g" $i
  sed -i "/^cmdline=/{s/$/& androidboot.selinux=permissive/}" $i
  sed -i -e 's;  *; ;g' -e 's;[ \t]*$;;' $i
  echo "> 修补完成"
done