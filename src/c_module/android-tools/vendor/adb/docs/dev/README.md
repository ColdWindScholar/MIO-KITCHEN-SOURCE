# ADB Internals

If you are new to adb source code, you should start by reading [overview.md](overview.md) which describes the three components of adb pipeline.

This document gives the "big picture" which should allow you to build a mental map to help navigate the code.

## Three components of adb pipeline

As described in the [overview](overview.md), this codebase generates three components (Client, Server (a.k.a Host), and Daemon (a.k.a adbd)).

The central part is the Server which runs on the Host computer. On one side the Server exposes a connection to Clients such as adb or DDMLIB.

On the other side, the Server continuously monitors for connecting Daemons (such as USB devices or TCP emulator). Communication with a device is done with a Transport.

```
+----------+              +------------------------+
|   ADB    +----------+   |      ADB SERVER        |                   +----------+
|  CLIENT  |          |   |                        |              (USB)|   ADBD   |
+----------+          |   |                     Transport+-------------+ (DEVICE) |
                      |   |                        |                   +----------+
+-----------          |   |                        |
|   ADB    |          v   +                        |                   +----------+
|  CLIENT  +--------->SmartSocket                  |              (USB)|   ADBD   |
+----------+          ^   | (TCP/IP)            Transport+-------------+ (DEVICE) |
                      |   |                        |                   +----------+
+----------+          |   |                        |
|  DDMLIB  |          |   |                     Transport+--+          +----------+
|  CLIENT  +----------+   |                        |        |  (TCP/IP)|   ADBD   |
+----------+              +------------------------+        +----------|(EMULATOR)|
                                                                       +----------+
```

The Client and the Server are contained in the same executable and both run on the Host machine. Code sections specific to the Host are enclosed within `ADB_HOST` guard. adbd runs on the Android Device. Daemon specific code is enclosed in `!ADB_HOST` but also sometimes within `__ANDROID__` guards.


## "SMART SOCKET" and TRANSPORT

A smart socket is a simple TCP socket with a smart protocol built on top of it which allows to target a device **after** the connection is initalized (see [services.md](services.md) families of `host:transport-` services for more information). This is what Clients connect onto from the Host side. The Client must always initiate communication via a human readable request but the response format varies. The smart protocol is documented in [services.md](services.md).

On the other side, the Server communicates with a device via a Transport. adb initially targeted devices connecting over USB, which is restricted to a fixed number of data streams. Therefore, adb multiplexes multiple byte streams over a single pipe via Transport. When devices connecting over other mechanisms (e.g. emulators over TCP) were introduced, the existing transport protocol was maintained.

## THREADING MODEL and FDEVENT system

At the heart of both the Server and Daemon is a main thread running an fdevent loop, which is a platform-independent abstraction over poll/epoll/WSAPoll monitoring file descriptors events. Requests and services are usually served from the main thread but some service requests result in new threads being spawned.

To allow for operations to run on the Main thread, fdevent features a RunQueue combined with an interrupt fd to force polling to return.

```
+------------+    +-------------------------^
|  RUNQUEUE  |    |                         |
+------------+    |  POLLING (Main thread)  |
| Function<> |    |                         |
+------------+    |                         |
| Function<> |    ^-^-------^-------^------^^
+------------+      |       |       |       |
|    ...     |      |       |       |       |
+------------+      |       |       |       |
|            |      |       |       |       |
|============|      |       |       |       |
|Interrupt fd+------+  +----+  +----+  +----+
+------------+         fd      Socket  Pipe
```

## ASOCKET, APACKET, and AMESSAGE

The asocket, apacket, and amessage constructs exist only to wrap data while it transits on a Transport. An asocket handles a stream of apackets. An apacket consists of an amessage header featuring a command (`A_SYNC`, `A_OPEN`, `A_CLSE`, `A_WRTE`, `A_OKAY`, ...) followed by a payload (find more documentation in [protocol.md](protocol.md). There is no `A_READ` command because an asocket is unidirectional. To model a bi-directional stream, asocket have peers which go in the opposite direction.

An asocket features a buffer containing apackets. If traffic is inbound, the buffer stores the apacket until it is consumed. If the traffic is oubound, the buffer stores apackets until they are sent down the wire (with `A_WRTE` commands).

```
+---------------------ASocket------------------------+
 |                                                   |
 | +----------------APacket Queue------------------+ |
 | |                                               | |
 | |            APacket     APacket     APacket    | |
 | |          +--------+  +--------+  +--------+   | |
 | |          |AMessage|  |AMessage|  |AMessage|   | |
 | |          +--------+  +--------+  +--------+   | |
 | |          |        |  |        |  |        |   | |
 | |  .....   |        |  |        |  |        |   | |
 | |          |  Data  |  |  Data  |  |  Data  |   | |
 | |          |        |  |        |  |        |   | |
 | |          |        |  |        |  |        |   | |
 | |          +--------+  +--------+  +--------+   | |
 | |                                               | |
 | +-----------------------------------------------+ |
 +---------------------------------------------------+
```

This system allows adb to multiplex data streams on an unique byte stream. Without going into too much detail, the amessage arg1 and arg2 fields are similar to the TCP local and remote ports, where the combination uniquely identifies a particular stream. Note that unlike TCP which features an [unacknowledged-send window](https://en.wikipedia.org/wiki/TCP_congestion_control), an apacket is sent only after the previous one has been confirmed to be received.
This is more of an historical accident than a design decision.

The two types of asocket (Remote and Local) differentiate between outbound and inbound traffic.

## adbd <-> APPPLICATION communication

This pipeline is detailed in [daemon/jdwp_service.cpp](../../daemon/jdwp_service.cpp) with ASCII drawings! The JDWP extension implemented by Dalvik/ART are documented in:
- platform/dalvik/+/main/docs/debugmon.html
- platform/dalvik/+/main/docs/debugger.html

### Sync protocol

To transfer files and directories, ADB places a smart-socket in SYNC mode and then issues SYNC commands. The SYNC protocol is documented in [sync.md](sync.md).
Despite its name the `sync` protocol is also what powers operations such as `pull` and `push`.

### ADB Wifi architecture

[here](adb_wifi.md)

### Benchmark sample run for Pixel 8,USB

```
$ ./benchmark_device.py
sink 100MiB: 10 runs: median 27.00 MiB/s, mean 26.39 MiB/s, stddev: 1.11 MiB/s
source 100MiB: 10 runs: median 36.97 MiB/s, mean 37.05 MiB/s, stddev: 0.46 MiB/s
push 100MiB: 10 runs: median 331.96 MiB/s, mean 329.81 MiB/s, stddev: 14.67 MiB/s
pull 100MiB: 10 runs: median 34.55 MiB/s, mean 33.57 MiB/s, stddev: 2.54 MiB/s
```

### Tests

#### Integration Tests
Run integration tests as follows.

```
$ atest adb_integration_test_device
$ atest adb_integration_test_adb
```

You can use a filter to run only a class of test.

```
atest adb_integration_test_device --test-filter=FileOperationsTest
```

You can also use the filter to run a single test in a class.

```
atest adb_integration_test_device --test-filter=FileOperationsTest#test_push_sync
```

#### Unit tests

The list of all the units tests can be found in [TEST_MAPPING](../../TEST_MAPPING)


### More Legacy documentation
[socket-activation.md](socket-activation.md): ADB socket control protocol.