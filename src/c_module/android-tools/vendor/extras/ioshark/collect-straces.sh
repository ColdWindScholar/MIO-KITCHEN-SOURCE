# Copyright (C) 2016 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
# # Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#!/bin/sh

# When signal is received, the stracer will get killed
# Call this (just to make sure anyway)
kill_strace() {
    ps_line=`ps -ef | grep strace | grep adb `
    if [ $? == 0 ]; then
        echo Killing `echo $ps_line | awk '{s = ""; for (i=8; i <= NF ; i++) s = s \
$i " "; print s}' `
        kill `echo $ps_line | awk '{print $2}' `
    fi
}

catch_sigint()
{
    echo "signal INT received, killing streaming trace capture"
    kill_strace
}

compile_tracefiles()
{
    for i in trace.*
    do
	if [ $i != trace.begin ] && [ $i != trace.tar ];
	then
	    egrep '\/system\/|\/data\/|\/vendor\/' $i > bar
# parse out /sys/devices/system/...
	    egrep -v '\/sys\/devices\/system\/' bar > bar0
	    mv bar0 bar
	    fgrep -v '= -1'	bar > foo
	    rm bar
	    # begin_time is seconds since epoch
	    begin_time=`cat trace.begin`
	    # replace seconds since epoch with SECONDS SINCE BOOT in the
	    # strace files
	    awk -v begin="$begin_time" '{ printf "%f strace ", $1 - begin; $1=""; print $0}' foo > bar
	    if [ -s bar ]
	    then
		echo parsing $i
		pid=${i##*.}
		compile_ioshark bar $pid.wl
		rm -f bar
	    else
		rm -f $i bar
	    fi
	fi
    done
}

# main() starts here

adb root && adb wait-for-device

adb shell 'ps' | grep zygote > zygote_pids

fgrep -v grep zygote_pids > bar
mv bar zygote_pids
pid1=`grep -w zygote zygote_pids | awk '{print $2}' `
pid2=`grep -w zygote64 zygote_pids | awk '{print $2}' `
rm -f zygote_pids

trap 'catch_sigint' INT

echo "^C this script once you finish running your test"

adb shell "date +%s > /data/local/tmp/trace.begin ; strace -p $pid1,$pid2 -o /data/local/tmp/trace -q -qq -f -ff -y -ttt -e trace=mmap2,read,write,pread64,pwrite64,fsync,fdatasync,openat,close,lseek,_llseek"

# Remove any remnant tracefiles first
rm -f trace.*

# Get the tracefiles from the device
adb shell 'cd /data/local/tmp ; tar cvf trace.tar trace.*'
adb pull /data/local/tmp/trace.tar

# Extract the tracefiles from the device
rm -f *.wl
tar xf trace.tar

# Compile the tracefiles
compile_tracefiles

# tar up the .wl files just created
rm -f wl.tar
tar cf wl.tar ioshark_filenames *.wl
