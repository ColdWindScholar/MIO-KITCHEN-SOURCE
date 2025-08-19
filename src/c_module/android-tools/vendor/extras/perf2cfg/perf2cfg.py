#!/usr/bin/env python3
# Copyright (C) 2020 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""This script annotates a CFG file with profiling information from simpleperf
record files.

Example:
    perf2cfg --cfg bench.cfg --perf-data perf.data
"""

import argparse
import logging
import os
import sys
import textwrap

from perf2cfg import analyze
from perf2cfg import edit


def parse_arguments() -> argparse.Namespace:
    """Parses program arguments.

    Returns:
        argparse.Namespace: A populated argument namespace.
    """
    parser = argparse.ArgumentParser(
        # Hardcode the usage string as argparse does not display long options
        # if short ones are specified
        usage=textwrap.dedent("""\
        perf2cfg [-h|--help] --cfg CFG --perf-data PERF_DATA [PERF_DATA ...]
                        [--output-file OUTPUT_FILE] [-e|--events EVENTS]
                        [--primary-event PRIMARY_EVENT]"""),
        description='Annotates a CFG file with profiling information from '
        'simpleperf data files.',
        add_help=False)
    required = parser.add_argument_group('required arguments')
    required.add_argument('--cfg',
                          required=True,
                          help='The CFG file to annotate.')
    required.add_argument(
        '--perf-data',
        nargs='+',
        required=True,
        help='The perf data files to extract information from.')
    parser.add_argument('-h',
                        '--help',
                        action='help',
                        default=argparse.SUPPRESS,
                        help='Show this help message and exit.')
    parser.add_argument('--output-file', help='A path to the output CFG file.')
    parser.add_argument(
        '-e',
        '--events',
        type=lambda events: events.split(',') if events else [],
        help='A comma-separated list of events only to use for annotating a '
        'CFG (default: use all events found in perf data). An error is '
        'reported if the events are not present in perf data.')
    parser.add_argument(
        '--primary-event',
        default='cpu-cycles',
        help='The event to be used for basic blocks hotness analysis '
        '(default: %(default)s). Basic blocks are color highlighted according '
        'to their hotness. An error is reported if the primary event is not '
        'present in perf data.')
    args = parser.parse_args()

    if not args.output_file:
        root, ext = os.path.splitext(args.cfg)
        args.output_file = f'{root}-annotated{ext}'

    return args


def analyze_record_files(args: argparse.Namespace) -> analyze.RecordAnalyzer:
    """Analyzes simpleperf record files.

    Args:
        args (argparse.Namespace): An argument namespace.

    Returns:
        analyze.RecordAnalyzer: A RecordAnalyzer object.
    """
    analyzer = analyze.RecordAnalyzer(args.events)
    for record_file in args.perf_data:
        analyzer.analyze(record_file)

    return analyzer


def validate_events(analyzer: analyze.RecordAnalyzer,
                    args: argparse.Namespace) -> None:
    """Validates event names given on the command line.

    Args:
        analyzer (analyze.RecordAnalyzer): A RecordAnalyzer object.
        args (argparse.Namespace): An argument namespace.
    """
    if not analyzer.event_counts:
        logging.error('The selected events are not present in perf data')
        sys.exit(1)

    if args.primary_event not in analyzer.event_counts:
        logging.error(
            'The selected primary event %s is not present in perf data',
            args.primary_event)
        sys.exit(1)


def annotate_cfg_file(analyzer: analyze.RecordAnalyzer,
                      args: argparse.Namespace) -> None:
    """Annotates a CFG file.

    Args:
        analyzer (analyze.RecordAnalyzer): A RecordAnalyzer object.
        args (argparse.Namespace): An argument namespace.
    """
    input_stream = open(args.cfg, 'r')
    output_stream = open(args.output_file, 'w')

    editor = edit.CfgEditor(analyzer, input_stream, output_stream,
                            args.primary_event)
    editor.edit()

    input_stream.close()
    output_stream.close()


def main() -> None:
    """Annotates a CFG file with information from simpleperf record files."""
    args = parse_arguments()
    analyzer = analyze_record_files(args)
    validate_events(analyzer, args)
    annotate_cfg_file(analyzer, args)


if __name__ == '__main__':
    main()
