import os
from os.path import abspath, exists


class Path:
    def __init__(self, path):
        self.path = path

    def absolute(self):
        return abspath(self.path)

    def exists(self):
        return exists(self.path)
    def write_bytes(self, bytes_data):
        with open(self.absolute(), "wb") as f:
            f.write(bytes_data)
    def read_bytes(self):
        with open(self.absolute(), "rb") as f:
            return f.read()
    def open(self, mode="r", encoding="utf-8", newline="\n"):
        return open(self.absolute(), mode, encoding=encoding, newline=newline)
    def unlink(self):
        os.unlink(self.absolute())
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        ...
