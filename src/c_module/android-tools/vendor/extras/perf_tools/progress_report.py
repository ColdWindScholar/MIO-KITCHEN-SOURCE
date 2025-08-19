#!/usr/bin/env python3
#
# Copyright (C) 2023 The Android Open Source Project
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

import argparse
from datetime import datetime
import yaml
import os
import report_pb2
import sys
import traceback

# Usage: python3 progress_report.py --logcat logcat.txt --config config.yaml --output_dir report_dir
#
# logcat.txt should contain the "boot_progress_start" and "boot_progress_enable_screen"".
# config.yaml contains all the keywords to be extracted.
# report_dir will contain three generated files:
#
# timestamp_log.txt: contains the same content as logcat.txt, but the timestamp is replaced
# with relative time with boot_progress_start time.
#
# report_proto.txt: contains the report for the events related to the keywords.
#
# report.txt: contains logcat messages corresponding to the events captured in report_proto.txt

def init_arguments():
    parser = argparse.ArgumentParser(
        prog = 'progrocess_report.py',
        description='Extract timing information and generate a report.')
    parser.add_argument(
        '--logcat', type=str, required=True,
        help = 'logcat file name')
    parser.add_argument(
        '--config', type=str, required=True,
        help = 'configuration file for keywords')
    parser.add_argument(
        '--output_dir', type= str, required=True,
        help = 'directory name to store the generated files')
    return parser.parse_args()

# Find boot_progress_start line and boot_progress_enable_screen find the time difference
# return the start time string
def find_boot_progress_start_end(fp):
    start = ""
    end = ""
    for line in fp:
        if "boot_progress_start" in line:
            start = line
        if "boot_progress_enable_screen" in line and len(start):
            end = line
            break

    missing_error = ""
    if start == "":
        missing_error = "******logcat file missing boot_progress_start\n"
    elif end == "":
        missing_error +=  "******logcat file missing boot_progress_end "
    if missing_error != "":
        sys.exit("Missing required message in the logcat:\n" + missing_error)
    return [start, end]

# TODO(b/262259622): passing a tuple of (startDate, endDate)
def replace_timestamp_abs(line, timestamp_str, date_time_obj0):
    index = line.find(" ", 6)
    if index <= 0:
        return line
    substr0 = line[:index]
    substr1 = line[index:]

    try:
        date_time_obj = datetime.strptime(substr0, '%m-%d %H:%M:%S.%f')
    except ValueError:
        return line

    date_time_delta = date_time_obj - date_time_obj0
    date_time_delta_str = str(date_time_delta)
    return date_time_delta_str + substr1

def in_time_range(start, end, line):
    try:
        current_time = datetime.strptime(line[:18], '%m-%d %H:%M:%S.%f')
    except ValueError:
        return False

    if current_time >= start and current_time <= end:
        return True

    return False

# Here is an example of event we would like extract:
# 09-15 16:04:15.655  root   991   991 I boot_progress_preload_start: 5440
# for each event, it is a tuple of(timestamp, event_name, timing)
def extract_event(line, keywords):
    words = line.split(" ")
    for keyword in keywords:
        if keyword in words[-2]:
            return (words[0], words[-2], words[-1])
    return ()

def write_to_new_file(timestamps, keywords, logcat_fp, timestamp_fixed_logcat_fp, report_fp,
                      report_proto_fp):
    start_timestamp_obj = datetime.strptime(timestamps[0][:18], '%m-%d %H:%M:%S.%f')
    end_timestamp_obj = datetime.strptime(timestamps[1][:18], '%m-%d %H:%M:%S.%f')
    report = report_pb2.Report()
    for line in logcat_fp:
        ts_fixed_line = replace_timestamp_abs(line, timestamps[0][:18], start_timestamp_obj)
        timestamp_fixed_logcat_fp.write(ts_fixed_line)
        if in_time_range(start_timestamp_obj, end_timestamp_obj, line):
            event = extract_event(ts_fixed_line, keywords)
            if len(event) == 0:
                continue

            report_fp.write(ts_fixed_line)
            record = report.record.add()
            record.timestamp = event[0]
            record.event = event[1]
            record.timing = int(event[2])
    report_proto_fp.write(str(report))

def main():
    args = init_arguments()

    keywords = []
    with open(args.config, 'r') as file:
        keywords = yaml.safe_load(file)

    if not os.path.isdir(args.output_dir):
        os.mkdir(args.output_dir)
    timestamp_fixed_logcat_fp = open(os.path.join(args.output_dir, "timestamp_fixed_log.txt"), 'w')
    report_fp = open(os.path.join(args.output_dir, "report.txt"), 'w')
    report_proto_fp = open(os.path.join(args.output_dir,  "report_proto.txt"), 'w')
    try:
        with open(args.logcat, 'r', errors = 'ignore') as logcat_fp:
            timestamps = find_boot_progress_start_end(logcat_fp)
            logcat_fp.seek(0)
            write_to_new_file(timestamps, keywords, logcat_fp, timestamp_fixed_logcat_fp, report_fp, report_proto_fp)
    except Exception as e:
        traceresult = traceback.format_exc()
        print("Caught an exception: {}".format(traceback.format_exc()))

    timestamp_fixed_logcat_fp.close()
    report_fp.close()
    report_proto_fp.close()

if __name__ == '__main__':
    main()
