from PySide6.QtWidgets import QHBoxLayout, QFileDialog
from qfluentwidgets import (
    LineEdit, BodyLabel, PushButton, MessageBoxBase
)


class DecryptXtcXmlMessageBox(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)

        # 1. Dialog Header Config
        self.titleLabel = BodyLabel("Decrypt Xtc Xml", self)
        self.titleLabel.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.setSpacing(16)

        # 2. Horizontal layout setup for file path selection
        path_layout = QHBoxLayout()
        path_layout.setSpacing(12)

        self.path_label = BodyLabel("Path")
        self.path_label.setFixedWidth(50)

        self.file_path_edit = LineEdit()
        self.file_path_edit.setPlaceholderText("")

        self.browse_btn = PushButton("Browse")
        self.browse_btn.setFixedWidth(85)
        self.browse_btn.clicked.connect(self.open_file_dialog)

        path_layout.addWidget(self.path_label)
        path_layout.addWidget(self.file_path_edit, 1)
        path_layout.addWidget(self.browse_btn)

        self.viewLayout.addLayout(path_layout)

        # 3. Action Buttons Configuration
        self.yesButton.setText("Run")
        self.cancelButton.setText("Close")

        # Disconnect default auto-dismiss functionality
        self.yesButton.clicked.disconnect()
        self.yesButton.clicked.connect(self.do_decrypt)

        # Enforce dialog dimensions to match the reference look
        self.widget.setMinimumWidth(460)

    def open_file_dialog(self):
        """Opens native file picker targeted at XML logs/files."""
        file_path, _ = QFileDialog.getExistingDirectory(
            self, "Select Encrypted XML File"
        )
        if file_path:
            self.file_path_edit.setText(file_path)



