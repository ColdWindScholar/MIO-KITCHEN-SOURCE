#!/usr/bin/python3

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
"""Tool to analyze logcat and dmesg logs.

bootanalyze read logcat and dmesg logs and determines key points for boot.
"""

import argparse
import collections
import datetime
import math
import operator
import os
import re
import select
import subprocess
import time
import threading
import yaml

from datetime import datetime

TIME_DMESG = r"\[\s*(\d+\.\d+)\]"
TIME_LOGCAT = r"[0-9]+\.?[0-9]*"
KERNEL_TIME_KEY = "kernel"
BOOT_ANIM_END_TIME_KEY = "BootAnimEnd"
KERNEL_BOOT_COMPLETE = "BootComplete_kernel"
LOGCAT_BOOT_COMPLETE = "BootComplete"
CARWATCHDOG_BOOT_COMPLETE = "CarWatchdogBootupProfilingComplete"
LAUNCHER_START = "LauncherStart"
CARWATCHDOG_DUMP_COMMAND = "adb shell dumpsys android.automotive.watchdog.ICarWatchdog/default"
BOOT_TIME_TOO_BIG = 200.0
MAX_RETRIES = 5
DEBUG = False
DEBUG_PATTERN = False
ADB_CMD = "adb"
TIMING_THRESHOLD = 5.0
BOOT_PROP = r"\[ro\.boottime\.([^\]]+)\]:\s+\[(\d+)\]"
BOOTLOADER_TIME_PROP = r"\[ro\.boot\.boottime\]:\s+\[([^\]]+)\]"
CARWATCHDOG_PARSER_CMD = 'perf_stats_parser'

max_wait_time = BOOT_TIME_TOO_BIG

