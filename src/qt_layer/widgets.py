from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget


import tkinter as tk

class TkinterEmbeddedPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # 1. Force Qt to create a native window handle/X11 ID for THIS specific widget
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.win_id = int(self.winId())  # Get the raw X11 Window ID

        # 2. Bind Tkinter root directly into the Qt Widget's handle
        # The 'use' parameter forces Tkinter to render inside the Qt boundary
        self.tk_root = tk.Tk(use=hex(self.win_id))

        # 3. Create your layout inside the bound root
        self.tk_frame = tk.Frame(self.tk_root, bg="darkred")
        self.tk_frame.pack(fill=tk.BOTH, expand=True)

        tk_label = tk.Label(self.tk_frame, text="Embedded via X11 Window Handle", fg="white", bg="darkred")
        tk_label.pack(pady=30, padx=30)

        # 4. Drive Tkinter event cycle asynchronously via Qt Timer
        self.timer = QTimer(self)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.tk_root.update)
        self.timer.start()