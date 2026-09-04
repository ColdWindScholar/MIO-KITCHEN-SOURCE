from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout
from qfluentwidgets import (
    MessageBoxBase,
    SubtitleLabel,
    BodyLabel,
    LineEdit,
    SwitchButton
)


class MergeImageDialog(MessageBoxBase):
    def __init__(self, parent=None, project_path:str|None = None):
        super().__init__(parent)

        # 1. Custom Title
        self.titleLabel = SubtitleLabel("Merge Image Segments", self)

        # 2. Description Text Block
        self.descriptionLabel = BodyLabel(
            "This utility will find and merge file segments (e.g., `super.img.0`, "
            "`super.img.1`) in your project to create a single, complete image.",
            self
        )
        self.descriptionLabel.setWordWrap(True)
        # Give a slight muted tint to mimic the original look
        self.descriptionLabel.setStyleSheet("color: #b0b0b0; font-size: 13px; line-height: 1.4;")

        # 3. Project Path Display
        self.pathLabel = BodyLabel(f"Project Path: {project_path}", self)
        self.pathLabel.setStyleSheet("color: #808080; font-size: 13px;")

        # 4. Form Controls
        self.outputFileNameLabel = BodyLabel("Output File Name:", self)
        self.outputFileNameLabel.setStyleSheet("font-size: 14px;")

        self.outputFileNameLineEdit = LineEdit(self)
        self.outputFileNameLineEdit.setText("super.img")

        # 5. Toggle Switch
        self.deleteSegmentsSwitch = SwitchButton(self)
        self.switchLabel = BodyLabel("Delete source segments after merging", self)
        self.switchLabel.setStyleSheet("font-size: 13px;")

        # 6. Build Layout Structure
        self.initLayout()

        # 7. Configure Bottom Main Button
        self.yesButton.setText("Create Super Image")
        self.cancelButton.hide()  # Hiding the default secondary button

        self.widget.setMinimumWidth(440)

    def initLayout(self):
        # Stack header information sequentially
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addSpacing(10)
        self.viewLayout.addWidget(self.descriptionLabel)
        self.viewLayout.addSpacing(10)
        self.viewLayout.addWidget(self.pathLabel)
        self.viewLayout.addSpacing(15)

        # Form Layout row containing Input field
        form_layout = QGridLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.addWidget(self.outputFileNameLabel, 0, 0, Qt.AlignLeft | Qt.AlignVCenter)
        form_layout.addWidget(self.outputFileNameLineEdit, 0, 1)
        # Give column 1 the expanding priority weight
        form_layout.setColumnStretch(1, 1)
        self.viewLayout.addLayout(form_layout)

        self.viewLayout.addSpacing(15)

        # Row layout for the Fluent Switch button setup
        switch_layout = QHBoxLayout()
        switch_layout.setContentsMargins(0, 0, 0, 10)
        switch_layout.setSpacing(10)
        switch_layout.addWidget(self.deleteSegmentsSwitch)
        switch_layout.addWidget(self.switchLabel)
        switch_layout.addStretch(1)  # Keep elements tightly grouped on the left

        self.viewLayout.addLayout(switch_layout)