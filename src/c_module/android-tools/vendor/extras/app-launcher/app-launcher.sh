#!/bin/bash

parseoptions() {
    verbose=false
    user_experience=false
    little_cores_off=false
    iterations=0
    pagecached=false

    adb="adb"
    while [ $# -gt 1 ]
    do
        case $1 in
            -a)
                ;;
            -b)
                little_cores_off=true
                ;;
            -c)
                pagecached=true
                ;;
            -h)
                usage
                ;;
            -s)
                if [ -z "$2" ]; then
                    usage
                fi
                adb="adb -s $2"
                shift
                ;;
            -u)
                user_experience=true
                ;;
            -v)
                verbose=true
                ;;
            *)
                usage
                ;;
            esac
        shift
    done

    iterations=$1
    if [ "$iterations" -lt 100 ]; then
        usage
    fi
}

getstats () {
    infile=$1
    app=$2
    echo "Data for $app :"

    # Activity Manager reports ThisTime and TotalTime. TotalTime seems to be
    # a more measure of the launch from the users perspective. So using TotalTime
    # as our metric for launch latency

    # From Activity Manager
    echo "Launch Time (TotalTime) :"
    grep -F TotalTime "$infile" | awk '{print $2}' | computestats

    # Data from simpleperf
    echo "cpu-cycles :"
    grep -F cpu-cycles "$infile" | awk '{print $1}' | sed s/,//g | computestats

    # CPU util% Data from /proc/stat
    echo "cpu-util% :"
    grep -F 'Total CPU util' "$infile" | awk '{print $5}' | computestatsf
    echo "user-cpu-util% :"
    grep -F 'User CPU util' "$infile" | awk '{print $5}' | computestatsf
    echo "sys-cpu-util% (incl hardirq/softirq) :"
    grep -F 'Sys CPU util' "$infile" | awk '{print $5}' | computestatsf

    if [ $verbose == true ]; then
        echo "instructions : "
        grep -F instructions "$infile" | awk '{print $1}' | sed s/,//g | computestats

        echo "cycles per instruction : "
        grep -F instructions "$infile" | awk '{print $4}' | sed s/,//g | computestatsf

        echo "branch-misses : "
        grep -F branch-misses "$infile" | awk '{print $1}' | sed s/,//g | computestats

        echo "context-switches : "
        grep -F context-switches "$infile" | awk '{print $1}' | sed s/,//g | computestats

        echo "page-faults : "
        grep -F page-faults "$infile" | awk '{print $1}' | sed s/,//g | computestats
    fi

    if [ "$system_bdev_set" == true ]; then
        # (Storage) Data from /proc we've collected
        echo "KB read for $system_block_device blkdev :"
        grep -F KB "$infile" | grep system | awk '{print $5}' | computestats

        echo "iowait% :"
        grep -F IOwait "$infile" | awk '{print $3}' | computestatsf

        echo "Device util% for $system_block_device blkdev :"
        grep -F 'Device util' "$infile" | awk '{print $4}' | computestatsf
    fi
}

cpufreq_volantis() {
    echo "Setting Governor to performance"
    if [ $little_cores_off == true ]; then
        echo "Cannot turn off Little cores on $model"
        exit 1
    fi
    i=0
    num_cores=2
    while [ $i -lt  $num_cores ]
    do
        $adb shell "echo performance  > /sys/devices/system/cpu/cpu$i/cpufreq/scaling_g\
overnor"
        $adb shell "echo 2499000 > /sys/devices/system/cpu/cpu$i/cpufreq/scaling_max_fr\
eq"
        i=$((i + 1))
    done
    # Lock the GPU frequencies
    echo -n 852000000 > /d/clock/override.gbus/rate
    echo -n 1 > /d/clock/override.gbus/state
}

cpufreq_fugu() {
    echo "Setting Governor to performance"
    if [ $little_cores_off == true ]; then
        echo "Cannot turn off Little cores on $model"
        exit 1
    fi
    i=0
    num_cores=4
    while [ $i -lt  $num_cores ]
    do
        $adb shell "echo performance  > /sys/devices/system/cpu/cpu$i/cpufreq/scaling_governor"
        $adb shell "echo 1833000 > /sys/devices/system/cpu/cpu$i/cpufreq/scaling_max_freq"
        i=$((i + 1))
    done
}

