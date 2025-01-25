import sys
if sys.version_info.major == 3:
    if sys.version_info.minor < 8:
        input(
            f"Not supported: [{sys.version}] yet\nEnter to quit\nSorry for any inconvenience caused")
        sys.exit(1)
try:
    from src.tool import *
except Exception:
    input("Sorry! We cannot init the tool.\nPlease clone source again!")
    sys.exit(1)

if __name__ == "__main__":
    init(sys.argv)