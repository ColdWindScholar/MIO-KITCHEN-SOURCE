from PySide6.QtWidgets import QHBoxLayout, QFileDialog
from qfluentwidgets import (
    LineEdit, BodyLabel, PushButton, MessageBoxBase
)


class TrimRawImageMessageBox(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)

        # 1. Dialog title configuration
        self.titleLabel = BodyLabel(self.tr("Trim Raw Image"), self)
        self.titleLabel.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.setSpacing(16)

        # 2. Hint text description panel
        hint_text = self.tr(
            "HINT: This removes any end zero padding from file, "
            "useful if you plan to flash it using tools like "
            "MTKClient when sparse isn't an option for you."
        )
        self.hintLabel = BodyLabel(hint_text, self)
        self.hintLabel.setWordWrap(True)
        self.hintLabel.setStyleSheet("color: rgba(255, 255, 255, 0.8); line-height: 1.4;")
        self.viewLayout.addWidget(self.hintLabel)

        # 3. Horizontal layout setup for file selection
        file_layout = QHBoxLayout()
        file_layout.setSpacing(10)

        self.select_label = BodyLabel(self.tr("Select file:"))
        self.select_label.setFixedWidth(70)

        self.file_path_edit = LineEdit()
        self.file_path_edit.setPlaceholderText("")

        self.choose_btn = PushButton(self.tr("Choose"))
        self.choose_btn.setFixedWidth(80)
        self.choose_btn.clicked.connect(self.open_file_dialog)

        file_layout.addWidget(self.select_label)
        file_layout.addWidget(self.file_path_edit, 1)
        file_layout.addWidget(self.choose_btn)

        self.viewLayout.addLayout(file_layout)

        # 4. Handle dialog confirmation button mapping
        self.yesButton.setText(self.tr("Run"))
        self.cancelButton.hide()  # Hide default cancel action button

        # Connect the Run button to the execution method

        # Enforce consistent layout width rules matching the design
        self.widget.setMinimumWidth(460)

    def open_file_dialog(self):
        """Opens a standard file browser dialog to pick the targeted image file."""
        file_path, _ = QFileDialog.getOpenFileName(self, self.tr("Select Raw Image File"), "", "All Files (*)")
        if file_path:
            self.file_path_edit.setText(file_path)
