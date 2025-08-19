#!/bin/sh -u

parseoptions() {
    trace_reads=false
    trace_writes=false
    trace_writepages=false
    pid_view=false

    while [ $# -ge 1 ]
    do
	case $1 in
	    -r)
		trace_reads=true
		;;
	    -w)
		trace_writes=true
		;;
	    -p)
		trace_writepages=true
		;;
	    -v)
		pid_view=true
		;;
	    *)
		usage
		;;
	    esac
	shift
    done
}

usage() {
    echo "Usage: $0 [-r|-w|-p|-v]"
    exit 1
}

getmodel() {
    model=`adb shell getprop ro.product.name`
    # Releases are inconsistent with various trailing characters, remove them all
    model=`echo $model | sed 's/[ \t\r\n]*$//' `
    echo Found $model Device

    case $model in
	aosp_gobo | gobo | gobo_512)
	    get_go_devnames
            ;;
	marlin | sailfish | walleye | taimen | blueline | crosshatch)
	    get_marlin_sailfish_devnames
	    ;;
	angler)
	    get_angler_devnames
	    ;;
	bullhead)
	    get_bullhead_devnames
	    ;;
	volantis | volantisg)
	    get_volantis_devnames
	    ;;
	*)
	    echo Unknown Device $model -- trying Pixel config
	    get_marlin_sailfish_devnames
	    ;;
    esac
}

get_go_devnames () {
    # Hardcoding all of the mmcblk0 device for now
    block_device=mmcblk0
    bdev_set=true
}

get_volantis_devnames() {
    bdev_set=true
    block_device=mmcblk0
}

get_bullhead_devnames() {
    bdev_set=true
    block_device=mmcblk0
}

get_marlin_sailfish_devnames() {
    bdev_set=true
    block_device=sda
}

get_angler_devnames () {
    # Get the underlying bdev from the "by-name" mapping
    block_device=`adb shell 'find /dev/block/platform -name by-name | xargs ls -l' | grep system | awk '{ print $10 }' `
    # extract the last component of the absolute device pathname we got above
    block_device=`echo $block_device | awk 'BEGIN { FS ="/" } ; { print $4 }' | sed 's/p.*//g' `
    bdev_set=true
}

disk_stats_before() {
    if [ $bdev_set == true ]; then
	DISKSTATS=`adb shell 'cat /proc/diskstats' | fgrep -w $block_device `
	# Get BEFORE read stats for bdev
	BEFORE_RD_IOS=`echo $DISKSTATS | awk '{ print $4 }' `
	BEFORE_RD_SECTORS=`echo $DISKSTATS | awk '{ print $6 }' `
	# Get BEFORE write stats for bdev
	BEFORE_WR_IOS=`echo $DISKSTATS | awk '{ print $8 }' `
	BEFORE_WR_SECTORS=`echo $DISKSTATS | awk '{ print $10 }' `
    fi
    if [ $f2fs_fs == 1 ] ; then
	adb shell 'mount -o remount,background_gc=off /data'
	F2FS_GC_SEGMENTS_BEFORE=`adb shell 'cat /sys/kernel/debug/f2fs/status' | grep segments | egrep 'data|node' | awk '{ segments += $5 } END { print segments }' `
    fi
}

disk_stats_after() {
    if [ $bdev_set == true ]; then
	DISKSTATS=`adb shell 'cat /proc/diskstats' | fgrep -w $block_device `
	# Get AFTER read stats for bdev
	AFTER_RD_IOS=`echo $DISKSTATS | awk '{ print $4 }' `
	AFTER_RD_SECTORS=`echo $DISKSTATS | awk '{ print $6 }' `
	# Get BEFORE write stats for bdev
	AFTER_WR_IOS=`echo $DISKSTATS | awk '{ print $8 }' `
	AFTER_WR_SECTORS=`echo $DISKSTATS | awk '{ print $10 }' `
    fi
    if [ $f2fs_fs == 1 ] ; then
	F2FS_GC_SEGMENTS_AFTER=`adb shell 'cat /sys/kernel/debug/f2fs/status' | grep segments | egrep 'data|node' | awk '{ segments += $5 } END { print segments }' `
	adb shell 'mount -o remount,background_gc=on /data'
    fi
}

