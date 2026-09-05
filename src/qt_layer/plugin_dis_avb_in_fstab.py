import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from qfluentwidgets import (
    BodyLabel, PushButton, CheckBox, SearchLineEdit,
    MessageBoxBase, TableWidget
)
from src.qt_layer.settings_cfg import cfg
from utils import JsonEdit


class DisableAvbMessageBox(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.__init_ui()
        self.__init_layout()
        self.partitions_with_fstab = dict()
        self.populate_partitions()
        self.widget.setMinimumWidth(520)

    def __init_ui(self):
        """Instantiates all interface components cleanly using Fluent widgets."""
        self.titleLabel = BodyLabel(self.tr("Disable AVB in fstab"), self)
        self.titleLabel.setStyleSheet("font-size: 18px; font-weight: bold;")

        hint_text = self.tr(
            "Select the partition(s) where you want to disable the AVB check.\n"
            "The tool will automatically find and edit the fstab files."
        )
        self.hintLabel = BodyLabel(hint_text, self)
        self.hintLabel.setWordWrap(True)

        self.list_header = BodyLabel(self.tr("Available Partitions"))
        self.list_header.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 12px;")

        # Card container box panel
        self.container_panel = QWidget()
        self.container_panel.setObjectName("ContainerPanel")


        # ─── UPDATED: Using qfluentwidgets.TableWidget for native Fluent style ───
        self.table_widget = TableWidget()
        self.table_widget.setColumnCount(2)
        self.table_widget.setHorizontalHeaderLabels([self.tr("Name"), self.tr("Type")])
        self.table_widget.setSelectionMode(QAbstractItemView.NoSelection)
        self.table_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # Grid settings matching Fluent guidelines
        self.table_widget.setBorderRadius(4)
        self.table_widget.setMinimumHeight(180)

        # Header configurations
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)

        self.line_separator = QWidget()
        self.line_separator.setFixedHeight(1)

        self.select_all_checkbox = CheckBox(self.tr("Select all"))
        self.select_all_checkbox.stateChanged.connect(self.toggle_all_items)

        self.search_edit = SearchLineEdit()
        self.search_edit.setPlaceholderText(self.tr("Search partitions..."))
        self.search_edit.textChanged.connect(self.filter_partitions)

        # Dialog control action buttons re-mapping configs
        self.yesButton.setText(self.tr("Run"))

        self.refresh_btn = PushButton(self.tr("Refresh"), self)
        self.refresh_btn.setFixedWidth(80)
        self.refresh_btn.clicked.connect(self.populate_partitions)
        self.buttonLayout.insertWidget(0, self.refresh_btn)


    def __init_layout(self):
        """Assembles components structural alignments layout framework hierarchy."""
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.setSpacing(12)
        self.viewLayout.addWidget(self.hintLabel)
        self.viewLayout.addWidget(self.list_header)

        container_layout = QVBoxLayout(self.container_panel)
        container_layout.setContentsMargins(12, 12, 12, 12)
        container_layout.setSpacing(12)
        container_layout.addWidget(self.table_widget)
        container_layout.addWidget(self.line_separator)

        bottom_tool_layout = QHBoxLayout()
        bottom_tool_layout.addWidget(self.select_all_checkbox)
        bottom_tool_layout.addWidget(self.search_edit, 1)
        container_layout.addLayout(bottom_tool_layout)

        self.viewLayout.addWidget(self.container_panel)

    def populate_partitions(self):
        """Populates the Fluent table view rows."""
        self.table_widget.setRowCount(0)
        self.select_all_checkbox.setChecked(False)
        self.search_edit.clear()

        # Partition data database list tuples (Name, Extension Type)
        path = os.path.join(cfg.workingFolder.value, cfg.currentProjectName.value)
        if not os.path.exists(path):
            return
        parts_info_path = os.path.join(path, "config", "parts_info")
        parts_dict = dict()
        if os.path.exists(parts_info_path):
            parts_dict = JsonEdit(parts_info_path).read()

        for item_name in sorted(os.listdir(path)):
            item_path = os.path.join(path, item_name)
            if os.path.isdir(item_path):
                for root, _, files in os.walk(item_path):
                    for file in files:
                        if 'fstab' in file.lower():
                            if item_name not in self.partitions_with_fstab:
                                self.partitions_with_fstab[item_name] = []
                            self.partitions_with_fstab[item_name].append(os.path.join(root, file))
        partitions_data = []
        for partition_name in self.partitions_with_fstab.keys():
            fs_type = parts_dict.get(partition_name, 'unknown')
            partitions_data.append((partition_name, fs_type))

        self.table_widget.setRowCount(len(partitions_data))

        for row, (name, ext) in enumerate(partitions_data):
            # Checkbox embedded in cell
            checkbox = CheckBox(name)
           # checkbox.setStyleSheet("background: transparent; padding-left: 6px;")
            self.table_widget.setCellWidget(row, 0, checkbox)

            # Formatted text column item
            ext_item = QTableWidgetItem(f"[{ext}]")
            ext_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            ext_item.setFlags(ext_item.flags() & ~Qt.ItemIsEditable)
            self.table_widget.setItem(row, 1, ext_item)

    def filter_partitions(self, text):
        """Filters rows dynamically based on the search query."""
        search_term = text.lower().strip()
        for row in range(self.table_widget.rowCount()):
            checkbox = self.table_widget.cellWidget(row, 0)
            if isinstance(checkbox, CheckBox):
                self.table_widget.setRowHidden(row, search_term not in checkbox.text().lower())

    def toggle_all_items(self, state):
        """Synchronizes row updates over currently active visible fields selection."""
        is_checked = (state == 2 or state == Qt.Checked)
        for row in range(self.table_widget.rowCount()):
            if not self.table_widget.isRowHidden(row):
                checkbox = self.table_widget.cellWidget(row, 0)
                if isinstance(checkbox, CheckBox):
                    checkbox.blockSignals(True)
                    checkbox.setChecked(is_checked)
                    checkbox.blockSignals(False)

    def get_selected_partitions(self):
        """Helper method to easily extract checked rows from your external scripts."""
        for row in range(self.table_widget.rowCount()):
            checkbox = self.table_widget.cellWidget(row, 0)
            if isinstance(checkbox, CheckBox) and checkbox.isChecked():
                yield checkbox.text()
