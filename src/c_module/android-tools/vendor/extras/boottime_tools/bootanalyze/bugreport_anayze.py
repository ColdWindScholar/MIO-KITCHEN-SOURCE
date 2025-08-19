#!/usr/bin/python

# Copyright (C) 2017 The Android Open Source Project
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
"""Tool to analyze boot-up time from bugreport."""

import argparse
import collections
import datetime
import math
import operator
import os
import re
import select
import subprocess
import sys
import time
import threading
import yaml

from datetime import datetime, date

DBG = True

LOG_START_PATTERN = r"""\-\-\-\-\-\-\s(.*)\s\-\-\-\-\-\-"""
LOG_END_PATTERN = r"""\-\-\-\-\-\-\s\S.*\s\-\-\-\-\-\-"""

KERNEL_LOG_TITLE = "KERNEL LOG"
SYSYEM_LOG_TITLE = "SYSTEM LOG"
LAST_KMSG_TITLE = "LAST KMSG"
LAST_LOGCAT_TITLE = "LAST LOGCAT"

SYSTEM_PROPS_TITLE = "SYSTEM PROPERTIES"

TIME_DMESG = "\[\s*(\d+\.\d+)\]"
TIME_LOGCAT = "(\d+)\-(\d+)\s(\d+):(\d+):(\d+\.\d+)"

NATIVE_CRASH_START_PATTERN = "I\sDEBUG\s+:\s\*\*\*\s\*\*\*"
NATIVE_CRASH_PATTERN = "I\sDEBUG\s+:"
JAVA_CRASH_START_PATTERN = "E\sAndroidRuntime:\sFATAL\sEXCEPTION"
JAVA_CRASH_PATTERN = "E\sAndroidRuntime:\s"

EPOCH = datetime.utcfromtimestamp(0)

def init_arguments():
  parser = argparse.ArgumentParser(description='Measures boot time from bugreport.')
  parser.add_argument('-c', '--config', dest='config',
                      default='config.yaml', type=argparse.FileType('r'),
                      help='config file for the tool')
  parser.add_argument('bugreport_file', nargs=1, help='bugreport txt file',
                       type=argparse.FileType('r'))
  parser.add_argument('-n', '--iterate', dest='iterate', type=int, default=1,
                      help='number of time to repeat the measurement', )
  return parser.parse_args()

# Event per each reboot, for distinghishing current boot from last boot
class Events:
  def __init__(self):
    self.events = collections.OrderedDict() #K: keyword, V:time in ms
    self.timings = collections.OrderedDict()
    self.shutdown_events = collections.OrderedDict()
    self.java_crash = collections.OrderedDict() #K:time, V:list of crash infos, each entry per line
    self.native_crash = collections.OrderedDict()

  def reset_events_time(self, delta):
    new_events = collections.OrderedDict()
    for entry in self.events.iteritems():
      new_events[entry[0]] = entry[1] - delta
    self.events = new_events
    if len(self.native_crash) > 0:
      new_crash = collections.OrderedDict()
      for entry in self.native_crash.iteritems():
        new_crash[entry[0] - delta] = entry[1]
      self.native_crash = new_crash
    if len(self.java_crash) > 0:
      new_crash = collections.OrderedDict()
      for entry in self.java_crash.iteritems():
        new_crash[entry[0] - delta] = entry[1]
      self.java_crash = new_crash

  def reset_shutdown_events_time(self):
    if len(self.shutdown_events) == 0:
      return
    time_offset = 0
    new_events = collections.OrderedDict()
    for entry in self.shutdown_events.iteritems():
      if time_offset == 0:
        time_offset = entry[1]
      new_events[entry[0]] = entry[1] - time_offset
    self.shutdown_events = new_events

  def dump_dict(self, d):
    for entry in d.iteritems():
        print ' {0:30}: {1}'.format(entry[0], entry[1])

  def dump_crash(self, time, stack):
    print "    Crash time:", time, " stack:"
    print ' '.join(stack)

  def dump(self):
    if len(self.events) > 0:
      print "\n***Events:"
      self.dump_dict(self.events)
    if len(self.timings) > 0:
      print "\n***Timings top 20"
      timings_sorted = sorted(self.timings.items(), key = lambda item: item[1], reverse=True)
      nums_to_dump = min(20, len(timings_sorted))
      for i in range(nums_to_dump):
          print ' {0:30}: {1}'.format(timings_sorted[i][0], timings_sorted[i][1])
      print "\n***Timings:"
      self.dump_dict(self.timings)
    if len(self.shutdown_events) > 0:
      print "\n***Shutdown Events (time relative to the begining of shutdown) :"
      self.dump_dict(self.shutdown_events)
    if len(self.native_crash) > 0:
      print "\n***Native crash founds:", len(self.native_crash)
      for entry in self.native_crash.iteritems():
        self.dump_crash(entry[0], entry[1])
    if len(self.java_crash) > 0:
      print "\n***Java crash founds:", len(self.java_crash)
      for entry in self.java_crash.iteritems():
        self.dump_crash(entry[0], entry[1])