disk_stats_delta_rd() {
    file_data_KB=$1
    if [ $bdev_set == true ]; then
	# Sectors to KB
	READ_KB=`expr $AFTER_RD_SECTORS - $BEFORE_RD_SECTORS`
	READ_KB=`expr $READ_KB / 2`
	echo "Total (ALL) Read KB $block_device = "$READ_KB
	BLOCK_MINUS_FILE=`expr $READ_KB - $file_data_KB`
	echo "READ DELTA: Total Blockdev Reads KB - Total File Data Reads KB = "$BLOCK_MINUS_FILE KB
	echo "Total (ALL) Read IOs $block_device = "`expr $AFTER_RD_IOS - $BEFORE_RD_IOS`
    fi
}

disk_stats_delta_wr() {
    file_data_KB=$1
    if [ $bdev_set == true ]; then
	# Sectors to KB
	WRITE_KB=`expr $AFTER_WR_SECTORS - $BEFORE_WR_SECTORS`
	WRITE_KB=`expr $WRITE_KB / 2`
	BLOCK_MINUS_FILE=`expr $WRITE_KB - $file_data_KB`
	echo "WRITE DELTA: Total Blockdev Writes KB - Total File Data Writes KB = "$BLOCK_MINUS_FILE KB
	echo "Total (ALL) Write IOs $block_device = "`expr $AFTER_WR_IOS - $BEFORE_WR_IOS`
    fi
    if [ $f2fs_fs == 1 ] ; then
	F2FS_GC_SEGMENTS_DELTA=`expr $F2FS_GC_SEGMENTS_AFTER - $F2FS_GC_SEGMENTS_BEFORE`
	F2FS_GC_KB_DELTA=`expr $F2FS_GC_SEGMENTS_DELTA \\* 2048`
    fi
}

# For good measure clean up traces and reenable traces
clean_up_tracepoints() {
    # This is a good point to check if the Android FS tracepoints are enabled in the
    # kernel or not
    tracepoint_exists=`adb shell 'if [ -d /sys/kernel/debug/tracing/events/f2fs ]; then echo 0; else echo 1; fi' `
    if [ $tracepoint_exists == 1 ]; then
	echo "Android FS tracepoints not enabled in kernel. Exiting..."
	exit 1
    fi
    adb shell 'echo 0 > /sys/kernel/debug/tracing/tracing_on'
    adb shell 'echo 0 > /sys/kernel/debug/tracing/trace'
    if [ $trace_reads == true ]; then
	adb shell 'echo 1 > /sys/kernel/debug/tracing/events/f2fs/f2fs_dataread_start/enable'
    fi
    if [ $trace_writes == true ]; then
	adb shell 'echo 1 > /sys/kernel/debug/tracing/events/f2fs/f2fs_datawrite_start/enable'
    fi
    if [ $f2fs_fs == 1 ] ; then
	if [ $trace_writepages == true ]; then
	    adb shell 'echo 1 > /sys/kernel/debug/tracing/events/f2fs/f2fs_writepages/enable'
	fi
    fi
    adb shell 'echo 1 > /sys/kernel/debug/tracing/tracing_on'
}

# stream trace out of trace_pipe
# Start this in the background ('&')
streamtrace_start() {
    adb shell cat /sys/kernel/debug/tracing/trace_pipe > trace_saved
}

# When signal is received, the trace_pipe reader will get killed
# Call this (just to make sure anyway)
streamtrace_end() {
    ps_line=`ps -ef | grep trace_pipe | grep adb `
    if [ $? == 0 ]; then
	echo Killing `echo $ps_line | awk '{s = ""; for (i=8; i <= NF ; i++) s = s $i " "; print s}' `
	kill `echo $ps_line | awk '{print $2}' `
    fi
}

