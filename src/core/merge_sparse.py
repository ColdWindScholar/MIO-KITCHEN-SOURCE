# src/core/merge_sparse.py

"""
Handles the merging of Android sparse image chunks into a single raw image file.

This module provides functionality to detect, sort, and combine split image
files (e.g., `super_sparsechunk.0`, `super_sparsechunk.1`) into a complete
raw image (e.g., `super.img`). It is designed to be self-contained, receiving all
external dependencies such as helper functions and configuration data as
arguments, thereby ensuring high cohesion and low coupling.

The core logic employs a "smart merge" strategy:
1.  It uses the `simg2img` tool to decompress only the first sparse chunk, which
    contains the sparse image header and initial data.
2.  It then directly appends the subsequent chunks to the output file. This
    is significantly faster, as these chunks are typically raw data segments that
    do not require decompression.
"""

import os
import re
import logging
from typing import List, Optional, Generator, Tuple, Callable

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
    segment_pattern = re.compile(r'.*(_sparsechunk|sparse_chunk|\.chunk|\.img)\.\d+$')
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
            logger.info(f"  - {getattr(lang, 'deleted_file_msg', 'Deleted: {filename}').format(filename=os.path.basename(segment_file))}")
        except OSError as e:
            logger.error(f"  - {getattr(lang, 'delete_error_msg', 'Failed to delete {filename}: {error}').format(filename=os.path.basename(segment_file), error=e)}")


def smart_merge_generator(
    project_path: str,
    output_name: str,
    lang: object,
    tool_bin_path: str,
    call_func: Callable,
    warn_func: Callable[[str], None]
) -> Generator[Tuple[int, Optional[str]], None, Optional[str]]:
    """
    A generator that merges sparse image chunks while yielding progress updates.

    This function implements the core "smart merge" logic. It processes the
    first segment with `simg2img` to correctly handle the sparse format header,
    then rapidly appends all subsequent segments to the resulting file.

    Args:
        project_path: The path to the directory containing the segment files.
        output_name: The desired filename for the final merged image.
        lang: An object providing localized strings for logging.
        tool_bin_path: The file path to the directory containing helper tools.
        call_func: A function to execute external commands. It should accept a
                   list of command arguments and a boolean `extra_path` flag.
        warn_func: A function to display a warning message to the user.

    Yields:
        A tuple `(percentage, output_path)`, where `percentage` is the
        current progress (0-100) and `output_path` is the path to the
        in-progress output file.

    Returns:
        The full path to the successfully merged file upon completion, or `None`
        if an error occurred.
    """
    output_path = os.path.join(project_path, output_name)

    executable_path = find_simg2img_executable(tool_bin_path)
    if not executable_path:
        warn_func(getattr(lang, 'simg2img_not_found_error', 'The simg2img tool was not found.'))
        return None

    segment_file_paths = _find_and_sort_segments(project_path)
    if not segment_file_paths:
        logger.info(f"> {getattr(lang, 'no_file_segments_found', 'No image segments found to merge.')}")
        return

    logger.info(f"> {getattr(lang, 'segments_found_msg', 'Found segments:')}")
    for f in segment_file_paths:
        logger.info(f"  - {os.path.basename(f)}")

    total_size = sum(os.path.getsize(p) for p in segment_file_paths)
    if total_size == 0:
        logger.warning("Total size of segments is 0. Nothing to merge.")
        return

    processed_size = 0

    # Step 1: Process the first segment using simg2img. This correctly
    # initializes the output file and handles the sparse format header.
    first_segment = segment_file_paths[0]
    command = [executable_path, first_segment, output_path]
    
    logger.info(f"\n> {getattr(lang, 'running_command_msg', 'Running command:').format(command=' '.join(command))}")
    logger.info(f"> {getattr(lang, 'processing_segment', 'Processing: {filename}').format(filename=os.path.basename(first_segment))}")
    
    # We pass 'extra_path=False' because we have the full, absolute path to the executable.
    return_code = call_func(command, extra_path=False, out=False)

    if return_code != 0:
        warn_func(getattr(lang, 'merge_fail_initial', 'Initial merge failed for {filename}').format(filename=os.path.basename(first_segment)))
        if os.path.exists(output_path):
            os.remove(output_path)
        return None

    processed_size += os.path.getsize(first_segment)
    yield int(processed_size * 100 / total_size), output_path

    # Step 2: Append the rest of the segments directly. This is much faster
    # than processing each one individually with simg2img.
    try:
        with open(output_path, "ab") as f_out:
            for segment_path in segment_file_paths[1:]:
                logger.info(f"> {getattr(lang, 'appending_segment', 'Appending: {filename}').format(filename=os.path.basename(segment_path))}")
                with open(segment_path, "rb") as f_in:
                    f_out.write(f_in.read())
                processed_size += os.path.getsize(segment_path)
                yield int(processed_size * 100 / total_size), output_path
    except IOError as e:
        warn_func(getattr(lang, 'merge_fail_append', 'Append failed: {error}').format(error=e))
        if os.path.exists(output_path):
            os.remove(output_path)
        return None

    return output_path


