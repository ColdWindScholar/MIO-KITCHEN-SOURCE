# src/core/merge_sparse.py

"""
Handles the merging of Android sparse image chunks into a single raw image file.

This module provides functionality to detect, sort, and combine split image
files (e.g., `super.img.0`, `super.img.1`) into a complete
raw image (e.g., `super.img`). It is designed to be self-contained, receiving all
external dependencies such as helper functions and configuration data as
arguments, thereby ensuring high cohesion and low coupling.

The core logic employs the most efficient merging strategy: it constructs a single
command that passes all sorted sparse chunks directly to the `simg2img` tool.
The tool is capable of processing multiple input chunks sequentially, creating the
final raw image in one pass without the need for intermediate temporary files.
This minimizes disk I/O and significantly speeds up the process.
"""

import os
import re
import logging
import subprocess
from typing import List, Optional, Generator, Tuple

# Set up a logger for this module. The logger is configured by the parent application.
logger = logging.getLogger(__name__)


def natural_sort_key(s: str) -> List:
    """
    Creates a sort key for "natural" sorting of strings containing numbers.

    This function is crucial for ordering file segments correctly, ensuring that
    'file10.chunk' is processed after 'file2.chunk', not before it, which would
    happen with standard lexicographical sorting.

    Args:
        s: The input string to generate a sort key for.

    Returns:
        A list of strings and integers that Python's sort functions can use
        to order strings in a human-intuitive way.
    """
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split('([0-9]+)', s)]


def find_simg2img_executable(tool_bin_path: str) -> Optional[str]:
    """
    Locates the `simg2img` executable within the provided tool directory.

    It checks for both the Windows (`.exe`) and Unix-style executable names.

    Args:
        tool_bin_path: The absolute path to the directory containing the tool.

    Returns:
        The full, absolute path to the executable if found, otherwise None.
    """
    if not tool_bin_path or not os.path.isdir(tool_bin_path):
        logger.error("The tool binary path ('tool_bin_path') was not provided or does not exist.")
        return None
    
    for name in ('simg2img.exe', 'simg2img'):
        executable_path = os.path.join(tool_bin_path, name)
        if os.path.exists(executable_path):
            return executable_path
            
    logger.error(f"The 'simg2img' executable was not found in the provided path: {tool_bin_path}")
    return None


def _find_and_sort_segments(project_path: str) -> List[str]:
    """
    Finds and sorts all image segment files within a given directory.

    It uses a regular expression to identify files matching common Android
    sparse chunk naming conventions (e.g., `_sparsechunk.N`, `.img.N`) and then
    sorts them using a natural sort algorithm.

    Args:
        project_path: The directory to search for segment files.

    Returns:
        A naturally sorted list of full, absolute paths to the segment files.
    """
    # This pattern matches both common formats:
    # 1. Names ending in _sparsechunk.N, sparse_chunk.N, or .chunk.N
    # 2. Names ending in .img.N (e.g., super.img.0)
    segment_pattern = re.compile(r'.*(_sparsechunk|sparse_chunk|\.chunk)\.\d+$|.+\.img\.\d+$')
    all_files = os.listdir(project_path)
    
    segment_files = [
        f for f in all_files
        if segment_pattern.match(f) and os.path.isfile(os.path.join(project_path, f))
    ]
    
    segment_files.sort(key=natural_sort_key)
    
    return [os.path.join(project_path, f) for f in segment_files]


def _delete_source_segments(segment_paths: List[str], lang: object) -> None:
    """
    Deletes the source segment files after a successful merge operation.

    Args:
        segment_paths: A list of file paths to be deleted.
        lang: A language object for fetching localized logging messages.
    """
    logger.info(f"> {getattr(lang, 'deleting_source_segments_msg', 'Deleting source segments...')}")
    for segment_file in segment_paths:
        try:
            os.remove(segment_file)
            logger.info(f"  - Deleted: {os.path.basename(segment_file)}")
        except OSError as e:
            logger.error(f"  - Failed to delete {os.path.basename(segment_file)}: {e}")


def smart_merge_generator(
    project_path: str,
    output_name: str,
    lang: object,
    tool_bin_path: str,
    call_func,
    warn_func
) -> Generator[Tuple[int, Optional[str]], None, Optional[str]]:
    """
    A generator that merges sparse chunks by passing all segments to simg2img at once.

    This is the most efficient method as it avoids creating intermediate files and
    leverages the tool's ability to process multiple inputs.

    Args:
        project_path: The path to the directory containing the segment files.
        output_name: The desired filename for the final merged image.
        lang: An object providing localized strings for logging.
        tool_bin_path: The file path to the directory containing helper tools.
        call_func: A function to execute external commands. It should accept a
                   list of command arguments and keyword arguments.
        warn_func: A function to display a warning message to the user.

    Yields:
        A tuple `(percentage, output_path)`, where `percentage` is the
        current progress (0-100) and `output_path` is the path to the
        final output file upon successful completion.

    Returns:
        The full path to the successfully merged file upon completion, or `None`
        if an error occurred.
    """
    # Step 1: Prepare paths and find the executable.
    output_path = os.path.join(project_path, output_name)
    executable_path = find_simg2img_executable(tool_bin_path)
    if not executable_path:
        warn_func(getattr(lang, 'simg2img_not_found_error', 'The simg2img tool was not found.'))
        return None

    # Step 2: Find and sort all segment files.
    segment_file_paths = _find_and_sort_segments(project_path)
    if not segment_file_paths:
        logger.info(f"> {getattr(lang, 'no_file_segments_found', 'No image segments found to merge.')}")
        return

    logger.info(f"> {getattr(lang, 'segments_found_msg', 'Found segments:')}")
    for f in segment_file_paths:
        logger.info(f"  - {os.path.basename(f)}")

    # Step 3: Build the full command list for a single tool execution.
    # Format: [simg2img_path, chunk1, chunk2, ..., output_path]
    command = [executable_path] + segment_file_paths + [output_path]
    
    logger.info(f"\n> {getattr(lang, 'running_command_msg', 'Running command:').format(command=' '.join(command))}")
    
    # Yield 50% progress right before the long-running operation starts.
    yield 50, None
    
    # Step 4: Execute the command. `call_func` handles the subprocess execution.
    return_code = call_func(command, extra_path=False, out=False)

    if return_code != 0:
        warn_func(getattr(lang, 'merge_fail_final', 'Final merge with simg2img failed.'))
        if os.path.exists(output_path):
            os.remove(output_path)
        return None

    # Success! Yield 100% and the final output path.
    yield 100, output_path
    return output_path


