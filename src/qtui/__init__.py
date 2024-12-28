from PyQt6.QtGui import QIcon, QPixmap, QFont
from ..core.images import icon_byte
from PyQt6.QtWidgets import QMainWindow, QWidget, QTabWidget, QVBoxLayout, QFrame, QLabel, QGridLayout
from PyQt6.QtCore import Qt, QTimer, QDateTime


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
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.layout = QGridLayout(self.main_widget)
        self.left_layout = QVBoxLayout()
        self.time_count = QLabel()
        self.time_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_count.setFont(QFont("SunValleyTitleFont", 18, 75))
        self.left_layout.addWidget(self.time_count)
        self.left_widget = QWidget()
        self.left_widget.setLayout(self.left_layout)
        self.layout.addWidget(self.left_widget, 0, 0, 5, 1)
        self.Timer = QTimer()
        self.Timer.start(1000)
        self.Timer.timeout.connect(self.update_time)

    def update_time(self):
        time = QDateTime.currentDateTime()
        timeplay = time.toString('hh:mm:ss')
        self.time_count.setText(timeplay)