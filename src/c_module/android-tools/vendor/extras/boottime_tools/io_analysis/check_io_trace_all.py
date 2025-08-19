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

# ex) <...>-52    [001] ...1     1.362574: block_bio_queue: 8,16 R 0 + 8 [kworker/u8:1]
RE_BLOCK = r'.+-([0-9]+).*\s+([0-9]+\.[0-9]+):\s+block_bio_queue:\s+([0-9]+)\,([0-9]+)\s(\S+)\s+([0-9]+)\s+\+\s+([0-9]+)\s+\[([^\]]+)'
# ex)  <...>-453   [001] d..4     3.181854: sched_blocked_reason: pid=471 iowait=1 caller=__wait_on_buffer+0x24/0x2c
RE_SCHED_BLOCKED_READSON = r'.+-([0-9]+)\s+\[([0-9]+)\]\s.*\s+([0-9]+\.[0-9]+):\s+sched_blocked_reason:\spid=([0-9]+)\siowait=([01])\scaller=(\S+)'
# ex) <idle>-0     [000] d..3     3.181864: sched_switch: prev_comm=swapper/0 prev_pid=0 prev_prio=120 prev_state=R ==> next_comm=ueventd next_pid=471 next_prio=120
RE_SCHED_SWITCH = r'.+-([0-9]+)\s+\[([0-9]+)\]\s.*\s+([0-9]+\.[0-9]+):\s+sched_switch:\sprev_comm=(.+)\sprev_pid=([0-9]+)\sprev_prio=([0-9]+)\sprev_state=(\S+).*next_comm=(.+)\snext_pid=([0-9]+)\snext_prio=([0-9]+)'

# dev_num = major * MULTIPLIER + minor
DEV_MAJOR_MULTIPLIER = 1000

# dm access is remapped to disk access. So account differently
DM_MAJOR = 253

MAX_PROCESS_DUMP = 10

class RwEvent:
  def __init__(self, block_num, start_time, size):
    self.block_num = block_num
    self.start_time = start_time
    self.size = size

def get_string_pos(strings, string_to_find):
  for i, s in enumerate(strings):
    if s == string_to_find:
      return i
  return -1

class ProcessData:
  def __init__(self, name):
    self.name = name
    self.reads = {} # k : dev_num, v : [] of reads
    self.per_device_total_reads = {}
    self.writes = {}
    self.per_device_total_writes = {}
    self.total_reads = 0
    self.total_writes = 0
    self.total_dm_reads = 0
    self.total_dm_writes = 0


  def add_read_event(self, major, minor, event):
    devNum = major * DEV_MAJOR_MULTIPLIER + minor;
    events = self.reads.get(devNum)
    if not events:
      events = []
      self.reads[devNum] = events
      self.per_device_total_reads[devNum] = 0
    events.append(event)
    self.total_reads += event.size
    self.per_device_total_reads[devNum] += event.size

  def add_write_event(self, major, minor, event):
    devNum = major * DEV_MAJOR_MULTIPLIER + minor;
    events = self.writes.get(devNum)
    if not events:
      events = []
      self.writes[devNum] = events
      self.per_device_total_writes[devNum] = 0
    events.append(event)
    self.total_writes += event.size
    self.per_device_total_writes[devNum] += event.size

  def add_dm_read(self, size):
    self.total_dm_reads += size

  def add_dm_write(self, size):
    self.total_dm_writes += size

  def dump(self):
    print "Process,", self.name
    print " total reads,", self.total_reads
    print " total writes,", self.total_writes
    print " total dm reads,", self.total_dm_reads
    print " total dm writes,", self.total_dm_writes
    print " R per device"
    sorted_r = collections.OrderedDict(sorted(self.per_device_total_reads.items(), \
      key = lambda item: item[1], reverse = True))
    for i in range(len(sorted_r)):
      dev = sorted_r.popitem(last=False)
      print " ", dev[0],dev[1]

    print " W per device"
    sorted_w = collections.OrderedDict(sorted(self.per_device_total_writes.items(), \
      key = lambda item: item[1], reverse = True))
    for i in range(len(sorted_w)):
      dev = sorted_w.popitem(last=False)
      print " ", dev[0],dev[1]

