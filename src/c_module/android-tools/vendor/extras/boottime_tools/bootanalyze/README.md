# bootanalyze

The bootanalyze tool helps to profile boot timing.

[TOC]

## Preliminaries

* Need to access "su" on the Device Under Test, e.g. a userdebug build.
* This only works on Linux with Python 2.7, PyYAML and pybootchartgui.

```
sudo pip install pyyaml
sudo apt-get install pybootchartgui
```

## Examples

* bootanalyze.sh provides an example to analyze boot-times and bootcharts.
```
ANDROID_BUILD_TOP="$PWD" \
CONFIG_YMAL="$ANDROID_BUILD_TOP/system/extras/boottime_tools/bootanalyze/config.yaml" \
    LOOPS=3 \
    RESULTS_DIR="$ANDROID_BUILD_TOP/bootAnalyzeResults" \
    $PWD/system/extras/boottime_tools/bootanalyze/bootanalyze.sh
```

## config.yaml
Per specific product modify config.yaml file to include
events you are looking for. Config should look like:

    stop_event: <logcat log message which will terminate log collection after reboot>
    events:
      event1_name: <pattern that matches log message>
      event2_.....

On some devise clock is showing incorrect time for first couple of seconds after boot.
To ensure correct adjustment of time, one has to include event in config that will
be present in dmesg log after clock correction.
