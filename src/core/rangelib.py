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

from heapq import merge
from itertools import cycle
from typing import List, Tuple, Union, Iterator, Optional, overload, TypeVar, Type

__all__ = ["RangeSet"]

# For class methods returning an instance of the class
_RS = TypeVar('_RS', bound='RangeSet')


class RangeSet:
    """
    A RangeSet represents a set of non-overlapping ranges on the
    integers (i.e., a set of integers, but efficient when the set contains
    lots of runs).
    Internally, it's stored as a sorted tuple of integers, where each pair
    represents [start, end) of a range. Example: (10, 20, 30, 35) means
    ranges [10, 20) and [30, 35).
    """

    def __init__(self, data: Optional[Union[str, Tuple[int, ...], List[int]]] = None):
        """
        Initializes a RangeSet.

        Args:
            data: Can be a string (e.g., "10-19 30"), a tuple/list of
                  integers (e.g., (10, 20, 30, 31) for ranges 10-19 and 30),
                  or None for an empty RangeSet.
                  The tuple/list form expects pairs representing [start, end).
        """
        self.data: Tuple[int, ...]
        self.monotonic: bool = False # True if input ranges were in increasing order

        if isinstance(data, str):
            self._parse_internal(data)
        elif data:
            if not isinstance(data, (tuple, list)):
                raise TypeError("Input data must be a string, tuple, list, or None.")
            if len(data) % 2 != 0:
                raise ValueError("Input data tuple/list must have an even number of elements.")
            # Normalize and sort the input data if it's a list/tuple of [start, end) pairs
            # Example: data = (10, 20, 5, 8) -> sorted_normalized_data = (5, 8, 10, 20)
            # This requires sorting based on pairs, then applying _remove_pairs.
            # The original code assumed 'data' if not str, was already in the internal format
            # but after _remove_pairs. Let's clarify.
            # If data is [s1, e1, s2, e2, ...], it needs to be sorted first to handle overlaps correctly.
            # The original implementation's `assert all(x < y for x, y in zip(self.data, self.data[1:]))`
            # for monotonicity suggests that if `data` is a list/tuple, it's expected to be pre-processed.
            # Let's make it more robust by processing it like the string parser does.
            
            # Simplified: if data is a list/tuple, it's assumed to be already somewhat processed.
            # The original code: self.data = tuple(self._remove_pairs(data))
            # This assumes `data` is already sorted if it comes as a list/tuple of boundaries.
            # For safety and consistency, let's process list/tuple data through a path similar to string parsing's sort & merge.
            temp_sorted_data = sorted(list(data))
            self.data = tuple(self._remove_pairs(temp_sorted_data))
            # Monotonicity for list/tuple input: check original order before sorting for _remove_pairs
            # However, the original code sets monotonicity based on the final `self.data` structure,
            # which is always sorted. So `monotonic` has a specific meaning related to parsing, not just internal state.
            # If initialized with a list/tuple, it's harder to define 'monotonic' in the same way as parsed text.
            # The original check was: `all(x < y for x, y in zip(self.data, self.data[1:]))`
            # which is true if self.data is not empty and sorted, but not what `monotonic` means for parsing.
            # Let's assume if data is a raw list/tuple, monotonicity is determined after normalization.
            # A truly 'monotonic' input list for `data` would be e.g. `[10,20,30,40]` not `[30,40,10,20]`
            # The most direct interpretation of original code is that if `data` is a list/tuple,
            # `monotonic` is True if `data` itself (before `_remove_pairs`) represents monotonic ranges.
            # This is tricky. The `monotonic` flag is primarily for the string parser.
            # For direct data initialization, we might assume it's not "parsed monotonic" unless specifically checked.
            # The original check `all(x < y for x, y in zip(self.data, self.data[1:]))` is for the *internal data*.
            # Let's stick to setting `monotonic` primarily via string parsing.
            # If `data` is a list/tuple, we assume it's not from a "monotonic parse".
            self.monotonic = False # Default for direct data init. String parser sets it.

        else: # data is None
            self.data = ()
            self.monotonic = True # Empty set can be considered monotonic

    def __iter__(self) -> Iterator[Tuple[int, int]]:
        """Iterates over the [start, end) tuples of the ranges."""
        for i in range(0, len(self.data), 2):
            yield (self.data[i], self.data[i+1])

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RangeSet):
            return NotImplemented
        return self.data == other.data

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, RangeSet):
            return NotImplemented
        return self.data != other.data

    def __bool__(self) -> bool: # Python 3
        return bool(self.data)

    def __str__(self) -> str:
        if not self.data:
            return "empty"
        else:
            return self.to_string()

    def __repr__(self) -> str:
        return f'<RangeSet("{self.to_string()}")>'

    @classmethod
    def parse(cls: Type[_RS], text: str) -> _RS:
        """
        Parse a text string consisting of a space-separated list of
        blocks and ranges, eg "10-20 30 35-40".  Ranges are interpreted to
        include both their ends (so "10-20" means blocks 10 through 20,
        which is range [10, 21) internally).
        Returns a RangeSet object.

        If the input has all its blocks in increasing order, then the returned
        RangeSet will have an attribute 'monotonic' set to True.
        """
        return cls(text)

    def _parse_internal(self, text: str) -> None:
        """
        Parses the string representation and sets self.data and self.monotonic.
        Ranges like "10-19" become internal [10, 20). Single numbers "30" become [30, 31).
        """
        parsed_data: List[int] = []
        last_block_parsed_end = -1  # To check for monotonicity of input text
        self.monotonic = True       # Assume monotonic until proven otherwise

        if not text.strip(): # Handle empty or whitespace-only string
            self.data = ()
            return

        for part in text.split():
            if "-" in part:
                try:
                    s_str, e_str = part.split("-", 1)
                    s = int(s_str)
                    e = int(e_str) # User provides inclusive end
                except ValueError:
                    raise ValueError(f"Invalid range format: {part}")
                
                if s > e:
                    raise ValueError(f"Range start {s} cannot be greater than end {e} in '{part}'")

                parsed_data.append(s)
                parsed_data.append(e + 1) # Internal representation is [start, end)
                
                # Monotonicity check based on user-provided inclusive 'e'
                if last_block_parsed_end < s: # Using strict < to ensure non-overlapping for monotonic
                    last_block_parsed_end = e
                else:
                    self.monotonic = False
            else:
                try:
                    s = int(part)
                except ValueError:
                    raise ValueError(f"Invalid block format: {part}")
                parsed_data.append(s)
                parsed_data.append(s + 1) # Single block s is range [s, s+1)
                
                if last_block_parsed_end < s:
                    last_block_parsed_end = s
                else:
                    self.monotonic = False
        
        # Sort the parsed start/end points to merge overlapping/adjacent ranges
        parsed_data.sort()
        self.data = tuple(self._remove_pairs(parsed_data))
        # Note: self.monotonic reflects the order in the *input string*, not necessarily self.data's order (which is always sorted).

    @staticmethod
    def _remove_pairs(source: List[int]) -> Iterator[int]:
        """
        Given a sorted list of integers representing change points (start/end of ranges),
        this method normalizes them into a sequence of [start_1, end_1, start_2, end_2, ...]
        boundaries for non-overlapping ranges.
        It effectively merges overlapping or adjacent ranges and removes empty ones.

        - If two consecutive numbers are the same (e.g., `X, X`), they "cancel out",
          meaning an interval ended at `X` and another immediately started at `X`,
          so `X` is not an external boundary of the merged interval.
        - Non-cancelled numbers are yielded as the boundaries of the resulting ranges.

        Example 1 (merge): source = [10, 20, 20, 30]  (represents [10,20) U [20,30))
                       yields 10, then 30. Result: (10, 30) (represents [10,30))

        Example 2 (no merge): source = [10, 15, 20, 25] (represents [10,15) U [20,25))
                          yields 10, 15, 20, 25. Result: (10, 15, 20, 25)

        Example 3 (empty range removal): source = [10, 10, 20, 30] (represents [10,10) U [20,30))
                                     yields 20, then 30. Result: (20, 30)
        """
        last_val: Optional[int] = None
        for i_val in source:
            if i_val == last_val: # Current val cancels out previous identical val (e.g., end of A, start of B)
                last_val = None
            else:
                if last_val is not None: # Yield the boundary that wasn't cancelled
                    yield last_val
                last_val = i_val
        if last_val is not None: # Yield the final uncancelled boundary
            yield last_val

    def to_string(self) -> str:
        """Converts RangeSet to human-readable string "10-19 30-34"."""
        out: List[str] = []
        for s, e in self: # Iterates over (start, end) tuples from __iter__
            if e == s + 1: # Single block
                out.append(str(s))
            else: # Range of blocks
                out.append(f"{s}-{e-1}") # User-visible format is inclusive end
        return " ".join(out)

    def to_string_raw(self) -> str:
        """Converts RangeSet to raw string format "count,s1,e1,s2,e2,..." for OTA scripts."""
        if not self.data: # Handle empty RangeSet
            return "0" # Or "0," depending on expected format for empty. Original code implies "0," if data is ()
                       # Let's assume original asserted self.data, so it was never called on empty.
                       # If it can be called on empty, "0" or "0," needs clarification.
                       # Let's make it robust for empty.
            # return "0," # A common way to represent empty for this format
            # The original code had `assert self.data`. Let's keep that implication or handle empty explicitly.
            # For now, assuming it won't be called on an empty set based on original `assert`.
            # If it can be, `len(self.data)` would be 0, so "0," + "" = "0," is fine.
            
        # No, original code `assert self.data` means it expects non-empty.
        # If we remove that assert, then:
        if not self.data:
            return "0," # Count of items is 0, no data items follow.
        return str(len(self.data)) + "," + ",".join(map(str, self.data))


    def union(self: _RS, other: _RS) -> _RS:
        """
        Return a new RangeSet representing the union of this RangeSet with the argument.
        Uses a sweep-line algorithm. Event points are start/end of ranges.
        `z` tracks the number of active ranges covering the current point.
        For union, a new range starts when `z` goes 0->1, ends when `z` goes 1->0.
        """
        out_data: List[int] = []
        z = 0  # Counter for active ranges
        # merge() yields (value, source_indicator) but here we only care about value and its type (start/end)
        # cycle((+1, -1)) assigns +1 to start points, -1 to end points.
        # The items from merge will be (point, type_delta)
        for point, delta in merge(zip(self.data, cycle((+1, -1))),
                                  zip(other.data, cycle((+1, -1)))):
            if (z == 0 and delta == +1):  # Start of a new unioned range
                out_data.append(point)
            elif (z == 1 and delta == -1): # End of a unioned range (and no other range covers this point from other set)
                out_data.append(point)
            z += delta
        return self.__class__(data=tuple(out_data)) # Use self.__class__ for subclass compatibility

    def intersect(self: _RS, other: _RS) -> _RS:
        """
        Return a new RangeSet representing the intersection.
        For intersection, a new range starts when `z` goes 1->2, ends when `z` goes 2->1.
        """
        out_data: List[int] = []
        z = 0
        for point, delta in merge(zip(self.data, cycle((+1, -1))),
                                  zip(other.data, cycle((+1, -1)))):
            if (z == 1 and delta == +1):  # Both ranges become active
                out_data.append(point)
            elif (z == 2 and delta == -1): # One of the two ranges ends
                out_data.append(point)
            z += delta
        return self.__class__(data=tuple(out_data))

    def subtract(self: _RS, other: _RS) -> _RS:
        """
        Return a new RangeSet representing subtracting 'other' from 'self'. (self - other)
        For subtraction, 'other' ranges are inverted (starts act as ends, ends as starts).
        A resulting range from 'self' starts if 'self' starts and 'other' isn't active (z from self=0->1).
        A resulting range from 'self' ends if 'self' ends and 'other' isn't active (z from self=1->0).
        """
        out_data: List[int] = []
        z = 0
        # For 'other', cycle is (-1, +1) to invert its ranges effect on 'z'
        for point, delta in merge(zip(self.data, cycle((+1, -1))),      # self: +1 for start, -1 for end
                                  zip(other.data, cycle((-1, +1)))):    # other: -1 for start, +1 for end
            if (z == 0 and delta == +1):  # Start of a 'self' range, and not inside an 'other' range
                out_data.append(point)
            elif (z == 1 and delta == -1): # End of a 'self' range, and not ending an 'other' range covering it
                out_data.append(point)
            z += delta
        return self.__class__(data=tuple(out_data))

    def overlaps(self, other: 'RangeSet') -> bool:
        """Returns true if 'other' has a non-empty overlap with this RangeSet."""
        # Similar to intersect, but can stop early.
        z = 0
        for _, delta in merge(zip(self.data, cycle((+1, -1))),
                              zip(other.data, cycle((+1, -1)))):
            # An overlap starts if z becomes 2 (both self and other are active)
            if (z == 1 and delta == +1): # z was 1 (one active), now delta is +1 (other becomes active) -> z becomes 2
                return True
            # An overlap also exists if z was already 2 and something ends (not sufficient to stop)
            # The condition `(z == 2 and delta == -1)` is when an overlap *ends*.
            # The crucial point is when z *becomes* 2.
            # Let's re-verify original logic: `(z == 1 and d == 1) or (z == 2 and d == -1)`
            # (z==1, d==1): self active, other starts -> z becomes 2. Overlap starts. -> return True
            # (z==2, d==-1): self and other active, one of them ends -> z becomes 1. Overlap ends here.
            # This means the original logic returns True if an intersection range *exists* (has a start or an end point).
            z += delta
            if z == 2: # As soon as z becomes 2, we have an overlap.
                return True
        return False # No point where z became 2.

    def size(self) -> int:
        """Returns the total number of integers in the set."""
        total = 0
        for s, e in self: # Iterates (start, end)
            total += (e - s)
        return total

    def map_within(self: _RS, other: _RS) -> _RS:
        """
        'other' should be a subset of 'self'. Returns a RangeSet
        representing what 'other' would be if 'self' were mapped
        contiguously starting at zero.
        Example: self="10-19 30-39", other="17-19 30-32" -> result="7-12"
                 (10-19 is 10 blocks, 30-39 is 10 blocks. Total self.size = 20 blocks for mapping)
                 17-19 is (17-10) = 7th, 8th, 9th block in self's first part. -> mapped to 7,8,9
                 30-32 is (30-30) = 0th, 1st, 2nd block in self's second part. This part starts after
                         first part's 10 blocks. So, mapped to 10+0, 10+1, 10+2 = 10,11,12.
                 Result: 7-9 and 10-12, which is [7,10) U [10,13) -> [7,13) -> "7-12"
        """
        # Assert that other is a subset of self.
        # (other - self) should be empty.
        # if not self.intersect(other) == other: # A more direct check: other.subtract(self).size() == 0
        #     raise ValueError("'other' must be a subset of 'self' for map_within")
        # Original code doesn't check this, so we won't add a strict check unless behavior is problematic.

        out_data: List[int] = []
        current_offset_from_self_map = 0 # How many blocks from 'self' have been skipped up to 'start_of_self_segment'
        start_of_self_segment: Optional[int] = None

        # Event types:
        # -5: Start of a segment in 'self'
        # +5: End of a segment in 'self'
        # -1: Start of a segment in 'other' (subset)
        # +1: End of a segment in 'other' (subset)
        # `point` is the block index, `delta` is the event type.
        for point, delta_event_type in merge(zip(self.data, cycle((-5, +5))),
                                             zip(other.data, cycle((-1, +1)))):
            if delta_event_type == -5: # Start of a 'self' segment
                start_of_self_segment = point
            elif delta_event_type == +5: # End of a 'self' segment
                if start_of_self_segment is None: # Should not happen if data is valid
                    raise AssertionError("RangeSet logic error in map_within: end of self_segment without start.")
                current_offset_from_self_map += (point - start_of_self_segment)
                start_of_self_segment = None # Reset for next segment of 'self'
            else: # Event from 'other' (-1 for start, +1 for end)
                if start_of_self_segment is None:
                    # This implies 'other' has a range outside any 'self' segment, if no assertion.
                    # Or, if other is truly a subset, this might indicate an issue with data.
                    # Given original code doesn't assert subset, this could occur.
                    # The behavior then would be to map relative to the end of the last 'self' segment, which seems complex.
                    # Assuming 'other' is indeed a subset, start_of_self_segment should always be set here.
                    # If not, `point - start_of_self_segment` would be an error.
                    # Let's assume valid subset for now or that merge order prevents this.
                     raise AssertionError(
                        "RangeSet logic error in map_within: 'other' event when not inside a 'self' segment. "
                        f"Point: {point}, Event: {delta_event_type}. Self: {self.data}, Other: {other.data}"
                    )

                # Map 'point' from 'other' into the 0-based space of 'self'.
                # (point - start_of_self_segment) is the offset within the current 'self' segment.
                # Add current_offset_from_self_map which is the size of all preceding 'self' segments.
                mapped_point = current_offset_from_self_map + (point - start_of_self_segment)
                out_data.append(mapped_point)
        
        return self.__class__(data=tuple(out_data))


    def extend(self: _RS, n: int) -> _RS:
        """
        Extend each range in the RangeSet by 'n' blocks in both directions.
        The lower bound of any extended range is guaranteed to be non-negative.
        Overlapping ranges resulting from extension are merged.
        This implementation iteratively unions, which might not be the most performant
        for many small initial ranges, but is correct.
        """
        if n < 0:
            raise ValueError("Cannot extend by a negative number of blocks.")
        if n == 0:
            return self.__class__(data=self.data) # Return a copy if n is 0

        # Start with a copy of self to union with extended ranges.
        # Or, more simply, build a list of new ranges and union them all at once.
        # However, the original code did `out = self` and then `out = out.union(...)`.
        # This iterative unioning is less efficient. A better way:
        
        extended_ranges_data: List[int] = []
        for s, e in self: # Iterate over [start, end) tuples
            s_extended = max(0, s - n)
            e_extended = e + n
            # Create temporary RangeSet for each extended part to normalize it.
            # This ensures [s_extended, e_extended) is correctly formed even if s_extended >= e_extended.
            # A simple pair (s_extended, e_extended) may not be valid for _remove_pairs if s_extended >= e_extended.
            # However, RangeSet constructor logic with _remove_pairs should handle (X,X) by removing it.
            if s_extended < e_extended: # Only add valid ranges
                 extended_ranges_data.extend((s_extended, e_extended))
        
        if not extended_ranges_data and not self.data : # Extending an empty set by n results in empty.
             return self.__class__(data=())
        if not extended_ranges_data and self.data: # Extending existing ranges by n=0 (or resulted in no valid extended ranges)
             return self.__class__(data=self.data)


        # Merge all extended_ranges_data with original self.data then normalize
        # This is more efficient than iterative union.
        # The sweep-line logic used in `union` is essentially what we need.
        # Let 'all_data_points' contain all start/end points from self and the conceptual extended ranges.
        
        # Simpler approach: create a RangeSet of all extended parts, then union with self.
        # This leverages the existing robust union.
        
        # If self is empty, the result is also empty (as per loop logic above)
        if not self.data:
            return self.__class__(data=())

        # Original iterative approach (kept for behavior consistency, though less optimal):
        out_result = self.__class__(data=self.data) # Start with a copy
        for s, e in self:
            s_extended = max(0, s - n)
            e_extended = e + n
            if s_extended < e_extended: # Only union if it forms a valid positive range
                # Create a RangeSet for the single extended range [s_extended, e_extended)
                # String parsing is a robust way to create a single-range RangeSet.
                # Or direct construction: RangeSet(data=(s_extended, e_extended))
                ext_range_str = f"{s_extended}-{e_extended-1}" # to_string format
                out_result = out_result.union(self.__class__(ext_range_str))
        return out_result


    def first(self: _RS, n: int) -> _RS:
        """
        Return a new RangeSet containing at most the first 'n' integers
        from this RangeSet.
        """
        if n < 0:
            raise ValueError("Number of first blocks 'n' cannot be negative.")
        if n == 0:
            return self.__class__(data=()) # Empty set
        if self.size() <= n: # If n is larger or equal to current size, return a copy of self
            return self.__class__(data=self.data)

        out_data: List[int] = []
        blocks_collected = 0
        for s, e in self: # Iterates [start, end)
            current_range_size = e - s
            if blocks_collected + current_range_size >= n:
                # This range contains or completes the 'n' blocks
                needed_from_this_range = n - blocks_collected
                out_data.extend((s, s + needed_from_this_range))
                blocks_collected += needed_from_this_range
                break # All 'n' blocks collected
            else:
                # Take the whole current range
                out_data.extend((s, e))
                blocks_collected += current_range_size
        
        return self.__class__(data=tuple(out_data))
