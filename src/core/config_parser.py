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
class ConfigParser:
    def __init__(self) -> None:
        self.dict = {'__init__': {}}
        self.dict_index = '__init__'

    def __setitem__(self, key, value):
        self.dict[key] = value

    def read(self, file):
        with open(file, encoding='utf-8') as f:
            for i in f.readlines():
                i = i.strip()
                if not i or i.startswith("#"):
                    continue
                if i.startswith('[') and i.endswith(']'):
                    self.dict_index = i[1:-1]
                    self.dict[self.dict_index] = {}
                else:
                    if '=' in i:
                        n, *v = i.split("=")
                        n, v = n.strip(), v[0].strip()
                        self.dict[self.dict_index][n] = v
                    else:
                        continue

    def read_string(self, s):
        for i in s.splitlines():
            i = i.strip()
            if not i or i.startswith("#"):
                continue
            if i.startswith('[') and i.endswith(']'):
                self.dict_index = i[1:-1]
                self.dict[self.dict_index] = {}
            else:
                if '=' in i:
                    n, *v = i.split("=")
                    n, v = n.strip(), v[0].strip()
                    self.dict[self.dict_index][n] = v
                else:
                    continue

    def items(self, item):
        items = self.dict[item]
        if item not in self.dict.keys():
            yield None, None
        else:
            for i in items:
                yield i, items[i]

    def write(self, fd):
        for i in self.dict.keys():
            if self.dict.get(i):
                fd.write(f"[{i}]\n")
                for i_ in self.dict[i]:
                    fd.write(f"{i_} = {self.dict[i][i_]}\n")

    def set(self, main_i, n, v):
        if main_i not in self.dict.keys():
            self.dict[main_i] = {}
        self.dict[main_i][n] = v

    def get(self, main_i, n, default=''):
        if main_i not in self.dict.keys():
            return default
        return self.dict[main_i].get(n, default)
