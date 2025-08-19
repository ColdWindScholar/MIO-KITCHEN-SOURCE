# Debug dwarf unwinding

Dwarf unwinding is the default way of getting call graphs in simpleperf. In this process,
simpleperf asks the kernel to add stack and register data to each sample. Then it uses
[libunwindstack](https://cs.android.com/android/platform/superproject/+/main:system/unwinding/libunwindstack/)
to unwind the call stack. libunwindstack uses dwarf sections (like .debug_frame or .eh_frame) in
elf files to know how to unwind the stack.

By default, `simpleperf record` unwinds a sample before saving it to disk, to reduce space consumed
by stack data. But this behavior makes it harder to reproduce unwinding problems. So we added
debug-unwind command, to help debug and profile dwarf unwinding. Below are two use cases.

[TOC]

## Debug failed unwinding cases

Unwinding a sample can fail for different reasons: not enough stack or register data, unknown
thread maps, no dwarf info, bugs in code, etc. And to fix them, we need to get error details
and be able to reproduce them. simpleperf record cmd has two options for this:
`--keep-failed-unwinding-result` keeps error code for failed unwinding samples. It's lightweight
and gives us a brief idea why unwinding stops.
`--keep-failed-unwinding-debug-info` keeps stack and register data for failed unwinding samples. It
can be used to reproduce the unwinding process given proper elf files. Below is an example.

```sh
# Run record cmd and keep failed unwinding debug info.
$ simpleperf64 record --app com.example.android.displayingbitmaps -g --duration 10 \
    --keep-failed-unwinding-debug-info
...
simpleperf I cmd_record.cpp:762] Samples recorded: 22026. Samples lost: 0.

# Generate a text report containing failed unwinding cases.
$ simpleperf debug-unwind --generate-report -o report.txt

# Pull report.txt on host and show it using debug_unwind_reporter.py.
# Show summary.
$ debug_unwind_reporter.py -i report.txt --summary
# Show summary of samples failed at a symbol.
$ debug_unwind_reporter.py -i report.txt --summary --include-end-symbol SocketInputStream_socketRead0
# Show details of samples failed at a symbol.
$ debug_unwind_reporter.py -i report.txt --include-end-symbol SocketInputStream_socketRead0

# Reproduce unwinding a failed case.
$ simpleperf debug-unwind --unwind-sample --sample-time 256666343213301

# Generate a test file containing a failed case and elf files for debugging it.
$ simpleperf debug-unwind --generate-test-file --sample-time 256666343213301 --keep-binaries-in-test-file \
    /apex/com.android.runtime/lib64/bionic/libc.so,/apex/com.android.art/lib64/libopenjdk.so -o test.data
```

## Profile unwinding process

We can also record samples without unwinding them. Then we can use debug-unwind cmd to unwind the
samples after recording. Below is an example.

```sh
# Record samples without unwinding them.
$ simpleperf record --app com.example.android.displayingbitmaps -g --duration 10 \
    --no-unwind
...
simpleperf I cmd_record.cpp:762] Samples recorded: 9923. Samples lost: 0.

# Use debug-unwind cmd to unwind samples.
$ simpleperf debug-unwind --unwind-sample
```

We can profile the unwinding process, get hot functions for improvement.

```sh
# Profile debug-unwind cmd.
$ simpleperf record -g -o perf_unwind.data simpleperf debug-unwind --unwind-sample --skip-sample-print

# Then pull perf_unwind.data and report it.
$ report_html.py -i perf_unwind.data

# We can also add source code annotation in report.html.
$ binary_cache_builder.py -i perf_unwind.data -lib <path to aosp-main>/out/target/product/<device-name>/symbols/system
$ report_html.py -i perf_unwind.data --add_source_code --source_dirs <path to aosp-main>/system/
```
