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
    environment = 1


class PluginLoader(object):
    def __init__(self):
        self.plugins = {}
        self.virtual = {}

    def register(self, id_: str = "addon", entry: Entry = Entry, func: None = None, virtual: bool = False,
                 virtual_info: dict = None, parent:str = 'addon'):
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

    def run(self, id_: str = "addon", entry: Entry = Entry,mapped_args:dict=None , *args, **kwargs):
        if not id_ in self.plugins.keys():
            print(f"{id_} is not callable.")
            return
        if not entry in self.plugins[id_].keys():
            print(f"{entry} not in {id_}")
            return
        if mapped_args:
            func = self.plugins[id_][entry]
            varnames = func.__code__.co_varnames[:func.__code__.co_argcount]
            args = [mapped_args.get(i).get() for i in varnames]
            return func(*args)
        try:
            return self.plugins[id_][entry](*args, **kwargs)
        except TypeError:
            return self.plugins[id_][entry]()

    def run_entry(self, entry: Entry):
        for id_ in self.plugins:
            if not entry in self.plugins[id_].keys():
                continue
            self.run(id_, entry)


loader = PluginLoader()
