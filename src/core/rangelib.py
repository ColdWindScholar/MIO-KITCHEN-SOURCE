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
from typing import (List, Tuple, Union, Iterator, Optional, overload, TypeVar,
                    Type)

__all__ = ["RangeSet"]

# A TypeVar for class methods that return an instance of the class,
# allowing for correct type inference with subclasses.
_RS = TypeVar('_RS', bound='RangeSet')


class RangeSet:
    """Represents a set of non-overlapping integer ranges.

    This class is useful for representing sets of integers that form long,
    contiguous runs. It provides methods for standard set operations like
    union, intersection, and subtraction.

    Internally, the ranges are stored as a sorted tuple of integers, where each
    pair of integers represents a half-open interval `[start, end)`.
    For example, the tuple `(10, 20, 30, 35)` represents the integer ranges
    [10, 19] and [30, 34].
    """

    def __init__(
        self,
        data: Optional[Union[str, Tuple[int, ...], List[int]]] = None
    ) -> None:
        """Initializes a RangeSet.

        Args:
            data: The data to initialize the set. Can be one of:
                - A string of space-separated numbers and ranges, e.g.,
                  "10-19 30". Ranges are inclusive.
                - A tuple or list of integers representing pre-sorted,
                  non-overlapping `[start, end)` boundaries, e.g., `(10, 20, 30, 31)`.
                  Input is normalized, so overlapping or unsorted data like
                  `(30, 40, 10, 20)` will be handled correctly.
                - None, to create an empty RangeSet.
        """
        self.data: Tuple[int, ...]
        self.monotonic: bool

        if isinstance(data, str):
            self._parse_internal(data)
        elif data:
            if not isinstance(data, (list, tuple)):
                raise TypeError("Input must be a string, tuple, list, or None.")
            if len(data) % 2 != 0:
                raise ValueError(
                    "Input tuple/list must have an even number of elements.")
            # The 'monotonic' flag is only meaningful when parsing a string,
            # as it relates to the order of tokens in the text.
            self.monotonic = False
            # Normalize the input by sorting all boundary points and then
            # merging any overlapping or adjacent ranges.
            sorted_data = sorted(data)
            self.data = tuple(self._remove_pairs(sorted_data))
        else:  # data is None or empty
            self.data = ()
            self.monotonic = True  # An empty set is considered monotonic.

    def __iter__(self) -> Iterator[Tuple[int, int]]:
        """Iterates over the [start, end) tuples of the ranges."""
        for i in range(0, len(self.data), 2):
            yield self.data[i], self.data[i + 1]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RangeSet):
            return NotImplemented
        return self.data == other.data

    def __bool__(self) -> bool:
        """Returns True if the RangeSet is not empty."""
        return bool(self.data)

    def __str__(self) -> str:
        """Returns a compact, human-readable string representation."""
        if not self.data:
            return "empty"
        return self.to_string()

    def __repr__(self) -> str:
        return f'<RangeSet("{self.to_string()}")>'

    @classmethod
    def parse(cls: Type[_RS], text: str) -> _RS:
        """Parses a string to create a RangeSet.

        The string should be a space-separated list of integers or inclusive
        ranges (e.g., "10-20 30 35-40").

        If all tokens in the string are in increasing order, the `monotonic`
        attribute of the returned RangeSet will be True.

        Args:
            text: The string to parse.

        Returns:
            A new RangeSet instance.
        """
        return cls(text)

    def _parse_internal(self, text: str) -> None:
        """Parses a string and initializes instance attributes."""
        if not text.strip():
            self.data = ()
            self.monotonic = True
            return

        points = []
        last_block_val = -1
        self.monotonic = True

        for part in text.split():
            try:
                if "-" in part:
                    s, e = (int(x) for x in part.split("-", 1))
                    if s > e:
                        raise ValueError(f"Range start > end: {part}")
                    points.extend((s, e + 1))
                    if self.monotonic and s <= last_block_val:
                        self.monotonic = False
                    last_block_val = e
                else:
                    s = int(part)
                    points.extend((s, s + 1))
                    if self.monotonic and s <= last_block_val:
                        self.monotonic = False
                    last_block_val = s
            except ValueError as e:
                raise ValueError(f"Invalid token '{part}': {e}") from e

        points.sort()
        self.data = tuple(self._remove_pairs(points))

    @staticmethod
    def _remove_pairs(source: List[int]) -> Iterator[int]:
        """Merges overlapping/adjacent ranges from a sorted list of boundaries.

        This function implements a sweep-line algorithm using an XOR-like rule.
        Given a sorted list of range boundaries, it "flips" a state from
        "outside" a range to "inside" and vice-versa at each point.
        If two identical points appear consecutively (e.g., `..., 20, 20, ...`),
        they cancel each other out. This correctly merges adjacent ranges
        like `[10, 20)` and `[20, 30)` into `[10, 30)`.

        Example:
            _remove_pairs([10, 20, 20, 30]) yields 10, 30.
            _remove_pairs([10, 15, 20, 25]) yields 10, 15, 20, 25.
        """
        last_val = None
        for i_val in source:
            if i_val == last_val:
                # This boundary is cancelled out (e.g., an end point
                # immediately followed by a start point).
                last_val = None
            else:
                if last_val is not None:
                    yield last_val
                last_val = i_val
        if last_val is not None:
            yield last_val

    def to_string(self) -> str:
        """Converts the RangeSet to a human-readable string like "10-19 30".

        Single-integer ranges are represented as one number, while multi-integer
        ranges are represented with an inclusive hyphenated format.
        """
        out = []
        for s, e in self:
            if e == s + 1:
                out.append(str(s))
            else:
                out.append(f"{s}-{e-1}")
        return " ".join(out)

    def to_string_raw(self) -> str:
        """Converts the RangeSet to "count,s1,e1,s2,e2,..." format.

        This format is used by Android's OTA update scripts. The first number
        is the count of subsequent integers in the list. An empty set is
        represented as "0,".
        """
        if not self.data:
            return "0,"
        return str(len(self.data)) + "," + ",".join(map(str, self.data))

    def _set_op(self, other: 'RangeSet',
                start_z: int, end_z: int) -> 'RangeSet':
        """Generic sweep-line algorithm for set operations."""
        out_data = []
        z = 0
        # Create iterators of (point, delta) tuples for the sweep-line.
        # Delta is +1 for a start point and -1 for an end point.
        self_events = zip(self.data, cycle((+1, -1)))
        other_events = zip(other.data, cycle((+1, -1)))

        for point, delta in merge(self_events, other_events):
            z_before = z
            z += delta
            if z_before == start_z and z > start_z:
                out_data.append(point)
            elif z_before == end_z and z < end_z:
                out_data.append(point)
        return self.__class__(data=tuple(out_data))

    def union(self: _RS, other: _RS) -> _RS:
        """Returns the union of this set and another.

        A new range in the union starts when the number of active ranges goes
        from 0 to 1, and ends when it goes from 1 to 0.
        """
        out_data = []
        z = 0
        self_events = zip(self.data, cycle((+1, -1)))
        other_events = zip(other.data, cycle((+1, -1)))

        for point, delta in merge(self_events, other_events):
            if z == 0 and delta == +1:  # A new range begins
                out_data.append(point)
            elif z == 1 and delta == -1:  # A combined range ends
                out_data.append(point)
            z += delta
        return self.__class__(data=tuple(out_data))

    def intersect(self: _RS, other: _RS) -> _RS:
        """Returns the intersection of this set and another.

        A new range in the intersection starts when the number of active ranges
        goes from 1 to 2, and ends when it goes from 2 to 1.
        """
        out_data = []
        z = 0
        self_events = zip(self.data, cycle((+1, -1)))
        other_events = zip(other.data, cycle((+1, -1)))

        for point, delta in merge(self_events, other_events):
            if z == 1 and delta == +1:  # Overlap begins
                out_data.append(point)
            elif z == 2 and delta == -1:  # Overlap ends
                out_data.append(point)
            z += delta
        return self.__class__(data=tuple(out_data))

    def subtract(self: _RS, other: _RS) -> _RS:
        """Returns the set of integers in `self` but not in `other`.

        This is implemented by inverting the effect of `other`'s ranges on
        the sweep-line counter. A range starts when `self` starts while not
        inside `other`, and ends when `self` ends.
        """
        out_data = []
        z = 0
        # Invert the delta for `other`: a start point decreases z, an end
        # point increases it. This effectively subtracts `other`'s regions.
        self_events = zip(self.data, cycle((+1, -1)))
        other_events = zip(other.data, cycle((-1, +1)))

        for point, delta in merge(self_events, other_events):
            if z == 0 and delta == +1:  # Start of a self-range, outside other
                out_data.append(point)
            elif z == 1 and delta == -1:  # End of a self-range
                out_data.append(point)
            z += delta
        return self.__class__(data=tuple(out_data))

    def overlaps(self, other: 'RangeSet') -> bool:
        """Returns True if the sets have any integers in common."""
        z = 0
        self_events = zip(self.data, cycle((+1, -1)))
        other_events = zip(other.data, cycle((+1, -1)))

        for _, delta in merge(self_events, other_events):
            z += delta
            # If z reaches 2, it means a point is covered by ranges from
            # both sets, so an overlap exists.
            if z == 2:
                return True
        return False

    def size(self) -> int:
        """Returns the total number of integers in all ranges."""
        return sum(e - s for s, e in self)

    def map_within(self: _RS, other: _RS) -> _RS:
        """Maps ranges from `other` into the contiguous space of `self`.

        This method requires that `other` is a subset of `self`. It returns a
        new RangeSet where the ranges of `other` are re-calculated as offsets
        within `self`, as if `self` were a single contiguous range starting at 0.

        Example:
            self = RangeSet("10-19 30-39")  # size=20. space is [0,20)
            other = RangeSet("17-19 30-32")
            map_within(other) -> RangeSet("7-12")

            Mapping:
            - "17-19" is at offset 7 from self's start (17-10=7) -> maps to [7,10)
            - "30-32" is in self's second part. The first part had 10 integers.
              The offset from the start of the second part is (30-30)=0.
              Total mapped offset = 10 + 0 = 10. -> maps to [10,13)
            - Result is [7,10) U [10,13), which normalizes to [7,13) or "7-12".

        Args:
            other: A RangeSet that is a subset of `self`.

        Returns:
            A new RangeSet with the mapped ranges.

        Raises:
            ValueError: If `other` is not a subset of `self`.
        """
        if not self.intersect(other) == other:
            raise ValueError("'other' must be a subset of 'self'")

        out_data = []
        self_offset = 0
        self_active_start = 0

        # Event types for the sweep-line:
        # -5: self range starts
        # +5: self range ends
        # -1: other range starts
        # +1: other range ends
        self_events = zip(self.data, cycle((-5, +5)))
        other_events = zip(other.data, cycle((-1, +1)))

        for point, event in merge(self_events, other_events):
            if event == -5:  # self range starts
                self_active_start = point
            elif event == +5:  # self range ends
                self_offset += (point - self_active_start)
            else:  # an 'other' event
                # Map the point from `other` into the 0-based contiguous space of `self`.
                mapped_point = self_offset + (point - self_active_start)
                out_data.append(mapped_point)

        return self.__class__(data=tuple(out_data))

    def extend(self: _RS, n: int) -> _RS:
        """Returns a new set with each range extended by `n` on both sides.

        Extended ranges are clipped at 0 on the lower bound. Any resulting
        overlapping ranges are merged.

        Args:
            n: The non-negative number of integers to extend by.

        Returns:
            A new, extended RangeSet.
        """
        if n < 0:
            raise ValueError("Cannot extend by a negative value.")
        if n == 0 or not self.data:
            return self.__class__(data=self.data)

        # Create a string representation of all the extended ranges.
        # This is an efficient way to leverage the robust parsing and merging
        # logic in the constructor.
        extended_ranges = []
        for s, e in self:
            s_ext = max(0, s - n)
            e_ext = e + n
            # to_string expects inclusive end, so e_ext-1
            extended_ranges.append(f"{s_ext}-{e_ext-1}")

        return self.parse(" ".join(extended_ranges))

    def first(self: _RS, n: int) -> _RS:
        """Returns a new set containing the first `n` integers from this set.

        If the set contains fewer than `n` integers, a copy of the original
        set is returned.

        Args:
            n: The non-negative number of integers to retrieve.

        Returns:
            A new RangeSet containing at most the first `n` integers.
        """
        if n < 0:
            raise ValueError("Number of integers 'n' cannot be negative.")
        if n == 0:
            return self.__class__(data=())
        if self.size() <= n:
            return self.__class__(data=self.data)

        out_data = []
        count = 0
        for s, e in self:
            size = e - s
            if count + size >= n:
                # This range contains the nth integer. Take a partial slice and stop.
                needed = n - count
                out_data.extend((s, s + needed))
                break
            else:
                # Take the whole range and continue.
                out_data.extend((s, e))
                count += size

        return self.__class__(data=tuple(out_data))
