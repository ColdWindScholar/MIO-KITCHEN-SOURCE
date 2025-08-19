#!/usr/bin/env python
#
# Copyright (C) 2022 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Reports disk I/O usage by UID/Package, process, and file level breakdowns."""

from datetime import datetime
from collections import namedtuple

import androidFsParser
import argparse
import collections
import os
import psutil
import re
import signal
import subprocess
import sys
import threading
import time
import uidProcessMapper

# ex) lrwxrwxrwx 1 root root   16 1970-01-06 13:22 userdata -> /dev/block/sda14
RE_LS_BLOCK_DEVICE = r"\S+\s[0-9]+\s\S+\s\S+\s+[0-9]+\s[0-9\-]+\s[0-9]+\:[0-9]+\suserdata\s\-\>\s\/dev\/block\/(\S+)"

# ex) 1002 246373245 418936352 1818624 0 0 0 0 0 0 0
RE_UID_IO_STATS_LINE = r"([0-9]+)\s([0-9]+)\s([0-9]+)\s([0-9]+)\s([0-9]+)\s([0-9]+)\s([0-9]+)\s([0-9]+)\s([0-9]+)\s([0-9]+)\s([0-9]+)"

# ex) 253       5 dm-5 3117 0 354656 3324 0 0 0 0 0 2696 3324 0 0 0 0
RE_DISK_STATS_LINE = r"\s+([0-9]+)\s+([0-9]+)\s([a-z\-0-9]+)\s([0-9]+)\s([0-9]+)\s([0-9]+)\s([0-9]+)\s([0-9]+)\s([0-9]+)\s([0-9]+)\s([0-9]+)\s([0-9]+)\s([0-9]+)\s([0-9]+)\s([0-9]+)\s([0-9]+)\s([0-9]+)\s([0-9]+)"

ADB_CMD = "adb"

TEMP_TRACE_FILE = "temp_trace_file.txt"
CARWATCHDOG_DUMP = "carwatchdog_dump.txt"
OUTPUT_FILE = "ioblame_out.txt"

WATCHDOG_BUFFER_SECS = 600

DID_RECEIVE_SIGINT = False


def signal_handler(sig, frame):
  global DID_RECEIVE_SIGINT
  DID_RECEIVE_SIGINT = True
  print("Received signal interrupt")


def init_arguments():
  parser = argparse.ArgumentParser(
      description="Collect and process f2fs traces")
  parser.add_argument(
      "-s",
      "--serial",
      dest="serial",
      action="store",
      help="Android device serial number")
  parser.add_argument(
      "-r",
      "--trace_reads",
      default=False,
      action="store_true",
      dest="traceReads",
      help="Trace f2fs_dataread_start")
  parser.add_argument(
      "-w",
      "--trace_writes",
      default=False,
      action="store_true",
      dest="traceWrites",
      help="Trace f2fs_datawrite_start")
  parser.add_argument(
      "-d",
      "--trace_duration",
      type=int,
      default=3600,
      dest="traceDuration",
      help="Total trace duration in seconds")
  parser.add_argument(
      "-i",
      "--sampling_interval",
      type=int,
      default=300,
      dest="samplingInterval",
      help="Sampling interval in seconds for CarWatchdog collection (applicable only on"
      " automotive form-factor")
  parser.add_argument(
      "-o",
      "--output_directory",
      type=dir_path,
      default=os.getcwd(),
      dest="outputDir",
      help="Output directory")

  return parser.parse_args()


def verify_arguments(args):
  if args.serial is not None:
    global ADB_CMD
    ADB_CMD = "%s %s" % ("adb -s", args.serial)
  if not args.traceReads and not args.traceWrites:
    raise argparse.ArgumentTypeError(
        "Must provide at least one of the --trace_reads or --trace_writes options"
    )


def dir_path(path):
  if os.path.isdir(path):
    return path
  else:
    raise argparse.ArgumentTypeError(
        "{} is not a valid directory path".format(path))


def run_adb_cmd(cmd):
  r = subprocess.check_output(ADB_CMD + " " + cmd, shell=True)
  return r.decode("utf-8")


def run_adb_shell_cmd(cmd):
  return run_adb_cmd("shell " + cmd)


def run_adb_shell_cmd_strip_output(cmd):
  return run_adb_cmd("shell " + cmd).strip()


def run_adb_shell_cmd_ignore_err(cmd):
  try:
    r = subprocess.run(
        ADB_CMD + " shell " + cmd, shell=True, capture_output=True)
    return r.stdout.decode("utf-8")
  except Exception:
    return ""


def run_shell_cmd(cmd):
  return subprocess.check_output(cmd, shell=True)


def run_bg_adb_shell_cmd(cmd):
  return subprocess.Popen(ADB_CMD + " shell " + cmd, shell=True)


