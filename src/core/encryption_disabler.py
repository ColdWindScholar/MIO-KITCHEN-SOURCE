#!/usr/bin/env python3
# Copyright (C) 2022-2025 The MIO-KITCHEN-SOURCE Project
#
# Licensed under the GNU AFFERO GENERAL PUBLIC LICENSE, Version 3.0
#

"""
This module is responsible for disabling forced data encryption on Android devices.

It achieves this by parsing fstab (filesystem table) files and removing specific
mount options (flags) that enforce file-based or full-disk encryption.
"""

import os
import re
import logging
from src.core.utils import lang

# Initialize a logger for this module.
logger = logging.getLogger(__name__)


# --- ENCRYPTION FLAG DEFINITIONS ---
# These sets define the fstab mount options that will be removed.

# Flags that are followed by an equals sign and a value (e.g., "fileencryption=ice").
# The entire "flag=value" pair will be removed.
FLAGS_TO_REMOVE_BY_PREFIX = ('fileencryption=', 'metadata_encryption=', 'keydirectory=', 'encryptable=')

# Standalone flags that appear as whole words (e.g., "forceencrypt").
FLAGS_TO_REMOVE_EXACT = {'forceencrypt', 'forcecrypt', 'fsverity', 'latemount', 'inlinecrypt', 'forcefdeorfbe', 'wrappedkey', 'encryptable'}


def clean_encryption_flags_preserve_format(options_part: str) -> tuple[str, bool]:
    """
    Removes encryption-related flags from an fstab options string.

    This function is designed to be format-preserving. It carefully removes flags
    and their preceding comma/space delimiters, avoiding breaking the structure
    of the remaining options. This is a more robust and careful approach.

    :param options_part: The raw options string from an fstab entry.
    :type options_part: str
    :return: A tuple containing the cleaned options string and a boolean
             indicating whether any modifications were made.
    :rtype: tuple[str, bool]
    """
    modified_options = options_part
    was_modified = False

    # 1. Remove flags that are followed by a value (prefix-based).
    for prefix in FLAGS_TO_REMOVE_BY_PREFIX:
        # The pattern targets the flag prefix, preceded by a comma or space,
        # and followed by any non-space/non-comma characters (the value).
        # `(?i)` makes the search case-insensitive.
        pattern = rf'(?i)(,\s*|\s+){re.escape(prefix)}[^\s,]*'
        if re.search(pattern, modified_options):
            was_modified = True
            modified_options = re.sub(pattern, '', modified_options)

    # 2. Remove standalone flags (exact matches).
    for flag in FLAGS_TO_REMOVE_EXACT:
        # The pattern targets the exact flag as a whole word (`\b`),
        # preceded by a comma or space. `(?i)` ensures case-insensitivity.
        pattern = rf'(?i)(,\s*|\s+)\b{re.escape(flag)}\b'
        if re.search(pattern, modified_options):
            was_modified = True
            modified_options = re.sub(pattern, '', modified_options)

    if was_modified:
        # 3. Post-removal cleanup.
        # Clean up any leading comma that might be left if the first flag was removed.
        modified_options = re.sub(r'^\s*,\s*', '', modified_options)
        
        # Edge case: If the options string becomes empty after removal,
        # it's safer to replace it with "defaults".
        if not modified_options.strip():
            return 'defaults', True

    return modified_options, was_modified


def process_fstab_for_encryption(fstab_path: str) -> bool:
    """
    Parses a given fstab file and removes all known encryption flags.

    This function has been completely reworked for improved reliability. It reads
    the file, automatically detects its encoding (UTF-8 or Latin-1 fallback),
    and iterates through each line. For valid fstab entries, it cleans the
    options field using `clean_encryption_flags_preserve_format`. If any
    modifications are made, the entire file is rewritten using its original
    encoding to ensure integrity.

    :param fstab_path: The absolute path to the fstab file to process.
    :type fstab_path: str
    :return: True if the process completed successfully (even if no flags were
             found/removed), False on critical file I/O or processing errors.
    :rtype: bool
    """
    if not os.path.isfile(fstab_path):
        print(f"[Enc Disabler] {lang.file_not_found.format(file=fstab_path)}")
        return False

    try:
        # Read the file as raw bytes first to handle encoding detection gracefully.
        with open(fstab_path, 'rb') as f:
            raw_content = f.read()

        # Try to decode as UTF-8 (most common), but fall back to Latin-1
        # to prevent crashes on non-standard or legacy file encodings.
        try:
            content = raw_content.decode('utf-8')
            encoding = 'utf-8'
        except UnicodeDecodeError:
            content = raw_content.decode('latin-1')
            encoding = 'latin-1'
            print(f"[Enc Disabler] {lang.encoding_warning.format(file=os.path.basename(fstab_path), encoding=encoding)}")

        original_lines = content.splitlines()
        modified_lines = []
        file_was_modified = False

        # This regex is compiled for efficiency and used to parse a standard fstab line.
        # It captures three essential fields into the 'fields' group (device, mount point, type)
        # and the entire rest of the line into the 'options' group.
        fstab_line_pattern = re.compile(r'^(?P<fields>\S+\s+\S+\s+\S+)\s+(?P<options>.*)$')

        for line_num, line in enumerate(original_lines, 1):
            stripped_line = line.strip()

            # Skip comments and empty lines, preserving them in the output.
            if not stripped_line or stripped_line.startswith('#'):
                modified_lines.append(line)
                continue

            match = fstab_line_pattern.match(stripped_line)

            if not match:
                # If a line doesn't match the standard fstab format, keep it as is.
                modified_lines.append(line)
                continue
            
            # Extract parts from the matched line.
            fields_part = match.group('fields')
            options_part = match.group('options')
            
            # Get the mount point (the second field) for more informative logging.
            mount_point = fields_part.split()[1]

            # Clean the encryption flags from the options part of the line.
            new_options, was_line_modified = clean_encryption_flags_preserve_format(options_part)

            if was_line_modified:
                file_was_modified = True
                # Reconstruct the modified line, ensuring a single space separator.
                modified_line = f"{fields_part} {new_options}"
                modified_lines.append(modified_line)
                print(f"[Enc Disabler] {lang.line_processed.format(line=line_num, mount=mount_point)}")
            else:
                # If the line was not modified, add the original line back.
                modified_lines.append(line)

        base_name = os.path.basename(fstab_path)
        if file_was_modified:
            # Join the processed lines back into a single string.
            new_content = '\n'.join(modified_lines)
            # Ensure the file ends with a newline, which is standard practice for text files.
            if not new_content.endswith('\n'):
                new_content += '\n'
            
            # Write the modified content back to the file using the originally detected encoding.
            with open(fstab_path, 'wb') as f:
                f.write(new_content.encode(encoding))

            print(f"[Enc Disabler] {lang.enc_flags_removed.format(file=base_name)}")
        else:
            print(f"[Enc Disabler] {lang.enc_flags_not_found.format(file=base_name)}")

        return True

    except Exception as e:
        # Catch any unexpected errors during file processing.
        print(f"[Enc Disabler] {lang.error_processing_file.format(file=fstab_path, error=str(e))}")
        import traceback
        traceback.print_exc()
        return False