class IoTrace:

  def __init__(self):
    self.ios = {} #K: process name, v:ProcessData
    self.total_reads = 0
    self.total_writes = 0
    self.total_reads_per_device = {} #K: block num, V: total blocks
    self.total_writes_per_device = {}
    self.total_dm_reads = {} #K: devnum, V: blocks
    self.total_dm_writes = {}
    self.re_block = re.compile(RE_BLOCK)

  def parse(self, l):
    match = self.re_block.match(l)
    if not match:
      return False
    try:
      self.do_parse_bio_queue(l, match)
    except ValueError:
      print "cannot parse:", l
      raise
    return True

  def do_parse_bio_queue(self, l, match):
    pid = match.group(1)
    start_time = float(match.group(2))*1000 #ms
    major = int(match.group(3))
    minor =  int(match.group(4))
    devNum = major * DEV_MAJOR_MULTIPLIER + minor;
    operation =  match.group(5)
    block_num = int(match.group(6))
    size = int(match.group(7))
    process = match.group(8) + "-" + pid
    event = RwEvent(block_num, start_time, size)
    io = self.ios.get(process)
    if not io:
      io = ProcessData(process)
      self.ios[process] = io
    if major == DM_MAJOR:
      devNum = major * DEV_MAJOR_MULTIPLIER + minor;
      if 'R' in operation[0]:
        if devNum not in self.total_dm_reads:
          self.total_dm_reads[devNum] = 0
        self.total_dm_reads[devNum] += size
        io.add_dm_read(size)
      elif 'W' in operation[0]:
        if devNum not in self.total_dm_writes:
          self.total_dm_writes[devNum] = 0
        self.total_dm_writes[devNum] += size
        io.add_dm_write(size)
      return
    if 'R' in operation[0]:
      io.add_read_event(major, minor, event)
      self.total_reads += size
      per_device = self.total_reads_per_device.get(devNum)
      if not per_device:
        self.total_reads_per_device[devNum] = 0
      self.total_reads_per_device[devNum] += size
    elif 'W' in operation[0]:
      io.add_write_event(major, minor, event)
      self.total_writes += size
      per_device = self.total_writes_per_device.get(devNum)
      if not per_device:
        self.total_writes_per_device[devNum] = 0
      self.total_writes_per_device[devNum] += size

  def dump(self):
    print "total read blocks,", self.total_reads
    print "total write blocks,", self.total_writes
    print "Total DM R"
    for dev,size in self.total_dm_reads.items():
      print dev, size
    print "Total DM W"
    for dev,size in self.total_dm_writes.items():
      print dev, size
    print "**Process total R/W"
    sorted_by_total_rw = collections.OrderedDict(sorted(self.ios.items(), \
      key = lambda item: item[1].total_reads + item[1].total_writes, reverse = True))
    for i in range(MAX_PROCESS_DUMP):
      process = sorted_by_total_rw.popitem(last=False)
      if not process:
        break
      process[1].dump()

    print "**Process total W"
    sorted_by_total_w = collections.OrderedDict(sorted(self.ios.items(), \
      key = lambda item: item[1].total_writes, reverse = True))
    for i in range(5):
      process = sorted_by_total_w.popitem(last=False)
      if not process:
        break
      process[1].dump()

    print "**Device total R"
    sorted_by_total_r = collections.OrderedDict(sorted(self.total_reads_per_device.items(), \
      key = lambda item: item[1], reverse = True))
    for i in range(len(sorted_by_total_r)):
      dev = sorted_by_total_r.popitem(last=False)
      print dev[0],dev[1]

    print "**Device total W"
    sorted_by_total_w = collections.OrderedDict(sorted(self.total_writes_per_device.items(), \
      key = lambda item: item[1], reverse = True))
    for i in range(len(sorted_by_total_w)):
      dev = sorted_by_total_w.popitem(last=False)
      print dev[0],dev[1]

