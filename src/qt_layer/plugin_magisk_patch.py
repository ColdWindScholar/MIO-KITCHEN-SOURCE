import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QFileDialog
from qfluentwidgets import (
    MessageBoxBase,
    SubtitleLabel,
    LineEdit,
    PushButton,
    ComboBox,
    CheckBox
)


class MagiskPatchDialog(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)

        # 1. Custom Title Setup
        self.titleLabel = SubtitleLabel(self.tr("Magisk Patch"), self)

        # 2. Main Input Controls
        self.bootFileLineEdit = LineEdit(self)
        self.bootFileLineEdit.setPlaceholderText(self.tr("Select Boot file (.img)..."))
        self.bootBrowseBtn = PushButton(self.tr("Browse"), self)

        self.magiskApkLineEdit = LineEdit(self)
        self.magiskApkLineEdit.setPlaceholderText(self.tr("Select Magisk APK (.apk)..."))
        self.magiskBrowseBtn = PushButton(self.tr("Browse"), self)

        self.archComboBox = ComboBox(self)
        self.archComboBox.addItems(["arm64-v8a", "armeabi-v7a", "x86", "x86_64"])
        self.archComboBox.setCurrentIndex(0)

        # 3. Checkboxes
        self.is64bitCheck = CheckBox("IS64BIT", self)
        self.keepVerityCheck = CheckBox("KEEPVERITY", self)
        self.keepForceEncryptCheck = CheckBox("KEEPFORCEENCRYPT", self)
        self.recoveryModeCheck = CheckBox("RECOVERYMODE", self)

        self.is64bitCheck.setChecked(True)
        self.keepVerityCheck.setChecked(True)
        self.keepForceEncryptCheck.setChecked(True)
        self.recoveryModeCheck.setChecked(True)

        # 4. Connect Click Events to File Browse Functions
        self.bootBrowseBtn.clicked.connect(self.browse_boot_file)
        self.magiskBrowseBtn.clicked.connect(self.browse_magisk_apk)

        # 5. Integrate into Dialog View Layout
        self.initLayout()

        self.yesButton.setText(self.tr("Patch"))
        self.cancelButton.hide()
        self.widget.setMinimumWidth(420)

    def initLayout(self):
        self.viewLayout.addWidget(self.titleLabel)

        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(0, 10, 0, 10)
        grid_layout.setSpacing(12)

        # Row 0: Boot File Selection
        boot_lbl = SubtitleLabel(self.tr("Boot file:"), self)
        boot_lbl.setStyleSheet("font-size: 14px;")
        grid_layout.addWidget(boot_lbl, 0, 0, Qt.AlignLeft | Qt.AlignVCenter)
        grid_layout.addWidget(self.bootFileLineEdit, 0, 1)
        grid_layout.addWidget(self.bootBrowseBtn, 0, 2)

        # Row 1: Magisk APK Selection
        apk_lbl = SubtitleLabel(self.tr("Magisk APK:"), self)
        apk_lbl.setStyleSheet("font-size: 14px;")
        grid_layout.addWidget(apk_lbl, 1, 0, Qt.AlignLeft | Qt.AlignVCenter)
        grid_layout.addWidget(self.magiskApkLineEdit, 1, 1)
        grid_layout.addWidget(self.magiskBrowseBtn, 1, 2)

        # Row 2: Architecture Dropdown
        arch_lbl = SubtitleLabel(self.tr("Arch:"), self)
        arch_lbl.setStyleSheet("font-size: 14px;")
        grid_layout.addWidget(arch_lbl, 2, 0, Qt.AlignLeft | Qt.AlignVCenter)
        grid_layout.addWidget(self.archComboBox, 2, 1, 1, 2)

        self.viewLayout.addLayout(grid_layout)

        check_layout = QGridLayout()
        check_layout.setContentsMargins(0, 5, 0, 15)
        check_layout.setSpacing(10)

        check_layout.addWidget(self.is64bitCheck, 0, 0)
        check_layout.addWidget(self.keepVerityCheck, 0, 1)
        check_layout.addWidget(self.keepForceEncryptCheck, 1, 0)
        check_layout.addWidget(self.recoveryModeCheck, 1, 1)

        self.viewLayout.addLayout(check_layout)

    # File browsing implementations
    def browse_boot_file(self):
        # Open file dialog limited to image files (.img)
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select Boot Image"),
            os.getcwd(),
            "Boot Image (*.img);;All Files (*)"
        )
        if file_path:
            self.bootFileLineEdit.setText(file_path)

    def browse_magisk_apk(self):
        # Open file dialog limited to Android package files (.apk)
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select Magisk APK"),
            os.getcwd(),
            "Android Package (*.apk);;All Files (*)"
        )
        if file_path:
            self.magiskApkLineEdit.setText(file_path)
