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
import logging

from enum import Enum


class Entry(Enum):
    # Normal Entry
    main = 0
    # When  Pack Rom
    before_pack = 1
    # Packing
    packing = 4
    # when the too close
    close = 2
    # When the tool boot
    boot = 3


class Type(Enum):
    normal = 0
    virtual = 1
    environ =  2


class PluginLoader(object):
    def __init__(self):
        self.plugins = {}
        self.virtual = {}

    def register(self, id_: str, entry: Entry = Entry, func: None = None, virtual: bool = False,
                 virtual_info: dict = None, parent: str = 'addon'):
        if not func:
            logging.debug(f"{entry} of {id_} is {func}!")
        if id_ not in self.plugins:
            self.plugins[id_] = {}
        self.plugins[id_][entry] = func
        if virtual and not virtual_info:
            virtual_info = {
                "id": id_,
                "name": id_,
                "author": "",
                "version": "",
                "parent": parent
            }
            self.virtual[id_] = virtual_info
        if entry == Entry.boot:
            self.run(id_, entry)

    def is_registered(self, id_:str) -> tuple[bool, Type]:
        if id_ in self.plugins:
            return True, Type.normal
        elif id_ in self.virtual:
            return True, Type.virtual
        elif not id_ in self.plugins and not id_ in self.virtual:
            return False, Type.normal
        return False, Type.normal

    def run(self, id_: str, entry: Entry = Entry, mapped_args: dict = None, *args, **kwargs):
        if not id_ in self.plugins.keys():
            print(f"{id_} is not callable.")
            return lambda: ...
        if not entry in self.plugins[id_].keys():
            print(f"{entry} not registered in {id_}")
            return lambda: ...
        if mapped_args:
            func = self.plugins[id_][entry]
            varnames = func.__code__.co_varnames[:func.__code__.co_argcount]
            args_mapped = [mapped_args.get(i).get() for i in varnames]
            return func(*args_mapped)
        try:
            return self.plugins[id_][entry](*args, **kwargs)
        except TypeError:
            return self.plugins[id_][entry]()

    def run_entry(self, entry: Entry):
        for id_ in self.plugins:
            if entry in self.plugins[id_].keys():
                self.run(id_, entry)


loader = PluginLoader()
