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
"""Classes for annotating a CFG file with profiling information.

Attributes:
    END_INSTRUCTION_MARKER (str): The marker used to indicate the end of a HIR
        instruction.
    EOF_MARKER (str): The marker used to indicate that the end-of-file has been
        reached.
"""

import collections
import enum
import logging
import os
import re

from typing import DefaultDict, Iterator, List, TextIO, Tuple

from perf2cfg import analyze
from perf2cfg import events
from perf2cfg import exceptions
from perf2cfg import parse

END_INSTRUCTION_MARKER = '<|@'
EOF_MARKER = '<EOF>'


class State(enum.Enum):
    """State represents the internal state of a CfgEditor object."""
    START = 1
    PARSE_METHOD_NAME = 2
    SKIP_METHOD = 3
    SKIP_TO_CFG = 4
    START_CFG = 5
    IS_DISASSEMBLY_PASS = 6
    SKIP_PASS = 7
    PARSE_FLAGS = 8
    SKIP_TO_HIR = 9
    HIR_INSTRUCTION = 10
    DISASSEMBLY = 11
    END_HIR = 12
    END_BLOCK = 13
    END_CFG = 14
    END = 15


class CfgEditor:
    """CfgEditor annotates a CFG file with profiling information.

    CfgEditor does *not* edit the input CFG file in place. Instead, it reads
    the input file line by line, generates annotations from profiling
    information, and writes an annotated CFG file to a given path.

    CfgEditor includes a CFG file parser based on a finite state machine. This
    parser supports CFG files in the c1visualizer format dumped by the ART
    optimizing compiler:
        - The CFG file must be valid (correctly parsed by c1visualizer).
        - Each line must contain only one directive.
        - Disassembly of an IR instruction must end with the `<|@` marker on a
          newline.

    Attributes:
        analyzer (analyzer.RecordAnalyzer): A RecordAnalyzer object.
        input_stream (TextIO): An input CFG text stream.
        output_stream (TextIO): An output CFG text stream.
        primary_event (str): An event used to color basic blocks.
        basic_block_event_counts (DefaultDict[str, int]): A mapping of event
            names to their total number of events for the current basic block.
        buffer (List[str]): A list of strings to be written to the output CFG
            file instead of the current line from the input CFG file.
        current_method (analyze.Method): A Method object representing the
            current method being annotated.
        event_names (List[str]): A list of sorted event names from the
            analysis.
        flags_offset (int): An output file offset pointing to the last flags
            directive seen.
        isa (str): The instruction set architecture as defined in the input CFG
            file metadata, or the string "unknown" if no metadata was found.
        padding (str): A string used to pad assembly instructions with no
            profiling information.
        saved_flags (List[str]): A list of strings representing the flags of
            the current basic block being parsed.
        state (State): A State value representing the internal state of the
            parser.
    """

    def __init__(self,
                 analyzer: analyze.RecordAnalyzer,
                 input_stream: TextIO,
                 output_stream: TextIO,
                 primary_event: str = 'cpu-cycles') -> None:
        """Instantiates a CfgEditor.

        Args:
            analyzer (analyze.RecordAnalyzer): A RecordAnalyzer object. An
                analysis must have been completed before passing this object to
                CfgEditor.
            input_stream (TextIO): An input CFG text stream.
            output_stream (TextIO): An output CFG text stream.
            primary_event (str): An event used to color basic blocks.
        """
        self.analyzer = analyzer
        self.input_stream = input_stream
        self.output_stream = output_stream
        self.primary_event = primary_event

        self.basic_block_event_counts: DefaultDict[
            str, int] = collections.defaultdict(int)
        self.buffer: List[str] = []
        self.current_method: analyze.Method
        self.event_names = events.sort_event_names(self.analyzer.event_counts)
        self.flags_offset = 0
        self.isa = ''
        self.padding = ''
        self.saved_flags: List[str] = []
        self.state = State.START

    def edit(self) -> None:
        """Annotates a CFG file with profiling information."""
        for lineno, raw_line in self.lines():
            line = raw_line.strip()
            try:
                self.parse_line(line)
            except exceptions.ArchitectureError as ex:
                logging.error(ex)
                return
            except exceptions.ParseError as ex:
                logging.error('Line %d: %s', lineno, ex)
                return

            if self.buffer:
                self.output_stream.write(''.join(self.buffer))
                self.buffer = []
            else:
                self.output_stream.write(raw_line)

        self.parse_line(EOF_MARKER)
        if self.state != State.END:
            logging.error('Unexpected end-of-file while parsing the CFG file')

    def lines(self) -> Iterator[Tuple[int, str]]:
        """Iterates over lines from the input CFG stream.

        Yields:
            Tuple[int, str]: A line number and a non-empty line.
        """
        for lineno, line in enumerate(self.input_stream, 1):
            if line:
                yield lineno, line

    def parse_line(self, line: str) -> None:
        """Parses a line from the input CFG file.

        Args:
            line (str): A line to parse.

        Raises:
            exceptions.ParseError: An error occurred during parsing.
        """
        if self.state == State.START:
            if line == EOF_MARKER:
                self.state = State.END
            elif line == 'begin_compilation':
                self.state = State.PARSE_METHOD_NAME
            else:
                raise exceptions.ParseError(
                    'Expected a `begin_compilation` directive')

        elif self.state == State.PARSE_METHOD_NAME:
            method_name = parse.parse_name(line)
            if not self.isa:
                self.set_isa(method_name)

            if method_name in self.analyzer.methods:
                self.update_current_method(method_name)
                self.state = State.SKIP_TO_CFG
            else:
                # If no profiling information has been recorded for this
                # method, skip it
                self.state = State.SKIP_METHOD

        elif self.state == State.SKIP_METHOD:
            if line == EOF_MARKER:
                self.state = State.END
            elif line == 'begin_compilation':
                self.state = State.PARSE_METHOD_NAME

        elif self.state == State.SKIP_TO_CFG:
            if line == 'end_compilation':
                self.state = State.START_CFG

        elif self.state == State.START_CFG:
            if line == 'begin_cfg':
                self.state = State.IS_DISASSEMBLY_PASS
            else:
                raise exceptions.ParseError('Expected a `begin_cfg` directive')

        elif self.state == State.IS_DISASSEMBLY_PASS:
            pass_name = parse.parse_name(line)
            if pass_name == 'disassembly (after)':
                self.state = State.PARSE_FLAGS
            else:
                self.state = State.SKIP_PASS

        elif self.state == State.SKIP_PASS:
            if line == 'end_cfg':
                self.state = State.END_CFG

        elif self.state == State.PARSE_FLAGS:
            if line.startswith('flags'):
                self.update_saved_flags(line)
                self.state = State.SKIP_TO_HIR

        elif self.state == State.SKIP_TO_HIR:
            if line == 'begin_HIR':
                self.state = State.HIR_INSTRUCTION

        elif self.state == State.HIR_INSTRUCTION:
            if line.endswith(END_INSTRUCTION_MARKER):
                # If no disassembly is available for this HIR instruction, skip
                # it
                pass
            elif line == 'end_HIR':
                self.state = State.END_HIR
            else:
                self.state = State.DISASSEMBLY

        elif self.state == State.DISASSEMBLY:
            if line == END_INSTRUCTION_MARKER:
                self.state = State.HIR_INSTRUCTION
            else:
                self.annotate_instruction(line)

        elif self.state == State.END_HIR:
            if line == 'end_block':
                self.annotate_block()
                self.state = State.END_BLOCK
            else:
                raise exceptions.ParseError('Expected a `end_block` directive')

        elif self.state == State.END_BLOCK:
            if line == 'begin_block':
                self.state = State.PARSE_FLAGS
            elif line == 'end_cfg':
                logging.info('Annotated %s', self.current_method.name)
                self.state = State.END_CFG
            else:
                raise exceptions.ParseError(
                    'Expected a `begin_block` or `end_cfg` directive')

        elif self.state == State.END_CFG:
            if line == EOF_MARKER:
                self.state = State.END
            elif line == 'begin_cfg':
                self.state = State.IS_DISASSEMBLY_PASS
            elif line == 'begin_compilation':
                self.state = State.PARSE_METHOD_NAME

    def set_isa(self, metadata: str) -> None:
        """Sets the instruction set architecture.

        Args:
            metadata (str): The input CFG file metadata.

        Raises:
            exceptions.ArchitectureError: An error occurred when the input CFG
                file ISA is incompatible with the target architecture.
        """
        match = re.search(r'isa:(\w+)', metadata)
        if not match:
            logging.warning(
                'Could not deduce the CFG file ISA, assuming it is compatible '
                'with the target architecture %s', self.analyzer.target_arch)
            self.isa = 'unknown'
            return

        self.isa = match.group(1)

        # Map CFG file ISAs to compatible target architectures
        target_archs = {
            'x86': [r'x86$', r'x86_64$'],
            'x86_64': [r'x86_64$'],
            'arm': [r'armv7', r'armv8'],
            'arm64': [r'aarch64$', r'armv8'],
        }

        if not any(
                re.match(target_arch, self.analyzer.target_arch)
                for target_arch in target_archs[self.isa]):
            raise exceptions.ArchitectureError(
                f'The CFG file ISA {self.isa} is incompatible with the target '
                f'architecture {self.analyzer.target_arch}')

    def update_current_method(self, method_name: str) -> None:
        """Updates the current method and the padding string.

        Args:
            method_name (str): The name of a method being annotated.
        """
        self.current_method = self.analyzer.methods[method_name]

        annotations = []
        for event_name in self.event_names:
            event_count = self.current_method.event_counts[event_name]
            annotation = self.generate_method_annotation(
                event_name, event_count)
            annotations.append(annotation)

        info = ', '.join(annotations)
        # By default, c1visualizer displays short method names which are built
        # by finding the first open parenthesis. To keep that behavior intact,
        # the profiling information is enclosed in square brackets.
        directive = parse.build_name(f'[{info}] {method_name}')
        self.buffer.append(f'{directive}\n')

        max_length = 0
        for event_name in self.event_names:
            max_event_count = max(
                instruction.event_counts[event_name]
                for instruction in self.current_method.instructions.values())
            annotation = self.generate_instruction_annotation(
                event_name, max_event_count)

            if len(annotation) > max_length:
                max_length = len(annotation)

        self.padding = '_' + ' ' * max_length

    def update_saved_flags(self, line: str) -> None:
        """Updates the saved flags and saves space for a block annotation.

        Args:
            line (str): A line containing a flags directive.
        """
        self.saved_flags = parse.parse_flags(line)
        self.flags_offset = self.output_stream.tell()

        flags = self.saved_flags.copy()
        for event_name in self.event_names:
            # The current method could have only one basic block, making the
            # maximum block event counts equal to the method ones
            event_count = self.current_method.event_counts[event_name]
            annotation = self.generate_block_annotation(event_name, event_count)
            flags.append(annotation)

        # Save space for a possible performance flag
        flags.append('LO')

        padding = ' ' * len(parse.build_flags(flags))
        self.buffer.append(f'{padding}\n')

    def annotate_block(self) -> None:
        """Annotates a basic block."""
        flags = []
        for event_name in self.event_names:
            event_count = self.basic_block_event_counts[event_name]
            annotation = self.generate_block_annotation(event_name, event_count)
            flags.append(annotation)

        flag = self.generate_performance_flag()
        if flag:
            flags.append(flag)

        flags.extend(self.saved_flags)

        self.basic_block_event_counts.clear()

        self.output_stream.seek(self.flags_offset)
        self.output_stream.write(parse.build_flags(flags))
        self.output_stream.seek(0, os.SEEK_END)

    def annotate_instruction(self, line: str) -> None:
        """Annotates an instruction.

        Args:
            line (str): A line containing an instruction to annotate.
        """
        addr = parse.parse_address(line)

        instruction = self.current_method.instructions.get(addr)
        if not instruction:
            # If no profiling information has been recorded for this
            # instruction, skip it
            self.buffer.append(f'{self.padding}{line}\n')
            return

        for eventno, event_name in enumerate(self.event_names):
            event_count = instruction.event_counts[event_name]
            self.basic_block_event_counts[event_name] += event_count
            annotation = self.generate_padded_instruction_annotation(
                event_name, event_count)

            if eventno:
                self.buffer.append(f'{annotation}\n')
            else:
                self.buffer.append(f'{annotation} {line}\n')

    def generate_performance_flag(self) -> str:
        """Generates a performance flag for the current basic block.

        For example, a `LO` (low) flag indicates the block is responsible for 1
        to 10% of the current method primary event (cpu-cycles by default).

        Returns:
            str: A performance flag, or an empty string if the block
                contribution is not high enough.
        """
        ranges = [
            # Low
            (1, 10, 'LO'),
            # Moderate
            (10, 30, 'MO'),
            # Considerable
            (30, 50, 'CO'),
            # High
            (50, 101, 'HI'),
        ]

        ratio = 0
        method_event_count = self.current_method.event_counts[
            self.primary_event]
        if method_event_count:
            ratio = int(self.basic_block_event_counts[self.primary_event] /
                        method_event_count * 100)

        for start, end, name in ranges:
            if start <= ratio < end:
                return name

        return ''

    def generate_padded_instruction_annotation(self, event_name: str,
                                               event_count: int) -> str:
        """Generates a padded instruction annotation.

        Args:
            event_name (str): An event name.
            event_count (int): An event count.

        Returns:
            str: A padded instruction annotation.
        """
        annotation = self.generate_instruction_annotation(
            event_name, event_count)

        # Remove one from the final length as a space may be added at the end
        # of the annotation. The final length will always be positive as the
        # length of the current padding is one more than the length of the
        # longest annotation for the current method.
        padding = ' ' * (len(self.padding) - len(annotation) - 1)
        parts = annotation.split(':')

        return f'{parts[0]}:{padding}{parts[1]}'

    def generate_method_annotation(self, event_name: str,
                                   event_count: int) -> str:
        """Generates a method annotation.

        Method annotations are relative to the whole analysis and exclude the
        event count.

        Args:
            event_name (str): An event name.
            event_count (int): An event count.

        Returns:
            str: A method annotation.
        """
        total_event_count = self.analyzer.event_counts[event_name]
        return self.generate_annotation(event_name,
                                        event_count,
                                        total_event_count,
                                        include_count=False)

    def generate_block_annotation(self, event_name: str,
                                  event_count: int) -> str:
        """Generates a basic block annotation.

        Basic block annotations are relative to the current method and exclude
        the event count.

        Args:
            event_name (str): An event name.
            event_count (int): An event count.

        Returns:
            str: A basic block annotation.
        """
        total_event_count = self.current_method.event_counts[event_name]
        return self.generate_annotation(event_name,
                                        event_count,
                                        total_event_count,
                                        include_count=False)

    def generate_instruction_annotation(self, event_name: str,
                                        event_count: int) -> str:
        """Generates an instruction annotation.

        Instruction annotations are relative to the current method and include
        the event count.

        Args:
            event_name (str): An event name.
            event_count (int): An event count.

        Returns:
            str: An instruction annotation.
        """
        total_event_count = self.current_method.event_counts[event_name]
        return self.generate_annotation(event_name,
                                        event_count,
                                        total_event_count,
                                        include_count=True)

    # pylint: disable=no-self-use
    def generate_annotation(self, event_name: str, event_count: int,
                            total_event_count: int, include_count: bool) -> str:
        """Generates an annotation.

        Args:
            event_name (str): An event name.
            event_count (int): An event count.
            total_event_count (int): A total event count.
            include_count (bool): If True, includes the event count alongside
                the event name and ratio.

        Returns:
            str: An annotation.
        """
        ratio = 0.0
        if total_event_count:
            ratio = event_count / total_event_count

        if include_count:
            return f'{event_name}: {event_count} ({ratio:.2%})'

        return f'{event_name}: {ratio:06.2%}'