cpufreq_taimen_walleye () {
    echo "Setting Governor to performance"
    # GPU Governor and Frequency
    $adb shell 'echo performance > /sys/class/kgsl/kgsl-3d0/devfreq/governor'
    $adb shell 'echo 624000000 > /sys/class/kgsl/kgsl-3d0/devfreq/max_freq'
    if [ $little_cores_off == true ]; then
        # Disable Little Cores, force app to run on big cores
        echo "Disabling Little Cores"
        $adb shell 'echo 0 > /sys/devices/system/cpu/cpu0/online'
        $adb shell 'echo 0 > /sys/devices/system/cpu/cpu1/online'
        $adb shell 'echo 0 > /sys/devices/system/cpu/cpu2/online'
        $adb shell 'echo 0 > /sys/devices/system/cpu/cpu3/online'
    else
        echo "Enabling All Cores"
        $adb shell 'echo 1 > /sys/devices/system/cpu/cpu0/online'
        $adb shell 'echo 1 > /sys/devices/system/cpu/cpu1/online'
        $adb shell 'echo 1 > /sys/devices/system/cpu/cpu2/online'
        $adb shell 'echo 1 > /sys/devices/system/cpu/cpu3/online'
        $adb shell 'echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'
        $adb shell 'echo 1900800 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq'
    fi
    # Set Governor to performance, up scaling_max_frequency to highest
    $adb shell 'echo performance  > /sys/devices/system/cpu/cpu4/cpufreq/scaling_governor'
    # Only necessary to set max_freq on cpu4, cpu5-7 are in same cluster and will
    # automatically get the same settings
    $adb shell 'echo 2457600 > /sys/devices/system/cpu/cpu2/cpufreq/scaling_max_freq'
}

cpufreq_marlin_sailfish () {
    echo "Setting Governor to performance"
    # GPU Governor and Frequency
    $adb shell 'echo performance > /sys/class/kgsl/kgsl-3d0/devfreq/governor'
    $adb shell 'echo 624000000 > /sys/class/kgsl/kgsl-3d0/devfreq/max_freq'
    if [ $little_cores_off == true ]; then
        # Disable Little Cores, force app to run on big cores
        echo "Disabling Little Cores"
        $adb shell 'echo 0 > /sys/devices/system/cpu/cpu0/online'
        $adb shell 'echo 0 > /sys/devices/system/cpu/cpu1/online'
    else
        echo "Enabling All Cores"
        $adb shell 'echo 1 > /sys/devices/system/cpu/cpu0/online'
        $adb shell 'echo 1 > /sys/devices/system/cpu/cpu1/online'
        $adb shell 'echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'
        $adb shell 'echo 1996800 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq'
        # cpu1 needed ?
        $adb shell 'echo performance > /sys/devices/system/cpu/cpu1/cpufreq/scaling_governor'
        $adb shell 'echo 1996800 > /sys/devices/system/cpu/cpu1/cpufreq/scaling_max_freq'
    fi
    # Set Governor to performance, up scaling_max_frequency to highest
    $adb shell 'echo performance  > /sys/devices/system/cpu/cpu2/cpufreq/scaling_governor'
    # Only necessary to set max_freq on cpu2, cpu3 is in same cluster and will
    # automatically get the same settings
    $adb shell 'echo 2150400 > /sys/devices/system/cpu/cpu2/cpufreq/scaling_max_freq'
}

