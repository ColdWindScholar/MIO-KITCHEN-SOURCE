#!/bin/bash

nethandle=0

readonly TEST_HOST="connectivitycheck.gstatic.com"
readonly TEST_PATH="/generate_204"
readonly PREFIX=">>>"

function getUrls() {
    if [ ! -z $(echo "$1" | sed -e 's/[^:]//g') ]; then
        echo "http://[$1]$TEST_PATH"
        echo "http://[$1]:80$TEST_PATH"
    else
        echo "http://$1$TEST_PATH"
        echo "http://$1:80$TEST_PATH"
    fi
}

function toHex() {
    readonly local hexValue=$(bc -q 2>/dev/null << EOT
obase=16
$1
EOT
)
    if [ ! -z "$hexValue" ]; then
        echo "0x$hexValue"
    fi
}


if [ ! -z "$1" ]; then
    nethandle="$1"
fi
echo "$PREFIX Using nethandle $nethandle ($(toHex $nethandle))"
echo ""

readonly IPADDRESSES=$(
    adb shell /system/bin/dnschk --nethandle $nethandle $TEST_HOST |
    sed -e 's/#.*//' -e '/^$/d')


for host in $TEST_HOST $IPADDRESSES; do
    urls=$(getUrls $host)
    for url in $urls; do
        echo "$PREFIX Checking $url" >&2
        adb shell /system/bin/httpurl --nethandle $nethandle "$url"
    done
done
