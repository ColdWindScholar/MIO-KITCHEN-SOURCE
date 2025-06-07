#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=line-too-long
# Copyright (C) 2022-2025 The MIO-KITCHEN-SOURCE Project
#
# Licensed under the GNU AFFERO GENERAL PUBLIC LICENSE, Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.gnu.org/licenses/agpl-3.0.en.html#license-text
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
import sys
from pathlib import Path
from typing import Dict, Generator, List, Tuple, Optional

# Assuming JsonEdit is a utility that correctly reads a JSON file into a dict.
from .utils import JsonEdit


def scan_context(context_file_path: Path) -> Dict[str, str]:
    """
    Reads an SELinux context file (e.g., file_contexts) and returns a dictionary.

    Args:
        context_file_path: The Path object pointing to the context file.

    Returns:
        A dictionary mapping file paths/regexes to their SELinux contexts.
    """
    contexts = {}
    print(f"ContextPatcher: Reading original contexts from {context_file_path.name}...")
    with context_file_path.open("r", encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split()
            if len(parts) < 2:
                print(f"[Warning] Malformed line {line_num}: '{line}'. Skipping.")
                continue

            path, context = parts[0], parts[1]
            path = path.replace(r'\@', '@')  # Un-escape characters if needed

            if len(parts) > 2:
                print(f"[Warning] Line {line_num} has extra data: '{line}'. Using first two parts.")

            contexts[path] = context
    return contexts


def scan_dir(unpacked_dir: Path) -> Generator[str, None, None]:
    """
    Scans a directory (representing an unpacked partition) and yields all file
    and directory paths in a Linux-like format (e.g., /system/app/SystemUI.apk).

    Args:
        unpacked_dir: The Path object of the directory to scan.

    Yields:
        Normalized, Linux-style paths for all files and directories.
    """
    partition_name = unpacked_dir.name
    
    yield f"/{partition_name}(/.*)?"
    yield f"/{partition_name}"
    yield f"/{partition_name}/"
    yield f"/{partition_name}/lost\\+found"

    for item_path in unpacked_dir.rglob('*'):
        relative_path = item_path.relative_to(unpacked_dir)
        target_path = f"/{partition_name}/{relative_path.as_posix()}"
        yield target_path.replace('/lost+found', '/lost\\+found')


def context_patch(original_contexts: Dict[str, str],
                  unpacked_dir: Path,
                  fix_rules: Dict[str, str]) -> Tuple[Dict[str, str], int]:
    """
    Compares files in a directory against existing SELinux contexts,
    adds missing entries using fix rules, and returns the updated context map.

    Args:
        original_contexts: A dict of existing file paths to contexts.
        unpacked_dir: The Path object of the unpacked partition directory.
        fix_rules: A dict of regex patterns to apply for missing contexts.

    Returns:
        A tuple containing:
        - The new, complete dictionary of contexts.
        - The number of new contexts that were added.
    """
    compiled_rules: List[Tuple[re.Pattern, str]] = []

    # --- INTELLIGENT RULE SORTING ---
    # Sort the rules by the length of the pattern in descending order.
    # This ensures that more specific rules (which are typically longer) are
    # checked before more generic, shorter rules. e.g.,
    # '^/system/app/My.apk$' is checked before '^/system/app/.*\.apk$'.
    # This greatly increases the accuracy of context patching.
    sorted_rules = sorted(fix_rules.items(), key=lambda item: len(item[0]), reverse=True)
    
    for pattern, context in sorted_rules:
        if ' ' in context:
            print(f"[Warning] Invalid context '{context}' for rule '{pattern}' contains a space. Skipping rule.")
            continue
        try:
            if pattern.startswith(('//', '__comment')):
                continue
            compiled_rules.append((re.compile(pattern), context))
        except re.error as e:
            print(f"[Warning] Invalid regex '{pattern}' in fix rules: {e}. Skipping rule.")

    new_contexts = original_contexts.copy()
    patched_paths_cache = set()
    newly_added_count = 0
    
    print("ContextPatcher: Scanning directory and patching contexts...")
    for path_str in scan_dir(unpacked_dir):
        if path_str in new_contexts or re.escape(path_str) in new_contexts:
            continue
            
        if path_str in patched_paths_cache:
            continue

        assigned_context = None
        for pattern, context in compiled_rules:
            if pattern.search(path_str):
                assigned_context = context
                break

        if not assigned_context:
            print(f"  [INFO] No specific rule for '{path_str}', please check your rules file. Using a safe default.")
            assigned_context = 'u:object_r:system_file:s0'
        
        print(f"  [ADD]  {path_str} -> {assigned_context}")
        new_contexts[path_str] = assigned_context
        patched_paths_cache.add(path_str)
        newly_added_count += 1
    
    print(f"ContextPatcher: Original file had {len(original_contexts)} entries.")
    return new_contexts, newly_added_count


def main(dir_path_str: str, fs_config_path_str: str, fix_permission_file_str: Optional[str]) -> None:
    """
    Main entry point for the context patching script.
    Accepts string paths and converts them to Path objects for robust handling.

    Args:
        dir_path_str: Path to the unpacked partition directory.
        fs_config_path_str: Path to the file_contexts file to be modified.
        fix_permission_file_str: Optional path to a JSON file with context fix rules.
    """
    dir_path = Path(dir_path_str)
    fs_config_path = Path(fs_config_path_str)
    fix_permission_file = Path(fix_permission_file_str) if fix_permission_file_str else None
    
    try:
        if not dir_path.is_dir():
            print(f"[Error] Directory not found: {dir_path}", file=sys.stderr)
            return
            
        fix_rules = {}
        if fix_permission_file:
            if not fix_permission_file.is_file():
                print(f"[Warning] Fix permission file not found: {fix_permission_file}. Proceeding without it.")
            else:
                fix_rules = JsonEdit(fix_permission_file).read()

        original_contexts = scan_context(fs_config_path.resolve())
        
        new_fs, add_new = context_patch(original_contexts, dir_path, fix_rules)

        with fs_config_path.open("w", encoding='utf-8', newline='\n') as f:
            sorted_paths = sorted(new_fs.keys())
            for path in sorted_paths:
                f.write(f"{path} {new_fs[path]}\n")
        
        print(f'ContextPatcher: Successfully added {add_new} new entries. Total entries: {len(new_fs)}.')

    except FileNotFoundError:
        print(f"[Error] Context file not found: {fs_config_path}", file=sys.stderr)
    except Exception as e:
        print(f"[Error] An unexpected error occurred: {e}", file=sys.stderr)
