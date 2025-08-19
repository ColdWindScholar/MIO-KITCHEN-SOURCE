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
"""Analyze dm_verity trace"""
import collections
import math
import os
import re
import string
import sys

RE_VERITY = r'.+\s+([0-9]+\.[0-9]+):\s+block_verity_msg:\s+(\S+)\s+([0-9]+)\,([0-9]+)\s+([0-9]+)\s+([0-9]+)'

def get_average_and_std_dev(l):
  sum_io = 0.0
  sum_verity = 0.0
  sum_total = 0.0
  N = len(l)
  sum_blocks = 0.0
  for e in l:
    sum_io += e.io_latency
    sum_verity += e.verity_latency
    sum_total += e.total_latency
    sum_blocks += e.size
  average_io = sum_io / N
  average_verity = sum_verity / N
  average_total = sum_total / N
  var_io = 0.0
  var_verity = 0.0
  var_total = 0.0
  for e in l:
    var_io += (e.io_latency - average_io)**2
    var_verity += (e.verity_latency - average_verity)**2
    var_total += (e.total_latency - average_total)**2
  sigma_io = math.sqrt(var_io / N)
  sigma_verity = math.sqrt(var_verity / N)
  sigma_total = math.sqrt(var_total / N)
  return (average_io, sigma_io, sum_io), (average_verity, sigma_verity, sum_verity), \
    (average_total, sigma_total, sum_total), sum_blocks


class Event:
  def __init__(self, start_time, block_num, size):
    self.block_num = block_num
    self.start_time = start_time
    self.io_end_time = 0
    self.finish_time = 0
    self.size = size
    self.total_latency = 0
    self.io_latency = 0
    self.verity_latency = 0

  def set_io_end_time(self, io_end_time):
    self.io_end_time = io_end_time
    self.io_latency = io_end_time - self.start_time

  def set_finish_time(self, finish_time):
    self.finish_time = finish_time
    self.verity_latency = finish_time - self.io_end_time
    self.total_latency = finish_time - self.start_time

class VerityTrace:
  def __init__(self):
    self.reads = [] # all events in start time
    self.block_size_vs_reads_histogram = {} # key: size, value: list of events
    self.recents = {} # not finished, key: block_nr, value: event
    self.re = re.compile(RE_VERITY)

  def handle_line(self, line):
    match = self.re.match(line)
    if not match:
      return
    time = int(float(match.group(1))*1000000) #us
    step = match.group(2)
    block_nr = int(match.group(5))
    size = int(match.group(6))
    recent_key = block_nr * 1000 + size
    if step == "map":
      event = Event(time, block_nr, size)
      self.recents[recent_key] = event
      self.reads.append(event)
      per_size_list = self.block_size_vs_reads_histogram.get(size)
      if not per_size_list:
        per_size_list = []
        self.block_size_vs_reads_histogram[size] = per_size_list
      per_size_list.append(event)
    elif step == "end_io":
      event = self.recents[recent_key]
      event.set_io_end_time(time)
    elif step == "finish_io":
      event = self.recents[recent_key]
      event.set_finish_time(time)
      del self.recents[recent_key]

  def dump_list(self, msg, l):
    io, verity, total, blocks = get_average_and_std_dev(l)
    print msg, "counts:", len(l), "io latency:", io[0], io[1], io[2], "verity latency:", \
      verity[0], verity[1], verity[2], "total:", total[0], total[1], total[2]
    return io, verity, total, blocks

  def dump(self):
    print "Numbers: average (us), stddev (us), total (us)"
    io, verity, total, blocks = self.dump_list ("total,", self.reads)
    io_latency_per_1024KB = io[2] / blocks * (1024 / 4)
    verity_latency_per_1024KB = verity[2] / blocks * (1024 / 4)
    total_latency_per_1024KB = io_latency_per_1024KB + verity_latency_per_1024KB
    print "Average latency for 1024KB (us), IO:", io_latency_per_1024KB, \
      "Verity:", verity_latency_per_1024KB, "Total:", total_latency_per_1024KB
    sizes = sorted(self.block_size_vs_reads_histogram.keys())
    print "Latency per read size"
    for s in sizes:
      self.dump_list ("size " + str(s), self.block_size_vs_reads_histogram[s])

def main(argv):
  if (len(argv) < 2):
    print "check_io_trace.py filename"
    return
  filename = argv[1]
  trace = VerityTrace()
  with open(filename) as f:
    for l in f:
      trace.handle_line(l)
  trace.dump()

if __name__ == '__main__':
  main(sys.argv)
