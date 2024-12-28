from PyQt6.QtGui import QIcon, QPixmap
from ..core.images import icon_byte
from PyQt6.QtWidgets import QMainWindow, QWidget
class Error(QWidget):
    def __init__(self, code, desc="unknown error"):
        super().__init__()
        self.setWindowTitle("")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MIO-KITCHEN")
        pm = QPixmap()
        pm.loadFromData(icon_byte, "png")
        windows_icon = QIcon(pm)
        self.setWindowIcon(windows_icon)