from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from qfluentwidgets import (
    BodyLabel, PushButton, CheckBox, SearchLineEdit,
    MessageBoxBase, TableWidget
)


class DisableAvbMessageBox(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.__init_ui()
        self.__init_layout()
        self.populate_partitions()

        self.widget.setMinimumWidth(520)

    def __init_ui(self):
        """Instantiates all interface components cleanly using Fluent widgets."""
        self.titleLabel = BodyLabel("Disable AVB in fstab", self)
        self.titleLabel.setStyleSheet("font-size: 18px; font-weight: bold;")

        hint_text = (
            "Select the partition(s) where you want to disable the AVB check.\n"
            "The tool will automatically find and edit the fstab files."
        )
        self.hintLabel = BodyLabel(hint_text, self)
        self.hintLabel.setWordWrap(True)

        self.list_header = BodyLabel("Available Partitions")
        self.list_header.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 12px;")

        # Card container box panel
        self.container_panel = QWidget()
        self.container_panel.setObjectName("ContainerPanel")


        # ─── UPDATED: Using qfluentwidgets.TableWidget for native Fluent style ───
        self.table_widget = TableWidget()
        self.table_widget.setColumnCount(2)
        self.table_widget.setHorizontalHeaderLabels(["Name", "Type"])
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

        self.select_all_checkbox = CheckBox("Select all")
        self.select_all_checkbox.stateChanged.connect(self.toggle_all_items)

        self.search_edit = SearchLineEdit()
        self.search_edit.setPlaceholderText("Search partitions...")
        self.search_edit.textChanged.connect(self.filter_partitions)

        # Dialog control action buttons re-mapping configs
        self.yesButton.setText("Run")
        self.cancelButton.hide()

        self.refresh_btn = PushButton("Refresh", self)
        self.refresh_btn.setFixedWidth(80)
        self.refresh_btn.clicked.connect(self.populate_partitions)
        self.buttonLayout.insertWidget(0, self.refresh_btn)

        self.yesButton.clicked.disconnect()
        self.yesButton.clicked.connect(self.on_run_clicked)

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

        partitions_data = [
            ("vendor", "ext"), ("system", "erofs"), ("product", "ext"),
            ("boot", "raw"), ("odm", "erofs")
        ]
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
        selected_targets = []
        for row in range(self.table_widget.rowCount()):
            checkbox = self.table_widget.cellWidget(row, 0)
            ext_item = self.table_widget.item(row, 1)
            if isinstance(checkbox, CheckBox) and checkbox.isChecked():
                name = checkbox.text()
                ext = ext_item.text().strip('[]') if ext_item else ""
                selected_targets.append({"name": name, "ext": ext})
        return selected_targets

    def on_run_clicked(self):
        """Triggered when the Run button is pressed."""
        selected = self.get_selected_partitions()
        print(f"Run triggered with selections: {selected}")