def default_call_func(command, **kwargs):
    """
    A simple, default implementation of `call_func` using subprocess.
    This is used if no external call function is provided to `main`.
    
    Args:
        command (List[str]): A list of command arguments.
        **kwargs: Catches extra arguments to maintain a consistent signature.

    Returns:
        int: The return code of the process.
    """
    try:
        # Using subprocess.run is simpler for a default implementation.
        # It waits for the command to complete.
        process = subprocess.run(command, capture_output=True, text=True, check=False, encoding='utf-8', errors='ignore')
        if process.stdout:
            logger.info(process.stdout)
        if process.stderr:
            logger.error(process.stderr)
        return process.returncode
    except FileNotFoundError:
        logger.error(f"Command not found: {command[0]}")
        return -1
    except Exception as e:
        logger.exception(f"Error executing command: {e}")
        return -1

class SimpleLang:
    """A fallback language object to prevent crashes if no lang object is provided."""
    def __getattr__(self, name):
        # Returns the requested attribute name as a default string.
        return f"<{name}>"

def main(
    project_path: str,
    output_name: str = "super.img",
    delete_source: bool = False,
    progress_callback=None,
    # --- Injected Dependencies ---
    lang: Optional[object] = None,
    tool_bin_path: Optional[str] = None,
    call_func=None,
    info_func=None,
    warn_func=None
) -> None:
    """
    The main entry point for orchestrating the sparse image merging process.

    This function serves as a wrapper for the `smart_merge_generator`. It handles
    pre-flight checks, reports progress, and manages final success/failure
    notifications and optional cleanup of source files.

    Args:
        project_path: The directory containing the image segments.
        output_name: The name for the final merged image file. Defaults to "super.img".
        delete_source: If True, original segment files are deleted after a successful merge.
        progress_callback: An optional function to call with progress updates. It
                           receives an integer percentage (0-100) or -1 on error.
        lang: An object for fetching localized strings.
        tool_bin_path: Path to the directory containing helper tools like `simg2img`.
        call_func: A function for executing external command-line tools.
        info_func: A function for displaying an informational message to the user.
        warn_func: A function for displaying a warning message to the user.
    """
    # --- Set default dependencies if they are not provided ---
    lang = lang if lang is not None else SimpleLang()
    call_func = call_func if call_func is not None else default_call_func
    info_func = info_func if info_func is not None else print
    warn_func = warn_func if warn_func is not None else lambda msg: print(f"WARNING: {msg}")

    if not all([lang, tool_bin_path, call_func, info_func, warn_func]):
        raise ValueError("One or more required dependencies were not provided to merge_sparse.main.")

    output_path = os.path.join(project_path, output_name)

    if not os.path.isdir(project_path):
        warn_func(getattr(lang, 'project_path_error', 'Project path does not exist: {path}').format(path=project_path))
        return

    if os.path.exists(output_path):
        logger.info(f"> Merge skipped: Output file {output_name} already exists.")
        if progress_callback:
            progress_callback(100)
        return

    logger.info(f"> Searching for segments in: {project_path}")

    try:
        final_output_path = None
        # Create and iterate through the generator.
        merge_gen = smart_merge_generator(
            project_path, output_name, lang, tool_bin_path, call_func, warn_func
        )
        for percentage, path in merge_gen:
            if progress_callback:
                progress_callback(percentage)
            if path: # The path is only non-None on the final, successful yield.
                final_output_path = path

        # After the generator is exhausted, check the outcome.
        if final_output_path and os.path.exists(final_output_path):
            # Success: The generator returned a path and the file exists.
            if progress_callback:
                progress_callback(100) # Ensure it finishes at 100%
            success_msg = getattr(lang, 'merge_success_msg', 'Merge successful. Output: {output_path}').format(output_path=final_output_path)
            logger.info(f"> {success_msg}")
            info_func(success_msg)

            if delete_source:
                source_segments = _find_and_sort_segments(project_path)
                _delete_source_segments(source_segments, lang)
        
        elif final_output_path is None:
            # Neutral: The generator finished without error but produced no output,
            # likely because no segments were found. The log inside the generator handles this.
            # We can also send a message to the UI.
            no_segments_msg = getattr(lang, 'no_segments_to_merge_in_project', 'No file segments were found to merge.')
            info_func(no_segments_msg)

    except Exception as e:
        # A final catch-all for any unexpected errors during the process.
        logger.exception("An unexpected error occurred in the merge process.")
        error_msg = getattr(lang, 'unexpected_merge_error', 'An unexpected error occurred during merge: {error}').format(error=e)
        warn_func(error_msg)
        if progress_callback:
            progress_callback(-1) # Signal an error state to the UI.