copyout_trace() {
    streamtrace_end
    if [ $trace_reads == true ]; then
	adb shell 'echo 0 > /sys/kernel/debug/tracing/events/f2fs/f2fs_dataread_start/enable'
    fi
    if [ $trace_writes == true ]; then
	adb shell 'echo 0 > /sys/kernel/debug/tracing/events/f2fs/f2fs_datawrite_start/enable'
    fi
    if [ $f2fs_fs == 1 ] ; then
	if [ $trace_writepages == true ]; then
	    adb shell 'echo 0 > /sys/kernel/debug/tracing/events/f2fs/f2fs_writepages/enable'
	fi
    fi
    adb shell 'echo 0 > /sys/kernel/debug/tracing/tracing_on'
}

prep_tracefile_common() {
    cp trace_saved $infile
    # Strip away all the extraneous stuff first
    fgrep $1 $infile | sed 's/^.* \[.*\] //' | sed s/://g | sed s/,//g > foo
    mv foo $infile
}

prep_tracefile_rd() {
    prep_tracefile_common f2fs_dataread
    # Strip away unnecessary stuff so we can compute latencies easily
    fgrep f2fs_dataread_start $infile > foo0
    # Throw away everything upto and including f2fs_dataread:
    cat foo0 | sed -n -e 's/^.*f2fs_dataread_start //p' > foo1
    mv foo1 $infile
    # At this stage, $infile should the following format :
    # entry_name <filename> offset <offset> bytes <bytes> cmdline <cmdline> pid <pid> i_size <i_size> ino <ino>
    rm foo0
}

prep_tracefile_writepages() {
    prep_tracefile_common f2fs_writepages
    # Throw away everything up to and including f2fs_writepages_start:
    cat $infile | sed -n -e 's/^.*f2fs_writepages //p' > foo1
    mv foo1 $infile
    # At this stage, $infile should the following format :
    # entry_name <filename> bytes <bytes> ino <ino>
}

# Latencies not supported for Writes. 'Write End' is just when the data has been
# written back to page cache.
prep_tracefile_wr() {
    prep_tracefile_common f2fs_datawrite
    fgrep f2fs_datawrite_start $infile > foo0
    # Throw away everything upto and including f2fs_datawrite:
    cat foo0 | sed -n -e 's/^.*f2fs_datawrite_start //p' > foo1
    mv foo1 $infile
    # At this stage, $infile should the following format :
    # entry_name <filename> offset <offset> bytes <bytes> cmdline <cmdline> pid <pid> i_size <i_size> ino <ino>
    rm foo0
}

get_unique_files_rw() {
    # Sort first by filename, then by pid
    cat $infile | sed s/,//g  | sort -d -k2,2 -k8,8 > foo1
    mv foo1 $infile
    # $infile now contains lines sorted by <filename, pid>
    # How many unique files are there ?
    cat $infile | awk '{ print $2 }' > foo1
    cat foo1 | uniq > uniq_files
    rm foo1
}

get_unique_files_writepages() {
    cat $infile | sed s/,//g  | sort -d -k2,2 > foo1
    # $infile now contains lines sorted by <filename>
    mv foo1 $infile
    # How many unique files are there ?
    cat $infile | awk '{ print $2 }' > foo1
    cat foo1 | uniq > uniq_files
    rm foo1
}

get_unique_pids_byfile() {
    # How many unique pids are there reading this file ?
    cat $1 | awk '{ print $8 }' > foo1
    cat foo1 | uniq > uniq_pids_byfile
    rm foo1
}

get_unique_pids() {
    # Sort first by pid, then by filename
    cat $infile | sed s/,//g  | sort -d -k8,8 -k2,2 > foo1
    mv foo1 $infile
    # $infile now contains lines sorted by <pid, filename>
    # How many unique pids are there ?
    cat $infile | awk '{ print $8 }' > foo1
    cat foo1 | uniq > uniq_pids
    rm foo1
}

