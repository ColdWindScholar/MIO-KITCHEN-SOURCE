#!/bin/bash

TRACE_DIR=/data/misc/anrd
TRACE_FILE_PATTEN=dump_of_anrdaemon

if [ $# -eq 1 ]; then
    DEVICE=$(echo "-s $1")
else
    DEVICE=""
fi

PID=$(adb $DEVICE shell "ps | grep anrd")

if [ $? -ne 0 ]; then
    echo "FAILED. ADB failed or Daemon is not running."
    exit 1
fi

PID=$(echo "$PID" | awk '{ print $2 }')
adb $DEVICE shell "kill -s SIGUSR1 $PID"

TRACE_FILE=$(adb $DEVICE shell "ls $TRACE_DIR \
    | grep $TRACE_FILE_PATTEN | tail -n1" | tr -d '\r')

# Wiat the trace file generation to complete
adb $DEVICE shell "lsof -p $PID" | grep $TRACE_FILE > /dev/null
while [ $? -eq 0 ];
do
    sleep 1
    adb $DEVICE shell "lsof -p $PID" | grep "$TRACE_FILE" > /dev/null
done

if [ -z "$TRACE_FILE" ]; then
    echo "FAILED. Trace file not created"
fi

adb $DEVICE pull "${TRACE_DIR}/${TRACE_FILE}" ${TRACE_FILE}

CURRENT_DIR=$(pwd)
echo SUCCEED!
echo Trace stored at ${CURRENT_DIR}/${TRACE_FILE}