def run_bg_shell_cmd(cmd):
  return subprocess.Popen(cmd, shell=True)


def get_block_dev():
  model = run_adb_shell_cmd_strip_output(
      "'getprop ro.product.name' | sed \'s/[ \\t\\r\\n]*$//\'")
  print("Found %s Device" % model)

  if "emu" in model:
    return "vda"

  result = run_adb_shell_cmd_strip_output(
      "'ls -la /dev/block/bootdevice/by-name | grep userdata'")

  match = re.compile(RE_LS_BLOCK_DEVICE).match(result)
  if not match:
    print("Unknown Device {} -- trying Pixel config".format(model))
    return "sda"

  return match.group(1)


def prep_to_do_something():
  run_adb_shell_cmd("'echo 3 > /proc/sys/vm/drop_caches'")
  time.sleep(1)


def setup_tracepoints(shouldTraceReads, shouldTraceWrites):
  # This is a good point to check if the Android FS tracepoints are enabled in the
  # kernel or not
  isTraceEnabled = run_adb_shell_cmd(
      "'if [ -d /sys/kernel/tracing/events/f2fs ]; then echo 0; else echo 1; fi'"
  )

  if isTraceEnabled == 0:
    raise RuntimeError("Android FS tracing is not enabled")

  run_adb_shell_cmd("'echo 0 > /sys/kernel/tracing/tracing_on;\
    echo 0 > /sys/kernel/tracing/trace;\
    echo 0 > /sys/kernel/tracing/events/ext4/enable;\
    echo 0 > /sys/kernel/tracing/events/block/enable'")

  if shouldTraceReads:
    run_adb_shell_cmd(
        "'echo 1 > /sys/kernel/tracing/events/f2fs/f2fs_dataread_start/enable'"
    )

  if shouldTraceWrites:
    run_adb_shell_cmd(
        "'echo 1 > /sys/kernel/tracing/events/f2fs/f2fs_datawrite_start/enable'"
    )

  run_adb_shell_cmd("'echo 1 > /sys/kernel/tracing/tracing_on'")


def clear_tracing(shouldTraceReads, shouldTraceWrites):
  if shouldTraceReads:
    run_adb_shell_cmd(
        "'echo 0 > /sys/kernel/tracing/events/f2fs/f2fs_dataread_start/enable'"
    )

  if shouldTraceWrites:
    run_adb_shell_cmd(
        "'echo 0 > /sys/kernel/tracing/events/f2fs/f2fs_datawrite_start/enable'"
    )

  run_adb_shell_cmd("'echo 0 > /sys/kernel/tracing/tracing_on'")


def start_streaming_trace(traceFile):
  return run_bg_adb_shell_cmd(
      "'cat /sys/kernel/tracing/trace_pipe | grep -e f2fs_data -e f2fs_writepages'\
      > {}".format(traceFile))


def stop_streaming_trace(sub_proc):
  process = psutil.Process(sub_proc.pid)
  for child_proc in process.children(recursive=True):
    child_proc.kill()
  process.kill()


class carwatchdog_collection(threading.Thread):

  def __init__(self, traceDuration, samplingInterval):
    threading.Thread.__init__(self)
    self.traceDuration = traceDuration
    self.samplingInterval = samplingInterval

  def run(self):
    isBootCompleted = 0

    while isBootCompleted == 0:
      isBootCompleted = run_adb_shell_cmd_strip_output(
          "'getprop sys.boot_completed'")
      time.sleep(1)

    # Clean up previous state.
    run_adb_shell_cmd(
        "'dumpsys android.automotive.watchdog.ICarWatchdog/default\
                       --stop_perf &>/dev/null'")

    run_adb_shell_cmd(
        "'dumpsys android.automotive.watchdog.ICarWatchdog/default \
                      --start_perf --max_duration  {} --interval {}'".format(
            self.traceDuration + WATCHDOG_BUFFER_SECS, self.samplingInterval))


def stop_carwatchdog_collection(outputDir):
  run_adb_shell_cmd("'dumpsys android.automotive.watchdog.ICarWatchdog/default"
                    " --stop_perf' > {}/{}".format(outputDir, CARWATCHDOG_DUMP))


def do_something(outpuDir, traceDuration, samplingInterval, uidProcessMapperObj):
  buildChars = run_adb_shell_cmd_strip_output(
      "'getprop ro.build.characteristics'")

  carwatchdog_collection_thread = None
  if "automotive" in buildChars:
    carwatchdog_collection_thread = carwatchdog_collection(
        traceDuration, samplingInterval)
    carwatchdog_collection_thread.start()

  for i in range(1, traceDuration):
    if DID_RECEIVE_SIGINT:
      break
    now = time.process_time()
    read_uid_process_mapping(uidProcessMapperObj)
    taken = time.process_time() - now
    if (taken < 1):
      time.sleep(1 - taken)

  read_uid_package_mapping(uidProcessMapperObj)

  if "automotive" in buildChars:
    carwatchdog_collection_thread.join()
    stop_carwatchdog_collection(outpuDir)


