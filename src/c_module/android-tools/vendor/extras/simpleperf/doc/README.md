# Simpleperf

Android Studio includes a graphical front end to Simpleperf, documented in
[Inspect CPU activity with CPU Profiler](https://developer.android.com/studio/profile/cpu-profiler).
Most users will prefer to use that instead of using Simpleperf directly.

Simpleperf is a native CPU profiling tool for Android. It can be used to profile
both Android applications and native processes running on Android. It can
profile both Java and C++ code on Android. The simpleperf executable can run on Android >=L,
and Python scripts can be used on Android >= N.

Simpleperf is part of the Android Open Source Project.
The source code is [here](https://android.googlesource.com/platform/system/extras/+/main/simpleperf/).
The latest document is [here](https://android.googlesource.com/platform/system/extras/+/main/simpleperf/doc/README.md).

[TOC]

## Introduction

An introduction slide deck is [here](./introduction.pdf).

Simpleperf contains two parts: the simpleperf executable and Python scripts.

The simpleperf executable works similar to linux-tools-perf, but has some specific features for
the Android profiling environment:

1. It collects more info in profiling data. Since the common workflow is "record on the device, and
   report on the host", simpleperf not only collects samples in profiling data, but also collects
   needed symbols, device info and recording time.

2. It delivers new features for recording.
   1) When recording dwarf based call graph, simpleperf unwinds the stack before writing a sample
      to file. This is to save storage space on the device.
   2) Support tracing both on CPU time and off CPU time with --trace-offcpu option.
   3) Support recording callgraphs of JITed and interpreted Java code on Android >= P.

3. It relates closely to the Android platform.
   1) Is aware of Android environment, like using system properties to enable profiling, using
      run-as to profile in application's context.
   2) Supports reading symbols and debug information from the .gnu_debugdata section, because
      system libraries are built with .gnu_debugdata section starting from Android O.
   3) Supports profiling shared libraries embedded in apk files.
   4) It uses the standard Android stack unwinder, so its results are consistent with all other
      Android tools.

4. It builds executables and shared libraries for different usages.
   1) Builds static executables on the device. Since static executables don't rely on any library,
      simpleperf executables can be pushed on any Android device and used to record profiling data.
   2) Builds executables on different hosts: Linux, Mac and Windows. These executables can be used
      to report on hosts.
   3) Builds report shared libraries on different hosts. The report library is used by different
      Python scripts to parse profiling data.

