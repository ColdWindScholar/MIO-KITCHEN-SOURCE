#!/usr/bin/env python
#
# Copyright (C) 2016 The Android Open Source Project
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
"""Analyze block trace"""

import collections
import os
import re
import string
import sys

RE_BLOCK = r'.+\s+(block[a-z_]+):\s+'
RE_BLOCK_BIO_QUEUE = r'.+\s+([0-9]+\.[0-9]+):\s+block_bio_queue:\s+([0-9]+)\,([0-9]+)\s+([RW]\S*)\s+([0-9]+)\s+\+\s+([0-9]+)\s+\[([^\]]+)'

# dev_num = major * MULTIPLIER + minor
DEV_MAJOR_MULTIPLIER = 1000

# dm access is remapped to disk access. So account differently
DM_MAJOR = 253

class RwEvent:
  def __init__(self, block_num, start_time, size):
    self.block_num = block_num
    self.start_time = start_time
    self.size = size
    self.latency = 0
  def set_latency(self, latency):
    self.latency = latency

def get_string_pos(strings, string_to_find):
  for i, s in enumerate(strings):
    if s == string_to_find:
      return i
  return -1


class Trace:
  def __init__(self, process):
    self.process = process
    self.reads = [] #(start time, RwEvent)
    self.writes = [] #(start time, RwEvent)
    self.recent_reads = {} # K:
    self.total_latency = 0
    self.total_reads = 0
    self.total_writes = 0
    self.total_dm_reads = {} #K: devnum, V: blocks
    self.total_dm_writes = {}
    self.re_block_queue = re.compile(RE_BLOCK_BIO_QUEUE)
    self.processes = set()
    if process[-1] == '*':
      print "Process name starts with", process[:-1]
      self.process_name_is_prefix = True
    else:
      print "Process name", process
      self.process_name_is_prefix = False

  def parse_bio_queue(self, l):
    match = self.re_block_queue.match(l)
    if not match:
      return
    start_time = int(float(match.group(1))*1000000) #us
    major = int(match.group(2))
    minor =  int(match.group(3))
    operation =  match.group(4)
    block_num = int(match.group(5))
    size = int(match.group(6))
    process = match.group(7)
    if self.process_name_is_prefix:
      if not process.startswith(self.process[:-1]):
        return
      self.processes.add(process)
    else:
      if process != self.process:
        return
    if major == DM_MAJOR:
        devNum = major * DEV_MAJOR_MULTIPLIER + minor;
        if operation[0] == 'R':
          if devNum not in self.total_dm_reads:
            self.total_dm_reads[devNum] = 0
          self.total_dm_reads[devNum] += size
        elif operation[0] == 'W':
          if devNum not in self.total_dm_writes:
            self.total_dm_writes[devNum] = 0
          self.total_dm_writes[devNum] += size
        return
    event = RwEvent(block_num, start_time, size)
    if operation[0] == 'R':
      self.reads.append((start_time, event))
      self.recent_reads[block_num] = event
      self.total_reads += size
    elif operation[0] == 'W':
      self.writes.append((start_time, event))
      self.total_writes += size

  def parse_rq_complete(self, l):
    words = string.split(l)
    cmd_pos = get_string_pos(words, "block_rq_complete:")
    if cmd_pos == -1:
      cmd_pos = get_string_pos(words, "block_bio_complete:")
    block_num = int(words[-4])
    event = self.recent_reads.get(block_num)
    if not event:
      return
    operation = words[cmd_pos + 2]
    if not operation.startswith("R"):
      return
    end_time = int(float(words[cmd_pos - 1][:-1])*1000000) #us
    latency = end_time - event.start_time
    if latency > 20000:
      print "very bad latency:", latency, l
      print "start time,", event.start_time
    event.set_latency(latency)
    del self.recent_reads[block_num]
    self.total_latency += latency

  def parse_block_trace(self, l, match):
    try:
      cmd = match.group(1)
      if cmd == "block_bio_queue":
        self.parse_bio_queue(l)
      elif cmd == "block_rq_complete" or cmd == "block_bio_complete":
        self.parse_rq_complete(l)
    except ValueError:
      print "cannot parse:", l
      raise

  def dump(self):
    if self.process_name_is_prefix:
      print "Processes:", self.processes
    print "total read blocks,", self.total_reads
    print "total write blocks,", self.total_writes
    if len(self.reads) > 0:
      total_read_time = self.reads[-1][0] + self.reads[-1][1].latency - self.reads[0][0]
    else:
      total_read_time = 0
    print "Total DM R"
    for dev,size in self.total_dm_reads.items():
      print dev, size
    print "Total DM W"
    for dev,size in self.total_dm_writes.items():
      print dev, size
    print "total read time,",total_read_time
    read_size_histogram = {}
    latency_per_read_size = {}
    for (time, event) in self.reads:
      if not read_size_histogram.get(event.size):
        read_size_histogram[event.size] = 0
      if not latency_per_read_size.get(event.size):
        latency_per_read_size[event.size] = [ 0, 0] # num events, total latency
      read_size_histogram[event.size] = read_size_histogram[event.size] + 1
      latency_sum = latency_per_read_size[event.size]
      latency_sum[0] += 1
      latency_sum[1] += event.latency
    read_size_histogram = collections.OrderedDict(sorted(read_size_histogram.items()))
    print "read histogram"
    for k,v in read_size_histogram.iteritems():
      print k, ',', v
    print "latency per read size"
    latency_per_read_size = collections.OrderedDict(sorted(latency_per_read_size.items()))
    for k,v in latency_per_read_size.iteritems():
      if v[0] != 0:
        print k, ',', v[1] / v[0], v[0], v[1]

def main(argv):
  if (len(argv) < 3):
    print "check_io_trace.py processname filename"
    return
  keyword = argv[1]
  filename = argv[2]
  trace = Trace(keyword)
  prog = re.compile(RE_BLOCK)
  with open(filename) as f:
    for l in f:
      result = prog.match(l)
      if result:
        trace.parse_block_trace(l, result)
  trace.dump()

if __name__ == '__main__':
  main(sys.argv)