def main():
  global ADB_CMD

  args = init_arguments()

  if args.iterate < 1:
    raise Exception('Number of iteration must be >=1')

  if args.iterate > 1 and not args.reboot:
    print("Forcing reboot flag")
    args.reboot = True

  if args.serial:
    ADB_CMD = "%s %s" % ("adb -s", args.serial)

  error_time = BOOT_TIME_TOO_BIG * 10
  if args.errortime:
    error_time = float(args.errortime)
  if args.maxwaittime:
    global max_wait_time
    max_wait_time = float(args.maxwaittime)

  components_to_monitor = {}
  if args.componentmonitor:
    items = args.componentmonitor.split(",")
    for item in items:
      kv = item.split("=")
      key = kv[0]
      value = float(kv[1])
      components_to_monitor[key] = value

  cfg = yaml.load(args.config, Loader=yaml.SafeLoader)

  if args.stressfs:
    if run_adb_cmd('install -r -g ' + args.stressfs) != 0:
      raise Exception('StressFS APK not installed')

  if args.iterate > 1 and args.bootchart:
    run_adb_shell_cmd_as_root('touch /data/bootchart/enabled')

  search_events_pattern = {key: re.compile(pattern)
                   for key, pattern in cfg['events'].items()}
  timing_events_pattern = {key: re.compile(pattern)
                   for key, pattern in cfg['timings'].items()}
  shutdown_events_pattern = {key: re.compile(pattern)
                   for key, pattern in cfg['shutdown_events'].items()}
  if DEBUG_PATTERN:
    print("search event:{} timing event:{}".format(search_events_pattern, timing_events_pattern))

  now = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
  boot_chart_file_path_prefix = "bootchart-" + now
  systrace_file_path_prefix = "systrace-" + now

  if args.output:
    boot_chart_file_path_prefix = args.output + '/' + boot_chart_file_path_prefix
    systrace_file_path_prefix = args.output + '/' + systrace_file_path_prefix

  data_points = {}
  kernel_timing_points = collections.OrderedDict()
  logcat_timing_points = collections.OrderedDict()
  boottime_points = collections.OrderedDict()
  shutdown_event_all = collections.OrderedDict()
  shutdown_timing_event_all = collections.OrderedDict()
  for it in range(0, args.iterate):
    if args.iterate > 1:
      print("Run: {0}".format(it))
    attempt = 1
    processing_data = None
    timings = None
    boottime_events = None
    while attempt <= MAX_RETRIES and processing_data is None:
      attempt += 1
      processing_data, kernel_timings, logcat_timings, boottime_events, shutdown_events,\
          shutdown_timing_events = iterate(\
        args, search_events_pattern, timing_events_pattern, shutdown_events_pattern, cfg,\
        error_time, components_to_monitor)
    if shutdown_events:
      for k, v in shutdown_events.items():
        events = shutdown_event_all.get(k)
        if not events:
          events = []
          shutdown_event_all[k] = events
        events.append(v)
    if shutdown_timing_events:
      for k, v in shutdown_timing_events.items():
        events = shutdown_timing_event_all.get(k)
        if not events:
          events = []
          shutdown_timing_event_all[k] = events
        events.append(v)
    if not processing_data or not boottime_events:
      # Processing error
      print("Failed to collect valid samples for run {0}".format(it))
      continue

    if args.bootchart:
      grab_bootchart(boot_chart_file_path_prefix + "_run_" + str(it))

    if args.systrace:
      grab_systrace(systrace_file_path_prefix + "_run_" + str(it))

    if args.carwatchdog:
      grab_carwatchdog_bootstats(args.output)

    for k, v in processing_data.items():
      if k not in data_points:
        data_points[k] = []
      data_points[k].append(v['value'])

    if kernel_timings is not None:
      for k, v in kernel_timings.items():
        if k not in kernel_timing_points:
          kernel_timing_points[k] = []
        kernel_timing_points[k].append(v)
    if logcat_timings is not None:
      for k, v in logcat_timings.items():
        if k not in logcat_timing_points:
          logcat_timing_points[k] = []
        logcat_timing_points[k].append(v)

    for k, v in boottime_events.items():
      if k not in boottime_points:
        boottime_points[k] = []
      boottime_points[k].append(v)

  if args.stressfs:
    run_adb_cmd('uninstall com.android.car.test.stressfs')
    run_adb_shell_cmd('"rm -rf /storage/emulated/0/stressfs_data*"')

  if args.iterate > 1:
    print("-----------------")
    print("\nshutdown events after {0} runs".format(args.iterate))
    print('{0:30}: {1:<7} {2:<7} {3}'.format("Event", "Mean", "stddev", "#runs"))
    for item in list(shutdown_event_all.items()):
      num_runs = len(item[1])
      print('{0:30}: {1:<7.5} {2:<7.5} {3} {4}'.format(
          item[0], sum(item[1])/num_runs, stddev(item[1]),\
          "*time taken" if item[0].startswith("init.") else "",\
          num_runs if num_runs != args.iterate else ""))
    print("\nshutdown timing events after {0} runs".format(args.iterate))
    print('{0:30}: {1:<7} {2:<7} {3}'.format("Event", "Mean", "stddev", "#runs"))
    for item in list(shutdown_timing_event_all.items()):
      num_runs = len(item[1])
      print('{0:30}: {1:<7.5} {2:<7.5} {3} {4}'.format(
          item[0], sum(item[1])/num_runs, stddev(item[1]),\
          "*time taken" if item[0].startswith("init.") else "",\
          num_runs if num_runs != args.iterate else ""))

    print("-----------------")
    print("ro.boottime.* after {0} runs".format(args.iterate))
    print('{0:30}: {1:<7} {2:<7} {3}'.format("Event", "Mean", "stddev", "#runs"))
    for item in list(boottime_points.items()):
        num_runs = len(item[1])
        print('{0:30}: {1:<7.5} {2:<7.5} {3} {4}'.format(
          item[0], sum(item[1])/num_runs, stddev(item[1]),\
          "*time taken" if item[0].startswith("init.") else "",\
          num_runs if num_runs != args.iterate else ""))

    if args.timings:
      dump_timings_points_summary("Kernel", kernel_timing_points, args)
      dump_timings_points_summary("Logcat", logcat_timing_points, args)


    print("-----------------")
    print("Avg values after {0} runs".format(args.iterate))
    print('{0:30}: {1:<7} {2:<7} {3}'.format("Event", "Mean", "stddev", "#runs"))

    average_with_stddev = []
    for item in list(data_points.items()):
      average_with_stddev.append((item[0], sum(item[1])/len(item[1]), stddev(item[1]),\
                                  len(item[1])))
    for item in sorted(average_with_stddev, key=lambda entry: entry[1]):
      print('{0:30}: {1:<7.5} {2:<7.5} {3}'.format(
        item[0], item[1], item[2], item[3] if item[3] != args.iterate else ""))

    run_adb_shell_cmd_as_root('rm /data/bootchart/enabled')


def dump_timings_points_summary(msg_header, timing_points, args):
      averaged_timing_points = []
      for item in list(timing_points.items()):
        average = sum(item[1])/len(item[1])
        std_dev = stddev(item[1])
        averaged_timing_points.append((item[0], average, std_dev, len(item[1])))

      print("-----------------")
      print(msg_header + " timing in order, Avg time values after {0} runs".format(args.iterate))
      print('{0:30}: {1:<7} {2:<7} {3}'.format("Event", "Mean", "stddev", "#runs"))
      for item in averaged_timing_points:
        print('{0:30}: {1:<7.5} {2:<7.5} {3}'.format(
          item[0], item[1], item[2], item[3] if item[3] != args.iterate else ""))

      print("-----------------")
      print(msg_header + " timing top items, Avg time values after {0} runs".format(args.iterate))
      print('{0:30}: {1:<7} {2:<7} {3}'.format("Event", "Mean", "stddev", "#runs"))
      for item in sorted(averaged_timing_points, key=lambda entry: entry[1], reverse=True):
        if item[1] < TIMING_THRESHOLD:
          break
        print('{0:30}: {1:<7.5} {2:<7.5} {3}'.format(
          item[0], item[1], item[2], item[3] if item[3] != args.iterate else ""))

