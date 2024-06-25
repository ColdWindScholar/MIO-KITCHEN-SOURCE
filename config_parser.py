class ConfigParser:
    def __init__(self) -> None:
        self.dict = {'__init__': {}}
        self.dict_index = '__init__'

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

    def items(self, item):
        items = self.dict[item]
        if item not in self.dict.keys():
            yield []
        else:
            for i in items:
                yield i, items[i]

    def write(self, fd):
        for i in self.dict.keys():
            fd.write(f"[{i}]\n")
            for i_ in self.dict[i]:
                fd.write(f"{i_} = {self.dict[i][i_]}\n")

    def set(self, main_i, n, v):
        if main_i not in self.dict.keys():
            self.dict[main_i] = {}
        self.dict[main_i][n] = v
