import logging
try:
    from enum import IntEnum
except ImportError:
    IntEnum = int
class Entry(IntEnum):
    # Normal Entry
    main = 0
    # When Pack Rom
    pack = 1
    # when the too close
    close = 2
    # When the tool boot
    boot = 3
class Type(IntEnum):
    sh = 0
    msh = 1
    python = 3

class PluginLoader(object):
    def __init__(self):
        self.plugins = {}

    def register(self, id_:str="addon", entry:Entry=Entry,func:None=None):
        if not func:
            logging.debug(f"{entry} of {id_} is {func}!")
        if id_ not in self.plugins:
            self.plugins[id_] = {}
        self.plugins[id_][entry] = func
        if entry == Entry.boot:
            self.run(id_, entry)

    def run(self, id_:str="addon", entry:Entry=Entry, *args, **kwargs):
        if not id_ in self.plugins.keys():
            logging.info(f"{id_} not in list")
            return
        if not entry in self.plugins[id_].keys():
            logging.info(f"{entry} not in {id_}")
            return
        return self.plugins[id_][entry](*args, **kwargs)


loader = PluginLoader()