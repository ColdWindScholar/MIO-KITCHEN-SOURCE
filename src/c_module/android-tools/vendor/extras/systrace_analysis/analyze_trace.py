#!/usr/bin/env python
#
# Copyright (C) 2015 The Android Open Source Project
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
import os
import subprocess
import sys

def main():
    # Create argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument('systrace_file', metavar='SYSTRACE_FILE', help='systrace file to analyze')
    parser.add_argument('-e', metavar='EVENT_LOG', help='android event log file')
    args = parser.parse_args()

    this_script_path = os.path.dirname(os.path.realpath(__file__))

    # Find chromium-trace directory and vinn binary as offset from this script
    chromium_trace_path = os.path.normpath(this_script_path + '/../../../external/chromium-trace')
    if not os.path.exists(chromium_trace_path):
        sys.exit('Can\'t find chromium-trace in your source tree')

    vinn_path = chromium_trace_path + '/catapult/third_party/vinn/'
    if not os.path.exists(vinn_path):
        sys.exit('Can\'t find vinn in your source tree')

    sys.path.append(vinn_path)
    import vinn

    # Find source paths and construct vinn launch arguments
    tracing_path = chromium_trace_path + '/catapult/tracing/'
    gldist_path = chromium_trace_path + '/catapult/tracing/third_party/gl-matrix/dist/'
    source_paths_arg = [tracing_path, gldist_path]
    js_args_arg = [args.systrace_file]
    if args.e is not None:
        js_args_arg += [args.e]
    res = vinn.RunFile(this_script_path + '/analysis.html', source_paths=source_paths_arg,
            js_args=js_args_arg, stdout=sys.stdout, stdin=sys.stdin);
    return res.returncode

if __name__ == '__main__':
    main()
