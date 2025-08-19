# Android application profiling

This section shows how to profile an Android application.
Some examples are [Here](https://android.googlesource.com/platform/system/extras/+/main/simpleperf/demo/README.md).

Profiling an Android application involves three steps:
1. Prepare an Android application.
2. Record profiling data.
3. Report profiling data.

[TOC]

## Prepare an Android application

Based on the profiling situation, we may need to customize the build script to generate an apk file
specifically for profiling. Below are some suggestions.

1. If you want to profile a debug build of an application:

For the debug build type, Android studio sets android::debuggable="true" in AndroidManifest.xml,
enables JNI checks and may not optimize C/C++ code. It can be profiled by simpleperf without any
change.

2. If you want to profile a release build of an application:

For the release build type, Android studio sets android::debuggable="false" in AndroidManifest.xml,
disables JNI checks and optimizes C/C++ code. However, security restrictions mean that only apps
with android::debuggable set to true can be profiled. So simpleperf can only profile a release
build under these three circumstances:
If you are on a rooted device, you can profile any app.

If you are on Android >= Q, you can add profileableFromShell flag in AndroidManifest.xml, this makes
a released app profileable by preinstalled profiling tools. In this case, simpleperf downloaded by
adb will invoke simpleperf preinstalled in system image to profile the app.

```
<manifest ...>
    <application ...>
      <profileable android:shell="true" />
    </application>
</manifest>
```

If you are on Android >= O, we can use [wrap.sh](https://developer.android.com/ndk/guides/wrap-script.html)
to profile a release build:
Step 1: Add android::debuggable="true" in AndroidManifest.xml to enable profiling.
```
<manifest ...>
    <application android::debuggable="true" ...>
```

Step 2: Add wrap.sh in lib/`arch` directories. wrap.sh runs the app without passing any debug flags
to ART, so the app runs as a release app. wrap.sh can be done by adding the script below in
app/build.gradle.
```
android {
    buildTypes {
        release {
            sourceSets {
                release {
                    resources {
                        srcDir {
                            "wrap_sh_lib_dir"
                        }
                    }
                }
            }
        }
    }
}

task createWrapShLibDir
    for (String abi : ["armeabi-v7a", "arm64-v8a", "x86", "x86_64"]) {
        def dir = new File("app/wrap_sh_lib_dir/lib/" + abi)
        dir.mkdirs()
        def wrapFile = new File(dir, "wrap.sh")
        wrapFile.withWriter { writer ->
            writer.write('#!/system/bin/sh\n\$@\n')
        }
    }
}
```

3. If you want to profile C/C++ code:

Android studio strips symbol table and debug info of native libraries in the apk. So the profiling
results may contain unknown symbols or broken callgraphs. To fix this, we can pass app_profiler.py
a directory containing unstripped native libraries via the -lib option. Usually the directory can
be the path of your Android Studio project.


4. If you want to profile Java code:

On Android >= P, simpleperf supports profiling Java code, no matter whether it is executed by
the interpreter, or JITed, or compiled into native instructions. So you don't need to do anything.

On Android O, simpleperf supports profiling Java code which is compiled into native instructions,
and it also needs wrap.sh to use the compiled Java code. To compile Java code, we can pass
app_profiler.py the --compile_java_code option.

On Android N, simpleperf supports profiling Java code that is compiled into native instructions.
To compile java code, we can pass app_profiler.py the --compile_java_code option.

On Android <= M, simpleperf doesn't support profiling Java code.


Below I use application [SimpleperfExampleCpp](https://android.googlesource.com/platform/system/extras/+/main/simpleperf/demo/SimpleperfExampleCpp).
It builds an app-debug.apk for profiling.

```sh
$ git clone https://android.googlesource.com/platform/system/extras
$ cd extras/simpleperf/demo
# Open SimpleperfExampleCpp project with Android studio, and build this project
# successfully, otherwise the `./gradlew` command below will fail.
$ cd SimpleperfExampleCpp

# On windows, use "gradlew" instead.
$ ./gradlew clean assemble
$ adb install -r app/build/outputs/apk/debug/app-debug.apk
```

## Record and report profiling data

We can use [app-profiler.py](scripts_reference.md#app_profilerpy) to profile Android applications.

```sh
# Cd to the directory of simpleperf scripts. Record perf.data.
# -p option selects the profiled app using its package name.
# --compile_java_code option compiles Java code into native instructions, which isn't needed on
# Android >= P.
# -a option selects the Activity to profile.
# -lib option gives the directory to find debug native libraries.
$ ./app_profiler.py -p simpleperf.example.cpp -a .MixActivity -lib path_of_SimpleperfExampleCpp
```

This will collect profiling data in perf.data in the current directory, and related native
binaries in binary_cache/.

Normally we need to use the app when profiling, otherwise we may record no samples. But in this
case, the MixActivity starts a busy thread. So we don't need to use the app while profiling.

```sh
# Report perf.data in stdio interface.
$ ./report.py
Cmdline: /data/data/simpleperf.example.cpp/simpleperf record ...
Arch: arm64
Event: task-clock:u (type 1, config 1)
Samples: 10023
Event count: 10023000000

Overhead  Command     Pid   Tid   Shared Object              Symbol
27.04%    BusyThread  5703  5729  /system/lib64/libart.so    art::JniMethodStart(art::Thread*)
25.87%    BusyThread  5703  5729  /system/lib64/libc.so      long StrToI<long, ...
...
```

[report.py](scripts_reference.md#reportpy) reports profiling data in stdio interface. If there
are a lot of unknown symbols in the report, check [here](README.md#how-to-solve-missing-symbols-in-report).

```sh
# Report perf.data in html interface.
$ ./report_html.py

# Add source code and disassembly. Change the path of source_dirs if it not correct.
$ ./report_html.py --add_source_code --source_dirs path_of_SimpleperfExampleCpp \
      --add_disassembly
```

[report_html.py](scripts_reference.md#report_htmlpy) generates report in report.html, and pops up
a browser tab to show it.

## Record and report call graph

We can record and report [call graphs](executable_commands_reference.md#record-call-graphs) as below.

```sh
# Record dwarf based call graphs: add "-g" in the -r option.
$ ./app_profiler.py -p simpleperf.example.cpp \
        -r "-e task-clock:u -f 1000 --duration 10 -g" -lib path_of_SimpleperfExampleCpp

# Record stack frame based call graphs: add "--call-graph fp" in the -r option.
$ ./app_profiler.py -p simpleperf.example.cpp \
        -r "-e task-clock:u -f 1000 --duration 10 --call-graph fp" \
        -lib path_of_SimpleperfExampleCpp

# Report call graphs in stdio interface.
$ ./report.py -g

# Report call graphs in python Tk interface.
$ ./report.py -g --gui

# Report call graphs in html interface.
$ ./report_html.py

# Report call graphs in flamegraphs.
# On Windows, use inferno.bat instead of ./inferno.sh.
$ ./inferno.sh -sc
```

## Report in html interface

We can use [report_html.py](scripts_reference.md#report_htmlpy) to show profiling results in a web browser.
report_html.py integrates chart statistics, sample table, flamegraphs, source code annotation
and disassembly annotation. It is the recommended way to show reports.

```sh
$ ./report_html.py
```

## Show flamegraph

To show flamegraphs, we need to first record call graphs. Flamegraphs are shown by
report_html.py in the "Flamegraph" tab.
We can also use [inferno](scripts_reference.md#inferno) to show flamegraphs directly.

```sh
# On Windows, use inferno.bat instead of ./inferno.sh.
$ ./inferno.sh -sc
```

We can also build flamegraphs using https://github.com/brendangregg/FlameGraph.
Please make sure you have perl installed.

```sh
$ git clone https://github.com/brendangregg/FlameGraph.git
$ ./report_sample.py --symfs binary_cache >out.perf
$ FlameGraph/stackcollapse-perf.pl out.perf >out.folded
$ FlameGraph/flamegraph.pl out.folded >a.svg
```

## Report in Android Studio

simpleperf report-sample command can convert perf.data into protobuf format accepted by
Android Studio cpu profiler. The conversion can be done either on device or on host. If you have
more symbol info on host, then prefer do it on host with --symdir option.

```sh
$ simpleperf report-sample --protobuf --show-callchain -i perf.data -o perf.trace
# Then open perf.trace in Android Studio to show it.
```

## Deobfuscate Java symbols

Java symbols may be obfuscated by ProGuard. To restore the original symbols in a report, we can
pass a Proguard mapping file to the report scripts or report-sample command via
`--proguard-mapping-file`.

```sh
$ ./report_html.py --proguard-mapping-file proguard_mapping_file.txt
```

## Record both on CPU time and off CPU time

We can [record both on CPU time and off CPU time](executable_commands_reference.md#record-both-on-cpu-time-and-off-cpu-time).

First check if trace-offcpu feature is supported on the device.

```sh
$ ./run_simpleperf_on_device.py list --show-features
dwarf-based-call-graph
trace-offcpu
```

If trace-offcpu is supported, it will be shown in the feature list. Then we can try it.

```sh
$ ./app_profiler.py -p simpleperf.example.cpp -a .SleepActivity \
    -r "-g -e task-clock:u -f 1000 --duration 10 --trace-offcpu" \
    -lib path_of_SimpleperfExampleCpp
$ ./report_html.py --add_disassembly --add_source_code \
    --source_dirs path_of_SimpleperfExampleCpp
```

## Profile from launch

We can [profile from launch of an application](scripts_reference.md#profile-from-launch-of-an-application).

```sh
# Start simpleperf recording, then start the Activity to profile.
$ ./app_profiler.py -p simpleperf.example.cpp -a .MainActivity

# We can also start the Activity on the device manually.
# 1. Make sure the application isn't running or one of the recent apps.
# 2. Start simpleperf recording.
$ ./app_profiler.py -p simpleperf.example.cpp
# 3. Start the app manually on the device.
```

## Control recording in application code

Simpleperf supports controlling recording from application code. Below is the workflow:

1. Run `api_profiler.py prepare -p <package_name>` to allow an app recording itself using
   simpleperf. By default, the permission is reset after device reboot. So we need to run the
   script every time the device reboots. But on Android >= 13, we can use `--days` options to
   set how long we want the permission to last.

2. Link simpleperf app_api code in the application. The app needs to be debuggable or
   profileableFromShell as described [here](#prepare-an-android-application). Then the app can
   use the api to start/pause/resume/stop recording. To start recording, the app_api forks a child
   process running simpleperf, and uses pipe files to send commands to the child process. After
   recording, a profiling data file is generated.

3. Run `api_profiler.py collect -p <package_name>` to collect profiling data files to host.

Examples are CppApi and JavaApi in [demo](https://android.googlesource.com/platform/system/extras/+/main/simpleperf/demo).


## Parse profiling data manually

We can also write python scripts to parse profiling data manually, by using
[simpleperf_report_lib.py](scripts_reference.md#simpleperf_report_libpy). Examples are report_sample.py,
report_html.py.
