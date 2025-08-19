#!/bin/bash
source $ANDROID_BUILD_TOP/build/envsetup.sh
cd $(dirname $0) && mm -j && \
  exec $ANDROID_HOST_OUT/testcases/adb_integration_test_device/$(arch)/adb_integration_test_device "$@"