def read_uid_process_mapping(uidProcessMapperObj):
  procStatusDump = run_adb_shell_cmd_ignore_err(
      "'cat /proc/*/status /proc/*/task/*/status 2> /dev/null'")

  uidProcessMapperObj.parse_proc_status_dump(procStatusDump)


def read_uid_package_mapping(uidProcessMapperObj):
  packageMappingDump = run_adb_shell_cmd_ignore_err(
      "'pm list packages -a -U | sort | uniq'")

  uidProcessMapperObj.parse_uid_package_dump(packageMappingDump)


# Parser for "/proc/diskstats".
class DiskStats:

  def __init__(self, readIos, readSectors, writeIos, writeSectors):
    self.readIos = readIos
    self.readSectors = readSectors
    self.writeIos = writeIos
    self.writeSectors = writeSectors

  def delta(self, other):
    return DiskStats(self.readIos - other.readIos,
                     self.readSectors - other.readSectors,
                     self.writeIos - other.writeIos,
                     self.writeSectors - other.writeSectors)

  def dump(self, shouldDumpReads, shouldDumpWrites, outputFile):
    if self.readIos is None or self.readIos is None or self.readIos is None\
       or self.readIos is None:
      outputFile.write("Missing disk stats")
      return

    if (shouldDumpReads):
      outputFile.write("Total dev block reads: {} KB, IOs: {}\n".format(
          self.readSectors / 2, self.readIos))

    if (shouldDumpWrites):
      outputFile.write("Total dev block writes: {} KB, IOs: {}\n".format(
          self.writeSectors / 2, self.writeIos))


def get_disk_stats(blockDev):
  line = run_adb_shell_cmd(
      "'cat /proc/diskstats' | fgrep -w {}".format(blockDev))
  matcher = re.compile(RE_DISK_STATS_LINE)
  match = matcher.match(line)

  if not match:
    return None

  readIos = int(match.group(4))
  readSectors = int(match.group(6))
  writeIos = int(match.group(8))
  writeSectors = int(match.group(10))

  return DiskStats(readIos, readSectors, writeIos, writeSectors)


IoBytes = namedtuple("IoBytes", "rdBytes wrBytes")


# Parser for "/proc/uid_io/stats".
class UidIoStats:

  def __init__(self):
    self.uidIoStatsReMatcher = re.compile(RE_UID_IO_STATS_LINE)
    self.ioBytesByUid = {}  # Key: UID, Value: IoBytes
    self.totalIoBytes = IoBytes(rdBytes=0, wrBytes=0)

  def parse(self, dump):
    totalRdBytes = 0
    totalWrBytes = 0
    for line in dump.split("\n"):
      (uid, ioBytes) = self.parse_uid_io_bytes(line)
      self.ioBytesByUid[uid] = ioBytes
      totalRdBytes += ioBytes.rdBytes
      totalWrBytes += ioBytes.wrBytes

    self.totalIoBytes = IoBytes(rdBytes=totalRdBytes, wrBytes=totalWrBytes)

  def parse_uid_io_bytes(self, line):
    match = self.uidIoStatsReMatcher.match(line)
    if not match:
      return None
    return (int(match.group(1)),
            IoBytes(
                rdBytes=(int(match.group(4)) + int(match.group(8))),
                wrBytes=(int(match.group(5)) + int(match.group(9)))))

  def delta(self, other):
    deltaStats = UidIoStats()
    deltaStats.totalIoBytes = IoBytes(
        rdBytes=self.totalIoBytes.rdBytes - other.totalIoBytes.rdBytes,
        wrBytes=self.totalIoBytes.wrBytes - other.totalIoBytes.wrBytes)

    for uid, ioBytes in self.ioBytesByUid.items():
      if uid not in other.ioBytesByUid:
        deltaStats.ioBytesByUid[uid] = ioBytes
        continue
      otherIoBytes = other.ioBytesByUid[uid]
      rdBytes = ioBytes.rdBytes - otherIoBytes.rdBytes if ioBytes.rdBytes > otherIoBytes.rdBytes\
          else 0
      wrBytes = ioBytes.wrBytes - otherIoBytes.wrBytes if ioBytes.wrBytes > otherIoBytes.wrBytes\
          else 0
      deltaStats.ioBytesByUid[uid] = IoBytes(rdBytes=rdBytes, wrBytes=wrBytes)
    return deltaStats

  def dumpTotal(self, mode, outputFile):
    totalBytes = self.totalIoBytes.wrBytes if mode == "write" else self.totalIoBytes.rdBytes
    outputFile.write("Total system-wide {} KB: {}\n".format(
        mode, to_kib(totalBytes)))

  def dump(self, uidProcessMapperObj, mode, func, outputFile):
    sortedEntries = collections.OrderedDict(
        sorted(
            self.ioBytesByUid.items(),
            key=lambda item: item[1].wrBytes
            if mode == "write" else item[1].rdBytes,
            reverse=True))
    totalEntries = len(sortedEntries)
    for i in range(totalEntries):
      uid, ioBytes = sortedEntries.popitem(last=False)
      totalBytes = ioBytes.wrBytes if mode == "write" else ioBytes.rdBytes
      if totalBytes < androidFsParser.MIN_PID_BYTES:
        continue
      uidInfo = uidProcessMapperObj.get_uid_info(uid)
      outputFile.write("{}, Total {} KB: {}\n".format(uidInfo.to_string(), mode,
                                                      to_kib(totalBytes)))
      func(uid)
      outputFile.write("\n" + ("=" * 100) + "\n")
      if i < totalEntries - 1:
        outputFile.write("\n")