get_unique_files_bypid() {
    # How many unique files are there read by this pid ?
    cat $1 | awk '{ print $2 }' > foo1
    cat foo1 | uniq > uniq_files_bypid
    rm foo1
}

catch_sigint()
{
    echo "signal INT received, killing streaming trace capture"
    streamtrace_end
}


prep_to_do_something() {
#    adb shell "am force-stop com.android.chrome"
#    adb shell "am force-stop com.google.android.gm"
    adb shell 'echo 3 > /proc/sys/vm/drop_caches'
    sleep 1
}

do_something() {
    # Arrange things so that the first SIGINT will kill the
    # child process (sleep), but will return to the parent.
    trap 'catch_sigint'  INT
    echo "OK to kill sleep when test is done"
    sleep 30d
#    adb shell "am start -W -n com.android.chrome/com.google.android.apps.chrome.Main"
#    adb shell "am start -W -n com.google.android.gm/.ConversationListActivityGmail"
}

# Get the aggregate list of files read/written. For each file, break up the IOs by pid
process_files_rw() {
    read_write=$1
    get_unique_files_rw
    # Loop over each file that was involved in IO
    # Find all the pids doing IO on that file
    # Aggregate the IO done by each pid on that file and dump it out
    grand_total_KB=0
    cp $infile tempfile
    for i in `cat uniq_files`
    do
	# Get just the tracepoints for this file
	fgrep -w "$i" tempfile > subtrace
	if [ -s subtrace ]; then
	    echo "File: $i"
	    total_file_KB=0
	    # Remove the tracepoints we just picked up
	    fgrep -v -w "$i" tempfile > foo
	    mv foo tempfile
	    # Get all the pids doing IO on this file
	    get_unique_pids_byfile subtrace
	    for j in `cat uniq_pids_byfile`
	    do
		echo -n "            $j $read_write: "
		pid_KB=`fgrep -w "$j" subtrace | awk '{ bytes += $6 } END { print bytes }' `
		pid_KB=`expr $pid_KB / 1024`
		echo "$pid_KB KB"
		total_file_KB=`expr $total_file_KB + $pid_KB`
	    done
	    i_size=`tail -n1 subtrace  | awk '{ if ($12 > 1024) printf "%d KB", ($12/1024); else printf "%d bytes", $12; }' `
	    echo "            Total $read_write: $total_file_KB KB i_size: $i_size"
	    grand_total_KB=`expr $grand_total_KB + $total_file_KB`
	fi
    done
    echo "Grand Total File DATA KB $read_write $grand_total_KB"
    rm tempfile
}

process_files_writepages() {
    get_unique_files_writepages
    # Loop over each file that was involved in IO
    # Aggregate the IO done on that file and dump it out
    grand_total_KB=0
    cp $infile tempfile
    for i in `cat uniq_files`
    do
	# Get just the tracepoints for this file
	fgrep -w "$i" tempfile > subtrace
	if [ -s subtrace ]; then
	    fgrep -v -w "$i" tempfile > foo
	    mv foo tempfile
	    total_file_KB=`cat subtrace | awk '{ bytes += $4 } END { print bytes }' `
	    total_file_KB=`expr $total_file_KB / 1024`
	    if [ $total_file_KB -gt 0 ]; then
		echo "File: $i Total $read_write: $total_file_KB KB"
		grand_total_KB=`expr $grand_total_KB + $total_file_KB`
	    fi
	fi
    done
    echo "Grand Total File DATA KB Writepages $grand_total_KB"
    rm tempfile
}

