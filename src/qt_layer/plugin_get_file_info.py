import os
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication, QVBoxLayout, QHBoxLayout, QFileDialog, QWidget
from qfluentwidgets import (
    BodyLabel, LineEdit, PushButton, MessageBoxBase
)

from src.core.utils import gettype, hum_convert, calculate_md5_file, calculate_sha256_file


class DropWidget(QWidget):
    """Custom drag & drop card that allows file drop or click-to-select."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(80)

        self.setObjectName("DropWidget")
        self.setStyleSheet("""
            #DropWidget {
                border: 1px dashed rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                background: rgba(255, 255, 255, 0.03);
            }
            #DropWidget:hover {
                background: rgba(255, 255, 255, 0.06);
                border: 1px dashed rgba(255, 255, 255, 0.3);
            }
        """)

        self.label = BodyLabel(self.tr("Drag and drop the file(s) here\nor click to select a file"), self)
        self.label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.setContentsMargins(15, 10, 15, 10)

        self.file_selected_callback = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            file_path, _ = QFileDialog.getOpenFileName(self, self.tr("Select File"))
            if file_path and self.file_selected_callback:
                self.file_selected_callback(file_path)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isfile(file_path) and self.file_selected_callback:
                self.file_selected_callback(file_path)
                break


class FileInfoRow(QHBoxLayout):
    """Reusable custom horizontal form field row with integrated Copy button."""
    def __init__(self, label_text: str, parent=None):
        super().__init__()

        self.label = BodyLabel(label_text)
        self.label.setFixedWidth(75)

        self.line_edit = LineEdit()
        self.line_edit.setReadOnly(True)

        self.copy_btn = PushButton(self.tr("Copy"))
        self.copy_btn.setFixedWidth(75)
        self.copy_btn.clicked.connect(self.copy_to_clipboard)

        self.addWidget(self.label)
        self.addWidget(self.line_edit)
        self.addWidget(self.copy_btn)
        self.setSpacing(10)

    def set_value(self, text: str):
        self.line_edit.setText(text)
        self.line_edit.setToolTip(text)

    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.line_edit.text())


class FileInfoMessageBox(MessageBoxBase):
    """Custom Dialog Box inheriting from MessageBoxBase."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = BodyLabel(self.tr("Get file info"), self)
        self.titleLabel.setStyleSheet("font-size: 18px; font-weight: bold;")

        # Add components to viewLayout (provided automatically by MessageBoxBase)
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.setSpacing(12)

        # 1. Drop Zone area
        self.drop_widget = DropWidget()
        self.drop_widget.file_selected_callback = self.update_file_info
        self.viewLayout.addWidget(self.drop_widget)

        # 2. Section Header
        self.info_header = BodyLabel(self.tr("INFO"))
        self.info_header.setStyleSheet("font-weight: bold; color: rgba(255, 255, 255, 0.6);")
        self.viewLayout.addWidget(self.info_header)

        # 3. Metadata fields
        self.rows = {
            "Name": FileInfoRow("Name:"),
            "Path": FileInfoRow("Path:"),
            "Type": FileInfoRow("Type:"),
            "Size": FileInfoRow("Size:"),
            "Size(B)": FileInfoRow("Size(B):"),
            "Time": FileInfoRow("Time:"),
            "MD5": FileInfoRow("MD5:"),
            "SHA256": FileInfoRow("SHA256:")
        }

        for row in self.rows.values():
            self.viewLayout.addLayout(row)

        # Configure action buttons
        self.yesButton.setText("Close")
        self.cancelButton.hide() # Hide the cancel button if it is not needed

        # Enforce dialog width rules
        self.widget.setMinimumWidth(480)

    def update_file_info(self, file_path: str):
        """Processes the file metrics onto row views."""
        if not os.path.exists(file_path):
            return

        stat_info = os.stat(file_path)
        file_name = os.path.basename(file_path)
        file_size_bytes = stat_info.st_size
        file_size_hum = hum_convert(file_size_bytes)
        file_type = gettype(file_path)

        self.rows["Name"].set_value(file_name)
        self.rows["Path"].set_value(file_path)
        self.rows["Type"].set_value(file_type)
        self.rows["Size"].set_value(file_size_hum)
        self.rows["Size(B)"].set_value(str(file_size_bytes))
        self.rows["Time"].set_value( time.ctime(os.path.getctime(file_path)))
        self.rows["MD5"].set_value(calculate_md5_file(file_path))
        self.rows["SHA256"].set_value(calculate_sha256_file(file_path))