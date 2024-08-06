# Copyright (C) 2024 The MIO-KITCHEN-SOURCE Project
#
# Licensed under theGNU AFFERO GENERAL PUBLIC LICENSE, Version 3.0 (the "License");
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
import blackboxprotobuf
from json import loads


class Type(int):
    REPLACE = 0
    REPLACE_BZ = 1
    MOVE = 2
    BSDIFF = 3
    SOURCE_COPY = 4
    SOURCE_BSDIFF = 5
    REPLACE_XZ = 8
    ZERO = 6
    DISCARD = 7
    BROTLI_BSDIFF = 10
    PUFFDIFF = 9
    ZUCCHINI = 11
    LZ4DIFF_BSDIFF = 12
    LZ4DIFF_PUFFDIFF = 13
    REPLACE_ZSTD = 14


class Metadata:
    def __init__(self, data):
        json_data: dict = loads(blackboxprotobuf.protobuf_to_json(data)[0])
        self.block_size = int(json_data.get('3', 4096))
        self.partitions = json_data.get('13', [])
