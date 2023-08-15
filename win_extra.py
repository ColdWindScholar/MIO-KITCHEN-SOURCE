# Windows Extra Module For MIO-KITCHEN
import os


def win2wslpath(path):
    if not ":" in path:
        path = os.path.abspath(path)
    f, e = path.split(":")
    return "".join([f"/mnt/{f.lower()}", e.replace("\\", "/")])


def wsl2winpath(path):
    if len(path) < 5 or path[:4] != "/mnt":
        if path[:1] == "/":
            path = path[1:].replace("/", "\\")
        return "\\wsl.localhost\\Ubuntu\\" + path
    else:
        if len(path) == 5:
            f, e = path[4:], ""
        else:
            f, e = path[5:].split("/", 1)
        if not len(f) > 1:
            return "".join([f.upper(), ":", e.replace("/", "\\")])
        else:
            if path[:1] == "/":
                path = path[1:].replace("/", "\\")
            return "\\wsl.localhost\\Ubuntu\\" + path
