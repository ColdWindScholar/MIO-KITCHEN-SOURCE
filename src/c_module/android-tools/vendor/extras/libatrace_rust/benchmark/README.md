# libatrace_rust benchmarks

Benchmarks to compare the performance of Rust ATrace bindings with directly calling the
`libcutils` methods from C++.

## Benchmarks

### ATrace wrapper benchmarks

There are two binaries implementing the same benchmarks:

* `libatrace_rust_benchmark` (`atrace_benchmark.rs`) for Rust.
* `libatrace_rust_benchmark_cc` (`atrace_benchmark.cc`) for C++.

The benchmarks emit ATrace events with tracing off and tracing on. `atrace_begin` is measured
with short and long event names to check if the string length affects timings. For example,
`tracing_on_begin/1000` measures `atrace_begin` with a 1000-character name and tracing enabled.

### ATrace tracing subscriber benchmark

There is a benchmark for the tracing crate subscriber - `libatrace_tracing_subscriber_benchmark`.
We use it to check overhead over the base `libatrace_rust`.

Similarly to the wrapper benchmarks, the subscriber is measured with tracing off and on. There are
cases with and without extra fields to measure the cost of formatting. Cases that start with
`filtered_` measure the subscriber in filtering mode with tracing disabled.

## Running the benchmarks

To run the benchmarks, push the binaries to the device with `adb` and launch them via `adb shell`.
You may need to push dynamic libraries they depend on as well if they're not present on device and
run with `LD_LIBRARY_PATH`.

Do not enable ATrace collectors. The benchmarks effectively emit events in a loop and will spam
any trace and distort performance results.

The benchmarks will override system properties to enable or disable events, specifically ATrace App
event collection in `debug.atrace.app_number` and `debug.atrace.app_0`. After a successful execution
the events will be disabled.

## Results

The timings are not representative of actual cost of fully enabling tracing, only of emitting
events via API, since there's nothing receiving the events.

The tests were done on a `aosp_cf_x86_64_phone-userdebug` Cuttlefish VM. Execution times on real
device may be different but we expect similar relative performance between Rust wrappers and C.

*If you notice that measurements with tracing off and tracing on have similar times, it might mean
that enabling ATrace events failed and you need to debug the benchmark.*

### ATrace wrapper

Rust results from `libatrace_rust_benchmark 2>&1 | grep time`:

```text
tracing_off_begin/10    time:   [6.0211 ns 6.0382 ns 6.0607 ns]
tracing_off_begin/1000  time:   [6.0119 ns 6.0418 ns 6.0823 ns]
tracing_off_end         time:   [6.5417 ns 6.6801 ns 6.8131 ns]
tracing_on_begin/10     time:   [1.2847 µs 1.2929 µs 1.3044 µs]
tracing_on_begin/1000   time:   [1.5395 µs 1.5476 µs 1.5580 µs]
tracing_on_end          time:   [1.1153 µs 1.1208 µs 1.1276 µs]
```

C++ results from `libatrace_rust_benchmark_cc`:

```text
------------------------------------------------------------------------
Benchmark                              Time             CPU   Iterations
------------------------------------------------------------------------
BM_TracingOffAtraceBegin/10         4.00 ns         3.96 ns    175953732
BM_TracingOffAtraceBegin/1000       4.05 ns         4.02 ns    176298494
BM_TracingOffAtraceEnd              4.08 ns         4.05 ns    176422059
BM_TracingOnAtraceBegin/10          1119 ns         1110 ns       640816
BM_TracingOnAtraceBegin/1000        1151 ns         1142 ns       615781
BM_TracingOnAtraceEnd               1076 ns         1069 ns       653646
```

### ATrace tracing subscriber

The tracing subscriber time consists of the underlying `libatrace_rust` call plus the time spent in
the subscriber itself.

Results from `libatrace_tracing_subscriber_benchmark 2>&1 | grep time`:

```text
tracing_off_event       time:   [47.444 ns 47.945 ns 48.585 ns]
filtered_event          time:   [26.852 ns 26.942 ns 27.040 ns]
tracing_off_event_args  time:   [80.597 ns 80.997 ns 81.475 ns]
filtered_event_args     time:   [26.680 ns 26.782 ns 26.887 ns]
tracing_off_span        time:   [316.48 ns 317.72 ns 319.12 ns]
filtered_span           time:   [27.900 ns 27.959 ns 28.018 ns]
tracing_off_span_args   time:   [364.92 ns 367.57 ns 370.95 ns]
filtered_span_args      time:   [27.625 ns 27.919 ns 28.207 ns]
tracing_on_event        time:   [1.4639 µs 1.4805 µs 1.4954 µs]
tracing_on_event_args   time:   [2.0088 µs 2.0197 µs 2.0314 µs]
tracing_on_span         time:   [2.7907 µs 2.7996 µs 2.8103 µs]
tracing_on_span_args    time:   [3.6846 µs 3.6992 µs 3.7168 µs]
```
