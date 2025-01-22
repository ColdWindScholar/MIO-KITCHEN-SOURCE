import sys
if sys.version_info.major == 3:
    if sys.version_info.minor < 8:
        input(
            f"Not supported: [{sys.version}] yet\nEnter to quit\nSorry for any inconvenience caused")
        sys.exit(1)

from src.tool import *

if __name__ == "__main__":
    init(sys.argv)