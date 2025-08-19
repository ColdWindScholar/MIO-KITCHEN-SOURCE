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
"""Trace parser for f2fs traces."""

import collections
import re

# ex) bt_stack_manage-21277   [000] ....  5879.043608: f2fs_datawrite_start: entry_name /misc/bluedroid/bt_config.bak.new, offset 0, bytes 408, cmdline bt_stack_manage, pid 21277, i_size 0, ino 9103
RE_WRITE_START = r".+-([0-9]+).*\s+([0-9]+\.[0-9]+):\s+f2fs_datawrite_start:\sentry_name\s(\S+)\,\soffset\s([0-9]+)\,\sbytes\s([0-9]+)\,\scmdline\s(\S+)\,\spid\s([0-9]+)\,\si_size\s([0-9]+)\,\sino\s([0-9]+)"

# ex)        dumpsys-21321   [001] ....  5877.599324: f2fs_dataread_start: entry_name /system/lib64/libbinder.so, offset 311296, bytes 4096, cmdline dumpsys, pid 21321, i_size 848848, ino 2397
RE_READ_START = r".+-([0-9]+).*\s+([0-9]+\.[0-9]+):\s+f2fs_dataread_start:\sentry_name\s(\S+)\,\soffset\s([0-9]+)\,\sbytes\s([0-9]+)\,\scmdline\s(\S+)\,\spid\s([0-9]+)\,\si_size\s([0-9]+)\,\sino\s([0-9]+)"

MIN_PID_BYTES = 1024 * 1024  # 1 MiB
SMALL_FILE_BYTES = 1024  # 1 KiB


class ProcessTrace:

  def __init__(self, cmdLine, filename, numBytes):
    self.cmdLine = cmdLine
    self.totalBytes = numBytes
    self.bytesByFiles = {filename: numBytes}

  def add_file_trace(self, filename, numBytes):
    self.totalBytes += numBytes
    if filename in self.bytesByFiles:
      self.bytesByFiles[filename] += numBytes
    else:
      self.bytesByFiles[filename] = numBytes

  def dump(self, mode, outputFile):
    smallFileCnt = 0
    smallFileBytes = 0
    for _, numBytes in self.bytesByFiles.items():
      if numBytes < SMALL_FILE_BYTES:
        smallFileCnt += 1
        smallFileBytes += numBytes

    if (smallFileCnt != 0):
      outputFile.write(
          "Process: {}, Traced {} KB: {}, Small file count: {}, Small file KB: {}\n"
          .format(self.cmdLine, mode, to_kib(self.totalBytes), smallFileCnt,
                  to_kib(smallFileBytes)))

    else:
      outputFile.write("Process: {}, Traced {} KB: {}\n".format(
          self.cmdLine, mode, to_kib(self.totalBytes)))

    if (smallFileCnt == len(self.bytesByFiles)):
      return

    sortedEntries = collections.OrderedDict(
        sorted(
            self.bytesByFiles.items(), key=lambda item: item[1], reverse=True))

    for i in range(len(sortedEntries)):
      filename, numBytes = sortedEntries.popitem(last=False)
      if numBytes < SMALL_FILE_BYTES:
        # Entries are sorted by bytes. So, break on the first small file entry.
        break

      outputFile.write("File: {}, {} KB: {}\n".format(filename, mode,
                                                      to_kib(numBytes)))


class UidTrace:

  def __init__(self, uid, cmdLine, filename, numBytes):
    self.uid = uid
    self.packageName = ""
    self.totalBytes = numBytes
    self.traceByProcess = {cmdLine: ProcessTrace(cmdLine, filename, numBytes)}

  def add_process_trace(self, cmdLine, filename, numBytes):
    self.totalBytes += numBytes
    if cmdLine in self.traceByProcess:
      self.traceByProcess[cmdLine].add_file_trace(filename, numBytes)
    else:
      self.traceByProcess[cmdLine] = ProcessTrace(cmdLine, filename, numBytes)

  def dump(self, mode, outputFile):
    outputFile.write("Traced {} KB: {}\n\n".format(mode,
                                                   to_kib(self.totalBytes)))

    if self.totalBytes < MIN_PID_BYTES:
      return

    sortedEntries = collections.OrderedDict(
        sorted(
            self.traceByProcess.items(),
            key=lambda item: item[1].totalBytes,
            reverse=True))
    totalEntries = len(sortedEntries)
    for i in range(totalEntries):
      _, processTrace = sortedEntries.popitem(last=False)
      if processTrace.totalBytes < MIN_PID_BYTES:
        # Entries are sorted by bytes. So, break on the first small PID entry.
        break

      processTrace.dump(mode, outputFile)
      if i < totalEntries - 1:
        outputFile.write("\n")


class AndroidFsParser:

  def __init__(self, re_string, uidProcessMapper):
    self.traceByUid = {}  # Key: uid, Value: UidTrace
    if (re_string == RE_WRITE_START):
      self.mode = "write"
    else:
      self.mode = "read"
    self.re_matcher = re.compile(re_string)
    self.uidProcessMapper = uidProcessMapper
    self.totalBytes = 0

  def parse(self, line):
    match = self.re_matcher.match(line)
    if not match:
      return False
    try:
      self.do_parse_start(line, match)
    except Exception:
      print("cannot parse: {}".format(line))
      raise
    return True

  def do_parse_start(self, line, match):
    pid = int(match.group(1))
    # start_time = float(match.group(2)) * 1000  #ms
    filename = match.group(3)
    # offset = int(match.group(4))
    numBytes = int(match.group(5))
    cmdLine = match.group(6)
    pid = int(match.group(7))
    # isize = int(match.group(8))
    # ino = int(match.group(9))
    self.totalBytes += numBytes
    uid = self.uidProcessMapper.get_uid(cmdLine, pid)

    if uid in self.traceByUid:
      self.traceByUid[uid].add_process_trace(cmdLine, filename, numBytes)
    else:
      self.traceByUid[uid] = UidTrace(uid, cmdLine, filename, numBytes)

  def dumpTotal(self, outputFile):
    if self.totalBytes > 0:
      outputFile.write("Traced system-wide {} KB: {}\n\n".format(
          self.mode, to_kib(self.totalBytes)))

  def dump(self, uid, outputFile):
    if uid not in self.traceByUid:
      return

    uidTrace = self.traceByUid[uid]
    uidTrace.dump(self.mode, outputFile)


def to_kib(bytes):
  return bytes / 1024
