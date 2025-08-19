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
"""Functions to build and parse directives from CFG files."""

import re

from typing import Iterable, List

from perf2cfg import exceptions


def build_flags(flags: Iterable[str]) -> str:
    """Builds a flags directive from a list of arguments.

    Args:
        flags (Iterable[str]): An iterable of flags.

    Returns:
        str: A flags directive with the given arguments.

    Examples:
        >>> parse_flags(['catch_block', 'critical'])
        '    flags "catch_block" "critical"'
    """
    if not flags:
        return '    flags'

    args = ' '.join(f'"{flag}"' for flag in flags)
    return f'    flags {args}'


def build_name(name: str) -> str:
    """Builds a name directive from an argument.

    Args:
        name (str): An argument.

    Returns:
        str: A name directive with the given argument.
    """
    return f'  name "{name}"'


def parse_address(line: str) -> int:
    """Parses an address from a line.

    Args:
        line (str): A line to parse an address from.

    Returns:
        int: An instruction address.

    Raises:
        exceptions.ParseError: An error occurred during parsing.

    Examples:
        >>> parse_address('0x0000001c: d503201f nop')
        28
    """
    parts = line.split(':', 1)
    addr = parts[0]

    try:
        return int(addr, 16)
    except ValueError:
        raise exceptions.ParseError('Expected an address')


def parse_flags(line: str) -> List[str]:
    """Parses a flags directive from a line.

    Args:
        line (str): A line to parse a flags directive from.

    Returns:
        List[str]: A list of unquoted arguments from a flags directive, or an
            empty list if no arguments were found.

    Raises:
        exceptions.ParseError: An error occurred during parsing.

    Example:
        >>> parse_flags('flags "catch_block" "critical"')
        ['catch_block', 'critical']
    """
    parts = line.split(None, 1)
    if parts[0] != 'flags':
        raise exceptions.ParseError('Expected a `flags` directive')

    if len(parts) < 2:
        return []

    return re.findall(r'\"([^\"]+)\"', parts[1])


def parse_name(line: str) -> str:
    """Parses a name directive from a line.

    Args:
        line (str): A line to parse a name directive from.

    Returns:
        str: The unquoted argument of a name directive.

    Raises:
        exceptions.ParseError: An error occurred during parsing.

    Examples:
        >>> parse_name('name "disassembly (after)"')
        'disassembly (after)'
    """
    parts = line.split(None, 1)
    if parts[0] != 'name':
        raise exceptions.ParseError('Expected a `name` directive')

    if len(parts) < 2:
        raise exceptions.ParseError(
            'Expected an argument to the `name` directive')

    return parts[1].strip('"')