def capture_bugreport(bugreport_hint, boot_complete_time):
    now = datetime.now()
    bugreport_file = ("bugreport-%s-" + bugreport_hint + "-%s.zip") \
        % (now.strftime("%Y-%m-%d-%H-%M-%S"), str(boot_complete_time))
    print("Boot up time too big, will capture bugreport %s" % (bugreport_file))
    os.system(ADB_CMD + " bugreport " + bugreport_file)

def generate_timing_points(timing_events, timings):
  timing_points = collections.OrderedDict()
  monitor_contention_points = collections.OrderedDict()
  for k, l in timing_events.items():
      for v in l:
        name, time_v = extract_timing(v, timings)
        if name and time_v:
          if v.find("SystemServerTimingAsync") > 0:
            name = "(" + name + ")"
          if k.endswith("_secs"):
            time_v = time_v * 1000.0
          if k.startswith("long_monitor_contention"):
            monitor_contention_points[v] = time_v
            continue
          new_name = name
          name_index = 0
          while timing_points.get(new_name): # if the name is already taken, append #digit
            name_index += 1
            new_name = name + "#" + str(name_index)
          timing_points[new_name] = time_v
  return timing_points, monitor_contention_points

def dump_timing_points(msg_header, timing_points):
    print(msg_header + " event timing in time order, key: time")
    for item in list(timing_points.items()):
      print('{0:30}: {1:<7.5}'.format(item[0], item[1]))
    print("-----------------")
    print(msg_header + " event timing top items")
    for item in sorted(list(timing_points.items()), key=operator.itemgetter(1), reverse=True):
      if item[1] < TIMING_THRESHOLD:
        break
      print('{0:30}: {1:<7.5}'.format(
        item[0], item[1]))
    print("-----------------")

def dump_monitor_contentions(logcat_monitor_contentions):
  print("Monitor contentions over 100ms:")
  for item in list(logcat_monitor_contentions.items()):
      if item[1] > 100:
        print('{0:<7.5}ms: {1}'.format(item[1], item[0]))
  print("-----------------")

def handle_reboot_log(capture_log_on_error, shutdown_events_pattern, components_to_monitor):
  shutdown_events, shutdown_timing_events = collect_logcat_for_shutdown(capture_log_on_error,\
		shutdown_events_pattern, components_to_monitor)
  print("\nshutdown events: time")
  for item in list(shutdown_events.items()):
    print('{0:30}: {1:<7.5}'.format(item[0], item[1]))
  print("\nshutdown timing events: time")
  for item in list(shutdown_timing_events.items()):
    print('{0:30}: {1:<7.5}'.format(item[0], item[1]))
  return shutdown_events, shutdown_timing_events

def collect_dmesg_events(search_events_pattern, timings_pattern, results):
  dmesg_events, kernel_timing_events = collect_events(search_events_pattern, ADB_CMD +\
                                                      ' shell su root dmesg -w', timings_pattern,\
                                                      [KERNEL_BOOT_COMPLETE], True)
  results.append(dmesg_events)
  results.append(kernel_timing_events)