class SchedProcess:
  def __init__(self, pid):
    self.pid = pid
    self.name = "unknown"
    self.total_execution_time = 0.0
    self.total_io_wait_time = 0.0
    self.total_other_wait_time = 0.0
    self.waiting_calls = {} # k: waiting_call, v : waiting counter
    self.io_waiting_call_times = {} # k: waiting_call, v: total wait time
    self.in_iowait = False
    self.last_waiting_call = None
    self.last_switch_out_time = 0.0
    self.last_switch_in_time = 0.0
    self.last_core = -1
    self.execution_time_per_core = {} # k: core, v : time
    self.io_latency_histograms = {} # k : delay in ms, v : count

  def handle_reason(self, current_time, iowait, waiting_call):
    #if self.pid == 1232:
    #  print current_time, iowait, waiting_call
    if iowait == 1:
      self.in_iowait = True
    self.last_waiting_call = waiting_call
    call_counter = self.waiting_calls.get(waiting_call, 0)
    call_counter += 1
    self.waiting_calls[waiting_call] = call_counter

  def handle_switch_out(self, current_time, out_state, priority, name, core):
    #if self.pid == 1232:
    #  print "out", current_time, out_state
    if self.name != name:
      self.name = name
    self.last_switch_out_time = current_time
    if self.last_switch_in_time == 0.0: # switch in not recorded. ignore this one
      return
    execution_time = current_time - self.last_switch_in_time
    self.total_execution_time += execution_time
    core_execution_time = self.execution_time_per_core.get(core, 0.0)
    core_execution_time += execution_time
    self.execution_time_per_core[core] = core_execution_time

  def handle_switch_in(self, current_time, priority, name, core):
    #if self.pid == 1232:
    #  print "in", current_time, self.in_iowait
    if self.name != name:
      self.name = name
    self.last_switch_in_time = current_time
    if self.last_switch_out_time == 0.0: # in without out, probably 1st
      self.in_iowait = False
      return
    wait_time = current_time - self.last_switch_out_time
    if self.in_iowait:
      self.total_io_wait_time += wait_time
      total_waiting_call_time = self.io_waiting_call_times.get(self.last_waiting_call, 0.0)
      total_waiting_call_time += wait_time
      self.io_waiting_call_times[self.last_waiting_call] = total_waiting_call_time
      wait_time_ms = int(wait_time*10) / 10.0 # resolution up to 0.1 ms
      histogram_count = self.io_latency_histograms.get(wait_time_ms, 0)
      histogram_count += 1
      self.io_latency_histograms[wait_time_ms] = histogram_count
    else:
      self.total_other_wait_time += wait_time
    self.in_iowait = False


  def dump(self):
    print "PID:", self.pid, " name:", self.name
    print " total execution time:", self.total_execution_time,\
      " io wait:", self.total_io_wait_time, " other wait:", self.total_other_wait_time
    sorted_data = collections.OrderedDict(sorted(self.execution_time_per_core.items(), \
      key = lambda item: item[0], reverse = False))
    print " Core execution:", sorted_data
    sorted_data = collections.OrderedDict(sorted(self.waiting_calls.items(), \
      key = lambda item: item[1], reverse = True))
    print " Wait calls:", sorted_data
    sorted_data = collections.OrderedDict(sorted(self.io_waiting_call_times.items(), \
      key = lambda item: item[1], reverse = True))
    print " IO Wait time per wait calls:", sorted_data
    sorted_data = collections.OrderedDict(sorted(self.io_latency_histograms.items(), \
      key = lambda item: item[0], reverse = False))
    print " Wait time histogram:", sorted_data

class SchedTrace:
  def __init__(self):
    self.re_switch = re.compile(RE_SCHED_SWITCH)
    self.re_reason = re.compile(RE_SCHED_BLOCKED_READSON)
    self.processes = {} # key: pid, v : SchedProcess

  def parse(self, l):
    checked_reason = False
    match = self.re_switch.match(l)
    if not match:
      match = self.re_reason.match(l)
      checked_reason = True
    if not match:
      return False
    try:
      if checked_reason:
        self.do_handle_reason(l, match)
      else:
        self.do_handle_switch(l, match)
    except ValueError:
      print "cannot parse:", l
      raise
    return True

  def do_handle_switch(self, l, match):
    current_pid = int(match.group(1))
    cpu_core = int(match.group(2))
    current_time = float(match.group(3))*1000 #ms
    out_name = match.group(4)
    out_pid = int(match.group(5))
    out_prio = int(match.group(6))
    out_state = match.group(7)
    in_name = match.group(8)
    in_pid = int(match.group(9))
    in_prio = int(match.group(10))
    out_process = self.processes.get(out_pid)
    if not out_process:
      out_process = SchedProcess(out_pid)
      self.processes[out_pid] = out_process
    in_process = self.processes.get(in_pid)
    if not in_process:
      in_process = SchedProcess(in_pid)
      self.processes[in_pid] = in_process
    out_process.handle_switch_out(current_time, out_state, out_prio, out_name, cpu_core)
    in_process.handle_switch_in(current_time, in_prio, in_name, cpu_core)

  def do_handle_reason(self, l, match):
    current_pid = int(match.group(1))
    cpu_core = int(match.group(2))
    current_time = float(match.group(3))*1000 #ms
    pid = int(match.group(4))
    iowait = int(match.group(5))
    waiting_call = match.group(6)
    process = self.processes.get(pid)
    if not process:
      process = SchedProcess(pid)
      self.processes[pid] = process
    process.handle_reason(current_time, iowait, waiting_call)

  def dump(self):
    sorted_by_total_execution = collections.OrderedDict(sorted(self.processes.items(), \
      key = lambda item: item[1].total_io_wait_time, reverse = True))
    for k, v in sorted_by_total_execution.iteritems():
      if v.total_execution_time > 10.0 or v.total_io_wait_time != 0.0:
        v.dump()

def main(argv):
  if (len(argv) < 2):
    print "check_io_trace_all.py filename"
    return
  filename = argv[1]

  io_trace = IoTrace()
  sched_trace = SchedTrace()
  with open(filename) as f:
    for l in f:
      if io_trace.parse(l):
        continue
      sched_trace.parse(l)
  io_trace.dump()
  print "\n\n\n"
  sched_trace.dump()

if __name__ == '__main__':
  main(sys.argv)
