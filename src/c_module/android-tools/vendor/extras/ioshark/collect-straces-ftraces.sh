#!/bin/sh

# This function just re-writes the timestamp of the strace entries to be
# seconds.usecs since boot. To match the timestamping of ftrace (so we can
# merge them later).
process_strace()
{
    strace=$1
    # parse in data/system/vendor and parse out /sys/devices/system/...
    egrep '\/system\/|\/data\/|\/vendor\/' $strace | egrep -v '\/sys\/devices\/system\/' > bar
    fgrep -v '= -1' bar > foo
    mv foo bar
    # begin_time is seconds since epoch
    begin_time=`cat trace.begin`
    # replace seconds since epoch with SECONDS SINCE BOOT in the
    # strace files
    awk -v begin="$begin_time" '{ printf "%f strace ", $1 - begin; $1=""; print $0}' bar > $2
    rm bar
}

#
# This function processes the ftrace file, removing the fields that we don't care
# about, breaks up the ftrace file into one file per pid.
# Input : One single fstrace file.
# Output : Multiple fstrace.pid files.
prep_fstrace()
{
    # Remove leading junk
    fgrep f2fs_data $1 | sed 's/^.* \[.*\] //' | sed s/://g | sed s/,//g > foo
    # Sanitize the filenames, removing spaces within the filename etc
    sed 's/f2fs_dataread_start/read/' foo > bar1
    mv bar1 bar
    # First column is timestamp SECONDS SINCE BOOT
    awk '{ print $2, "ftrace", $3, $5, $7, $9, $13 }' bar > foo
    #awk '{ s ="" ; for (i=2; i <= NF ; i++) s = s $i " "; print s}' bar > foo
    rm bar
    # Get all the uniq pids
    awk '{print $7}' foo | sort | uniq > pidlist
    for i in `cat pidlist`
    do
	awk -v pid=$i '{ if (pid == $7) print $0}' foo > fstrace.$i
    done
    rm pidlist
    rm foo
}

