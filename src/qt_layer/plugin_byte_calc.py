from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout
from qfluentwidgets import (
    LineEdit, ComboBox, BodyLabel, MessageBoxBase
)

class FileBytesMessageBox(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.units = {
            "B": 1,
            "KB": 1024,
            "MB": 1024 ** 2,
            "GB": 1024 ** 3,
            "TB": 1024 ** 4,
            "PB": 1024 ** 5
        }

        self._is_calculating = False  # Flag to prevent recursion

        # 1. Dialog title configuration
        self.titleLabel = BodyLabel(self.tr("Byte calculator"), self)
        self.titleLabel.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.setSpacing(15)

        # 2. Horizontal layout setup for calculation inputs
        calc_layout = QHBoxLayout()
        calc_layout.setSpacing(8)

        # Left field
        self.origin_size = LineEdit()
        self.origin_size.textChanged.connect(self.calc_forward)

        # Left combobox
        self.h = ComboBox()
        self.h.addItems(list(self.units.keys()))
        self.h.setCurrentIndex(0)
        self.h.currentTextChanged.connect(self.calc_forward)
        self.h.setFixedWidth(75)

        # Equals separator
        equal_label = BodyLabel("=")
        equal_label.setAlignment(Qt.AlignCenter)

        # Right field
        self.result_size = LineEdit()
        self.result_size.textChanged.connect(self.calc_reverse)

        # Right combobox
        self.f_ = ComboBox()
        self.f_.addItems(list(self.units.keys()))
        self.f_.setCurrentIndex(0)
        self.f_.currentTextChanged.connect(self.calc_reverse)
        self.f_.setFixedWidth(75)

        # Stack calculation components horizontally
        calc_layout.addWidget(self.origin_size, 1)
        calc_layout.addWidget(self.h)
        calc_layout.addWidget(equal_label)
        calc_layout.addWidget(self.result_size, 1)
        calc_layout.addWidget(self.f_)

        self.viewLayout.addLayout(calc_layout)

        # 3. Handle base action buttons
        self.yesButton.setText(self.tr("Close"))
        self.cancelButton.hide()  # Hide default cancel action button

        # Set modal window constraint boundaries
        self.widget.setMinimumWidth(540)

    def calc_forward(self, text=None):
        """Calculates value conversion from left to right."""
        if self._is_calculating:
            return

        self._is_calculating = True
        try:
            origin_unit = self.h.currentText()
            target_unit = self.f_.currentText()
            origin_value_str = self.origin_size.text()

            result_value_str = self.__calc(origin_unit, target_unit, origin_value_str)

            if self.result_size.text() != result_value_str:
                self.result_size.setText(result_value_str)
        finally:
            self._is_calculating = False

    def calc_reverse(self, text=None):
        """Calculates value conversion from right to left."""
        if self._is_calculating:
            return

        self._is_calculating = True
        try:
            origin_unit = self.f_.currentText()
            target_unit = self.h.currentText()
            origin_value_str = self.result_size.text()

            result_value_str = self.__calc(origin_unit, target_unit, origin_value_str)

            if self.origin_size.text() != result_value_str:
                self.origin_size.setText(result_value_str)
        finally:
            self._is_calculating = False

    def __calc(self, origin_unit: str, target_unit: str, size_str: str) -> str:
        """Core unit scaling calculation logic."""
        size_str = size_str.strip()

        if not size_str:
            return ""

        try:
            size = float(size_str)
        except ValueError:
            if size_str == '.' or size_str == '-' or size_str == '-.' or \
                    (size_str.startswith('-') and size_str.count('.') <= 1 and all(
                        c.isdigit() or c == '.' for c in size_str[1:])) or \
                    (size_str.count('.') <= 1 and all(c.isdigit() or c == '.' for c in size_str)):
                return ""
            else:
                return "Invalid"

        if origin_unit == target_unit:
            return str(int(size)) if size.is_integer() else str(size)

        result = size * self.units[origin_unit] / self.units[target_unit]

        if result.is_integer():
            return str(int(result))
        else:
            return f"{result:.6f}".rstrip('0').rstrip('.')