def iterate(args, search_events_pattern, timings_pattern, shutdown_events_pattern, cfg, error_time,\
    components_to_monitor):
  shutdown_events = None
  shutdown_timing_events = None
  if args.reboot:
    # sleep to make sure that logcat reader is reading before adb is gone by reboot. ugly but make
    # impl simple.
    t = threading.Thread(target=lambda: (time.sleep(2), reboot(args.serial, args.stressfs != '',\
        args.permissive, args.adb_reboot, args.buffersize)))
    t.start()
    shutdown_events, shutdown_timing_events = handle_reboot_log(True, shutdown_events_pattern,\
        components_to_monitor)
    t.join()

  results = []
  t = threading.Thread(target=collect_dmesg_events, args=(search_events_pattern,\
    timings_pattern, results))
  t.start()

  logcat_stop_events = [LOGCAT_BOOT_COMPLETE, LAUNCHER_START]
  if args.fs_check:
    logcat_stop_events.append("FsStat")
  if args.carwatchdog:
    logcat_stop_events.append(CARWATCHDOG_BOOT_COMPLETE)
  logcat_events, logcat_timing_events = collect_events(
    search_events_pattern, ADB_CMD + ' logcat -b all -v epoch', timings_pattern,\
    logcat_stop_events, False)

  t.join()
  dmesg_events = results[0]
  kernel_timing_events = results[1]

  logcat_event_time = extract_time(logcat_events, TIME_LOGCAT, float)
  logcat_original_time = extract_time(logcat_events, TIME_LOGCAT, str);
  dmesg_event_time = extract_time(dmesg_events, TIME_DMESG, float);
  boottime_events = fetch_boottime_property()
  events = {}
  events_to_correct = []
  replaced_from_dmesg = set()

  time_correction_delta = 0
  time_correction_time = 0
  if ('time_correction_key' in cfg
      and cfg['time_correction_key'] in logcat_events):
    match = search_events_pattern[cfg['time_correction_key']].search(
      logcat_events[cfg['time_correction_key']])
    if match and logcat_event_time[cfg['time_correction_key']]:
      time_correction_delta = float(match.group(1))
      time_correction_time = logcat_event_time[cfg['time_correction_key']]

  debug("time_correction_delta = {0}, time_correction_time = {1}".format(
    time_correction_delta, time_correction_time))

  for k, v in logcat_event_time.items():
    if v <= time_correction_time:
      logcat_event_time[k] += time_correction_delta
      v = v + time_correction_delta
      debug("correcting event to event[{0}, {1}]".format(k, v))

  diffs = []
  if logcat_event_time.get(KERNEL_TIME_KEY) is None:
    print("kernel time not captured in logcat")
  else:
    diffs.append((logcat_event_time[KERNEL_TIME_KEY], logcat_event_time[KERNEL_TIME_KEY]))

  if logcat_event_time.get(BOOT_ANIM_END_TIME_KEY) and dmesg_event_time.get(BOOT_ANIM_END_TIME_KEY):
      diffs.append((logcat_event_time[BOOT_ANIM_END_TIME_KEY],\
                    logcat_event_time[BOOT_ANIM_END_TIME_KEY] -\
                      dmesg_event_time[BOOT_ANIM_END_TIME_KEY]))
  if not dmesg_event_time.get(KERNEL_BOOT_COMPLETE):
      print("BootAnimEnd time or BootComplete-kernel not captured in both log" +\
        ", cannot get time diff")
      print("dmesg {} logcat {}".format(dmesg_event_time, logcat_event_time))
      return None, None, None, None, None, None
  diffs.append((logcat_event_time[LOGCAT_BOOT_COMPLETE],\
                logcat_event_time[LOGCAT_BOOT_COMPLETE] - dmesg_event_time[KERNEL_BOOT_COMPLETE]))

  for k, v in logcat_event_time.items():
    debug("event[{0}, {1}]".format(k, v))
    events[k] = v
    if k in dmesg_event_time:
      debug("{0} is in dmesg".format(k))
      events[k] = dmesg_event_time[k]
      replaced_from_dmesg.add(k)
    else:
      events_to_correct.append(k)

  diff_prev = diffs[0]
  for k in events_to_correct:
    diff = diffs[0]
    while diff[0] < events[k] and len(diffs) > 1:
      diffs.pop(0)
      diff_prev = diff
      diff = diffs[0]
    events[k] = events[k] - diff[1]
    if events[k] < 0.0:
        if events[k] < -0.1: # maybe previous one is better fit
          events[k] = events[k] + diff[1] - diff_prev[1]
        else:
          events[k] = 0.0

  data_points = collections.OrderedDict()

  print("-----------------")
  print("ro.boottime.*: time")
  for item in list(boottime_events.items()):
    print('{0:30}: {1:<7.5} {2}'.format(item[0], item[1],\
      "*time taken" if item[0].startswith("init.") else ""))
  print("-----------------")

  if args.timings:
    kernel_timing_points, _ = generate_timing_points(kernel_timing_events, timings_pattern)
    logcat_timing_points, logcat_monitor_contentions =\
      generate_timing_points(logcat_timing_events, timings_pattern)
    dump_timing_points("Kernel", kernel_timing_points)
    dump_timing_points("Logcat", logcat_timing_points)
    dump_monitor_contentions(logcat_monitor_contentions)

  for item in sorted(list(events.items()), key=operator.itemgetter(1)):
    data_points[item[0]] = {
      'value': item[1],
      'from_dmesg': item[0] in replaced_from_dmesg,
      'logcat_value': logcat_original_time[item[0]]
    }
  # add times with bootloader
  if events.get("BootComplete") and boottime_events.get("bootloader"):
    total = events["BootComplete"] + boottime_events["bootloader"]
    data_points["*BootComplete+Bootloader"] = {
      'value': total,
      'from_dmesg': False,
      'logcat_value': 0.0
    }
  if events.get("LauncherStart") and boottime_events.get("bootloader"):
    total = events["LauncherStart"] + boottime_events["bootloader"]
    data_points["*LauncherStart+Bootloader"] = {
      'value': total,
      'from_dmesg': False,
      'logcat_value': 0.0
    }
  for k, v in data_points.items():
    print('{0:30}: {1:<7.5} {2:1} ({3})'.format(
      k, v['value'], '*' if v['from_dmesg'] else '', v['logcat_value']))

  print('\n* - event time was obtained from dmesg log\n')

  if events[LOGCAT_BOOT_COMPLETE] > error_time and not args.ignore:
    capture_bugreport("bootuptoolong", events[LOGCAT_BOOT_COMPLETE])

  for k, v in components_to_monitor.items():
    logcat_value_measured = logcat_timing_points.get(k)
    kernel_value_measured = kernel_timing_points.get(k)
    data_from_data_points = data_points.get(k)
    if logcat_value_measured and logcat_value_measured > v:
      capture_bugreport(k + "-" + str(logcat_value_measured), events[LOGCAT_BOOT_COMPLETE])
      break
    elif kernel_value_measured and kernel_value_measured > v:
      capture_bugreport(k + "-" + str(kernel_value_measured), events[LOGCAT_BOOT_COMPLETE])
      break
    elif data_from_data_points and data_from_data_points['value'] * 1000.0 > v:
      capture_bugreport(k + "-" + str(data_from_data_points['value']), events[LOGCAT_BOOT_COMPLETE])
      break

  if args.fs_check:
    fs_stat = None
    if logcat_events.get("FsStat"):
      fs_stat_pattern = cfg["events"]["FsStat"]
      m = re.search(fs_stat_pattern, logcat_events.get("FsStat"))
      if m:
        fs_stat = m.group(1)
    print('fs_stat:', fs_stat)

    if fs_stat:
      fs_stat_val = int(fs_stat, 0)
      if (fs_stat_val & ~0x17) != 0:
        capture_bugreport("fs_stat_" + fs_stat, events[LOGCAT_BOOT_COMPLETE])

  return data_points, kernel_timing_points, logcat_timing_points, boottime_events, shutdown_events,\
      shutdown_timing_events