# Get the aggregate list of pids. For each pid, break up the IOs by file
process_pids() {
    read_write=$1
    get_unique_pids
    list_of_pids=`cat uniq_pids`
    # $list_of_pids is a list of all the pids involved in IO
    #
    # Loop over each pid that was involved in IO
    # Find all the files the pid was doing IO on
    # Aggregate the IO done by the pid for each file and dump it out
    #
    grand_total_KB=0
    for i in $list_of_pids
    do
	echo "PID: $i"
	total_pid_KB=0
	# Get just the tracepoints for this pid
	fgrep -w "$i" $infile > subtrace
	# Get all the pids doing IO on this file
	get_unique_files_bypid subtrace
	list_of_files=`cat uniq_files_bypid`
	# $list_of_files is a list of all the files IO'ed by this pid
	for j in $list_of_files
	do
	    i_size=`fgrep -w "$j" subtrace | tail -n1 | awk '{ if ($12 > 1024) printf "%d KB", ($12/1024); else printf "%d bytes", $12; }' `
	    file_KB=`fgrep -w "$j" subtrace | awk '{ bytes += $6 } END { print bytes }' `
	    file_KB=`expr $file_KB / 1024`
	    echo "            $j $read_write: $file_KB KB i_size: $i_size"
	    total_pid_KB=`expr $total_pid_KB + $file_KB`
	done
	echo "            Total $read_write: $total_pid_KB KB"
	grand_total_KB=`expr $grand_total_KB + $total_pid_KB`
    done
    echo "Grand Total File DATA KB $read_write $grand_total_KB"
}

# main() starts here :

if [ $# -lt 1 ]; then
    usage
fi

bdev_set=false
infile=tracefile.$$

parseoptions $@
adb root && sleep 2
getmodel

found_f2fs=`adb shell 'mount | grep f2fs > /dev/null; echo $?' `

if [ $found_f2fs == 0 ]; then
    f2fs_fs=1
else
    f2fs_fs=0
fi

if [ $f2fs_fs == 0 ] && [ $trace_writepages == true ]; then
    echo "Writepages is only supported with f2fs, please use -r, -w"
    exit 1
fi

prep_to_do_something

clean_up_tracepoints
disk_stats_before
# Start streaming the trace into the tracefile
streamtrace_start &

do_something

streamtrace_end
disk_stats_after

copyout_trace

if [ $trace_reads == true ]; then
    echo
    echo "READS :"
    echo "_______"
    echo
    prep_tracefile_rd
    # Get file specific stats - for each file, how many pids read that file ?
    echo "FILE VIEW:"
    process_files_rw Reads
    if [ $pid_view == true ]; then
	# Get pid specific stats - for each pid, what files do they do IO on ?
	echo "PID VIEW:"
	process_pids Reads
    fi
    disk_stats_delta_rd $grand_total_KB

    debug_FileKB_rd=`cat $infile | awk '{ bytes += $6 } END { printf "%d", bytes/1024 }' `
    echo Debug Grand Total KB READ $debug_FileKB_rd
fi

if [ $trace_writes == true ]; then
    echo
    echo "Writes :"
    echo "_______"
    echo
    prep_tracefile_wr
    # Get file specific stats - for each file, how many pids read that file ?

    echo "FILE VIEW:"
    process_files_rw Writes
    if [ $pid_view == true ]; then
	# Get pid specific stats - for each pid, what files do they do IO on ?
	echo "PID VIEW:"
	process_pids Writes
    fi
    disk_stats_delta_wr $grand_total_KB

    if [ $f2fs_fs == 1 ] ; then
	echo f2fs GC_KB delta = $F2FS_GC_KB_DELTA
    fi
fi

if [ $f2fs_fs == 1 ] && [ $trace_writepages == true ] ; then
    echo
    echo "Writepages :"
    echo "__________"
    echo
    prep_tracefile_writepages
    # Get file specific stats - for each file, how much did we writepage ?

    echo "FILE VIEW:"
    process_files_writepages

    disk_stats_delta_wr $grand_total_KB

    echo f2fs GC_KB delta = $F2FS_GC_KB_DELTA
fi

rm -rf tracefile* uniq_* subtrace trace_saved
