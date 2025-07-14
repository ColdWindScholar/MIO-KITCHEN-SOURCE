import sys

from PyQt5.QtWidgets import QApplication

class Tool(QApplication):
    def __init__(self, argv):
        super().__init__(argv)

def __init__qt(argv):
    app = Tool(argv)
    sys.exit(app.exec_())

init = lambda args: __init__qt(args)
