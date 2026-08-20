from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtGui import QCursor


class ClickableLabel(QLabel):
    clicked = Signal()

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMouseTracking(True)

    def enterEvent(self, event):
        """Show hand cursor when entering widget"""
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Reset cursor when leaving widget"""
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)