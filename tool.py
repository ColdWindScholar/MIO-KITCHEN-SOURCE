#!/bin/env python3
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
import sys
if sys.version_info.major == 3:
    if sys.version_info.minor < 8:
        input(
            f"Not supported: [{sys.version}] yet\nEnter to quit\nSorry for any inconvenience caused")
        sys.exit(1)
try:
    from src.tkui.tool import *
except Exception as e:
    print(e)
    input(f"Sorry! We cannot init the tool.\nPlease clone source again!")
    sys.exit(1)

if __name__ == "__main__":
    init(sys.argv)