def debug(string):
  if DEBUG:
    print(string)

def extract_timing(s, patterns):
  for _, p in patterns.items():
    m = p.search(s)
    if m:
      timing_dict = m.groupdict()
      return timing_dict['name'], float(timing_dict['time'])
  return None, None

def init_arguments():
  parser = argparse.ArgumentParser(description='Measures boot time.')
  parser.add_argument('-r', '--reboot', dest='reboot',
                      action='store_true',
                      help='reboot device for measurement', )
  parser.add_argument('-o', '--output', dest='output', type=str,
                      help='Output directory where results are stored')
  parser.add_argument('-c', '--config', dest='config',
                      default='config.yaml', type=argparse.FileType('r'),
                      help='config file for the tool', )
  parser.add_argument('-s', '--stressfs', dest='stressfs',
                      default='', type=str,
                      help='APK file for the stressfs tool used to write to the data partition ' +\
                           'during shutdown')
  parser.add_argument('-n', '--iterate', dest='iterate', type=int, default=1,
                      help='number of time to repeat the measurement', )
  parser.add_argument('-g', '--ignore', dest='ignore', action='store_true',
                      help='ignore too big values error', )
  parser.add_argument('-t', '--timings', dest='timings', action='store_true',
                      help='print individual component times', default=True, )
  parser.add_argument('-p', '--serial', dest='serial', action='store',
                      help='android device serial number')
  parser.add_argument('-e', '--errortime', dest='errortime', action='store',
                      help='handle bootup time bigger than this as error')
  parser.add_argument('-w', '--maxwaittime', dest='maxwaittime', action='store',
                      help='wait for up to this time to collect logs. Retry after this time.' +\
                           ' Default is 200 sec.')
  parser.add_argument('-f', '--fs_check', dest='fs_check',
                      action='store_true',
                      help='check fs_stat after reboot', )
  parser.add_argument('-a', '--adb_reboot', dest='adb_reboot',
                      action='store_true',
                      help='reboot with adb reboot', )
  parser.add_argument('-v', '--permissive', dest='permissive',
                      action='store_true',
                      help='set selinux into permissive before reboot', )
  parser.add_argument('-m', '--componentmonitor', dest='componentmonitor', action='store',
                      help='capture bugreport if specified timing component is taking more than ' +\
                           'certain time. Unlike errortime, the result will not be rejected in' +\
                           'averaging. Format is key1=time1,key2=time2...')
  parser.add_argument('-b', '--bootchart', dest='bootchart',
                      action='store_true',
                      help='collect bootchart from the device.', )
  parser.add_argument('-y', '--systrace', dest='systrace',
                      action='store_true',
                      help='collect systrace from the device. kernel trace should be already enabled', )
  parser.add_argument('-W', '--carwatchdog', dest='carwatchdog', action='store_true',
                      help='collect carwatchdog boot stats')
  parser.add_argument('-G', '--buffersize', dest='buffersize', action='store', type=str,
                      default=None,
                      help='set logcat buffersize')
  return parser.parse_args()

def handle_zygote_event(zygote_pids, events, event, line):
  words = line.split()
  if len(words) > 1:
    pid = int(words[1])
    if len(zygote_pids) == 2:
      if pid == zygote_pids[1]: # secondary
        event = event + "-secondary"
    elif len(zygote_pids) == 1:
      if zygote_pids[0] != pid: # new pid, need to decide if old ones were secondary
        primary_pid = min(pid, zygote_pids[0])
        secondary_pid = max(pid, zygote_pids[0])
        zygote_pids.pop()
        zygote_pids.append(primary_pid)
        zygote_pids.append(secondary_pid)
        if pid == primary_pid: # old one was secondary:
          move_to_secondary = []
          for k, l in events.items():
            if k.startswith("zygote"):
              move_to_secondary.append((k, l))
          for item in move_to_secondary:
            del events[item[0]]
            if item[0].endswith("-secondary"):
              print("Secondary already exists for event %s  while found new pid %d, primary %d "\
                % (item[0], secondary_pid, primary_pid))
            else:
              events[item[0] + "-secondary"] = item[1]
        else:
          event = event + "-secondary"
    else:
      zygote_pids.append(pid)
  events[event] = line

