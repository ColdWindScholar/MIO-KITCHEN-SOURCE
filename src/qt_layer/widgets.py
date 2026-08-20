import tkinter as tk

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout


class TkinterEmbeddedPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # 1. Force Qt to create a native window handle/X11 ID for THIS specific widget
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        layout = QVBoxLayout()
        self.widget = QWidget()
        layout.addWidget(self.widget)
        self.setLayout(layout)
        # 2. Bind Tkinter root directly into the Qt Widget's handle
        # The 'use' parameter forces Tkinter to render inside the Qt boundary
        self.tk_root = tk.Tk(use=hex(self.widget.winId()))
        self.timer = QTimer(self)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.tk_root.update)
        self.timer.start()

class Empty2(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("e12")


class Empty3(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("e1122")


class Empty4(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("e12121")