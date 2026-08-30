from PySide6.QtWidgets import QHBoxLayout, QWidget, QFileDialog
from qfluentwidgets import (
    LineEdit, EditableComboBox, BodyLabel, PushButton, MessageBoxBase
)


class MergeQualcommImageMessageBox(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.__init_ui()
        self.__init_layout()

        # Enforce dialog structural width
        self.widget.setMinimumWidth(480)

    def __init_ui(self):
        """Instantiates all form elements and controls."""
        # Main Dialog Header Title
        self.titleLabel = BodyLabel("Merge Qualcomm Image", self)
        self.titleLabel.setStyleSheet("font-size: 18px; font-weight: bold;")

        # ─── Row 1: RawProgram Xml ───
        self.raw_label = BodyLabel("RawProgram Xml :")
        self.raw_label.setFixedWidth(130)
        self.raw_path_edit = LineEdit()
        self.raw_browse_btn = PushButton("Browse")
        self.raw_browse_btn.setFixedWidth(85)
        self.raw_browse_btn.clicked.connect(self.browse_raw_xml)

        # ─── Row 2: Partition Name ───
        self.partition_label = BodyLabel("Partition Name:")
        self.partition_label.setFixedWidth(130)
        self.partition_combo = EditableComboBox()
        # Populating standard mock items; user can type custom partitions too
        self.partition_combo.addItems(["userdata", "system", "vendor", "boot"])
        self.partition_combo.setCurrentText("userdata")

        # ─── Row 3: OutPut Path ───
        self.output_label = BodyLabel("OutPut Path:")
        self.output_label.setFixedWidth(130)
        self.output_path_edit = LineEdit()
        self.output_browse_btn = PushButton("Browse")
        self.output_browse_btn.setFixedWidth(85)
        self.output_browse_btn.clicked.connect(self.browse_output_folder)

        # ─── Action Buttons ───
        self.yesButton.setText("Run")


    def __init_layout(self):
        """Builds cohesive horizontal rows inside the core layout view context."""
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.setSpacing(16)

        # Row 1 Layout Assembly
        row1 = QHBoxLayout()
        row1.setSpacing(10)
        row1.addWidget(self.raw_label)
        row1.addWidget(self.raw_path_edit, 1)
        row1.addWidget(self.raw_browse_btn)
        self.viewLayout.addLayout(row1)

        # Row 2 Layout Assembly
        row2 = QHBoxLayout()
        row2.setSpacing(10)
        row2.addWidget(self.partition_label)
        row2.addWidget(self.partition_combo, 1)
        # Adding an empty placeholder widget mirroring the browse layout spacing alignment gap
        spacer = QWidget()
        spacer.setFixedWidth(85)
        row2.addWidget(spacer)
        self.viewLayout.addLayout(row2)

        # Row 3 Layout Assembly
        row3 = QHBoxLayout()
        row3.setSpacing(10)
        row3.addWidget(self.output_label)
        row3.addWidget(self.output_path_edit, 1)
        row3.addWidget(self.output_browse_btn)
        self.viewLayout.addLayout(row3)

    def browse_raw_xml(self):
        """Picks a single XML configuration targets stream."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select RawProgram XML File", "", "XML Files (*.xml);;All Files (*)"
        )
        if file_path:
            self.raw_path_edit.setText(file_path)

    def browse_output_folder(self):
        """Targets directory files creation destination paths hooks."""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Output Directory", "")
        if folder_path:
            self.output_path_edit.setText(folder_path)

    def get_form_data(self):
        """Helper to extract active widget configurations."""
        return {
            "xml_path": self.raw_path_edit.text().strip(),
            "partition": self.partition_combo.currentText().strip(),
            "output_path": self.output_path_edit.text().strip()
        }
