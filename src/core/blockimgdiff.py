# Copyright (C) 2014 The Android Open Source Project
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
# pylint: disable=line-too-long
import logging
import os
import subprocess
import tempfile
import hashlib
from array import array
from functools import total_ordering
from heapq import heappop, heappush, heapify
from itertools import chain
from multiprocessing import cpu_count
from re import sub
from threading import Lock
from collections import deque, OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed # For improved threading

from .rangelib import RangeSet # Assuming rangelib is in the same package directory

__all__ = ["EmptyImage", "DataImage", "BlockImageDiff"]

# Default logger if none is provided by the application
DEFAULT_LOGGER = logging.getLogger(__name__)

# Placeholder for the language object, expected to be provided by the application
# It should have a get(key, default_text=None, **kwargs) method
class DummyLang:
    def get(self, key, default_text=None, **kwargs):
        text = default_text or key
        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError: # Silently ignore if key is not in format string
                pass
        return text

DEFAULT_LANG = DummyLang()


class Image:
    """Abstract base class for image representations."""
    blocksize = 4096 # Default block size

    def ReadRangeSet(self, ranges: RangeSet):
        """
        Reads data for the given ranges.
        Returns an iterable of bytes objects.
        """
        raise NotImplementedError

    def TotalSha1(self, include_clobbered_blocks=False):
        """
        Calculates SHA1 hash of the image data.
        Returns a hex digest string.
        """
        raise NotImplementedError


class EmptyImage(Image):
    """A zero-length image."""
    care_map = RangeSet()
    clobbered_blocks = RangeSet()
    extended = RangeSet()
    total_blocks = 0
    file_map = {}

    def ReadRangeSet(self, ranges: RangeSet):
        return () # Returns an empty tuple, which is an iterable of bytes (empty)

    def TotalSha1(self, include_clobbered_blocks=False):
        # EmptyImage always carries empty clobbered_blocks, so
        # include_clobbered_blocks can be ignored.
        assert self.clobbered_blocks.size() == 0
        return hashlib.sha1().hexdigest()


class DataImage(Image):
    """An image wrapped around a single bytes object of data."""

    def __init__(self, data: bytes, trim=False, pad=False, lang=DEFAULT_LANG):
        self.data = data
        # blocksize is inherited from Image class

        assert not (trim and pad)

        partial = len(self.data) % self.blocksize
        padded = False
        if partial > 0:
            if trim:
                self.data = self.data[:-partial]
            elif pad:
                self.data += b'\0' * (self.blocksize - partial) # Use bytes for padding
                padded = True
            else:
                # This error message should be localizable if DataImage is created
                # in a context where `lang` is available.
                # For now, using f-string and passing lang for future potential.
                error_msg = lang.get(
                    "imgdiff_error_file_must_be_multiple_of_blocksize",
                    default_text="Data for DataImage must be multiple of {blocksize} bytes unless trim or pad is specified",
                    blocksize=self.blocksize
                )
                raise ValueError(error_msg)

        assert len(self.data) % self.blocksize == 0

        self.total_blocks = len(self.data) // self.blocksize # Use integer division
        self.care_map = RangeSet(data=(0, self.total_blocks))

        # When the last block is padded, we always write the whole block even for
        # incremental OTAs. Because otherwise the last block may get skipped if
        # unchanged for an incremental, but would fail the post-install
        # verification if it has non-zero contents in the padding bytes.
        # Bug: 23828506
        if padded:
            # Ensure clobbered_blocks is a RangeSet for consistency
            self.clobbered_blocks = RangeSet(data=[self.total_blocks - 1, self.total_blocks])
        else:
            self.clobbered_blocks = RangeSet() # Empty RangeSet
        self.extended = RangeSet()

        zero_blocks_list = []
        nonzero_blocks_list = []
        # Use bytes for reference block
        reference_block = b'\0' * self.blocksize

        # Iterate up to total_blocks, unless it's padded, then exclude last block from this specific categorization
        # The clobbered_blocks handles the padded block explicitly.
        iterate_up_to = self.total_blocks - 1 if padded else self.total_blocks
        for i in range(iterate_up_to):
            block_data = self.data[i * self.blocksize: (i + 1) * self.blocksize]
            if block_data == reference_block:
                zero_blocks_list.extend((i, i + 1))
            else:
                nonzero_blocks_list.extend((i, i + 1))
        
        self.file_map = {}
        if zero_blocks_list:
            self.file_map["__ZERO"] = RangeSet(data=zero_blocks_list)
        if nonzero_blocks_list:
            self.file_map["__NONZERO"] = RangeSet(data=nonzero_blocks_list)
        
        # If padded, the last block is handled by __COPY logic if not covered.
        # The original logic for clobbered_blocks in __init__ was:
        # self.clobbered_blocks = [self.total_blocks - 1, self.total_blocks] if padded else []
        # This was then assigned to self.file_map["__COPY"]. We now use RangeSet directly.
        if self.clobbered_blocks.size() > 0 : # If there are clobbered blocks (i.e., it was padded)
            self.file_map["__COPY"] = self.clobbered_blocks

        # Ensure at least one map entry if there's data, or if it was padded (meaning __COPY will exist)
        # This assertion might need adjustment based on how empty but padded images are handled.
        # assert zero_blocks_list or nonzero_blocks_list or self.clobbered_blocks.size() > 0 or self.total_blocks == 0

    def ReadRangeSet(self, ranges: RangeSet):
        # Yield bytes for memory efficiency with large images, instead of list construction
        for s, e in ranges:
            yield self.data[s * self.blocksize:e * self.blocksize]

    def TotalSha1(self, include_clobbered_blocks=False):
        ctx = hashlib.sha1()
        if not include_clobbered_blocks:
            ranges_to_hash = self.care_map.subtract(self.clobbered_blocks)
            for chunk in self.ReadRangeSet(ranges_to_hash):
                ctx.update(chunk)
        else:
            # Hash all data if clobbered blocks are included
            # This assumes self.data correctly represents the entire image content
            ctx.update(self.data)
        return ctx.hexdigest()


class Transfer:
    def __init__(self, tgt_name, src_name, tgt_ranges, src_ranges, style, by_id_list):
        self.tgt_name = tgt_name
        self.src_name = src_name
        self.tgt_ranges = tgt_ranges
        self.src_ranges = src_ranges
        self.style = style
        self.intact = (getattr(tgt_ranges, "monotonic", False) and
                       getattr(src_ranges, "monotonic", False))

        self.goes_before = OrderedDict()
        self.goes_after = OrderedDict()

        self.stash_before = []
        self.use_stash = []

        self.id = len(by_id_list)
        by_id_list.append(self)

        # Attributes for patch data, set later in ComputePatches
        self.patch_start = 0
        self.patch_len = 0


    def NetStashChange(self):
        return (sum(sr.size() for (_, sr) in self.stash_before) -
                sum(sr.size() for (_, sr) in self.use_stash))

    def ConvertToNew(self):
        assert self.style != "new"
        self.use_stash = [] # No longer uses stashed blocks
        self.style = "new"
        self.src_ranges = RangeSet() # No source ranges for "new" style

    def __str__(self):
        return (f"{self.id}: <{self.src_ranges} {self.style} to {self.tgt_ranges}> "
                f"(tgt: {self.tgt_name}, src: {self.src_name or 'N/A'})")


