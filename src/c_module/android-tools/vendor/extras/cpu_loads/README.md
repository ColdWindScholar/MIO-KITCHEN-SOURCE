# CPU test loads

These are a collection of simple workloads designed to induce various levels of power consumption on the CPU and memory subsystems of an SOC. All of these workloads run in an infinite loop and are designed to be measured across a fixed duration. They are not benchmarks and provide no information about the performance of various cores; they are only designed to generate different amounts of load for the purposes of measuring power consumption.

## Workloads

- `simd` is a large double-precision matrix multiplication using Eigen
- `memcpy` copies a 1GB buffer to a second 1GB buffer using bionic `memcpy`
- `memcpy-16kb` copies a 16KB buffer to a second 16KB buffer using bionic `memcpy`
- `memcpy-2048kb` copies a 2048KB buffer to a second 2048KB buffer using bionic `memcpy`
- `memcpy-byte` copies a 1GB buffer to a second 1GB buffer using byte assignment
- `while-true` stalls at a `while (true);`, which becomes an unconditional branch to the same instruction
- `pss` allocates a 1GB buffer and repeatedly measures the process's PSS

## Usage

1. Build the tests for a given device with `mm`.
2. Push the tests to the device; usually this is something like

```
adb push out/target/product/<device target>/system/bin/simd /data/local/tmp
```

3. Prepare the device to run the test. This usually means stopping the framework, locking a sustainable CPU frequency, and moving the shell to a cpuset containing only a single core. For example:

```
stop
mkdir /dev/cpuset/cpu7
echo 0 > /dev/cpuset/cpu7/mems
echo 7 > /dev/cpuset/cpu7/cpus
echo $$ > /dev/cpuset/cpu7/cgroup.procs

cat /sys/devices/system/cpu/cpu7/cpufreq/scaling_available_frequencies
# 500000 851000 984000 1106000 1277000 1426000 1582000 1745000 1826000 2048000 2188000 2252000 2401000 2507000 2630000 2704000 2802000 2850000
echo 1826000 > /sys/devices/system/cpu/cpu7/cpufreq/scaling_min_freq
echo 1826000 > /sys/devices/system/cpu/cpu7/cpufreq/scaling_max_freq
```

4. Run the tests on the device; there are no arguments.
5. Measure power somehow. On a device with ODPM capabilities, this could be something like

```
dumpsys android.hardware.power.stats.IPowerStats/default | tail -27 && sleep 120 && killall memcpy-2048kb && echo "done" && dumpsys android.hardware.power.stats.IPowerStats/default | tail -27
```

from a separate `adb shell` to the shell running the test. Alternately, a breakout board with per-rail measurements or a separate battery monitor could be used.