class Parser:
  def __init__(self, config_file, bugreport_file):
    self.re_log_start = re.compile(LOG_START_PATTERN)
    self.re_log_end = re.compile(LOG_END_PATTERN)
    self.f = bugreport_file
    cfg = yaml.load(config_file, Loader=yaml.SafeLoader)
    self.event_patterns = {key: re.compile(pattern)
                         for key, pattern in cfg['events'].iteritems()}
    self.timing_patterns = {key: re.compile(pattern)
                         for key, pattern in cfg['timings'].iteritems()}
    self.shutdown_event_patterns = {key: re.compile(pattern)
                           for key, pattern in cfg['shutdown_events'].iteritems()}
    self.current_boot_kernel = Events()
    self.current_boot_logcat = Events()
    self.last_boot_kernel = Events()
    self.last_boot_logcat = Events()
    self.boottime_props = collections.OrderedDict() # K:prop, V:boot time, added in boot time order
    self.bootloader_time = 0
    self.re_time_dmesg = re.compile(TIME_DMESG)
    self.re_time_logcat = re.compile(TIME_LOGCAT)
    self.re_native_crash_start = re.compile(NATIVE_CRASH_START_PATTERN)
    self.re_native_crash = re.compile(NATIVE_CRASH_PATTERN)
    self.re_java_crash_start = re.compile(JAVA_CRASH_START_PATTERN)
    self.re_java_crash = re.compile(JAVA_CRASH_PATTERN)

  def match_an_event(self, event_patterns, line):
    for event_key, event_pattern in event_patterns.iteritems():
      m = event_pattern.search(line)
      if m:
        return event_key, m
    return None, None

  def get_event_time(self, line, is_kernel):
    if is_kernel:
      m = self.re_time_dmesg.search(line)
      if not m:
        print "Cannot get time from log:", line
        return -1
      return int(float(m.group(1)) * 1000)
    else:
      m = self.re_time_logcat.search(line)
      if not m:
          print "Cannot get time from log:", line
          return -1
      mm = int(m.group(1))
      dd = int(m.group(2))
      hh = int(m.group(3))
      min = int(m.group(4))
      usecs = int(float(m.group(5)) * 1000000)
      secs = usecs / 1000000
      usecs = usecs - 1000000 * secs
      dt = datetime(2017, mm, dd, hh, min, secs, usecs)
      return int((dt - EPOCH).total_seconds() * 1000)

  def queue_crash(self, event, crash_time, crash_stacks, is_native_crash):
    stacks = list(crash_stacks)
    if is_native_crash:
      event.native_crash[crash_time] = stacks
    else:
      event.java_crash[crash_time] = stacks

  def check_crash(self, event, orig_line):
    line = orig_line
    crash_time = 0
    crash_stacks = []
    is_native_crash = True
    while len(line) > 0:
      m = self.re_native_crash_start.search(line)
      if m:
        if len(crash_stacks) > 0:
          self.queue_crash(event, crash_time, crash_stacks, is_native_crash)
          crash_stacks = []
        is_native_crash = True
        crash_stacks.append(line)
        crash_time = self.get_event_time(line, False)
        line = self.f.readline()
        continue
      m = self.re_native_crash.search(line)
      if m:
        crash_stacks.append(line)
        line = self.f.readline()
        continue
      m = self.re_java_crash_start.search(line)
      if m:
        if len(crash_stacks) > 0:
          self.queue_crash(event, crash_time, crash_stacks, is_native_crash)
          crash_stacks = []
        is_native_crash = False
        crash_stacks.append(line)
        crash_time = self.get_event_time(line, False)
        line = self.f.readline()
        continue
      m = self.re_java_crash.search(line)
      if m:
        crash_stacks.append(line)
        line = self.f.readline()
        continue
      # reaching here means not crash, so return new line
      if line != orig_line:
        return line
      else:
        return self.f.readline()



  def handle_events(self, event, is_kernel):
    line = self.f.readline()
    while len(line) > 0 and not self.re_log_end.match(line):
      key, m = self.match_an_event(self.event_patterns, line)
      if m:
        event.events[key] = self.get_event_time(line, is_kernel)
        line = self.f.readline()
        continue
      key, m = self.match_an_event(self.timing_patterns, line)
      if m:
        name = m.group('name')
        time = float(m.group('time'))
        if key.endswith('_secs'):
          time = time * 1000
        event.timings[name] = int(time)
        line = self.f.readline()
        continue
      key, m = self.match_an_event(self.shutdown_event_patterns, line)
      if m:
          event.shutdown_events[key] = self.get_event_time(line, is_kernel)
          line = self.f.readline()
          continue
      if not is_kernel: # collect crash
        line = self.check_crash(event, line)
        continue
      line = self.f.readline()

  def handle_kernel_log(self):
    if DBG:
      print "start " + KERNEL_LOG_TITLE
    self.handle_events(self.current_boot_kernel, True)

  def handle_system_log(self):
    if DBG:
      print "start " + SYSYEM_LOG_TITLE
    self.handle_events(self.current_boot_logcat, False)

  def handle_last_kernel_log(self):
      if DBG:
          print "start " + LAST_KMSG_TITLE
      self.handle_events(self.last_boot_kernel, True)

  def handle_last_system_log(self):
    if DBG:
        print "start " + LAST_LOGCAT_TITLE
    self.handle_events(self.last_boot_logcat, False)

  def handle_system_props(self):
    if DBG:
        print "start " + SYSTEM_PROPS_TITLE
    re_prop = re.compile(r"""\[(.+)\].*\[(.*)\]""")
    RO_BOOTTIME_PROP = "ro.boottime."
    boottime_props = {} # K: prop name, V: boot time in ms
    line = self.f.readline()
    while len(line) > 0 and not self.re_log_end.match(line):
      m = re_prop.match(line)
      if not m:
        print "Cannot parse prop:", line
        line = self.f.readline()
        continue
      if m.group(1).startswith(RO_BOOTTIME_PROP):
        name = m.group(1)[len(RO_BOOTTIME_PROP):]
        time = int(m.group(2)) / 1000000 # ns to ms
        boottime_props[name] = time
      elif m.group(1) == "ro.boot.boottime":
        print "Found bootloader boottime ", line
        entries = m.group(2).split(",")
        for entry in entries:
          values = entry.split(":")
          if values[0] != "SW":
              self.bootloader_time += int(values[1])
      line = self.f.readline()
    self.boottime_props = collections.OrderedDict(sorted(
        boottime_props.items(), key = lambda item: item[1]))

  def parse(self):
    while (True):
      l = self.f.readline()
      if len(l) == 0: # EOF
        return
      m = self.re_log_start.match(l)
      if not m:
        continue
      #print m.group(1)
      if m.group(1).startswith(KERNEL_LOG_TITLE):
        self.handle_kernel_log()
      elif m.group(1).startswith(SYSYEM_LOG_TITLE):
        self.handle_system_log()
      elif m.group(1).startswith(SYSTEM_PROPS_TITLE):
        self.handle_system_props()
      elif m.group(1).startswith(LAST_KMSG_TITLE):
        self.handle_last_kernel_log()
      elif m.group(1).startswith(LAST_LOGCAT_TITLE):
        self.handle_last_system_log()

  def dump_props(self):
    if self.bootloader_time != 0:
      print "*bootloader time:", self.bootloader_time
    if self.boottime_props:
      print "*ro.boottime.*:"
      for name, t in self.boottime_props.iteritems():
        print ' {0:30}: {1}'.format(name, t)

  def reset_event_times(self, kernel_event, logcat_event):
    has_boot_complete = True
    kernel_bootcomplete_time = kernel_event.events.get("BootComplete_kernel")
    if not kernel_bootcomplete_time:
      has_boot_complete = False
    logcat_bootcomplete_time = logcat_event.events.get("BootComplete")
    if not logcat_bootcomplete_time:
      has_boot_complete = False
    time_delta = 0
    if has_boot_complete:
      time_delta = logcat_bootcomplete_time - kernel_bootcomplete_time
    else:
      time_delta = logcat_event.events.values()[0] if len(logcat_event.events) > 0 else 0
    logcat_event.reset_events_time(time_delta)
    logcat_event.reset_shutdown_events_time()
    kernel_event.reset_shutdown_events_time()
    return has_boot_complete

  def dump(self):
    self.dump_props()
    boot_complete_found = self.reset_event_times(self.current_boot_kernel, self.current_boot_logcat)
    print "* Kernel dmesg:"
    self.current_boot_kernel.dump()
    print "\n\n* Logcat " + ("(time matched with kernel dmesg):" if boot_complete_found\
        else "(time set relative to the first event):")
    self.current_boot_logcat.dump()
    print "\n\n\n==== Data from last boot ==="
    boot_complete_found = self.reset_event_times(self.last_boot_kernel, self.last_boot_logcat)
    print "\n\n* Last Kernel dmesg:"
    self.last_boot_kernel.dump()
    print "\n\n* Last Logcat " + ("(time matched with kernel dmesg):" if boot_complete_found \
        else "(time set relative to the first event):")
    self.last_boot_logcat.dump()

def main():
  args = init_arguments()

  parser = Parser(args.config, args.bugreport_file[0])
  parser.parse()
  parser.dump()

if __name__ == '__main__':
  main()