Detailed documentation for the simpleperf executable is [here](#executable-commands-reference).

Python scripts are split into three parts according to their functions:

1. Scripts used for recording, like app_profiler.py, run_simpleperf_without_usb_connection.py.

2. Scripts used for reporting, like report.py, report_html.py, inferno.

3. Scripts used for parsing profiling data, like simpleperf_report_lib.py.

The python scripts are tested on Python >= 3.9. Older versions may not be supported.
Detailed documentation for the Python scripts is [here](#scripts-reference).


## Tools in simpleperf

The simpleperf executables and Python scripts are located in simpleperf/ in ndk releases, and in
system/extras/simpleperf/scripts/ in AOSP. Their functions are listed below.

bin/: contains executables and shared libraries.

bin/android/${arch}/simpleperf: static simpleperf executables used on the device.

bin/${host}/${arch}/simpleperf: simpleperf executables used on the host, only supports reporting.

bin/${host}/${arch}/libsimpleperf_report.${so/dylib/dll}: report shared libraries used on the host.

*.py, inferno, purgatorio: Python scripts used for recording and reporting. Details are in [scripts_reference.md](scripts_reference.md).


## Android application profiling

See [android_application_profiling.md](./android_application_profiling.md).


## Android platform profiling

See [android_platform_profiling.md](./android_platform_profiling.md).


## Executable commands reference

See [executable_commands_reference.md](./executable_commands_reference.md).


## Scripts reference

See [scripts_reference.md](./scripts_reference.md).

## View the profile

See [view_the_profile.md](./view_the_profile.md).

## Answers to common issues

### Support on different Android versions

On Android < N, the kernel may be too old (< 3.18) to support features like recording DWARF
based call graphs.
On Android M - O, we can only profile C++ code and fully compiled Java code.
On Android >= P, the ART interpreter supports DWARF based unwinding. So we can profile Java code.
On Android >= Q, we can used simpleperf shipped on device to profile released Android apps, with
  `<profileable android:shell="true" />`.


### Comparing DWARF based and stack frame based call graphs

Simpleperf supports two ways recording call stacks with samples. One is DWARF based call graph,
the other is stack frame based call graph. Below is their comparison:

Recording DWARF based call graph:
1. Needs support of debug information in binaries.
2. Behaves normally well on both ARM and ARM64, for both Java code and C++ code.
3. Can only unwind 64K stack for each sample. So it isn't always possible to unwind to the bottom.
   However, this is alleviated in simpleperf, as explained in the next section.
4. Takes more CPU time than stack frame based call graphs. So it has higher overhead, and can't
   sample at very high frequency (usually <= 4000 Hz).

Recording stack frame based call graph:
1. Needs support of stack frame registers.
2. Doesn't work well on ARM. Because ARM is short of registers, and ARM and THUMB code have
   different stack frame registers. So the kernel can't unwind user stack containing both ARM and
   THUMB code.
3. Also doesn't work well on Java code. Because the ART compiler doesn't reserve stack frame
   registers. And it can't get frames for interpreted Java code.
4. Works well when profiling native programs on ARM64. One example is profiling surfacelinger. And
   usually shows complete flamegraph when it works well.
5. Takes much less CPU time than DWARF based call graphs. So the sample frequency can be 10000 Hz or
   higher.

So if you need to profile code on ARM or profile Java code, DWARF based call graph is better. If you
need to profile C++ code on ARM64, stack frame based call graphs may be better. After all, you can
fisrt try DWARF based call graph, which is also the default option when `-g` is used. Because it
always produces reasonable results. If it doesn't work well enough, then try stack frame based call
graph instead.


### Fix broken DWARF based call graph

A DWARF-based call graph is generated by unwinding thread stacks. When a sample is recorded, a
kernel dumps up to 64 kilobytes of stack data. By unwinding the stack based on DWARF information,
we can get a call stack.

Two reasons may cause a broken call stack:
1. The kernel can only dump up to 64 kilobytes of stack data for each sample, but a thread can have
   much larger stack. In this case, we can't unwind to the thread start point.

2. We need binaries containing DWARF call frame information to unwind stack frames. The binary
   should have one of the following sections: .eh_frame, .debug_frame, .ARM.exidx or .gnu_debugdata.

To mitigate these problems,


For the missing stack data problem:
1. To alleviate it, simpleperf joins callchains (call stacks) after recording. If two callchains of
   a thread have an entry containing the same ip and sp address, then simpleperf tries to join them
   to make the callchains longer. So we can get more complete callchains by recording longer and
   joining more samples. This doesn't guarantee to get complete call graphs. But it usually works
   well.

2. Simpleperf stores samples in a buffer before unwinding them. If the bufer is low in free space,
   simpleperf may decide to truncate stack data for a sample to 1K. Hopefully, this can be recovered
   by callchain joiner. But when a high percentage of samples are truncated, many callchains can be
   broken. We can tell if many samples are truncated in the record command output, like:

```sh
$ simpleperf record ...
simpleperf I cmd_record.cpp:809] Samples recorded: 105584 (cut 86291). Samples lost: 6501.

$ simpleperf record ...
simpleperf I cmd_record.cpp:894] Samples recorded: 7,365 (1,857 with truncated stacks).
```

   There are two ways to avoid truncating samples. One is increasing the buffer size, like
   `--user-buffer-size 1G`. But `--user-buffer-size` is only available on latest simpleperf. If that
   option isn't available, we can use `--no-cut-samples` to disable truncating samples.

For the missing DWARF call frame info problem:
1. Most C++ code generates binaries containing call frame info, in .eh_frame or .ARM.exidx sections.
   These sections are not stripped, and are usually enough for stack unwinding.

2. For C code and a small percentage of C++ code that the compiler is sure will not generate
   exceptions, the call frame info is generated in .debug_frame section. .debug_frame section is
   usually stripped with other debug sections. One way to fix it, is to download unstripped binaries
   on device, as [here](#fix-broken-callchain-stopped-at-c-functions).

3. The compiler doesn't generate unwind instructions for function prologue and epilogue. Because
   they operates stack frames and will not generate exceptions. But profiling may hit these
   instructions, and fails to unwind them. This usually doesn't matter in a frame graph. But in a
   time based Stack Chart (like in Android Studio and Firefox profiler), this causes stack gaps once
   in a while. We can remove stack gaps via `--remove-gaps`, which is already enabled by default.


### Fix broken callchain stopped at C functions

When using dwarf based call graphs, simpleperf generates callchains during recording to save space.
The debug information needed to unwind C functions is in .debug_frame section, which is usually
stripped in native libraries in apks. To fix this, we can download unstripped version of native
libraries on device, and ask simpleperf to use them when recording.

To use simpleperf directly:

```sh
# create native_libs dir on device, and push unstripped libs in it (nested dirs are not supported).
$ adb shell mkdir /data/local/tmp/native_libs
$ adb push <unstripped_dir>/*.so /data/local/tmp/native_libs
# run simpleperf record with --symfs option.
$ adb shell simpleperf record xxx --symfs /data/local/tmp/native_libs
```

To use app_profiler.py:

```sh
$ ./app_profiler.py -lib <unstripped_dir>
```


### How to solve missing symbols in report?

The simpleperf record command collects symbols on device in perf.data. But if the native libraries
you use on device are stripped, this will result in a lot of unknown symbols in the report. A
solution is to build binary_cache on host.

```sh
# Collect binaries needed by perf.data in binary_cache/.
$ ./binary_cache_builder.py -lib NATIVE_LIB_DIR,...
```

The NATIVE_LIB_DIRs passed in -lib option are the directories containing unstripped native
libraries on host. After running it, the native libraries containing symbol tables are collected
in binary_cache/ for use when reporting.

```sh
$ ./report.py --symfs binary_cache

# report_html.py searches binary_cache/ automatically, so you don't need to
# pass it any argument.
$ ./report_html.py
```


### Show annotated source code and disassembly

To show hot places at source code and instruction level, we need to show source code and
disassembly with event count annotation. Simpleperf supports showing annotated source code and
disassembly for C++ code and fully compiled Java code. Simpleperf supports two ways to do it:

1. Through report_html.py:
   1) Generate perf.data and pull it on host.
   2) Generate binary_cache, containing elf files with debug information. Use -lib option to add
     libs with debug info. Do it with
     `binary_cache_builder.py -i perf.data -lib <dir_of_lib_with_debug_info>`.
   3) Use report_html.py to generate report.html with annotated source code and disassembly,
     as described [here](https://android.googlesource.com/platform/system/extras/+/main/simpleperf/doc/scripts_reference.md#report_html_py).

2. Through pprof.
   1) Generate perf.data and binary_cache as above.
   2) Use pprof_proto_generator.py to generate pprof proto file. `pprof_proto_generator.py`.
   3) Use pprof to report a function with annotated source code, as described [here](https://android.googlesource.com/platform/system/extras/+/main/simpleperf/doc/scripts_reference.md#pprof_proto_generator_py).


### Reduce lost samples and samples with truncated stack

When using `simpleperf record`, we may see lost samples or samples with truncated stack data. Before
saving samples to a file, simpleperf uses two buffers to cache samples in memory. One is a kernel
buffer, the other is a userspace buffer. The kernel puts samples to the kernel buffer. Simpleperf
moves samples from the kernel buffer to the userspace buffer before processing them. If a buffer
overflows, we lose samples or get samples with truncated stack data. Below is an example.

```sh
$ simpleperf record -a --duration 1 -g --user-buffer-size 100k
simpleperf I cmd_record.cpp:799] Recorded for 1.00814 seconds. Start post processing.
simpleperf I cmd_record.cpp:894] Samples recorded: 79 (16 with truncated stacks).
                                 Samples lost: 2,129 (kernelspace: 18, userspace: 2,111).
simpleperf W cmd_record.cpp:911] Lost 18.5567% of samples in kernel space, consider increasing
                                 kernel buffer size(-m), or decreasing sample frequency(-f), or
                                 increasing sample period(-c).
simpleperf W cmd_record.cpp:928] Lost/Truncated 97.1233% of samples in user space, consider
                                 increasing userspace buffer size(--user-buffer-size), or
                                 decreasing sample frequency(-f), or increasing sample period(-c).
```

In the above example, we get 79 samples, 16 of them are with truncated stack data. We lose 18
samples in the kernel buffer, and lose 2111 samples in the userspace buffer.

To reduce lost samples in the kernel buffer, we can increase kernel buffer size via `-m`. To reduce
lost samples in the userspace buffer, or reduce samples with truncated stack data, we can increase
userspace buffer size via `--user-buffer-size`.

We can also reduce samples generated in a fixed time period, like reducing sample frequency using
`-f`, reducing monitored threads, not monitoring multiple perf events at the same time.


## Bugs and contribution

Bugs and feature requests can be submitted at https://github.com/android/ndk/issues.
Patches can be uploaded to android-review.googlesource.com as [here](https://source.android.com/setup/contribute/),
or sent to email addresses listed [here](https://android.googlesource.com/platform/system/extras/+/main/simpleperf/OWNERS).

If you want to compile simpleperf C++ source code, follow below steps:
1. Download AOSP main branch as [here](https://source.android.com/setup/build/requirements).
2. Build simpleperf.
```sh
$ . build/envsetup.sh
$ lunch aosp_arm64-trunk_staging-userdebug
$ mmma system/extras/simpleperf -j30
```

If built successfully, out/target/product/generic_arm64/system/bin/simpleperf is for ARM64, and
out/target/product/generic_arm64/system/bin/simpleperf32 is for ARM.

The source code of simpleperf python scripts is in [system/extras/simpleperf/scripts](https://android.googlesource.com/platform/system/extras/+/main/simpleperf/scripts/).
Most scripts rely on simpleperf binaries to work. To update binaries for scripts (using linux
x86_64 host and android arm64 target as an example):
```sh
$ cp out/host/linux-x86/lib64/libsimpleperf_report.so system/extras/simpleperf/scripts/bin/linux/x86_64/libsimpleperf_report.so
$ cp out/target/product/generic_arm64/system/bin/simpleperf_ndk64 system/extras/simpleperf/scripts/bin/android/arm64/simpleperf
```

Then you can try the latest simpleperf scripts and binaries in system/extras/simpleperf/scripts.