def update_name_if_already_exist(events, name):
  existing_event = events.get(name)
  i = 0
  new_name = name
  while existing_event:
    i += 1
    new_name = name + "_" + str(i)
    existing_event = events.get(new_name)
  return new_name

def collect_logcat_for_shutdown(capture_log_on_error, shutdown_events_pattern,\
    log_capture_conditions):
  events = collections.OrderedDict()
  # shutdown does not have timing_events but calculated from checking Xyz - XyzDone / XyzTimeout
  timing_events = collections.OrderedDict()
  process = subprocess.Popen(ADB_CMD + ' logcat -b all -v epoch', shell=True,
                             stdout=subprocess.PIPE)
  lines = []
  capture_log = False
  shutdown_start_time = 0
  while True:
    line = process.stdout.readline()
    if not line:
      break
    line = line.decode('utf-8', 'ignore').lstrip().rstrip()
    lines.append(line)
    event = get_boot_event(line, shutdown_events_pattern)
    if not event:
      continue
    time = extract_a_time(line, TIME_LOGCAT, float)
    if time is None:
      print("cannot get time from: " + line)
      continue
    if shutdown_start_time == 0:
      shutdown_start_time = time
    time = time - shutdown_start_time
    events[event] = time
    time_limit1 = log_capture_conditions.get(event)
    if time_limit1 and time_limit1 <= time:
      capture_log = True
    pair_event = None
    if event.endswith('Done'):
      pair_event = event[:-4]
    elif event.endswith('Timeout'):
      pair_event = event[:-7]
      if capture_log_on_error:
        capture_log = True
    if not pair_event:
      continue
    start_time = events.get(pair_event)
    if not start_time:
      print("No start event for " + event)
      continue
    time_spent = time - start_time
    timing_event_name = pair_event + "Duration"
    timing_events[timing_event_name] = time_spent
    time_limit2 = log_capture_conditions.get(timing_event_name)
    if time_limit2 and time_limit2 <= time_spent:
      capture_log = True

  if capture_log:
    now = datetime.now()
    log_file = ("shutdownlog-error-%s.txt") % (now.strftime("%Y-%m-%d-%H-%M-%S"))
    print("Shutdown error, capture log to %s" % (log_file))
    with open(log_file, 'w') as f:
      f.write('\n'.join(lines))
  return events, timing_events

def log_timeout(time_left, stop_events, events, timing_events):
  print("timeout waiting for event, continue", time_left)
  print(" remaininig events {}, event {} timing events {}".\
    format(stop_events, events, timing_events))

def collect_events(search_events, command, timings, stop_events, disable_timing_after_zygote):
  events = collections.OrderedDict()
  timing_events = {}

  data_available = stop_events is None
  zygote_pids = []
  start_time = time.time()
  zygote_found = False
  line = None
  print("remaining stop_events:", stop_events)
  init = True
  while True:
    if init:
      process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
      read_poll = select.poll()
      read_poll.register(process.stdout, select.POLLIN)
      init = False
    if len(stop_events) == 0:
      break
    time_left = start_time + max_wait_time - time.time()
    if time_left <= 0:
      log_timeout(time_left, stop_events, events, timing_events)
      break
    polled_events = read_poll.poll(time_left * 1000.0)
    # adb logcat subprocess is auto-terminated when the adb connection is lost.
    # Thus, check for the subprocess return code and reconnect to the device if
    # needed. Otherwise, the logcat events cannot be polled completely.
    if process.poll() is not None:
      print("adb might be disconnected?\nRetrying to connect.")
      run_adb_cmd('wait-for-device')
      print(" reconnected")
      init = True
      continue
    if len(polled_events) == 0:
      log_timeout(time_left, stop_events, events, timing_events)
      break
    for polled_event in polled_events:
      if polled_event[1] == select.POLLIN:
        line = process.stdout.readline().decode('utf-8', 'ignore')
      else:
        if polled_event[1] == select.POLLHUP:
          if len(stop_events) == 0:
            break;
        # adb connection lost
        print("poll error waiting for event, adb lost?")
        if time_left > 0:
          print("retry adb")
          run_adb_cmd('wait-for-device')
          print(" reconnected")
          init = True
          continue
        else:
          break
      if not data_available:
        print("Collecting data samples from '%s'. Please wait...\n" % command)
        data_available = True
      event = get_boot_event(line, search_events)
      if event:
        debug("event[{0}] captured: {1}".format(event, line))
        if event == "starting_zygote":
          events[event] = line
          zygote_found = True
        elif event.startswith("zygote"):
          handle_zygote_event(zygote_pids, events, event, line)
        else:
          new_event = update_name_if_already_exist(events, event)
          events[new_event] = line
        if event in stop_events:
          stop_events.remove(event)
          print("remaining stop_events:", stop_events)

      timing_event = get_boot_event(line, timings)
      if timing_event and (not disable_timing_after_zygote or not zygote_found):
        if timing_event not in timing_events:
          timing_events[timing_event] = []
        timing_events[timing_event].append(line)
        debug("timing_event[{0}] captured: {1}".format(timing_event, line))

  process.terminate()
  return events, timing_events