cpufreq_angler () {
    echo "Setting Governor and Frequency"
    # GPU Governor and Frequency
    $adb shell "echo performance > /sys/class/kgsl/kgsl-3d0/devfreq/governor"
    $adb shell "echo 0 > /sys/class/kgsl/kgsl-3d0/bus_split"
    $adb shell "echo 1 > /sys/class/kgsl/kgsl-3d0/force_clk_on"
    $adb shell "echo 10000 > /sys/class/kgsl/kgsl-3d0/idle_timer"
    if [ $little_cores_off == true ]; then
        # Disable Little Cores, force app to run on big cores
        echo "Disabling Little Cores"
        i=0
        num_cores=4
        while [ $i -lt $num_cores ]
        do
            $adb shell "echo 0 > /sys/devices/system/cpu/cpu$i/online"
            i=$((i + 1))
        done
    else
        echo "Enabling All Cores"
        # Enable Little cores here, set governor to performance
        # Lock frequency of little cores
        i=0
        num_cores=4
        while [ $i -lt $num_cores ]
        do
            $adb shell "echo 1 > /sys/devices/system/cpu/cpu$i/online"
            $adb shell "echo performance > /sys/devices/system/cpu/cpu$i/cpufreq/scaling_governor"
            # Lock frequency of little cores
            $adb shell "echo 1555200 > /sys/devices/system/cpu/cpu$i/cpufreq/scaling_max_freq"
            i=$((i + 1))
        done
    fi
    i=4
    num_cores=8
    while [ $i -lt $num_cores ]
    do
        $adb shell "echo performance > /sys/devices/system/cpu/cpu$i/cpufreq/scaling_governor"
        # Lock frequency of big cores
        $adb shell "echo 1958400 > /sys/devices/system/cpu/cpu$i/cpufreq/scaling_max_freq"
        i=$((i + 1))
    done
}

cpufreq_go() {
    echo "Setting Governor to performance"
    $adb shell 'echo 0 > /proc/hps/enabled'
    for i in 0 1 2 3
    do
	$adb shell "echo 1 > /sys/devices/system/cpu/cpu$i/online"
	$adb shell "echo performance > /sys/devices/system/cpu/cpu$i/cpufreq/scaling_governor"
	$adb shell "echo 1092000 > /sys/devices/system/cpu/cpu$i/cpufreq/scaling_max_freq"
    done
}

get_taimen_walleye_devnames () {
    # This bit of code required to get the block dev for /system and /vendor
    # Suffix can be _a or _b, depending on what the active /system partition is
#    suffix=`$adb shell getprop ro.boot.slot_suffix`
    # Get the blockdevice using the suffix we got above
#    system_block_device=`$adb shell ls -l /dev/block/platform/soc/*ufs*/by-name/system$suffix | awk '{ print $10 }' `
    # Vendor is more straightforward, but we don't use it right now
#    vendor_block_device=`$adb shell df /vendor | grep -v Filesystem | awk '{print $1}' `
    # finally extract the last component of the absolute device pathname we got above
#    system_block_device=`echo $system_block_device | awk 'BEGIN { FS ="/" } ; { print $4 }' `
#    vendor_block_device=`echo $vendor_block_device | awk 'BEGIN { FS ="/" } ; { print $4 }' `
    system_bdev_set=true
#   For now, hardcode sda for Marlin/Sailfish block device
#   XXX - We'll get stats for entire device
    system_block_device=sda
    echo Block Device $system_block_device
}

#
# This strange bit of logic is needed to get the underlying block devices for /system
# for Marlin/Sailfish
#
get_marlin_sailfish_devnames () {
    # This bit of code required to get the block dev for /system and /vendor
    # Suffix can be _a or _b, depending on what the active /system partition is
#    suffix=`$adb shell getprop ro.boot.slot_suffix`
    # Get the blockdevice using the suffix we got above
#    system_block_device=`$adb shell ls -l /dev/block/platform/soc/*ufs*/by-name/system$suffix | awk '{ print $10 }' `
    # Vendor is more straightforward, but we don't use it right now
#    vendor_block_device=`$adb shell df /vendor | grep -v Filesystem | awk '{print $1}' `
    # finally extract the last component of the absolute device pathname we got above
#    system_block_device=`echo $system_block_device | awk 'BEGIN { FS ="/" } ; { print $4 }' `
#    vendor_block_device=`echo $vendor_block_device | awk 'BEGIN { FS ="/" } ; { print $4 }' `
    system_bdev_set=true
#   For now, hardcode sda for Marlin/Sailfish block device
#   XXX - We'll get stats for entire device
    system_block_device=sda
    echo Block Device $system_block_device
}

