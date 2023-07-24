from sys import argv
from os.path import exists


class handle:
    def __init__(self, file_) -> None:
        if not exists(file_):
            return
        self.file_ = file_
        self.data = self.read_()
        self.write(sorted(set(self.data), key=self.data.index))

    def read_(self) -> Ellipsis:
        with open(self.file_, 'r', encoding='utf-8') as f:
            return f.readlines()

    def write(self, new_data):
        if len(new_data) == len(self.data):
            print("No need to handle")
            return 1
        with open(self.file_, 'w+', encoding='utf-8', newline='\n') as f:
            f.writelines(new_data)


if __name__ == "__main__":
    if len(argv) < 2:
        print("Usage: {} file".format(argv[0]))
    else:
        handle(argv[1])
