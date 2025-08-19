# Simpleperf

Android Studio includes a graphical front end to Simpleperf, documented in
[Inspect CPU activity with CPU Profiler](https://developer.android.com/studio/profile/cpu-profiler).
Most users will prefer to use that instead of using Simpleperf directly.

If you prefer to use the command line, Simpleperf is a versatile command-line
CPU profiling tool included in the NDK for Mac, Linux, and Windows.

This file contains documentation for simpleperf maintainers.

There is also [user documentation](doc/README.md).

## Building new prebuilts

To snap the aosp-simpleperf-release branch to ToT AOSP main and kick off a
build, use [this coastguard
page](https://android-build.googleplex.com/coastguard/dashboard/5938649007521792/#/request/create)
and choose "aosp-simpleperf-release" from the "Branch" dropdown. Then click
"Submit build requests". You'll get emails keeping you up to date with the
progress of the snap and the build.

## Updating the prebuilts

Once you have the build id (a 7-digit number) and the build is complete, run the
update script from within the `system/extras/simpleperf` directory:
```
$ ./scripts/update.py --build 1234567
```

This will create a new change that you can `repo upload`, then approve and
submit as normal.

For testing, I usually only run python host tests as below:
```
$ ./scripts/test/test.py --only-host-test
```

To test all scripts, please use python 3.8+ and install below packages:
```
$ pip install bokeh jinja2 pandas protobuf textable
```

## Updating the prebuilts in prebuilts/simpleperf

Download ndk branch.
```
$ repo init -u persistent-https://android.git.corp.google.com/platform/manifest -b master-ndk
$ repo sync
```

In prebuilts/simpleperf, run `update.py`:
```
$ ./update.py --build <bid>
```

Then manually edit `ChangeLog`.
This will create a new change that you can `repo upload`, then approve and submit as normal.

For testing, we need to test if the scripts run on darwin/linux/windows for different android
versions. I usually split it to four parts:

1. Test on android emulators running on linux x86_64 host, for android version N/O/P/Q/R/S/current.

```
$ ./test/test.py -d <devices> -r 3
```

The scripts support android >= N. But it's easier to test old versions on emulators. So I only test
android N on emulators.

Currently, the tests have problems in clean up. So tests on emulator may fail and take too long to
run. And there are a few known failed cases. Hopefully they will be fixed soon.

1. Test on android devices connected to linux x86_64 host, for android version O/P/Q/R/S/current.

```
$ ./test/test.py -d <devices> -r 3
```

3. Test on an android device connected to darwin x86_64 host, for one of android version O/P/Q/R/S/current.

```
$ ./test/test.py -d <devices> -r 1
```

4. Test on an android device connected to darwin x86_64 host, for one of android version O/P/Q/R/S/current.

```
$ ./test/test.py -d <devices> -r 1
```

To check simpleperf contents released in ndk, we can build ndk package.
```
$ <top_dir>/ndk/checkbuild.py --package --system linux --module simpleperf
```

The ndk package is generated in `out/` directory.