def main(
    project_path: str,
    output_name: str = "super.img",
    delete_source: bool = False,
    progress_callback: Optional[Callable[[int], None]] = None,
    # --- Injected Dependencies ---
    lang: Optional[object] = None,
    tool_bin_path: Optional[str] = None,
    call_func: Optional[Callable] = None,
    info_func: Optional[Callable[[str], None]] = None,
    warn_func: Optional[Callable[[str], None]] = None
) -> None:
    """
    The main entry point for orchestrating the sparse image merging process.

    This function serves as a wrapper for the `smart_merge_generator`. It handles
    pre-flight checks, reports progress via the provided callback, and manages
    the final success/failure notifications and optional cleanup of source files.

    Args:
        project_path: The directory containing the image segments.
        output_name: The name for the final merged image file. Defaults to "super.img".
        delete_source: If True, the original segment files will be deleted after a
                       successful merge. Defaults to False.
        progress_callback: An optional function to call with progress updates. It
                           receives an integer percentage (0-100) or -1 on error.
        lang: An object for fetching localized strings.
        tool_bin_path: The file path to the directory containing helper tools like `simg2img`.
        call_func: A function for executing external command-line tools.
        info_func: A function for displaying an informational message to the user.
        warn_func: A function for displaying a warning message to the user.
    """
    if not all([lang, tool_bin_path, call_func, info_func, warn_func]):
        raise ValueError("One or more required dependencies were not provided to merge_sparse.main.")

    output_path = os.path.join(project_path, output_name)

    if not os.path.isdir(project_path):
        warn_func(getattr(lang, 'project_path_error', 'Project path does not exist or is not a directory: {project_path}').format(project_path=project_path))
        return

    if os.path.exists(output_path):
        logger.info(f"> {getattr(lang, 'merge_skipped_exists', 'Output file {output_name} already exists. Skipping merge.').format(output_name=output_name)}")
        if progress_callback:
            progress_callback(100)
        return

    logger.info(f"> {getattr(lang, 'searching_for_segments_msg', 'Searching for image segments in: {project_path}').format(project_path=project_path)}")

    try:
        final_output_path = None
        merge_gen = smart_merge_generator(
            project_path, output_name, lang, tool_bin_path, call_func, warn_func
        )
        for percentage, path in merge_gen:
            if progress_callback:
                progress_callback(percentage)
            final_output_path = path

        # After the generator is exhausted, check the outcome.
        if final_output_path and os.path.exists(final_output_path):
            # Success: The generator returned a path and the file exists.
            if progress_callback:
                progress_callback(100)
            success_msg = getattr(lang, 'merge_success_msg', 'Merge successful. Output: {output_path}').format(output_path=final_output_path)
            logger.info(f"> {success_msg}")
            info_func(success_msg)

            if delete_source:
                source_segments = _find_and_sort_segments(project_path)
                _delete_source_segments(source_segments, lang)
        
        elif final_output_path is None:
            # Neutral: The generator finished without error but produced no output,
            # likely because no segments were found.
            info_func(getattr(lang, 'no_segments_to_merge_in_project', 'No file segments were found to merge in this project.'))

    except Exception as e:
        # A final catch-all for any unexpected errors during the process.
        logger.exception("An unexpected error occurred in the merge process.")
        error_msg = getattr(lang, 'unexpected_merge_error', 'An unexpected error occurred during merge: {error}').format(error=e)
        warn_func(error_msg)
        if progress_callback:
            progress_callback(-1) # Signal an error state to the UI.