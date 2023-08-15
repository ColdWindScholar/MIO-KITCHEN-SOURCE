# Windows Extra Module For MIO-KITCHEN
import os


def win2wslpath(path):
    if not ":" in path:
        path = os.path.abspath(path)
    f, e = path.split(":")
    return "".join([f"/mnt/{f.lower()}", e.replace("\\", "/")])
