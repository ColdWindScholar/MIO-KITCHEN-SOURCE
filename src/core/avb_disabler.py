#!/usr/bin/env python3
# Copyright (C) 2022-2025 The MIO-KITCHEN-SOURCE Project
#
# Licensed under the GNU AFFERO GENERAL PUBLIC LICENSE, Version 3.0

"""
This module is responsible for removing Android Verified Boot (AVB) flags
from fstab (file system table) files. This is a common operation in
custom ROM development to disable verity checks, allowing modified system
partitions to boot.
"""

import os
import re
import logging
from src.core.utils import lang # Assuming 'lang' is a module for localized strings

# Set up a logger for this module
logger = logging.getLogger(__name__)

# --- AVB Flag Definitions ---
# These constants define the specific AVB-related flags to be removed.

# Flags that are identified by a prefix, e.g., "avb=..." or "avb_keys=..."
AVB_FLAGS_TO_REMOVE_BY_PREFIX: tuple[str, ...] = ('avb=', 'avb_keys=')

# Flags that must be an exact match, e.g., "avb" or "verify".
AVB_FLAGS_TO_REMOVE_EXACT: set[str] = {'avb', 'verify'}


def clean_avb_flags(options_part: str) -> tuple[str, bool]:
    """
    Safely removes AVB flags from a fstab options string while preserving formatting.

    This function intelligently handles commas and whitespace to ensure the resulting
    options string is valid. If all options are removed, it returns 'defaults'.

    Args:
        options_part: The string containing mount options from an fstab line.
                      Example: "rw,nosuid,nodev,verify,avb=vbmeta,wait"

    Returns:
        A tuple containing:
        - The cleaned options string.
        - A boolean indicating whether the string was modified.
    """
    modified_options = options_part
    was_modified = False

    # Remove flags based on their prefix (e.g., "avb=vbmeta")
    for prefix in AVB_FLAGS_TO_REMOVE_BY_PREFIX:
        # Regex explanation:
        # (?i)          - Case-insensitive match.
        # (,\s*|\s+)    - Match a preceding comma with optional whitespace, or just whitespace.
        # {re.escape(prefix)} - The literal prefix, escaped for regex.
        # [^\s,]*      - Match any characters that are not whitespace or a comma.
        pattern = rf'(?i)(,\s*|\s+){re.escape(prefix)}[^\s,]*'
        if re.search(pattern, modified_options):
            was_modified = True
            modified_options = re.sub(pattern, '', modified_options)

    # Remove flags based on an exact word match (e.g., "verify")
    for flag in AVB_FLAGS_TO_REMOVE_EXACT:
        # Regex explanation:
        # (?i)          - Case-insensitive match.
        # (,\s*|\s+)    - Match a preceding comma with optional whitespace, or just whitespace.
        # \b{re.escape(flag)}\b - The exact flag, bounded by word boundaries.
        pattern = rf'(?i)(,\s*|\s+)\b{re.escape(flag)}\b'
        if re.search(pattern, modified_options):
            was_modified = True
            modified_options = re.sub(pattern, '', modified_options)

    if was_modified:
        # Clean up any leading comma that might result from removing the first option.
        modified_options = re.sub(r'^\s*,\s*', '', modified_options)
        
        # If all options were removed, the field cannot be empty.
        # 'defaults' is a safe and standard fallback.
        if not modified_options.strip():
            return 'defaults', True

    return modified_options, was_modified


def process_fstab(fstab_path: str) -> bool:
    """
    Reads an fstab file, removes all AVB-related flags, and overwrites the file.

    This function handles file I/O, character encoding detection (UTF-8 with a
    fallback to latin-1), and line-by-line processing. It only writes to the file
    if modifications were actually made.

    Args:
        fstab_path: The absolute path to the fstab file to process.

    Returns:
        True if the file was processed successfully (or if no changes were needed),
        False if an error occurred (e.g., file not found, permission error).
    """
    if not os.path.isfile(fstab_path):
        # Use getattr for safe access to localized strings, with a fallback.
        msg = getattr(lang, 'file_not_found', 'File not found')
        print(f"[AVB Disabler] {msg}: {fstab_path}")
        return False

    try:
        # Read the file in binary mode to handle encoding manually.
        with open(fstab_path, 'rb') as f:
            raw_content = f.read()

        # Attempt to decode as UTF-8, which is standard.
        # Fallback to latin-1 if it fails, as it can decode any byte sequence.
        try:
            content = raw_content.decode('utf-8')
            encoding = 'utf-8'
        except UnicodeDecodeError:
            content = raw_content.decode('latin-1')
            encoding = 'latin-1'
            msg = getattr(lang, 'encoding_warning', 
                          "Warning: File '{file}' is not UTF-8. Using {encoding}.")
            print(f"[AVB Disabler] {msg.format(file=os.path.basename(fstab_path), encoding=encoding)}")

        original_lines = content.splitlines()
        modified_lines = []
        file_was_modified = False

        # Regex to parse a standard fstab line into two main parts:
        # 1. 'fields': The first three columns (device, mount point, fs_type).
        # 2. 'options': The fourth column and everything after it.
        fstab_line_pattern = re.compile(
            r'^(?P<fields>\S+\s+\S+\s+\S+)\s+(?P<options>.*)$'
        )

        for line in original_lines:
            stripped_line = line.strip()
            # Ignore empty lines and comments.
            if not stripped_line or stripped_line.startswith('#'):
                modified_lines.append(line)
                continue

            match = fstab_line_pattern.match(stripped_line)
            
            # If the line doesn't match the standard fstab format, keep it as is.
            if not match:
                modified_lines.append(line)
                continue

            fields_part = match.group('fields')
            options_part = match.group('options')

            # Process the options string to remove AVB flags.
            new_options, was_line_modified = clean_avb_flags(options_part)

            if was_line_modified:
                file_was_modified = True
                # Reconstruct the modified line.
                modified_line = f"{fields_part} {new_options}"
                modified_lines.append(modified_line)
            else:
                # If no changes were made to this line, add the original line back.
                modified_lines.append(line)

        base_name = os.path.basename(fstab_path)
        if file_was_modified:
            msg = getattr(lang, 'avb_flags_removed', "AVB flags removed in {file}.")
            print(f"[AVB Disabler] {msg.format(file=base_name)}")
            
            new_content = "\n".join(modified_lines)
            # Ensure the file ends with a newline, a common convention for text files.
            if not new_content.endswith('\n'):
                new_content += '\n'
            
            # Write the modified content back to the file using the original encoding.
            with open(fstab_path, 'wb') as f:
                f.write(new_content.encode(encoding))
        else:
            msg = getattr(lang, 'avb_flags_not_found', "No AVB flags found in {file}.")
            print(f"[AVB Disabler] {msg.format(file=base_name)}")
            
        return True

    except Exception as e:
        msg = getattr(lang, 'error_processing_file', "Error processing {file}: {error}")
        print(f"[AVB Disabler] {msg.format(file=fstab_path, error=e)}")
        # For debugging, print the full traceback of the exception.
        import traceback
        traceback.print_exc()
        return False