get_angler_devnames () {
    # Get the underlying bdev from the "by-name" mapping
    system_block_device=$($adb shell 'find /dev/block/platform -name by-name | xargs ls -l' | grep system | awk '{ print $10 }')
    # extract the last component of the absolute device pathname we got above
    system_block_device=$(echo "$system_block_device" | awk 'BEGIN { FS ="/" } ; { print $4 }')
    # vendor is unused right now, but get the bdev anyway in case we decide to use it
    # Get the underlying bdev from the "by-name" mapping
    vendor_block_device=$($adb shell 'find /dev/block/platform -name by-name | xargs ls -l' | grep vendor | awk '{ print $10 }')
    # extract the last component of the absolute device pathname we got above
    vendor_block_device=$(echo "$vendor_block_device" | awk 'BEGIN { FS ="/" } ; { print $4 }')
    system_bdev_set=true
}

get_fugu_devnames () {
    system_block_device=$($adb shell ls -l /dev/block/by-name/system | awk '{ print $10 }')
    system_block_device=$(echo "$system_block_device" | awk 'BEGIN { FS ="/" } ; { print $4 }')
    system_bdev_set=true
}

dev_name_default_mmc () {
    system_block_device=mmcblk0
    system_bdev_set=true
}

get_volantis_devnames () {
    dev_name_default_mmc
}

get_go_devnames () {
    dev_name_default_mmc
}

system_stats_before() {
    if [ $system_bdev_set == true ]; then
        # Get BEFORE read stats for /system
        system=$($adb shell 'cat /proc/diskstats' | grep -w $system_block_device)
        BEFORE_RD_IOS_SYSTEM=$(echo "$system" | awk '{ print $4 }')
        BEFORE_RD_SECTORS_SYSTEM=$(echo "$system" | awk '{ print $6 }')
        # iowait% computation
        procstat=$($adb shell 'cat /proc/stat' | grep -w cpu)
        user_ticks_before=$(echo "$procstat" | awk '{ print ($2 + $3) }')
        sys_ticks_before=$(echo "$procstat" | awk '{ print ($4 + $7 + $8) }')
        cpubusy_ticks_before=$(echo "$procstat" | awk '{ print ($2 + $3 + $4 + $7 + $8) }')
        iowait_ticks_before=$(echo "$procstat" | awk '{ print $6 }')
        total_ticks_before=$(echo "$procstat" | awk '{ print ($2 + $3 + $4 + $5 + $7 + $8) }')
        # Device util% computation
        uptime=$($adb shell 'cat /proc/uptime')
        uptime_before_ms=$(echo "$uptime" | awk '{ print ($1 * 1000) }')
        device_util_before_ms=$(echo "$system" | awk '{ print ($13) }')
    fi
}

system_stats_after() {
    if [ $system_bdev_set == true ]; then
        # Get AFTER read stats for /system
        system=$($adb shell 'cat /proc/diskstats' | grep -w $system_block_device)
        AFTER_RD_IOS_SYSTEM=$(echo "$system" | awk '{ print $4 }')
        AFTER_RD_SECTORS_SYSTEM=$(echo "$system" | awk '{ print $6 }')
        # iowait% computation
        procstat=$($adb shell 'cat /proc/stat' | grep -w cpu)
        user_ticks_after=$(echo "$procstat" | awk '{ print ($2 + $3) }')
        sys_ticks_after=$(echo "$procstat" | awk '{ print ($4 + $7 + $8) }')
        cpubusy_ticks_after=$(echo "$procstat" | awk '{ print ($2 + $3 + $4 + $7 + $8) }')
        iowait_ticks_after=$(echo "$procstat" | awk '{ print $6 }')
        total_ticks_after=$(echo "$procstat" | awk '{ print ($2 + $3 + $4 + $5 + $7 + $8) }')
        # Device util% computation
        uptime=$($adb shell 'cat /proc/uptime')
        uptime_after_ms=$(echo "$uptime" | awk '{ print ($1 * 1000) }')
        device_util_after_ms=$(echo "$system" | awk '{ print ($13) }')
    fi
}

