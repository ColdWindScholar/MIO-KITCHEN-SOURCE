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
"""Sorts event names according to a predefined order.

Attributes:
    EVENT_SORT_ORDER (List[str]): A list of event names sorted as they should
        appear in the output CFG file.
    EVENT_SORT_MAP (Dict[str, int]): A mapping of event names to their index in
        the event sort order list.
"""

from typing import Iterable, List

EVENT_SORT_ORDER = [
    'cpu-cycles',
    'stalled-cycles-frontend',
    'stalled-cycles-backend',
    'instructions',
    'branch-instructions',
    'branch-misses',
    'cache-references',
    'cache-misses',
    'task-clock',
    'context-switches',
    'page-faults',
]

EVENT_SORT_MAP = {name: i for i, name in enumerate(EVENT_SORT_ORDER)}


def sort_event_names(event_names: Iterable[str]) -> List[str]:
    """Sorts event names according to a predefined order.

    Args:
        event_names (Iterable[str]): An iterable of event names.

    Returns:
        List[str]: A list of sorted event names.
    """
    default_index = len(EVENT_SORT_MAP)
    return sorted(event_names,
                  key=lambda name: EVENT_SORT_MAP.get(name, default_index))