def fetch_boottime_property():
  cmd = ADB_CMD + ' shell su root getprop'
  events = {}
  process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
  out = process.stdout
  pattern = re.compile(BOOT_PROP)
  pattern_bootloader = re.compile(BOOTLOADER_TIME_PROP)
  bootloader_time = 0.0
  for line in out:
    line = line.decode('utf-8', 'ignore')
    match = pattern.match(line)
    if match:
      if match.group(1).startswith("init."):
        events[match.group(1)] = float(match.group(2)) / 1000.0 #ms to s
      else:
        events[match.group(1)] = float(match.group(2)) / 1000000000.0 #ns to s
    match = pattern_bootloader.match(line)
    if match:
      items = match.group(1).split(",")
      for item in items:
        entry_pair = item.split(":")
        entry_name = entry_pair[0]
        time_spent = float(entry_pair[1]) / 1000 #ms to s
        if entry_name != "SW":
          bootloader_time = bootloader_time + time_spent
  ordered_event = collections.OrderedDict()
  if bootloader_time != 0.0:
    ordered_event["bootloader"] = bootloader_time
  for item in sorted(list(events.items()), key=operator.itemgetter(1)):
    ordered_event[item[0]] = item[1]
  return ordered_event


def get_boot_event(line, events):
  for event_key, event_pattern in events.items():
    if event_pattern.search(line):
      return event_key
  return None

def extract_a_time(line, pattern, date_transform_function):
    found = re.findall(pattern, line)
    if len(found) > 0:
      return date_transform_function(found[0])
    else:
      return None

def extract_time(events, pattern, date_transform_function):
  result = collections.OrderedDict()
  for event, data in events.items():
    time = extract_a_time(data, pattern, date_transform_function)
    if time is not None:
      result[event] = time
    else:
      print("Failed to find time for event: ", event, data)
  return result


def do_reboot(serial, use_adb_reboot):
  # do not update time
  run_adb_cmd('shell settings put global auto_time 0')
  run_adb_cmd('shell settings put global auto_time_zone 0')
  original_devices = subprocess.check_output("adb devices", shell=True).decode('utf-8', 'ignore')
  if use_adb_reboot:
    print('Rebooting the device using adb reboot')
    run_adb_cmd('reboot')
  else:
    print('Rebooting the device using svc power reboot')
    run_adb_shell_cmd_as_root('svc power reboot')
  # Wait for the device to go away
  retry = 0
  while retry < 20:
    current_devices = subprocess.check_output("adb devices", shell=True).decode('utf-8', 'ignore')
    if original_devices != current_devices:
      if not serial or (serial and current_devices.find(serial) < 0):
        return True
    time.sleep(1)
    retry += 1
  return False

def reboot(serial, use_stressfs, permissive, use_adb_reboot, adb_buffersize=None):
  if use_stressfs:
    print('Starting write to data partition')
    run_adb_shell_cmd('am start' +\
                      ' -n com.android.car.test.stressfs/.WritingActivity' +\
                      ' -a com.android.car.test.stressfs.START')
    # Give this app some time to start.
    time.sleep(1)
  if permissive:
    run_adb_shell_cmd_as_root('setenforce 0')

  retry = 0
  while retry < 5:
    if do_reboot(serial, use_adb_reboot):
      break
    retry += 1

  print('Waiting the device')
  run_adb_cmd('wait-for-device')
  print(' found a device')

  if adb_buffersize is not None:
    # increase the buffer size
    if run_adb_cmd('logcat -G {}'.format(adb_buffersize)) != 0:
      debug('Fail to set logcat buffer size as {}'.format(adb_buffersize))

'''
Runs adb command. If do_return_result is true then output of command is
returned otherwise an empty string is returned.
'''
def run_adb_cmd(cmd, do_return_result=False):
  if do_return_result:
    return subprocess.check_output(ADB_CMD + ' ' + cmd, shell=True).decode('utf-8', 'ignore').strip()
  subprocess.call(ADB_CMD + ' ' + cmd, shell=True)
  return ""

def run_adb_shell_cmd(cmd, do_return_result=False):
  return run_adb_cmd('shell ' + cmd, do_return_result)

def run_adb_shell_cmd_as_root(cmd, do_return_result=False):
  return run_adb_shell_cmd('su root ' + cmd, do_return_result)

def logcat_time_func(offset_year):
  def f(date_str):
    ndate = datetime.datetime.strptime(str(offset_year) + '-' +
                                 date_str, '%Y-%m-%d %H:%M:%S.%f')
    return datetime_to_unix_time(ndate)
  return f

def datetime_to_unix_time(ndate):
  return time.mktime(ndate.timetuple()) + ndate.microsecond/1000000.0

def stddev(data):
  items_count = len(data)
  avg = sum(data) / items_count
  sq_diffs_sum = sum([(v - avg) ** 2 for v in data])
  variance = sq_diffs_sum / items_count
  return math.sqrt(variance)