def get_uid_io_stats():
  uidIoStatsDump = run_adb_shell_cmd_strip_output("'cat /proc/uid_io/stats'")
  uidIoStats = UidIoStats()
  uidIoStats.parse(uidIoStatsDump)
  return uidIoStats


def to_kib(bytes):
  return bytes / 1024


def main(argv):
  signal.signal(signal.SIGINT, signal_handler)

  args = init_arguments()
  verify_arguments(args)

  run_adb_cmd("root")
  buildDesc = run_adb_shell_cmd_strip_output("'getprop ro.build.description'")
  blockDev = get_block_dev()

  prep_to_do_something()
  setup_tracepoints(args.traceReads, args.traceWrites)
  diskStatsBefore = get_disk_stats(blockDev)
  uidIoStatsBefore = get_uid_io_stats()

  traceFile = "{}/{}".format(args.outputDir, TEMP_TRACE_FILE)

  startDateTime = datetime.now()
  proc = start_streaming_trace(traceFile)
  print("Started trace streaming")

  uidProcessMapperObj = uidProcessMapper.UidProcessMapper()
  do_something(args.outputDir, args.traceDuration, args.samplingInterval,
               uidProcessMapperObj)

  stop_streaming_trace(proc)
  endDateTime = datetime.now()
  print("Stopped trace streaming")

  clear_tracing(args.traceReads, args.traceWrites)

  diskStatsAfter = get_disk_stats(blockDev)
  uidIoStatsAfter = get_uid_io_stats()
  diskStatsDelta = diskStatsAfter.delta(diskStatsBefore)
  uidIoStatsDelta = uidIoStatsAfter.delta(uidIoStatsBefore)

  print("Completed device side collection")

  writeParser = androidFsParser.AndroidFsParser(androidFsParser.RE_WRITE_START,
                                                uidProcessMapperObj)
  readParser = androidFsParser.AndroidFsParser(androidFsParser.RE_READ_START,
                                               uidProcessMapperObj)
  with open(traceFile) as file:
    for line in file:
      if args.traceWrites and writeParser.parse(line):
        continue
      if args.traceReads:
        readParser.parse(line)

  outputFile = open("{}/{}".format(args.outputDir, OUTPUT_FILE), "w")
  outputFile.write("Collection datetime: {}, Total duration: {}\n".format(
      endDateTime, endDateTime - startDateTime))
  outputFile.write("Build description: {}\n".format(buildDesc))
  outputFile.write(
      "Minimum KB per process or UID: {}, Small file KB: {}\n\n".format(
          to_kib(androidFsParser.MIN_PID_BYTES),
          to_kib(androidFsParser.SMALL_FILE_BYTES)))

  diskStatsDelta.dump(args.traceReads, args.traceWrites, outputFile)

  if args.traceWrites:
    uidIoStatsDelta.dumpTotal("write", outputFile)
    writeParser.dumpTotal(outputFile)
    uidIoStatsDelta.dump(uidProcessMapperObj, "write",
                         lambda uid: writeParser.dump(uid, outputFile),
                         outputFile)

  if args.traceWrites and args.traceReads:
    outputFile.write("\n\n\n")

  if args.traceReads:
    uidIoStatsDelta.dumpTotal("read", outputFile)
    readParser.dumpTotal(outputFile)
    uidIoStatsDelta.dump(uidProcessMapperObj, "read",
                         lambda uid: readParser.dump(uid, outputFile),
                         outputFile)

  outputFile.close()
  run_shell_cmd("rm {}/{}".format(args.outputDir, TEMP_TRACE_FILE))


if __name__ == "__main__":
  main(sys.argv)
