#!/bin/bash

# Copyright (C) 2020 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

readme() {
    echo '
Analyze boot-time
e.g.
ANDROID_BUILD_TOP="$PWD" \
CONFIG_YMAL="$ANDROID_BUILD_TOP/system/extras/boottime_tools/bootanalyze/config.yaml" \
    LOOPS=3 \
    RESULTS_DIR="$PWD/bootAnalyzeResults" \
    $ANDROID_BUILD_TOP/system/extras/boottime_tools/bootanalyze/bootanalyze.sh

Flags:
-a : Uses "adb reboot" (instead of "adb shell su root svc power reboot") command to reboot
-b : If set grabs bootchart
-w : If set grabs carwatchdog perf stats
'
    exit
}


if [[ -z $ANDROID_BUILD_TOP ]]; then
    echo 'Error: you need to specify ANDROID_BUILD_TOP'
    readme
fi
echo "ANDROID_BUILD_TOP=$ANDROID_BUILD_TOP"
SCRIPT_DIR="$ANDROID_BUILD_TOP/system/extras/boottime_tools/bootanalyze"


if [[ -z $CONFIG_YMAL ]]; then
	CONFIG_YMAL="$SCRIPT_DIR/config.yaml"
fi
echo "CONFIG_YMAL=$CONFIG_YMAL"


if [[ -z $RESULTS_DIR ]]; then
	RESULTS_DIR="$PWD/bootAnalyzeResults"
fi
echo "RESULTS_DIR=$RESULTS_DIR"
mkdir -p $RESULTS_DIR

ADB_REBOOT_FLAG=""
BOOTCHART_FLAG=""
CARWATCHDOG_FLAG=""

while getopts 'abw' OPTION; do
  case "$OPTION" in
    a)
      ADB_REBOOT_FLAG="-a"
      ;;
    b)
      BOOTCHART_FLAG="-b"
      ;;
    w)
      CARWATCHDOG_FLAG="-W"
      ;;
    ?)
      echo 'Error: Invalid flag set'
      readme
      ;;
  esac
done
shift "$(($OPTIND -1))"


adb shell 'touch /data/bootchart/enabled'

if [[ -z $LOOPS ]]; then
	LOOPS=1
fi
echo "Analyzing boot-time for LOOPS=$LOOPS"
BOOTCHART_TGZ="/tmp/android-bootchart/bootchart.tgz"
START=1

SLEEP_SEC=20
for (( l=$START; l<=$LOOPS; l++ )); do
    echo "Loop: $l"
    SECONDS=0
    mkdir $RESULTS_DIR/$l
    $SCRIPT_DIR/bootanalyze.py -c $CONFIG_YMAL -G 4M -r \
        $ADB_REBOOT_FLAG $BOOTCHART_FLAG $CARWATCHDOG_FLAG \
        -o "$RESULTS_DIR/$l" 1> "$RESULTS_DIR/$l/boot.txt"
    if [[ $? -ne 0 ]]; then
        echo "bootanalyze.py failed"
        exit 1
    fi
    echo "$SECONDS sec."
    if [ -f "$BOOTCHART_TGZ" ]; then
        cp $BOOTCHART_TGZ "$RESULTS_DIR/$l/bootchart.tgz"
    fi
    echo "Sleep for $SLEEP_SEC sec."
    sleep $SLEEP_SEC
done

echo
echo "Complete $LOOPS"