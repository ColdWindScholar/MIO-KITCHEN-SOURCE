#!/usr/bin/env python3
# Copyright (C) 2022-2025 The MIO-KITCHEN-SOURCE Project
#
# Licensed under the GNU AFFERO GENERAL PUBLIC LICENSE, Version 3.0

"""
This module is responsible for removing Android Verified Boot (AVB) flags
from fstab (file system table) files. This is a common operation in
custom ROM development to disable verity checks, allowing modified system
partitions to boot.

✅ Now correctly parses Android fstab format (5+ columns)
✅ Removes flags ONLY from fs_mgr_flags (5th column)
✅ Preserves original formatting, spacing, and comments
"""

import os
import re
import logging
import traceback
from src.core.utils import lang  # Assuming 'lang' is a module for localized strings

# Set up a logger for this module
logger = logging.getLogger(__name__)

# --- AVB Flag Definitions ---
# These constants define the specific AVB-related flags to be removed.

# Flags that are identified by a prefix, e.g., "avb=..." or "avb_keys=..."
AVB_FLAGS_TO_REMOVE_BY_PREFIX: tuple[str, ...] = (
    'avb=',
    'avb_keys=',

)

# Flags that must be an exact match, e.g., "avb" or "verify".
AVB_FLAGS_TO_REMOVE_EXACT: set[str] = {
    'avb',
    'verify',

}


def clean_avb_flags(options_part: str) -> tuple[str, bool]:
    """
    Safely removes AVB flags from a string while preserving formatting.

    Args:
        options_part: String like "wait,avb,verify,slotselect"

    Returns:
        Tuple: (cleaned_string, was_modified)
    """
    modified_options = options_part
    was_modified = False

    # Remove flags based on prefix
    for prefix in AVB_FLAGS_TO_REMOVE_BY_PREFIX:
        pattern = rf'(?i)(,\s*|\s+){re.escape(prefix)}[^\s,]*'
        if re.search(pattern, modified_options):
            was_modified = True
            modified_options = re.sub(pattern, '', modified_options)

    # Remove exact word flags
    for flag in AVB_FLAGS_TO_REMOVE_EXACT:
        pattern = rf'(?i)(,\s*|\s+)\b{re.escape(flag)}\b'
        if re.search(pattern, modified_options):
            was_modified = True
            modified_options = re.sub(pattern, '', modified_options)

    if was_modified:
        # Clean leading comma or space
        modified_options = re.sub(r'^\s*,\s*', '', modified_options)
        # If empty, use 'defaults' (though unlikely in fs_mgr_flags)
        if not modified_options.strip():
            return 'defaults', True

    return modified_options.strip(), was_modified


# Android fstab regex — captures 5 required fields, preserves formatting
ANDROID_FSTAB_PATTERN = re.compile(
    r'^(?P<device>\S+)'
    r'\s+(?P<mount_point>\S+)'
    r'\s+(?P<fs_type>\S+)'
    r'\s+(?P<mount_options>\S*)'
    r'\s+(?P<fs_mgr_flags>\S+)'
    r'(?:\s+#\s*(?P<comment>.*))?$',
    re.MULTILINE
)


def process_fstab(fstab_path: str) -> bool:
    """
    Reads an Android fstab file, removes AVB-related flags from fs_mgr_flags column,
    and overwrites the file — preserving original formatting.

    Args:
        fstab_path: Path to fstab file.

    Returns:
        True if processed successfully, False on error.
    """
    if not os.path.isfile(fstab_path):
        msg = getattr(lang, 'file_not_found', 'File not found')
        print(f"[AVB Disabler] {msg}: {fstab_path}")
        return False

    try:
        with open(fstab_path, 'rb') as f:
            raw_content = f.read()

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

        for line in original_lines:
            stripped_line = line.strip()
            # Preserve empty lines and comments as-is
            if not stripped_line or stripped_line.startswith('#'):
                modified_lines.append(line)
                continue

            # Match against original line (to preserve formatting)
            match = ANDROID_FSTAB_PATTERN.match(line)
            if not match:
                # Not a valid fstab line? Keep unchanged.
                modified_lines.append(line)
                continue

            # Extract fs_mgr_flags from match
            old_flags = match.group('fs_mgr_flags')
            new_flags, was_modified = clean_avb_flags(old_flags)

            if was_modified:
                file_was_modified = True
                # Replace ONLY the fs_mgr_flags part, preserve everything else
                start = match.start('fs_mgr_flags')
                end = match.end('fs_mgr_flags')
                new_line = line[:start] + new_flags + line[end:]
                modified_lines.append(new_line)
            else:
                modified_lines.append(line)

        base_name = os.path.basename(fstab_path)

        if file_was_modified:
            msg = getattr(lang, 'avb_flags_removed', "AVB flags removed in {file}.")
            print(f"[AVB Disabler] {msg.format(file=base_name)}")

            new_content = "\n".join(modified_lines)
            if not new_content.endswith('\n'):
                new_content += '\n'

            with open(fstab_path, 'wb') as f:
                f.write(new_content.encode(encoding))
        else:
            msg = getattr(lang, 'avb_flags_not_found', "No AVB flags found in {file}.")
            print(f"[AVB Disabler] {msg.format(file=base_name)}")

        return True

    except Exception as e:
        msg = getattr(lang, 'error_processing_file', "Error processing {file}: {error}")
        print(f"[AVB Disabler] {msg.format(file=fstab_path, error=e)}")
        traceback.print_exc()
        return False
