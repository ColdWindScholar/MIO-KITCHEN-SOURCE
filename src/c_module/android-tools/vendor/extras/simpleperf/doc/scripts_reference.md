# Scripts reference

[TOC]

## Record a profile

### app_profiler.py

`app_profiler.py` is used to record profiling data for Android applications and native executables.

```sh
# Record an Android application.
$ ./app_profiler.py -p simpleperf.example.cpp

# Record an Android application with Java code compiled into native instructions.
$ ./app_profiler.py -p simpleperf.example.cpp --compile_java_code

# Record the launch of an Activity of an Android application.
$ ./app_profiler.py -p simpleperf.example.cpp -a .SleepActivity

# Record a native process.
$ ./app_profiler.py -np surfaceflinger

# Record a native process given its pid.
$ ./app_profiler.py --pid 11324

# Record a command.
$ ./app_profiler.py -cmd \
    "dex2oat --dex-file=/data/local/tmp/app-debug.apk --oat-file=/data/local/tmp/a.oat"

# Record an Android application, and use -r to send custom options to the record command.
$ ./app_profiler.py -p simpleperf.example.cpp \
    -r "-e cpu-clock -g --duration 30"

# Record both on CPU time and off CPU time.
$ ./app_profiler.py -p simpleperf.example.cpp \
    -r "-e task-clock -g -f 1000 --duration 10 --trace-offcpu"

# Save profiling data in a custom file (like perf_custom.data) instead of perf.data.
$ ./app_profiler.py -p simpleperf.example.cpp -o perf_custom.data
```

### Profile from launch of an application

Sometimes we want to profile the launch-time of an application. To support this, we added `--app` in
the record command. The `--app` option sets the package name of the Android application to profile.
If the app is not already running, the record command will poll for the app process in a loop with
an interval of 1ms. So to profile from launch of an application, we can first start the record
command with `--app`, then start the app. Below is an example.

```sh
$ ./run_simpleperf_on_device.py record --app simpleperf.example.cpp \
    -g --duration 1 -o /data/local/tmp/perf.data
# Start the app manually or using the `am` command.
```

To make it convenient to use, `app_profiler.py` supports using the `-a` option to start an Activity
after recording has started.

```sh
$ ./app_profiler.py -p simpleperf.example.cpp -a .MainActivity
```

### api_profiler.py

`api_profiler.py` is used to control recording in application code. It does preparation work
before recording, and collects profiling data files after recording.