# Merge straces and ftraces.
# The goal here is to catch mmap'ed IO (reads) that won't be in the
# strace file. The algorithm is to look for mmaps in the strace file,
# use the files tha are mmap'ed to search in the ftraces to pick up
# tracepoints from there, and merge those with the straces.
# The output of this function is a set of parsed_input_trace.<pid>
# files, that can then be compiled into .wl files
merge_compile()
{
    for stracefile in trace.*
    do
	if [ $stracefile == trace.begin ] || [ $stracefile == trace.tar ];
	then
	    continue
	fi
	# Get the pid from the strace filename (pid is the extension)
	pid=${stracefile##*.}
	process_strace $stracefile foo.$pid
	if ! [ -s foo.$pid ]; then
	    rm foo.$pid
	    continue
	fi
	#
	# If we have matching strace and ftrace files, then look for mmaps in
	# the strace pluck the corresponding entries for the mmap (mmaped IO)
	# from the ftrace and merge them into the strace
	#
	if [ -f fstrace.$pid ]; then
	    fgrep mmap foo.$pid > bar
	    if [ -s bar ]; then
		# Get all the unique mmap'ed filenames from the strace
		awk '{ print $7 }' bar | sed 's/^[^<]*<//g' | sed 's/>,//g' > mapped_files
		# Pluck all the lines from the ftrace corresponding to the mmaps
		cat /dev/null > footemp
		for j in `sort mapped_files | uniq`
		do
		    # Merge the readpage(s) traces from the ftrace into strace
		    # for this mmaped file.
		    grep -w $j fstrace.$pid > foobar
		    if [ $? == 0 ]; then
			sort foo.$pid foobar >> footemp
		    fi
		    rm foobar
		done
		rm mapped_files
		if [ -s footemp ]; then
		    mv footemp parsed_input_trace.$pid
		else
		    mv foo.$pid parsed_input_trace.$pid
		fi
	    else
		mv foo.$pid parsed_input_trace.$pid
	    fi
	    rm bar
	else
	    mv foo.$pid parsed_input_trace.$pid
	fi
	echo compiling parsed_input_trace.$pid
	compile_ioshark parsed_input_trace.$pid $pid.wl
	rm parsed_input_trace.$pid
	rm -f foo.$pid
    done
}

catch_sigint()
{
    echo "signal INT received, killing streaming trace capture"
    ps_line=`ps -ef | grep trace_pipe | grep adb `
    if [ $? == 0 ]; then
        echo Killing `echo $ps_line | awk '{s = ""; for (i=8; i <= NF ; i++) s = s $i " "; print s}' `
	kill `echo $ps_line | awk '{print $2}' `
    fi
    ps_line=`ps -ef | grep strace | grep adb `
    if [ $? == 0 ]; then
        echo Killing `echo $ps_line | awk '{s = ""; for (i=8; i <= NF ; i++) s = s $i " "; print s}' `
	kill `echo $ps_line | awk '{print $2}' `
    fi
}

enable_tracepoints()
{
    adb shell "echo 1 > /sys/kernel/debug/tracing/events/f2fs/f2fs_dataread_start/enable"
    adb shell "echo 1 > /sys/kernel/debug/tracing/tracing_on"
}

disable_tracepoints()
{
    adb shell "echo 0 > /sys/kernel/debug/tracing/events/f2fs/f2fs_dataread_start/enable"
    adb shell "echo 0 > /sys/kernel/debug/tracing/tracing_on"
}

kill_traces()
{
    ps_line=`ps -ef | grep trace_pipe | grep adb `
    if [ $? == 0 ]; then
        echo Killing `echo $ps_line | awk '{s = ""; for (i=8; i <= NF ; i++) s = s $i " "; print s}' `
	kill `echo $ps_line | awk '{print $2}' `
    fi
    ps_line=`ps -ef | grep strace | grep adb `
    if [ $? == 0 ]; then
        echo Killing `echo $ps_line | awk '{s = ""; for (i=8; i <= NF ; i++) s = s $i " "; print s}' `
	kill `echo $ps_line | awk '{print $2}' `
    fi
}

catch_sigint()
{
    echo "signal INT received, killing streaming trace capture"
    kill_traces
}

# main() starts here

adb root && adb wait-for-device

enable_tracepoints

trap 'catch_sigint' INT

adb shell 'ps' | grep zygote > zygote_pids
fgrep -v grep zygote_pids > bar
mv bar zygote_pids
pid1=`grep -w zygote zygote_pids | awk '{print $2}' `
pid2=`grep -w zygote64 zygote_pids | awk '{print $2}' `
rm -f zygote_pids

adb shell "date +%s > /data/local/tmp/trace.begin ; strace -p $pid1,$pid2 -o /data/local/tmp/trace -q -qq -f -ff -y -ttt -e trace=mmap2,read,write,pread64,pwrite64,fsync,fdatasync,openat,close,lseek,_llseek" &
adb shell "cat /sys/kernel/debug/tracing/trace_pipe" > fstrace &

echo "^C this when done with the test"

wait

adb shell 'monkey -p com.android.alarmclock -p com.android.chrome -p com.android.calculator -p com.android.calendar -p com.google.android.calendar -p com.google.android.camera -p com.android.contacts -p com.google.android.gm -p com.android.im -p com.android.launcher -p com.google.android.apps.maps -p com.android.mms -p com.google.android.music -p com.android.phone -p com.google.android.youtube -p com.android.email -p com.google.android.voicesearch -c android.intent.category.LAUNCHER --throttle 200 --ignore-security-exceptions --ignore-crashes --ignore-timeouts -v -v -v 25000'

kill_traces

disable_tracepoints

rm -f trace.*
rm -f fstrace.*
rm -f *.wl
rm -f parsed*

# Get the tracefiles from the device
adb shell 'cd /data/local/tmp ; tar cvf trace.tar trace.*'
adb pull /data/local/tmp/trace.tar
tar xf trace.tar

# Pre-process the ftrace file
prep_fstrace fstrace
# Merge the ftrace file(s) with the strace files
merge_compile

# tar up the .wl files just created
tar cf wl.tar ioshark_filenames *.wl
