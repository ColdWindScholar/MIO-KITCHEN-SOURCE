OUTPUT_DIR=$(dirname "$0")
. "$OUTPUT_DIR"/include.sh
export CLANG_COVERAGE=true
export NATIVE_COVERAGE_PATHS=packages/modules/adb

. "$ANDROID_BUILD_TOP"/build/envsetup.sh

# When generating coverage on non-AOSP builds, APEX_NAME should be set to com.google.android.adbd.
# TODO: Figure this out from the environment instead?
APEX_NAME="${APEX_NAME:-com.android.adbd}"

m $APEX_NAME $ADB_TESTS
adb push $ANDROID_PRODUCT_OUT/data/nativetest64 /data
adb install $ANDROID_PRODUCT_OUT/system/apex/$APEX_NAME.apex
adb reboot
