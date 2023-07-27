from sys import argv
from os.path import exists


def handle(file_) -> None:
    if not exists(file_):
        return
    with open(file_, 'rw', encoding='utf-8', newline='\n') as f:
        data = f.readlines()
        new_data = sorted(set(data), key=data.index)
        if len(new_data) == len(data):
            print("No need to handle")
            return
        f.writelines(new_data)
    del data, new_data


if __name__ == "__main__":
    if len(argv) < 2:
        print("Usage: {} file".format(argv[0]))
    else:
        handle(argv[1])