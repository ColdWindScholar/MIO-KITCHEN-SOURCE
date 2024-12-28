from PyQt6.QtWidgets import QMainWindow, QWidget
class Error(QWidget):
    def __init__(self, code, desc="unknown error"):
        super().__init__()
        self.setWindowTitle("")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MIO-KITCHEN")