system_stats_delta() {
    if [ $system_bdev_set == true ]; then
        # Sectors to KB
        READ_KB_SYSTEM=$((AFTER_RD_SECTORS_SYSTEM - BEFORE_RD_SECTORS_SYSTEM))
        READ_KB_SYSTEM=$((READ_KB_SYSTEM / 2))
        echo Read IOs /system = $((AFTER_RD_IOS_SYSTEM - BEFORE_RD_IOS_SYSTEM))
        echo Read KB /system = $READ_KB_SYSTEM
        echo "$iowait_ticks_before" "$iowait_ticks_after" "$total_ticks_before" "$total_ticks_after" | awk '{ printf "IOwait = %.2f\n", (($2 - $1) * 100.0) / ($4 - $3) }'
        echo "$device_util_before_ms" "$device_util_after_ms" "$uptime_before_ms" "$uptime_after_ms" | awk '{ printf "Device util% = %.2f\n", (($2 - $1) * 100.0) / ($4 - $3) }'
        echo "$user_ticks_after" "$user_ticks_before" "$total_ticks_after" "$total_ticks_before" | awk '{ printf "User CPU util% = %.2f\n", (($1 - $2) * 100.0) / ($3 - $4) }'
        echo "$sys_ticks_after" "$sys_ticks_before" "$total_ticks_after" "$total_ticks_before" | awk '{ printf "Sys CPU util% = %.2f\n", (($1 - $2) * 100.0) / ($3 - $4) }'
        echo "$cpubusy_ticks_after" "$cpubusy_ticks_before" "$total_ticks_after" "$total_ticks_before" | awk '{ printf "Total CPU util% = %.2f\n", (($1 - $2) * 100.0) / ($3 - $4) }'
    fi
}

launch_app() {
    package=$1
    activity=$2
    $adb shell "am force-stop $package"
    sleep 1

    printf "Testing %s: \n" "$package" 1>&2
    i=0
    while [ $i -lt "$iterations" ]
    do
        if [ $pagecached == false ]; then
            $adb shell 'echo 3 > /proc/sys/vm/drop_caches'
        fi
        printf '[ %d%% ]\r' "$((i * 100 / iterations))" 1>&2
        # The -W argument to am start forces am start to wait till the launch completes.
        # The -S argument forces it to kill any existing app that is running first
        # eg. adb shell 'am start -W -S -n com.android.chrome/com.google.android.apps.chrome.Main'
        system_stats_before
        $adb shell "simpleperf stat -a am start -W -n $package/$activity"
        system_stats_after
        system_stats_delta
        sleep 1
        $adb shell "am force-stop $package"
        sleep 1
        i=$((i + 1))
    done
    printf "\n" 1>&2
}

launch_fugu_apps() {
    launch_app com.google.android.youtube.tv com.google.android.apps.youtube.tv.activity.TvGuideActivity > "$BASHPID-youtube-$model"
    getstats "$BASHPID-youtube-$model" YouTube
    launch_app com.google.android.play.games com.google.android.gms.games.pano.activity.PanoGamesOnboardHostActivity > "$BASHPID-games-$model"
    getstats "$BASHPID-games-$model" Games
    launch_app com.google.android.music com.android.music.activitymanagement.TopLevelActivity > "$BASHPID-music-$model"
    getstats "$BASHPID-music-$model" Music
}

launch_phone_apps() {
    launch_app com.android.chrome com.google.android.apps.chrome.Main > "$BASHPID-chrome-$model"
    getstats "$BASHPID-chrome-$model" Chrome
    launch_app com.google.android.GoogleCamera com.android.camera.CameraActivity > "$BASHPID-camera-$model"
    getstats "$BASHPID-camera-$model" Camera
    launch_app com.google.android.apps.maps com.google.android.maps.MapsActivity > "$BASHPID-maps-$model"
    getstats "$BASHPID-maps-$model" Maps
    launch_app com.google.android.youtube com.google.android.apps.youtube.app.WatchWhileActivity > "$BASHPID-youtube-$model"
    getstats "$BASHPID-youtube-$model" YouTube
}

launch_go_apps() {
    launch_app com.android.chrome com.google.android.apps.chrome.Main > "$BASHPID-chrome-$model"
    getstats "$BASHPID-chrome-$model" Chrome
    launch_app com.google.android.gm.lite com.google.android.gm.ConversationListActivityGmail > "$BASHPID-gmailgo-$model"
    getstats "$BASHPID-gmailgo-$model" GmailGo
    launch_app com.google.android.apps.youtube.mango com.google.android.apps.youtube.lite.frontend.activities.SplashActivity > "$BASHPID-youtubego-$model"
    getstats "$BASHPID-youtubego-$model" YouTubeGo
    launch_app com.android.vending com.google.android.finsky.activities.MainActivity > "$BASHPID-play-$model"
    getstats "$BASHPID-play-$model" Play
    launch_app com.android.settings com.android.settings.Settings > "$BASHPID-settings-$model"
    getstats "$BASHPID-settings-$model" Settings
}