@total_ordering
class HeapItem:
    def __init__(self, item):
        self.item = item
        self.score = -item.score # Min-heap for max-score

    def clear(self):
        self.item = None # Allows garbage collection if item is no longer needed

    def __bool__(self):
        return self.item is not None # True if item is still valid

    def __eq__(self, other):
        if not isinstance(other, HeapItem):
            return NotImplemented
        return self.score == other.score

    def __lt__(self, other): # Changed from __le__ to __lt__ for standard total_ordering
        if not isinstance(other, HeapItem):
            return NotImplemented
        return self.score < other.score


class BlockImageDiff:
    def __init__(self, tgt: Image, src: Image = None, version=4, threads=None,
                 disable_imgdiff=False,
                 cache_size_bytes=None, stash_threshold=0.8,
                 tool_path_resolver=None, # Function: str_tool_name -> str_tool_path
                 lang=DEFAULT_LANG, logger=DEFAULT_LOGGER):
        
        self.tgt = tgt
        self.src = src if src is not None else EmptyImage()
        self.version = version
        self.disable_imgdiff = disable_imgdiff
        self.cache_size_bytes = cache_size_bytes
        self.stash_threshold = stash_threshold
        self.tool_path_resolver = tool_path_resolver or (lambda name: name) # Default: assume in PATH
        self.lang = lang
        self.logger = logger

        if threads is None:
            threads = cpu_count() // 2
            if threads == 0:
                threads = 1
        elif threads <= 0:
            self.logger.warning(self.lang.get("imgdiff_warn_threads_invalid", 
                                             default_text="Invalid thread count ({threads_requested}), defaulting to 1.",
                                             threads_requested=threads))
            threads = 1
        self.threads = threads

        self.transfers = []
        self.src_basenames = {}
        self.src_numpatterns = {}
        self._max_stashed_size = 0
        self.touched_src_ranges = RangeSet()
        self.touched_src_sha1 = None # Will be hex string

        assert version in (1, 2, 3, 4), "Unsupported version"
        assert tgt.blocksize == 4096, "Target blocksize must be 4096"
        assert self.src.blocksize == 4096, "Source blocksize must be 4096"

        self.AssertPartition(self.src.care_map, self.src.file_map.values())
        self.AssertPartition(self.tgt.care_map, self.tgt.file_map.values())

    @property
    def max_stashed_size(self):
        return self._max_stashed_size

    def _compute_patch_for_transfer(self, src_data_iter, tgt_data_iter, xf: Transfer):
        """
        Computes a patch between src and tgt data for a given transfer.
        Updates xf.style if data is identical ("move").
        Returns the patch data (bytes) or None if style changed to "move".
        Raises ValueError on diff tool failure.
        """
        # Create temporary files for diffing
        src_fd, src_path = tempfile.mkstemp(prefix="imgdiff-src-")
        tgt_fd, tgt_path = tempfile.mkstemp(prefix="imgdiff-tgt-")
        patch_path = src_path + "-patch" # Create patch file in same temp dir

        try:
            with os.fdopen(src_fd, "wb") as f_src:
                for chunk in src_data_iter:
                    f_src.write(chunk)
            with os.fdopen(tgt_fd, "wb") as f_tgt:
                for chunk in tgt_data_iter:
                    f_tgt.write(chunk)
            
            tool_name = "imgdiff" if xf.style == "imgdiff" else "bsdiff"
            tool_executable = self.tool_path_resolver(tool_name)
            
            cmd = [tool_executable]
            if xf.style == "imgdiff":
                cmd.extend(["-z", src_path, tgt_path, patch_path])
            else: # bsdiff
                cmd.extend([src_path, tgt_path, patch_path])

            # Use subprocess.run for better control and error capturing
            process = subprocess.run(cmd, capture_output=True, text=False, check=False)

            if process.returncode != 0:
                error_output = process.stderr.decode(errors='replace') if process.stderr else "No stderr output."
                error_msg = self.lang.get(
                    "imgdiff_error_diff_tool_failed",
                    default_text="Diff tool '{tool}' failed for {target_name} (source: {source_name}). Exit code: {code}. Error: {error_output}",
                    tool=tool_name, target_name=xf.tgt_name, source_name=xf.src_name,
                    code=process.returncode, error_output=error_output
                )
                raise ValueError(error_msg)

            with open(patch_path, "rb") as f_patch:
                return f_patch.read()

        finally:
            # Clean up temporary files
            for p in [src_path, tgt_path, patch_path]:
                try:
                    if os.path.exists(p):
                        os.unlink(p)
                except OSError as e:
                    self.logger.warning(f"Failed to delete temporary file {p}: {e}")


    def Compute(self, prefix: str):
        """
        Main computation orchestrator.
        prefix: Base name for output files (e.g., "ota_package/ Абсолютный путь или относительный ")
        """
        self.AbbreviateSourceNames()
        self.FindTransfers()

        self.GenerateDigraph()
        self.FindVertexSequence()

        if self.version == 1:
            self.RemoveBackwardEdges()
        else:
            self.ReverseBackwardEdges()
            self.ImproveVertexSequence()

        if self.version >= 2 and self.cache_size_bytes is not None:
            self.ReviseStashSize()

        self.AssertSequenceGood()
        self.ComputePatches(prefix)
        self.WriteTransfers(prefix)

    def HashBlocks(self, image_source: Image, ranges: RangeSet) -> str:
        """Hashes data from specified ranges of an image source."""
        ctx = hashlib.sha1()
        for chunk in image_source.ReadRangeSet(ranges):
            ctx.update(chunk)
        return ctx.hexdigest()

    def WriteTransfers(self, prefix: str):
        """Writes the transfer list file."""
        out_lines = []
        total_target_blocks_written = 0
        stashes = {}  # For v3+: sha_hex -> count; For v2: id -> None (presence implies stashed)
        stashed_blocks_count = 0
        max_stashed_blocks_count = 0
        free_stash_ids_v2 = [] # Min-heap of available stash IDs for version 2
        next_stash_id_v2 = 0

        for xf in self.transfers:
            if self.version < 2:
                assert not xf.stash_before and not xf.use_stash

            # Handle stashing blocks before the transfer
            for stash_id_or_sha, stash_ranges in xf.stash_before:
                if self.version == 2: # stash_id_or_sha is an ID
                    sid = stash_id_or_sha
                    assert sid not in stashes, f"Stash ID {sid} already in use"
                    stashes[sid] = True # Mark as active
                    out_lines.append(f"stash {sid:d} {stash_ranges.to_string_raw()}\n")
                else: # self.version >= 3, stash_id_or_sha is a SHA1 hash
                    sha_hex = stash_id_or_sha
                    if sha_hex not in stashes:
                        stashes[sha_hex] = 0
                        # Only count blocks and add stash command for the first occurrence of this SHA
                        stashed_blocks_count += stash_ranges.size()
                        self.touched_src_ranges = self.touched_src_ranges.union(stash_ranges)
                        out_lines.append(f"stash {sha_hex} {stash_ranges.to_string_raw()}\n")
                    stashes[sha_hex] += 1
                if self.version != 2: # For v3+, stashed_blocks_count updated above for unique SHAs
                    pass # Stashed_blocks_count for v3+ is based on unique content
                else: # For v2, all stashed blocks count
                     stashed_blocks_count += stash_ranges.size()


            max_stashed_blocks_count = max(max_stashed_blocks_count, stashed_blocks_count)

            # Prepare source string for v2+ commands
            src_str_parts = []
            if self.version >= 2:
                src_size = xf.src_ranges.size()
                src_str_parts.append(str(src_size))

                unstashed_src_ranges_in_xf = xf.src_ranges
                mapped_stashes_for_xf = [] # For AssertPartition

                temp_free_cmds = []
                temp_freed_blocks_count = 0

                for stash_id_or_sha, ranges_to_use_from_stash in xf.use_stash:
                    # Map these ranges *within the context of xf.src_ranges*
                    # This `sr_in_xf_space` is what the command script expects.
                    sr_in_xf_space = xf.src_ranges.map_within(ranges_to_use_from_stash)
                    mapped_stashes_for_xf.append(sr_in_xf_space)
                    
                    unstashed_src_ranges_in_xf = unstashed_src_ranges_in_xf.subtract(ranges_to_use_from_stash)

                    if self.version == 2:
                        sid = stash_id_or_sha
                        assert stashes.pop(sid, None), f"Stash ID {sid} not found for use"
                        src_str_parts.append(f"{sid:d}:{sr_in_xf_space.to_string_raw()}")
                        heappush(free_stash_ids_v2, sid) # Make ID available again
                        temp_free_cmds.append(f"free {sid:d}\n")
                        temp_freed_blocks_count += ranges_to_use_from_stash.size() # Original size
                    else: # self.version >= 3
                        sha_hex = stash_id_or_sha
                        assert sha_hex in stashes and stashes[sha_hex] > 0, f"Stash SHA {sha_hex} not found or count is zero"
                        stashes[sha_hex] -= 1
                        src_str_parts.append(f"{sha_hex}:{sr_in_xf_space.to_string_raw()}")
                        if stashes[sha_hex] == 0:
                            stashes.pop(sha_hex)
                            temp_free_cmds.append(f"free {sha_hex}\n")
                            # Freed blocks only count if the SHA is no longer referenced
                            temp_freed_blocks_count += ranges_to_use_from_stash.size()


                if unstashed_src_ranges_in_xf.size() > 0:
                    src_str_parts.insert(1, unstashed_src_ranges_in_xf.to_string_raw())
                    if xf.use_stash: # If stashes were used, need to add mapped unstashed ranges
                        mapped_unstashed = xf.src_ranges.map_within(unstashed_src_ranges_in_xf)
                        src_str_parts.insert(2, mapped_unstashed.to_string_raw())
                        mapped_stashes_for_xf.append(mapped_unstashed)
                    # Assert that the combination of stashed and unstashed parts perfectly covers the original xf.src_ranges (mapped to 0..size)
                    if mapped_stashes_for_xf:
                         self.AssertPartition(RangeSet(data=(0, src_size)), mapped_stashes_for_xf)

                elif xf.src_ranges.size() > 0 : # All source blocks came from stash
                    src_str_parts.insert(1, "-")
                    self.AssertPartition(RangeSet(data=(0, src_size)), mapped_stashes_for_xf)
                # If xf.src_ranges.size() == 0 (e.g. for "new"), src_str_parts might be just ['0'] or similar
                
                final_src_str = " ".join(src_str_parts)

            # Construct the command line
            cmd_line = ""
            tgt_size_current_xf = xf.tgt_ranges.size()

            if xf.style == "new":
                assert xf.tgt_ranges.size() > 0
                cmd_line = f"new {xf.tgt_ranges.to_string_raw()}\n"
            elif xf.style == "move":
                assert xf.tgt_ranges.size() > 0 and xf.src_ranges.size() == tgt_size_current_xf
                if xf.src_ranges != xf.tgt_ranges: # No command if src and tgt ranges are identical
                    if self.version == 1:
                        cmd_line = f"move {xf.src_ranges.to_string_raw()} {xf.tgt_ranges.to_string_raw()}\n"
                    elif self.version == 2:
                        cmd_line = f"move {xf.tgt_ranges.to_string_raw()} {final_src_str}\n"
                    else: # version >= 3
                        if xf.src_ranges.overlaps(xf.tgt_ranges): # Potential implicit stash
                             max_stashed_blocks_count = max(max_stashed_blocks_count, stashed_blocks_count + xf.src_ranges.size())
                        self.touched_src_ranges = self.touched_src_ranges.union(xf.src_ranges)
                        tgt_hash = self.HashBlocks(self.tgt, xf.tgt_ranges)
                        cmd_line = f"move {tgt_hash} {xf.tgt_ranges.to_string_raw()} {final_src_str}\n"
            elif xf.style in ("bsdiff", "imgdiff"):
                assert xf.tgt_ranges.size() > 0 and xf.src_ranges.size() > 0
                if self.version == 1:
                    cmd_line = f"{xf.style} {xf.patch_start:d} {xf.patch_len:d} {xf.src_ranges.to_string_raw()} {xf.tgt_ranges.to_string_raw()}\n"
                elif self.version == 2:
                    cmd_line = f"{xf.style} {xf.patch_start:d} {xf.patch_len:d} {xf.tgt_ranges.to_string_raw()} {final_src_str}\n"
                else: # version >= 3
                    if xf.src_ranges.overlaps(xf.tgt_ranges): # Potential implicit stash
                        max_stashed_blocks_count = max(max_stashed_blocks_count, stashed_blocks_count + xf.src_ranges.size())
                    self.touched_src_ranges = self.touched_src_ranges.union(xf.src_ranges)
                    src_hash = self.HashBlocks(self.src, xf.src_ranges)
                    tgt_hash = self.HashBlocks(self.tgt, xf.tgt_ranges)
                    cmd_line = f"{xf.style} {xf.patch_start:d} {xf.patch_len:d} {src_hash} {tgt_hash} {xf.tgt_ranges.to_string_raw()} {final_src_str}\n"
            elif xf.style == "zero":
                assert xf.tgt_ranges.size() > 0
                # Only zero out blocks in tgt_ranges that are not already meant to be zero from src_ranges
                # (though 'zero' typically implies tgt should be zero regardless of src content for these blocks)
                ranges_to_make_zero = xf.tgt_ranges # Original interpretation implies all of tgt_ranges becomes zero.
                # If it meant "zero out blocks in tgt that were NOT zero in src", it would be:
                # ranges_to_make_zero = xf.tgt_ranges.subtract(xf.src_ranges.intersect(self.src.file_map.get("__ZERO", RangeSet())))
                
                written_count = self._write_zero_commands(out_lines, ranges_to_make_zero) # Appends to out_lines
                tgt_size_current_xf = written_count # Actual blocks zeroed
                cmd_line = None # Commands already added by _write_zero_commands
            else:
                raise ValueError(self.lang.get("imgdiff_error_unknown_transfer_style",
                                               default_text="Unknown transfer style '{style}'", style=xf.style))

            if cmd_line:
                out_lines.append(cmd_line)
            total_target_blocks_written += tgt_size_current_xf
            
            if temp_free_cmds:
                out_lines.extend(temp_free_cmds)
                stashed_blocks_count -= temp_freed_blocks_count


            # Sanity check for stash limits (if cache_size_bytes is known)
            if self.version >= 2 and self.cache_size_bytes is not None:
                max_allowed_stash_bytes = self.cache_size_bytes * self.stash_threshold
                current_max_stashed_bytes = max_stashed_blocks_count * self.tgt.blocksize
                if current_max_stashed_bytes > max_allowed_stash_bytes:
                    error_msg = self.lang.get(
                        "imgdiff_error_stash_exceeds_limit",
                        default_text="Stash size {stash_bytes} ({stash_blocks} * {block_size}) exceeds the limit {max_allowed_bytes} ({cache_size_bytes} * {threshold:.2f}). Cannot proceed.",
                        stash_bytes=current_max_stashed_bytes, stash_blocks=max_stashed_blocks_count,
                        block_size=self.tgt.blocksize, max_allowed_bytes=int(max_allowed_stash_bytes),
                        cache_size_bytes=self.cache_size_bytes, threshold=self.stash_threshold
                    )
                    self.logger.error(error_msg)
                    raise RuntimeError(error_msg) # Fatal error

        if self.version >= 3:
            self.touched_src_sha1 = self.HashBlocks(self.src, self.touched_src_ranges)

        # Zero out extended blocks (b=20881595)
        if self.tgt.extended.size() > 0:
            written_count = self._write_zero_commands(out_lines, self.tgt.extended)
            total_target_blocks_written += written_count
        
        # Erase unused blocks (b=28347095)
        all_target_device_blocks = RangeSet(data=(0, self.tgt.total_blocks))
        target_blocks_minus_extended = all_target_device_blocks.subtract(self.tgt.extended)
        new_image_dont_care_blocks = target_blocks_minus_extended.subtract(self.tgt.care_map)

        erase_at_beginning = new_image_dont_care_blocks.subtract(self.touched_src_ranges)
        if erase_at_beginning.size() > 0:
            out_lines.insert(0, f"erase {erase_at_beginning.to_string_raw()}\n")

        erase_at_end = new_image_dont_care_blocks.subtract(erase_at_beginning)
        if erase_at_end.size() > 0:
            out_lines.append(f"erase {erase_at_end.to_string_raw()}\n")

        # Header lines for the transfer list
        header = [f"{self.version:d}\n", f"{total_target_blocks_written:d}\n"]
        if self.version >= 2:
            actual_next_stash_id_v2 = next_stash_id_v2
            if self.version == 2 : # For v2, count actual unique stash IDs used.
                 # Reconstruct next_stash_id_v2 based on actual usage if necessary
                 # For simplicity, assume next_stash_id_v2 was correctly incremented when IDs were allocated.
                 # A more robust way would be to find max sid used if they weren't sequential.
                 # However, the original logic with heappop/heappush for free_stash_ids_v2
                 # and incrementing next_stash_id_v2 should manage this.
                 # Let's find the max ID actually used by inspecting stash commands.
                 max_sid_in_use_v2 = -1
                 for xf_check_stash in self.transfers:
                     for sid, _ in xf_check_stash.stash_before:
                         if self.version == 2: max_sid_in_use_v2 = max(max_sid_in_use_v2, sid)
                 actual_next_stash_id_v2 = max_sid_in_use_v2 + 1 if max_sid_in_use_v2 != -1 else 0


            header.append(f"{actual_next_stash_id_v2:d}\n")
            header.append(f"{max_stashed_blocks_count:d}\n")
        
        out_lines = header + out_lines

        # Write to file
        transfer_list_path = prefix + ".transfer.list"
        with open(transfer_list_path, "wb") as f: # Use wb for bytes
            for line_content in out_lines:
                f.write(line_content.encode("UTF-8"))
        
        self._max_stashed_size = max_stashed_blocks_count * self.tgt.blocksize
        if self.cache_size_bytes is not None:
            max_allowed_b = self.cache_size_bytes * self.stash_threshold
            percentage = (self._max_stashed_size * 100.0 / max_allowed_b) if max_allowed_b > 0 else float('inf')
            self.logger.info(self.lang.get("imgdiff_info_max_stashed_limit",
                default_text="Max stashed blocks: {blocks} ({bytes} bytes), limit: {limit_bytes} bytes ({percentage:.2f}%)",
                blocks=max_stashed_blocks_count, bytes=self._max_stashed_size,
                limit_bytes=int(max_allowed_b), percentage=percentage
            ))
        else:
            self.logger.info(self.lang.get("imgdiff_info_max_stashed_unknown_limit",
                default_text="Max stashed blocks: {blocks} ({bytes} bytes), limit: <unknown>",
                blocks=max_stashed_blocks_count, bytes=self._max_stashed_size
            ))

    def _write_zero_commands(self, out_lines_list, ranges_to_zero: RangeSet, limit_per_cmd=1024):
        """Helper to write 'zero' commands, respecting a block limit per command."""
        blocks_zeroed = 0
        current_ranges = ranges_to_zero
        while current_ranges.size() > 0:
            chunk_to_zero = current_ranges.first(limit_per_cmd)
            out_lines_list.append(f"zero {chunk_to_zero.to_string_raw()}\n")
            blocks_zeroed += chunk_to_zero.size()
            current_ranges = current_ranges.subtract(chunk_to_zero)
        return blocks_zeroed


    def ReviseStashSize(self):
        """Revises stash usage if it exceeds configured limits."""
        self.logger.info(self.lang.get("imgdiff_info_revising_stash", default_text="Revising stash size..."))
        
        # Map: stash_id_or_sha -> (RangeSet, defining_transfer, using_transfer)
        # For v2, key is stash_id. For v3+, key is SHA.
        stash_definitions = {} 

        for xf in self.transfers:
            for id_or_sha, sr in xf.stash_before:
                # defining_transfer is xf itself
                stash_definitions[id_or_sha] = (sr, xf, None) 
            for id_or_sha, _ in xf.use_stash:
                 # using_transfer is xf
                if id_or_sha in stash_definitions: # Should always be true if graph is correct
                    sr, def_cmd, _ = stash_definitions[id_or_sha]
                    stash_definitions[id_or_sha] = (sr, def_cmd, xf)
                else: # Should not happen in a correctly processed graph
                    self.logger.warning(f"Stash {id_or_sha} used by {xf} but no definition found.")


        max_allowed_blocks = (self.cache_size_bytes * self.stash_threshold) // self.tgt.blocksize
        
        current_stashed_blocks = 0
        converted_to_new_blocks = 0

        for xf in self.transfers:
            commands_to_convert_to_new = set() # Use set to avoid duplicate conversions

            # Check explicit stashes defined by xf (xf.stash_before)
            for id_or_sha, sr_stashed in xf.stash_before:
                # If stashing this would exceed the limit
                if current_stashed_blocks + sr_stashed.size() > max_allowed_blocks:
                    # Find the command that uses this stash and convert IT to "new"
                    _, _, use_cmd = stash_definitions.get(id_or_sha, (None, None, None))
                    if use_cmd and use_cmd.style != "new": # Avoid re-converting
                        commands_to_convert_to_new.add(use_cmd)
                        self.logger.info(f"  Will convert {use_cmd} (uses {id_or_sha}) to NEW due to stash limit for explicit stash {sr_stashed.size()} blocks.")
                else:
                    # Tentatively add to stash (will be confirmed or removed if use_cmd is converted)
                    # This count is only for *active* stashes.
                    pass # Actual increment happens after checking use_cmd conversion status.

            # Check implicit stashes for 'move' or 'diff' in v3+ (which might be xf itself)
            if self.version >= 3 and xf.style in ("move", "diff"): # "diff" is pre-patch-computation style for both
                if xf.src_ranges.overlaps(xf.tgt_ranges):
                    # This overlap implies an implicit stash of xf.src_ranges
                    if current_stashed_blocks + xf.src_ranges.size() > max_allowed_blocks:
                        if xf.style != "new": # Avoid re-converting
                             commands_to_convert_to_new.add(xf)
                             self.logger.info(f"  Will convert {xf} to NEW due to stash limit for implicit stash {xf.src_ranges.size()} blocks.")
            
            # Now, process conversions and update actual stashed_blocks
            for cmd_to_new in commands_to_convert_to_new:
                if cmd_to_new.style == "new": continue # Already converted

                # For each stash this command *would have used*, remove it from its definer
                for used_id_or_sha, used_sr in cmd_to_new.use_stash:
                    _, def_cmd, _ = stash_definitions.get(used_id_or_sha, (None,None,None))
                    if def_cmd:
                        try:
                            def_cmd.stash_before.remove((used_id_or_sha, used_sr))
                            # If this was the only use of this stash, the blocks are not "stashed"
                            # This part is tricky: current_stashed_blocks should reflect active stashes.
                            # This loop is more about preventing future stashing than decrementing current_stashed_blocks
                        except ValueError:
                            pass # Item might have been removed by another conversion path

                converted_to_new_blocks += cmd_to_new.tgt_ranges.size()
                cmd_to_new.ConvertToNew()
                self.logger.info(f"    Converted {cmd_to_new} to NEW.")

            # Update current_stashed_blocks based on xf's *actual* stash operations
            # (after potential modifications to stash_before by converting users)
            for _, sr in xf.stash_before: # These are stashes xf *still* makes
                current_stashed_blocks += sr.size()
            
            for _, sr in xf.use_stash: # These are stashes xf *still* uses
                current_stashed_blocks -= sr.size()


        if converted_to_new_blocks > 0:
            num_bytes = converted_to_new_blocks * self.tgt.blocksize
            self.logger.info(self.lang.get("imgdiff_info_packed_as_new_due_to_cache",
                default_text="Total {blocks} blocks ({bytes} bytes) are packed as new blocks due to insufficient cache size.",
                blocks=converted_to_new_blocks, bytes=num_bytes
            ))

    def ComputePatches(self, prefix: str):
        """Computes patches for 'diff' transfers using multiple threads."""
        self.logger.info(self.lang.get("imgdiff_info_preparing_diff_data", default_text="Preparing data for diffing..."))

        # Transfers that need patch computation
        diff_tasks = [] 
        # Data for "new" transfers
        new_data_chunks = []

        for xf in self.transfers:
            if xf.style == "new":
                for piece in self.tgt.ReadRangeSet(xf.tgt_ranges):
                    new_data_chunks.append(piece)
            elif xf.style == "diff": # Original style before checking for identical data
                # Read data now to avoid issues with data changing if src/tgt are complex objects
                # Ensure ReadRangeSet returns iterables that can be consumed multiple times or store them
                src_data_list = list(self.src.ReadRangeSet(xf.src_ranges))
                tgt_data_list = list(self.tgt.ReadRangeSet(xf.tgt_ranges))

                src_sha1 = hashlib.sha1()
                for p in src_data_list: src_sha1.update(p)
                
                tgt_sha1 = hashlib.sha1()
                tgt_byte_count = 0
                for p in tgt_data_list: 
                    tgt_sha1.update(p)
                    tgt_byte_count += len(p)

                if src_sha1.digest() == tgt_sha1.digest():
                    xf.style = "move" # Identical data, no patch needed
                else:
                    # Determine if imgdiff can be used
                    use_imgdiff = (not self.disable_imgdiff and xf.intact and
                                   xf.tgt_name.split(".")[-1].lower() in ("apk", "jar", "zip"))
                    xf.style = "imgdiff" if use_imgdiff else "bsdiff"
                    # Add task: (src_data_iter, tgt_data_iter, transfer_object, original_target_byte_count)
                    diff_tasks.append((src_data_list, tgt_data_list, xf, tgt_byte_count))
            # "zero" and "move" (if already set) styles don't need patch computation here

        # Write .new.dat file
        new_dat_path = prefix + ".new.dat"
        with open(new_dat_path, "wb") as f_new:
            for chunk in new_data_chunks:
                f_new.write(chunk)

        # Compute patches if there are tasks
        # Store patches indexed by a unique ID from the transfer if needed, or process in order
        # The original code used patch_num. We can use the transfer object's ID or index.
        # Let's keep patches in a list corresponding to diff_tasks order.
        
        computed_patches = [None] * len(diff_tasks) # To store (patch_data, original_xf_object)

        if diff_tasks:
            if self.threads > 1:
                self.logger.info(self.lang.get("imgdiff_info_computing_patches_threads",
                                               default_text="Computing patches (using {threads} threads)...",
                                               threads=self.threads))
            else:
                self.logger.info(self.lang.get("imgdiff_info_computing_patches_single_thread",
                                               default_text="Computing patches..."))

            # Sort tasks by target size (original heuristic) - for potentially better processing order
            # Though with ThreadPoolExecutor, order of submission vs completion can vary.
            # The primary benefit of sorting was for the print order in the original single-threaded-like loop.
            diff_tasks.sort(key=lambda item: item[3], reverse=True) # item[3] is tgt_byte_count

            patch_results = {} # Store results: xf.id -> (patch_data, style, name, patch_size, tgt_size)
                               # or xf.id -> Exception
            
            with ThreadPoolExecutor(max_workers=self.threads) as executor:
                future_to_xf_idx = {
                    executor.submit(self._compute_patch_for_transfer, src_d, tgt_d, xf_task): idx
                    for idx, (src_d, tgt_d, xf_task, _) in enumerate(diff_tasks)
                }

                for future in as_completed(future_to_xf_idx):
                    idx = future_to_xf_idx[future]
                    _, _, xf_task, tgt_size_bytes = diff_tasks[idx]
                    try:
                        patch_data = future.result()
                        computed_patches[idx] = (patch_data, xf_task) # Store result
                        
                        patch_size_bytes = len(patch_data)
                        percentage = (patch_size_bytes * 100.0 / tgt_size_bytes) if tgt_size_bytes > 0 else 0.0
                        log_name = xf_task.tgt_name
                        if xf_task.tgt_name != xf_task.src_name and xf_task.src_name:
                            log_name += f" (from {xf_task.src_name})"

                        self.logger.info(self.lang.get("imgdiff_info_patch_stats",
                            default_text="{patch_size:>10d} {target_size:>10d} ({percentage:6.2f}%) {style:>7} {name}",
                            patch_size=patch_size_bytes, target_size=tgt_size_bytes,
                            percentage=percentage, style=xf_task.style, name=log_name
                        ))
                    except Exception as e:
                        # Store exception to handle later or re-raise
                        computed_patches[idx] = (e, xf_task) 
                        self.logger.error(self.lang.get("imgdiff_error_patch_computation_failed",
                            default_text="Patch computation failed for {target_name}: {error}",
                            target_name=xf_task.tgt_name, error=str(e)
                        ))
                        # Optionally, re-raise if one failure should stop everything: raise
            
            # Check for failures
            for result, xf_task_check in computed_patches:
                if isinstance(result, Exception):
                    # Decide on error handling strategy: aggregate errors or raise first one
                    raise RuntimeError(f"Patch computation failed for {xf_task_check.tgt_name}. See logs for details.") from result


        # Write .patch.dat file
        patch_dat_path = prefix + ".patch.dat"
        current_patch_offset = 0
        with open(patch_dat_path, "wb") as f_patch:
            # Iterate through computed_patches which maintains original order of diff_tasks
            for item in computed_patches:
                if item is None: continue # Should not happen if all tasks processed
                patch_data, xf_ref = item 
                
                if isinstance(patch_data, Exception): # Already handled by raising above
                    continue

                xf_ref.patch_start = current_patch_offset
                xf_ref.patch_len = len(patch_data)
                f_patch.write(patch_data)
                current_patch_offset += len(patch_data)


    def AssertSequenceGood(self):
        """Validates the transfer sequence for correctness."""
        touched_target_blocks = array("B", (0,) * self.tgt.total_blocks)

        for xf in self.transfers:
            # Determine source blocks actually read from device (not from stash)
            source_blocks_from_device = xf.src_ranges
            if self.version >= 2:
                for _, stashed_ranges_used_by_xf in xf.use_stash:
                    source_blocks_from_device = source_blocks_from_device.subtract(stashed_ranges_used_by_xf)

            # Check: source blocks read from device must not have been touched (written to) yet
            for s, e in source_blocks_from_device:
                # Iterate only over blocks that are actually on the target device
                # (source image could be larger or have different block mapping)
                for i in range(s, min(e, self.tgt.total_blocks)):
                    assert touched_target_blocks[i] == 0, \
                        f"Block {i} read by transfer {xf} but already written."

            # Check: target blocks written by this transfer must not have been touched yet
            # Then, mark them as touched.
            for s, e in xf.tgt_ranges:
                for i in range(s, e):
                    assert touched_target_blocks[i] == 0, \
                        f"Block {i} written by transfer {xf} but already written (target overlap)."
                    touched_target_blocks[i] = 1
        
        # Check: all blocks in target's care_map must have been written exactly once
        for s, e in self.tgt.care_map:
            for i in range(s, e):
                assert touched_target_blocks[i] == 1, \
                    f"Target care_map block {i} was not written."
        self.logger.debug("Transfer sequence asserted good.")


    def ImproveVertexSequence(self):
        self.logger.info(self.lang.get("imgdiff_info_improving_order", default_text="Improving vertex order..."))
        for xf in self.transfers:
            xf.incoming = xf.goes_after.copy()
            xf.outgoing = xf.goes_before.copy()

        ordered_transfers = []
        # S is a min-heap of (net_stash_change, original_order, transfer_object)
        # We want to pick transfers that reduce stash or keep it small.
        source_nodes = [(u.NetStashChange(), u.order, u) for u in self.transfers if not u.incoming]
        heapify(source_nodes)

        while source_nodes:
            _, _, current_xf = heappop(source_nodes)
            ordered_transfers.append(current_xf)
            # For each neighbor 'm' of current_xf (i.e., current_xf -> m)
            for neighbor_xf in list(current_xf.outgoing.keys()): # Iterate copy as it's modified
                del neighbor_xf.incoming[current_xf] # Remove edge current_xf -> neighbor_xf
                if not neighbor_xf.incoming: # If neighbor_xf becomes a source node
                    heappush(source_nodes, (neighbor_xf.NetStashChange(), neighbor_xf.order, neighbor_xf))
        
        assert len(ordered_transfers) == len(self.transfers), "Cycle detected or error in topological sort."
        self.transfers = ordered_transfers
        for i, xf in enumerate(self.transfers):
            xf.order = i # Update order based on new sequence

    def RemoveBackwardEdges(self): # Specific to version 1
        self.logger.info(self.lang.get("imgdiff_info_removing_backward_edges",
                                      default_text="Removing backward edges (v1 method)..."))
        in_order_deps = 0
        out_of_order_deps = 0
        total_lost_source_blocks = 0

        for xf in self.transfers:
            original_src_size = xf.src_ranges.size()
            # Check edges xf -> u (xf.goes_before links to u)
            for u_neighbor in list(xf.goes_before.keys()): # Iterate copy
                if xf.order < u_neighbor.order: # Edge is in correct order
                    in_order_deps += 1
                else: # Backward edge: xf.order >= u_neighbor.order, but xf should be before u_neighbor
                    out_of_order_deps += 1
                    # Trim blocks from xf's source that u_neighbor writes
                    # This allows xf to (conceptually) go after u_neighbor
                    xf.src_ranges = xf.src_ranges.subtract(u_neighbor.tgt_ranges)
                    xf.intact = False # Source integrity potentially compromised for imgdiff

            if xf.style == "diff" and not xf.src_ranges:
                xf.style = "new" # No source data left, convert to new
            
            total_lost_source_blocks += (original_src_size - xf.src_ranges.size())

        if (in_order_deps + out_of_order_deps) > 0:
            percentage_violated = (out_of_order_deps * 100.0 / (in_order_deps + out_of_order_deps))
        else:
            percentage_violated = 0.0
        
        self.logger.info(self.lang.get("imgdiff_info_backward_edges_stats_v1",
            default_text="  {out_of_order}/{total} dependencies ({percentage:.2f}%) were violated; {lost_source} source blocks removed.",
            out_of_order=out_of_order_deps, total=(in_order_deps + out_of_order_deps),
            percentage=percentage_violated, lost_source=total_lost_source_blocks
        ))

    def ReverseBackwardEdges(self): # Specific to version >= 2
        self.logger.info(self.lang.get("imgdiff_info_reversing_backward_edges",
                                      default_text="Reversing backward edges (v2+ method)..."))
        in_order_deps = 0
        out_of_order_deps = 0
        next_stash_entity_id = 0 # Unique ID for v2 stashes, or placeholder for v3+ SHA logic
        total_stashed_blocks = 0

        for xf in self.transfers:
            # Check edges xf -> u_neighbor (xf.goes_before links to u_neighbor)
            for u_neighbor in list(xf.goes_before.keys()): # Iterate copy
                if xf.order < u_neighbor.order: # Edge is in correct order
                    in_order_deps += 1
                else: # Backward edge: xf.order >= u_neighbor.order
                    out_of_order_deps += 1
                    
                    # Identify overlapping blocks: u_neighbor writes these, xf reads them
                    overlap = xf.src_ranges.intersect(u_neighbor.tgt_ranges)
                    assert overlap.size() > 0, "Backward edge without overlap?"

                    stash_entity_key = ""
                    if self.version == 2:
                        stash_entity_key = next_stash_entity_id
                        next_stash_entity_id +=1
                    else: # version >=3, use SHA1 of the overlapping content from source
                         # Note: This implies self.src must be available and correct
                        stash_entity_key = self.HashBlocks(self.src, overlap)

                    # u_neighbor must stash these blocks *before* it writes to its target
                    u_neighbor.stash_before.append((stash_entity_key, overlap))
                    # xf will use these blocks from stash
                    xf.use_stash.append((stash_entity_key, overlap))
                    
                    total_stashed_blocks += overlap.size()

                    # Reverse the dependency: now u_neighbor must go before xf
                    del xf.goes_before[u_neighbor]
                    del u_neighbor.goes_after[xf]
                    u_neighbor.goes_before[xf] = None # Weight/value might not be critical after reversal
                    xf.goes_after[u_neighbor] = None
        
        if (in_order_deps + out_of_order_deps) > 0:
            percentage_violated = (out_of_order_deps * 100.0 / (in_order_deps + out_of_order_deps))
        else:
            percentage_violated = 0.0

        self.logger.info(self.lang.get("imgdiff_info_reversed_edges_stats_v2plus",
            default_text="  {out_of_order}/{total} dependencies ({percentage:.2f}%) were violated; {stashed_size} source blocks stashed.",
            out_of_order=out_of_order_deps, total=(in_order_deps + out_of_order_deps),
            percentage=percentage_violated, stashed_size=total_stashed_blocks
        ))

    def FindVertexSequence(self):
        self.logger.info(self.lang.get("imgdiff_info_finding_vertex_sequence",
                                      default_text="Finding vertex sequence..."))
        for xf in self.transfers:
            xf.incoming = xf.goes_after.copy() # Edges u -> xf
            xf.outgoing = xf.goes_before.copy() # Edges xf -> u
            # Score: sum of weights of outgoing edges minus sum of weights of incoming edges
            xf.score = sum(xf.outgoing.values()) - sum(xf.incoming.values())
            # Add HeapItem for efficient retrieval in the main loop
            # xf.heap_item is set and managed inside the loop now

        # G is the set of all vertices not yet placed in s1 or s2
        # Using OrderedDict for deterministic behavior if scores are equal (though heap stability also matters)
        G_nodes = OrderedDict((xf, None) for xf in self.transfers)
        
        s1_sequence = deque()  # Sequence from left to right
        s2_sequence = deque()  # Sequence from right to left (elements added to left of deque)

        # Max-heap based on score (using negated scores for min-heap)
        # Store (HeapItem(item)) to allow item.clear()
        # Heap stores HeapItem instances
        # Initialize heap_item for each transfer
        for xf_node in self.transfers:
            xf_node.heap_item = HeapItem(xf_node)
        
        # Heap stores HeapItem objects directly
        active_heap = [xf.heap_item for xf in self.transfers]
        heapify(active_heap)

        # Helper to update score and re-heapify (or use a heap that supports update-priority)
        # Python's heapq doesn't directly support update. Standard way: mark old invalid, add new.
        def update_score_in_heap(item_to_update, delta_score):
            # Invalidate the old entry in heap (heap_item.clear())
            # This means the main loop needs to check if popped item is valid.
            if hasattr(item_to_update, 'heap_item') and item_to_update.heap_item:
                 item_to_update.heap_item.clear() 
            
            item_to_update.score += delta_score
            item_to_update.heap_item = HeapItem(item_to_update) # New HeapItem with updated score
            heappush(active_heap, item_to_update.heap_item)

        while G_nodes:
            # Process sinks: nodes with no outgoing edges in G
            sinks_in_G = {node for node in G_nodes if not node.outgoing}
            while sinks_in_G:
                u_sink = sinks_in_G.pop() # Get an arbitrary sink
                if u_sink not in G_nodes: continue # Already processed

                s2_sequence.appendleft(u_sink)
                del G_nodes[u_sink]
                if hasattr(u_sink, 'heap_item') and u_sink.heap_item: u_sink.heap_item.clear() # Remove from heap consideration

                # For each predecessor 'v' of u_sink (v -> u_sink)
                for v_predecessor in list(u_sink.incoming.keys()):
                    if v_predecessor in G_nodes: # If predecessor is still in G
                        edge_weight = v_predecessor.outgoing.pop(u_sink)
                        update_score_in_heap(v_predecessor, -edge_weight) # Score increases as an outgoing edge is removed
                        if not v_predecessor.outgoing: # If v_predecessor becomes a sink
                            sinks_in_G.add(v_predecessor)
            
            # Process sources: nodes with no incoming edges in G
            sources_in_G = {node for node in G_nodes if not node.incoming}
            while sources_in_G:
                u_source = sources_in_G.pop()
                if u_source not in G_nodes: continue

                s1_sequence.append(u_source)
                del G_nodes[u_source]
                if hasattr(u_source, 'heap_item') and u_source.heap_item: u_source.heap_item.clear()

                # For each successor 'v' of u_source (u_source -> v)
                for v_successor in list(u_source.outgoing.keys()):
                     if v_successor in G_nodes:
                        edge_weight = v_successor.incoming.pop(u_source)
                        update_score_in_heap(v_successor, +edge_weight) # Score decreases as an incoming edge is removed
                        if not v_successor.incoming: # If v_successor becomes a source
                            sources_in_G.add(v_successor)
            
            if not G_nodes: break # All nodes processed

            # Select node with max score from G (not yet a source or sink)
            # Pop from heap until a valid item in G_nodes is found
            selected_u = None
            while active_heap:
                heap_item_u = heappop(active_heap)
                if heap_item_u and heap_item_u.item in G_nodes: # Check if item is valid and in G
                    selected_u = heap_item_u.item
                    break
            
            if not selected_u: # Should not happen if G_nodes is not empty
                if G_nodes: raise AssertionError("Heap empty but G_nodes not empty")
                break 

            s1_sequence.append(selected_u) # Add to left sequence
            del G_nodes[selected_u]
            # No need to clear heap_item here as it's already popped.

            # Update scores of neighbors of selected_u
            # For successors v (selected_u -> v):
            for v_successor in list(selected_u.outgoing.keys()):
                if v_successor in G_nodes:
                    edge_weight = v_successor.incoming.pop(selected_u)
                    update_score_in_heap(v_successor, +edge_weight)
                    if not v_successor.incoming: sources_in_G.add(v_successor) # Became a source

            # For predecessors v (v -> selected_u):
            for v_predecessor in list(selected_u.incoming.keys()):
                if v_predecessor in G_nodes:
                    edge_weight = v_predecessor.outgoing.pop(selected_u)
                    update_score_in_heap(v_predecessor, -edge_weight)
                    if not v_predecessor.outgoing: sinks_in_G.add(v_predecessor) # Became a sink

        # Combine s1 and s2 to form the final sequence
        final_ordered_transfers = list(s1_sequence) + list(s2_sequence)
        assert len(final_ordered_transfers) == len(self.transfers), "Sequence generation error."

        self.transfers = final_ordered_transfers
        for i, xf in enumerate(self.transfers):
            xf.order = i
            del xf.incoming # Clean up temporary attributes
            del xf.outgoing
            if hasattr(xf, 'heap_item'): del xf.heap_item


    def GenerateDigraph(self):
        self.logger.info(self.lang.get("imgdiff_info_generating_digraph",
                                      default_text="Generating digraph..."))
        
        # Map: block_index -> set of transfers reading this block
        # This can be large if source image is large.
        # Consider if self.src.total_blocks is a safe upper bound.
        # If src can be much larger than tgt, this might be an issue.
        # Assuming block indices are within a manageable range.
        max_src_block_idx = 0
        if self.src and self.src.total_blocks > 0:
             # Iterate through all src_ranges to find the max extent
            for xf_for_max in self.transfers:
                if xf_for_max.src_ranges.size() > 0:
                    # Get the maximum block index from the ranges
                    for _, end_idx in xf_for_max.src_ranges:
                        if end_idx > max_src_block_idx:
                            max_src_block_idx = end_idx
        
        # Initialize source_block_readers list/array
        # Using a list of sets for flexibility, None if no reader.
        source_block_readers = [None] * max_src_block_idx

        for xf_b in self.transfers: # 'b' for the transfer that reads (is a source user)
            for s, e in xf_b.src_ranges:
                for block_idx in range(s, e):
                    if block_idx < max_src_block_idx: # Ensure within bounds
                        if source_block_readers[block_idx] is None:
                            source_block_readers[block_idx] = {xf_b}
                        else:
                            source_block_readers[block_idx].add(xf_b)
        
        # For each transfer 'xf_a' (that writes to target):
        # Find all transfers 'xf_b' that read any block written by 'xf_a'.
        # If xf_a writes block X, and xf_b reads block X, then xf_b must go before xf_a.
        # This creates an edge: xf_b -> xf_a.
        # xf_b.goes_before[xf_a] = size_of_overlap
        # xf_a.goes_after[xf_b] = size_of_overlap
        for xf_a in self.transfers:
            writers_of_blocks_read_by_xf_a = set() # Not needed here, this is for read-after-write by same xf.
                                                # We are looking for xf_b reading what xf_a writes.
            
            intersecting_readers = set() # Set of xf_b's that read blocks xf_a writes to.
            for s, e in xf_a.tgt_ranges: # Blocks written by xf_a
                for block_idx in range(s, e):
                    if block_idx < max_src_block_idx and source_block_readers[block_idx] is not None:
                        intersecting_readers.update(source_block_readers[block_idx])

            for xf_b in intersecting_readers:
                if xf_a is xf_b: continue # A transfer cannot depend on itself in this manner

                # xf_b reads blocks that xf_a writes. So, xf_b must happen before xf_a.
                # This means there is a dependency: xf_b ----> xf_a
                overlap_ranges = xf_a.tgt_ranges.intersect(xf_b.src_ranges)
                if overlap_ranges.size() > 0:
                    # Cost/weight of this dependency edge
                    # If xf_b's source is __ZERO, cost is negligible as zero blocks are cheap to recreate.
                    edge_weight = 0 if xf_b.src_name == "__ZERO" else overlap_ranges.size()
                    
                    xf_b.goes_before[xf_a] = edge_weight
                    xf_a.goes_after[xf_b] = edge_weight


    def FindTransfers(self):
        """Generates all Transfer objects based on source and target file maps."""
        
        # Max blocks per transfer piece for diffs (v3+), helps manage stash.
        # 1/8th of cache size heuristic.
        max_blocks_per_diff_piece = -1 # Effectively no splitting if cache_size unknown
        if self.version >=3 and self.cache_size_bytes is not None and self.tgt.blocksize > 0:
             max_blocks_per_diff_piece = int((self.cache_size_bytes * 0.125) / self.tgt.blocksize)

        empty_rangeset = RangeSet()

        for tgt_fn, tgt_fn_ranges in self.tgt.file_map.items():
            if tgt_fn == "__ZERO":
                src_fn_ranges = self.src.file_map.get("__ZERO", empty_rangeset)
                self._AddTransferWrapper(tgt_fn, "__ZERO", tgt_fn_ranges, src_fn_ranges, "zero", max_blocks_per_diff_piece)
            elif tgt_fn == "__COPY": # Unconditional copy from target image data (effectively "new")
                self._AddTransferWrapper(tgt_fn, None, tgt_fn_ranges, empty_rangeset, "new", max_blocks_per_diff_piece)
            else:
                # Try to find a source for this target file
                src_fn_match = None
                src_fn_ranges_match = None

                if tgt_fn in self.src.file_map: # Exact path match
                    src_fn_match = tgt_fn
                    src_fn_ranges_match = self.src.file_map[tgt_fn]
                else:
                    basename_tgt = os.path.basename(tgt_fn)
                    if basename_tgt in self.src_basenames: # Exact basename match
                        src_fn_match = self.src_basenames[basename_tgt]
                        src_fn_ranges_match = self.src.file_map[src_fn_match]
                    else:
                        num_pattern_tgt = sub("[0-9]+", "#", basename_tgt)
                        if num_pattern_tgt in self.src_numpatterns: # Number pattern match
                            src_fn_match = self.src_numpatterns[num_pattern_tgt]
                            src_fn_ranges_match = self.src.file_map[src_fn_match]
                
                if src_fn_match and src_fn_ranges_match:
                    self._AddTransferWrapper(tgt_fn, src_fn_match, tgt_fn_ranges, src_fn_ranges_match,
                                            "diff", max_blocks_per_diff_piece)
                else: # No source found, treat as new
                    self._AddTransferWrapper(tgt_fn, None, tgt_fn_ranges, empty_rangeset, "new", max_blocks_per_diff_piece)

    def _AddTransferWrapper(self, tgt_name, src_name, tgt_ranges: RangeSet, src_ranges: RangeSet,
                            style: str, split_threshold_blocks: int):
        """
        Helper to create Transfer objects, potentially splitting large 'diff' transfers.
        split_threshold_blocks: Max blocks for a piece of a diff transfer. If < 0, no splitting.
        """
        # Splitting logic only for 'diff' style and if version >= 3 and valid split_threshold
        if style == "diff" and self.version >= 3 and split_threshold_blocks > 0 and \
           (tgt_ranges.size() > split_threshold_blocks or src_ranges.size() > split_threshold_blocks):
            
            piece_num = 0
            # Operate on copies to allow modification
            current_tgt_ranges = tgt_ranges 
            current_src_ranges = src_ranges

            while (current_tgt_ranges.size() > split_threshold_blocks and \
                   current_src_ranges.size() > split_threshold_blocks):
                
                tgt_piece = current_tgt_ranges.first(split_threshold_blocks)
                src_piece = current_src_ranges.first(split_threshold_blocks)
                
                Transfer(f"{tgt_name}-p{piece_num}", f"{src_name}-p{piece_num}" if src_name else None,
                         tgt_piece, src_piece, style, self.transfers)
                
                current_tgt_ranges = current_tgt_ranges.subtract(tgt_piece)
                current_src_ranges = current_src_ranges.subtract(src_piece)
                piece_num += 1
            
            # Handle remaining blocks if any (must be both non-empty if style is diff)
            if current_tgt_ranges.size() > 0 or current_src_ranges.size() > 0:
                if style == "diff": # For diff, both must have remaining parts or it's an issue
                    assert current_tgt_ranges.size() > 0 and current_src_ranges.size() > 0, \
                        "Diff splitting resulted in mismatched remaining parts."
                
                Transfer(f"{tgt_name}-p{piece_num}", f"{src_name}-p{piece_num}" if src_name else None,
                         current_tgt_ranges, current_src_ranges, style, self.transfers)
        else:
            # No splitting needed or applicable
            Transfer(tgt_name, src_name, tgt_ranges, src_ranges, style, self.transfers)


    def AbbreviateSourceNames(self):
        """Precomputes maps for basename and number-pattern matching of source files."""
        for k_path in self.src.file_map.keys():
            if k_path.startswith("__"): continue # Skip special domains

            b_name = os.path.basename(k_path)
            if b_name not in self.src_basenames: # Prioritize first encountered if multiple paths have same basename
                self.src_basenames[b_name] = k_path
            
            num_pattern = sub("[0-9]+", "#", b_name)
            if num_pattern not in self.src_numpatterns:
                self.src_numpatterns[num_pattern] = k_path
    
    @staticmethod
    def AssertPartition(total_rangeset: RangeSet, list_of_rangesets):
        """Asserts that RangeSets in list_of_rangesets form a non-overlapping partition of total_rangeset."""
        accumulated_ranges = RangeSet()
        for rs_item in list_of_rangesets:
            assert not accumulated_ranges.overlaps(rs_item), \
                f"Partition assertion failed: {rs_item} overlaps with prior ranges {accumulated_ranges}"
            accumulated_ranges = accumulated_ranges.union(rs_item)
        assert accumulated_ranges == total_rangeset, \
            f"Partition assertion failed: Union {accumulated_ranges} does not equal total {total_rangeset}"
