# How to enable host (server) adb traces for bug reports:

> :warning: **This will enable tracing permanently**. These instructions are
 well suited for tools managing adb lifecycle (like Android Studio).
Once done, it is recommended to undoing the changes made here and then
restarting adb via `adb kill-server ; adb server`.

## 1. Set the environment variable

### On MacOS/Linux

Add the following line to `~/.bashrc` (.zshrc on MacOS 10.15+:W
).

```
ADB_TRACE=all
```

### On Windows

Add the global variable via the `System Properties` window.
In the `Advanced` tab, click on `Environment Variables`. Add the Variable/
Value to the `User variables` list. Alternatively, you can bring up the same
window by searching for "Edit Environment Variables".

## 2. Cycle adb server

Shutdown adb server via command `adb kill-server`. Close the current terminal,
open a new one, and start adb server via `adb server`.

## 3. Locate the log files

### On MacOS/Linux

The log files are located in `$TMPDIR` which is almost always `/tmp`. Log files
are created on a per uid basis, `adb.<UID>.log`.

### On Windows

The log files are located in `%TEMP%` which is often `C:\Users\<USERNAME>\AppData\Local\Temp`.
The filename is always `adb.log`.

# How to capture device-side logs for adb bug reports (needs root privilege):

Device-side (adbd) debugging is best accomplished from a post-mortem standpoint, because real-time
debugging is impossible given the fact that adb itself is the underlying
debugging channel.

## 1. Set trace mask on and restart the daemon
Device logs tend to be noisy so reproduce the problem
as soon as possible, collect the logs and turn tracing off.

$ adb shell setprop persist.adb.trace_mask 1
$ adb shell pkill adbd

## 2. Collect the logs using `adb pull` and turn off tracing
$ adb shell
sargo:/ # cd /data/adb
sargo:/data/adb # ls -al
total 23
drwx------  2 root   root   3488 2022-02-08 18:04 .
drwxrwx--x 49 system system 4096 2022-01-18 12:13 ..
-rw-------  1 root   root   8521 2022-02-08 18:05 adb-2022-02-08-18-04-49-18527

From the host:
$adb pull /data/adb/adb-2022-02-08-18-04-49-18527

## Error(s) that you may run into, and resolution:
You may run into errors either during `adb shell` or `adb pull`.
Make sure you are running as root.

$ adb shell setprop persist.adb.trace_mask 0
Failed to set property 'persist.adb.trace_mask' to '0'.
See dmesg for error reason.
$ adb root
$ adb shell setprop persist.adb.trace_mask 0