usage() {
    echo 'Usage: app-launcher [-c|-v|-s <serial num>] -a|-b|-u num-iterations'
    echo 'where num-iterations >= 100'
    echo '-v (optional) for verbose stats dump'
    echo '-s <serial num> (optional) run test on specific device'
    echo '-a|-b|-u required:'
    echo '        -a:all cores'
    echo '        -b:only big cores'
    echo '        -c:pagecached. Do not drop pagecache before each launch (not default)'
    echo '        -h:Dump this help menu'
    echo '        -u:user experience, no change to cpu/gpu frequencies or governors'
    echo '        -a/-b locks CPU/GPU freqs to max, performance governor, thermal/perfd off'
    echo '        -u runs with default device configs, as users would see it'
    exit 1
}

setup() {
    echo "Setting up device"
    # Set developer options, will automatically 'Stay Awake'
    $adb shell 'am start -n com.android.settings/.DevelopmentSettings'
    # Set screen timeout to 30 minutes
    $adb shell 'settings put system screen_off_timeout 1800000'

    # TODO: Consider rebooting device to start with a clean state

    # Disable automatic rotation and NFC
    # This works on OC, but haven't tested on NYC or earlier
    $adb shell 'content insert --uri content://settings/system --bind name:s:accelerometer_rotation --bind value:i:0'
    $adb shell 'svc nfc disable'

    # Clear all notifications
    $adb shell 'service call notification 1'
    # Go to home screen
    $adb shell 'input keyevent KEYCODE_WAKEUP' && sleep 0.5
    $adb shell 'input keyevent KEYCODE_MENU'   && sleep 0.5
    $adb shell 'input keyevent KEYCODE_HOME'   && sleep 0.5
    sleep 2
    # TODO: kill all background apps
    # TODO: clear popups
}

#
# The main() part of the script follows :
#

if [ $# -lt 2 ]; then
    usage
fi

if ! which computestats > /dev/null ; then
    echo "ERROR: Please add computestats utiliy to your PATH"
    exit 1
fi

if ! which computestatsf > /dev/null ; then
    echo "Error: Please add computestatsf utility to your PATH"
    exit 1
fi

parseoptions "$@"

$adb root && $adb wait-for-device

if [ $user_experience == false ]; then
    # Important to stop the thermal-engine to prevent throttling while test is running
    # and stop perfd
    $adb shell 'stop thermal-engine'
    $adb shell 'stop perfd'
else
    echo "User Experience: Default Configs. No changes to cpufreq settings"
fi

# Releases are inconsistent with various trailing characters, remove them all
model=$($adb shell getprop ro.product.name | sed 's/[ \t\r\n]*$//')

echo "Found $model Device"

system_bdev_set=false
case $model in
    # Android Go
    aosp_gobo | full_k37_y33_gms | gobo | gobo_512)
	if [ $user_experience == false ]; then
	    cpufreq_go
        fi
	get_go_devnames
        ;;
    taimen | muskie | walleye)
        if [ $user_experience == false ]; then
            cpufreq_taimen_walleye
        fi
        get_taimen_walleye_devnames
        ;;
    marlin | sailfish)
        if [ $user_experience == false ]; then
            cpufreq_marlin_sailfish
        fi
        get_marlin_sailfish_devnames
        ;;
    angler)
        if [ $user_experience == false ]; then
            cpufreq_angler
        fi
        get_angler_devnames
        ;;
    fugu)
        if [ $user_experience == false ]; then
            cpufreq_fugu
        fi
        get_fugu_devnames
        ;;
    volantis | volantisg)
        if [ $user_experience == false ]; then
            cpufreq_volantis
        fi
        get_volantis_devnames
        ;;
    *)
        echo "Unknown Device $model"
        exit 1
        ;;
esac

setup

#
# launch each app in turn
#
case $model in
    # Android Go
    aosp_gobo | full_k37_y33_gms | gobo | gobo_512)
	launch_go_apps
	;;
    fugu)
	launch_fugu_apps
        ;;
    *)
	launch_phone_apps
        ;;
esac

# cleanup
rm $BASHPID*