def grab_bootchart(boot_chart_file_path):
  subprocess.run("$ANDROID_BUILD_TOP/system/core/init/grab-bootchart.sh", shell=True,
                 stdout=subprocess.DEVNULL)
  print("Saving boot chart as " + boot_chart_file_path + ".tgz")
  subprocess.call('cp /tmp/android-bootchart/bootchart.tgz ' + boot_chart_file_path + '.tgz', \
                  shell=True)
  subprocess.call('cp ./bootchart.png ' + boot_chart_file_path + '.png', shell=True)

def grab_systrace(systrace_file_path_prefix):
  trace_file = systrace_file_path_prefix + "_trace.txt"
  with open(trace_file, 'w') as f:
    f.write("TRACE:\n")
  run_adb_shell_cmd_as_root("cat /d/tracing/trace >> " + trace_file)
  html_file = systrace_file_path_prefix + ".html"
  subprocess.call("$ANDROID_BUILD_TOP/external/chromium-trace/systrace.py --from-file=" + trace_file + " -o " +\
                  html_file, shell=True)

def capture_build_info(out_dir, build_info_file_name):
  fingerprint = run_adb_shell_cmd('getprop ro.build.fingerprint', True)
  brand = run_adb_shell_cmd('getprop ro.product.brand', True)
  product = run_adb_shell_cmd('getprop ro.product.name', True)
  device = run_adb_shell_cmd('getprop ro.product.device', True)
  version_release = run_adb_shell_cmd('getprop ro.build.version.release', True)
  id = run_adb_shell_cmd('getprop ro.build.id', True)
  version_incremental = run_adb_shell_cmd('getprop ro.build.version.incremental', True)
  type = run_adb_shell_cmd('getprop ro.build.type', True)
  tags = run_adb_shell_cmd('getprop ro.build.tags', True)
  sdk = run_adb_shell_cmd('getprop ro.build.version.sdk', True)
  platform_minor = run_adb_shell_cmd('getprop ro.android.car.version.platform_minor', True)
  codename = run_adb_shell_cmd('getprop ro.build.version.codename', True)
  carwatchdog_collection_interval = run_adb_shell_cmd('getprop ro.carwatchdog.system_event_collection_interval', True)
  carwatchdog_post_event_duration = run_adb_shell_cmd('getprop ro.carwatchdog.post_system_event_duration', True)
  carwatchdog_top_n_category = run_adb_shell_cmd('getprop ro.carwatchdog.top_n_stats_per_category', True)
  carwatchdog_top_n_subcategory = run_adb_shell_cmd('getprop ro.carwatchdog.top_n_stats_per_subcategory', True)

  # TODO: Change file format to JSON to avoid custom parser
  build_info = []
  build_info.append('Build information: ')
  build_info.append('-' * 20)
  build_info.append('fingerprint: ' + fingerprint)
  build_info.append('brand: ' + brand)
  build_info.append('product: ' + product)
  build_info.append('device: ' + device)
  build_info.append('version.release: ' + version_release)
  build_info.append('id: ' + id)
  build_info.append('version.incremental: ' + version_incremental)
  build_info.append('type: ' + type)
  build_info.append('tags: ' + tags)
  build_info.append('sdk: ' + sdk)
  build_info.append('platform minor version: ' + platform_minor)
  build_info.append('codename: ' + codename)
  build_info.append('carwatchdog collection interval (s): ' + carwatchdog_collection_interval)
  build_info.append('carwatchdog post event duration (s): ' + carwatchdog_post_event_duration)
  build_info.append('carwatchdog top N packages: ' + carwatchdog_top_n_category)
  build_info.append('carwatchdog top N processes: ' + carwatchdog_top_n_subcategory)

  build_info_str = '\n'.join(build_info)

  with open(out_dir + '/' + build_info_file_name, 'w') as f:
    f.write(build_info_str)

def generate_proto(dump_file, build_info_file, out_proto_file):
  subprocess.run("{} -f {} -b {} -d {}".format(CARWATCHDOG_PARSER_CMD,
                                               dump_file,
                                               build_info_file,
                                               out_proto_file),
                  shell=True, stdout=subprocess.DEVNULL)

def grab_carwatchdog_bootstats(result_dir):
  carwatchdog_state = run_adb_shell_cmd_as_root('getprop init.svc.carwatchdogd', True)
  if carwatchdog_state != "running":
    print('carwatchdog (-d) flag set but CarWatchdog is not running on device')
    return
  elif not result_dir:
    print('carwatchdog needs the output directory to be specified.')
    return
  print("Capturing carwatchdog stats")
  build_info_file_name = "device_build_info.txt"
  capture_build_info(result_dir, build_info_file_name)

  # Capture CW dump and save dump to txt
  dump_file_name = result_dir + '/carwatchdog_dump.txt'
  subprocess.call(CARWATCHDOG_DUMP_COMMAND + " > " + dump_file_name, shell=True)

  # Generate proto from dump
  build_info_file_path = result_dir + '/' + build_info_file_name
  out_proto_file_path = result_dir + '/carwatchdog_perf_stats_out.pb'
  generate_proto(dump_file_name, build_info_file_path, out_proto_file_path)


if __name__ == '__main__':
  main()