[Here](./android_application_profiling.md#control-recording-in-application-code) are the details.

### run_simpleperf_without_usb_connection.py

`run_simpleperf_without_usb_connection.py` records profiling data while the USB cable isn't
connected. Maybe `api_profiler.py` is more suitable, which also don't need USB cable when recording.
Below is an example.

```sh
$ ./run_simpleperf_without_usb_connection.py start -p simpleperf.example.cpp
# After the command finishes successfully, unplug the USB cable, run the
# SimpleperfExampleCpp app. After a few seconds, plug in the USB cable.
$ ./run_simpleperf_without_usb_connection.py stop
# It may take a while to stop recording. After that, the profiling data is collected in perf.data
# on host.
```

### binary_cache_builder.py

The `binary_cache` directory is a directory holding binaries needed by a profiling data file. The
binaries are expected to be unstripped, having debug information and symbol tables. The
`binary_cache` directory is used by report scripts to read symbols of binaries. It is also used by
`report_html.py` to generate annotated source code and disassembly.

By default, `app_profiler.py` builds the binary_cache directory after recording. But we can also
build `binary_cache` for existing profiling data files using `binary_cache_builder.py`. It is useful
when you record profiling data using `simpleperf record` directly, to do system wide profiling or
record without the USB cable connected.

`binary_cache_builder.py` can either pull binaries from an Android device, or find binaries in
directories on the host (via `-lib`).

```sh
# Generate binary_cache for perf.data, by pulling binaries from the device.
$ ./binary_cache_builder.py

# Generate binary_cache, by pulling binaries from the device and finding binaries in
# SimpleperfExampleCpp.
$ ./binary_cache_builder.py -lib path_of_SimpleperfExampleCpp
```

### run_simpleperf_on_device.py

This script pushes the `simpleperf` executable on the device, and run a simpleperf command on the
device. It is more convenient than running adb commands manually.

## Viewing the profile

Scripts in this section are for viewing the profile or converting profile data into formats used by
external UIs. For recommended UIs, see [view_the_profile.md](view_the_profile.md).

### report.py

report.py is a wrapper of the `report` command on the host. It accepts all options of the `report`
command.

```sh
# Report call graph
$ ./report.py -g

# Report call graph in a GUI window implemented by Python Tk.
$ ./report.py -g --gui
```

### report_html.py

`report_html.py` generates `report.html` based on the profiling data. Then the `report.html` can show
the profiling result without depending on other files. So it can be shown in local browsers or
passed to other machines. Depending on which command-line options are used, the content of the
`report.html` can include: chart statistics, sample table, flamegraphs, annotated source code for
each function, annotated disassembly for each function.

```sh
# Generate chart statistics, sample table and flamegraphs, based on perf.data.
$ ./report_html.py

# Add source code.
$ ./report_html.py --add_source_code --source_dirs path_of_SimpleperfExampleCpp

# Add disassembly.
$ ./report_html.py --add_disassembly

# Adding disassembly for all binaries can cost a lot of time. So we can choose to only add
# disassembly for selected binaries.
$ ./report_html.py --add_disassembly --binary_filter libgame.so
# Add disassembly and source code for binaries belonging to an app with package name
# com.example.myapp.
$ ./report_html.py --add_source_code --add_disassembly --binary_filter com.example.myapp

# report_html.py accepts more than one recording data file.
$ ./report_html.py -i perf1.data perf2.data
```

Below is an example of generating html profiling results for SimpleperfExampleCpp.

```sh
$ ./app_profiler.py -p simpleperf.example.cpp
$ ./report_html.py --add_source_code --source_dirs path_of_SimpleperfExampleCpp \
    --add_disassembly
```

After opening the generated [`report.html`](./report_html.html) in a browser, there are several tabs:

The first tab is "Chart Statistics". You can click the pie chart to show the time consumed by each
process, thread, library and function.

The second tab is "Sample Table". It shows the time taken by each function. By clicking one row in
the table, we can jump to a new tab called "Function".

The third tab is "Flamegraph". It shows the graphs generated by [`inferno`](./inferno.md).

The fourth tab is "Function". It only appears when users click a row in the "Sample Table" tab.
It shows information of a function, including:

1. A flamegraph showing functions called by that function.
2. A flamegraph showing functions calling that function.
3. Annotated source code of that function. It only appears when there are source code files for
   that function.
4. Annotated disassembly of that function. It only appears when there are binaries containing that
   function.

### inferno

[`inferno`](./inferno.md) is a tool used to generate flamegraph in a html file.

```sh
# Generate flamegraph based on perf.data.
# On Windows, use inferno.bat instead of ./inferno.sh.
$ ./inferno.sh -sc --record_file perf.data

# Record a native program and generate flamegraph.
$ ./inferno.sh -np surfaceflinger
```

### purgatorio

[`purgatorio`](../scripts/purgatorio/README.md) is a visualization tool to show samples in time order.

### pprof_proto_generator.py

It converts a profiling data file into `pprof.proto`, a format used by [pprof](https://github.com/google/pprof).

```sh
# Convert perf.data in the current directory to pprof.proto format.
$ ./pprof_proto_generator.py
# Show report in pdf format.
$ pprof -pdf pprof.profile

# Show report in html format. To show disassembly, add --tools option like:
#  --tools=objdump:<ndk_path>/toolchains/llvm/prebuilt/linux-x86_64/aarch64-linux-android/bin
# To show annotated source or disassembly, select `top` in the view menu, click a function and
# select `source` or `disassemble` in the view menu.
$ pprof -http=:8080 pprof.profile
```

### gecko_profile_generator.py

Converts `perf.data` to [Gecko Profile
Format](https://github.com/firefox-devtools/profiler/blob/main/docs-developer/gecko-profile-format.md),
the format read by https://profiler.firefox.com/.

Firefox Profiler is a powerful general-purpose profiler UI which runs locally in
any browser (not just Firefox), with:

- Per-thread tracks
- Flamegraphs
- Search, focus for specific stacks
- A time series view for seeing your samples in timestamp order
- Filtering by thread and duration

Usage:

```
# Record a profile of your application
$ ./app_profiler.py -p simpleperf.example.cpp

# Convert and gzip.
$ ./gecko_profile_generator.py -i perf.data | gzip > gecko-profile.json.gz
```

Then open `gecko-profile.json.gz` in https://profiler.firefox.com/.

### report_sample.py

`report_sample.py` converts a profiling data file into the `perf script` text format output by
`linux-perf-tool`.

This format can be imported into:

- [FlameGraph](https://github.com/brendangregg/FlameGraph)
- [Flamescope](https://github.com/Netflix/flamescope)
- [Firefox
  Profiler](https://github.com/firefox-devtools/profiler/blob/main/docs-user/guide-perf-profiling.md),
  but prefer using `gecko_profile_generator.py`.
- [Speedscope](https://github.com/jlfwong/speedscope/wiki/Importing-from-perf-(linux))

```sh
# Record a profile to perf.data
$ ./app_profiler.py <args>

# Convert perf.data in the current directory to a format used by FlameGraph.
$ ./report_sample.py --symfs binary_cache >out.perf

$ git clone https://github.com/brendangregg/FlameGraph.git
$ FlameGraph/stackcollapse-perf.pl out.perf >out.folded
$ FlameGraph/flamegraph.pl out.folded >a.svg
```

### stackcollapse.py

`stackcollapse.py` converts a profiling data file (`perf.data`) to [Brendan
Gregg's "Folded Stacks"
format](https://queue.acm.org/detail.cfm?id=2927301#:~:text=The%20folded%20stack%2Dtrace%20format,trace%2C%20followed%20by%20a%20semicolon).

Folded Stacks are lines of semicolon-delimited stack frames, root to leaf,
followed by a count of events sampled in that stack, e.g.:

```
BusyThread;__start_thread;__pthread_start(void*);java.lang.Thread.run 17889729
```

All similar stacks are aggregated and sample timestamps are unused.

Folded Stacks format is readable by:

- The [FlameGraph](https://github.com/brendangregg/FlameGraph) toolkit
- [Inferno](https://github.com/jonhoo/inferno) (Rust port of FlameGraph)
- [Speedscope](https://speedscope.app/)

Example:

```sh
# Record a profile to perf.data
$ ./app_profiler.py <args>

# Convert to Folded Stacks format
$ ./stackcollapse.py --kernel --jit | gzip > profile.folded.gz

# Visualise with FlameGraph with Java Stacks and nanosecond times
$ git clone https://github.com/brendangregg/FlameGraph.git
$ gunzip -c profile.folded.gz \
    | FlameGraph/flamegraph.pl --color=java --countname=ns \
    > profile.svg
```

## simpleperf_report_lib.py

`simpleperf_report_lib.py` is a Python library used to parse profiling data files generated by the
record command. Internally, it uses libsimpleperf_report.so to do the work. Generally, for each
profiling data file, we create an instance of ReportLib, pass it the file path (via SetRecordFile).
Then we can read all samples through GetNextSample(). For each sample, we can read its event info
(via GetEventOfCurrentSample), symbol info (via GetSymbolOfCurrentSample) and call chain info
(via GetCallChainOfCurrentSample). We can also get some global information, like record options
(via GetRecordCmd), the arch of the device (via GetArch) and meta strings (via MetaInfo).

Examples of using `simpleperf_report_lib.py` are in `report_sample.py`, `report_html.py`,
`pprof_proto_generator.py` and `inferno/inferno.py`.

## ipc.py
`ipc.py`captures the instructions per cycle (IPC) of the system during a specified duration.

Example:
```sh
./ipc.py
./ipc.py 2 20          # Set interval to 2 secs and total duration to 20 secs
./ipc.py -p 284 -C 4   # Only profile the PID 284 while running on core 4
./ipc.py -c 'sleep 5'  # Only profile the command to run
```

The results look like:
```
K_CYCLES   K_INSTR      IPC
36840      14138       0.38
70701      27743       0.39
104562     41350       0.40
138264     54916       0.40
```

## sample_filter.py

`sample_filter.py` generates sample filter files as documented in [sample_filter.md](https://android.googlesource.com/platform/system/extras/+/refs/heads/main/simpleperf/doc/sample_filter.md).
A filter file can be passed in `--filter-file` when running report scripts.

For example, it can be used to split a large recording file into several report files.

```sh
$ sample_filter.py -i perf.data --split-time-range 2 -o sample_filter
$ gecko_profile_generator.py -i perf.data --filter-file sample_filter_part1 \
    | gzip >profile-part1.json.gz
$ gecko_profile_generator.py -i perf.data --filter-file sample_filter_part2 \
    | gzip >profile-part2.json.gz
```
