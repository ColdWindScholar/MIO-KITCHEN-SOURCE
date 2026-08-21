import os
from shutil import rmtree

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QListWidget, QHBoxLayout, QWidget, QListWidgetItem
from qfluentwidgets import SimpleCardWidget, BodyLabel, CheckBox, ComboBox, RadioButton, PushButton, ScrollArea, \
    SearchLineEdit, FluentIcon as FIF, ListWidget, PrimaryPushButton, SubtitleLabel

from qt_layer.settings import cfg


class ProjectManager:
    def __init__(self):
        self.hide_items = ['bin', 'src', 'readmes']

    @staticmethod
    def get_work_path(name):
        path = str(os.path.join(cfg.workingFolder.value, name) + os.sep)
        return path if os.name != 'nt' else path.replace('\\', '/')

    def get_projects(self):
        for f in os.listdir(cfg.workingFolder.value):
            if os.path.isdir(f'{cfg.workingFolder.value}/{f}') and f not in self.hide_items and not f.startswith('.'):
                yield f

    def new(self, name: str):
        if ' ' in name:
            name = name.replace(" ", '_')
        path = self.get_work_path(name)
        os.makedirs(path, exist_ok=True)
        return path

    def current_work_path(self, mkdir=False):
        if cfg.projectStructure.value == 'Single':
            path = self.get_work_path(cfg.currentProjectName.value)
        else:
            path = os.path.join(self.get_work_path(cfg.currentProjectName.value), 'Source') + os.sep
            if not os.path.exists(path) and cfg.currentProjectName.value:
                os.makedirs(path, exist_ok=True)
        if mkdir:
            os.makedirs(path, exist_ok=True)
        return path if os.name != 'nt' else path.replace('\\', '/')

    def current_origin_path(self):
        if cfg.projectStructure.value == 'Single':
            path = self.get_work_path(cfg.currentProjectName.value)
        else:
            path = os.path.join(self.get_work_path(cfg.currentProjectName.value), 'Origin') + os.sep
            if not os.path.exists(path) and cfg.currentProjectName.value:
                os.makedirs(path, exist_ok=True)
        return path if os.name == 'nt' else path.replace('\\', '/')

    def current_work_output_path(self):
        if cfg.workingFolder.value == 'Single':
            path = self.get_work_path(cfg.currentProjectName.value)
        else:
            path = os.path.join(self.get_work_path(cfg.currentProjectName.value), 'Output') + os.sep
            if not os.path.exists(path) and cfg.currentProjectName.value:
                os.makedirs(path, exist_ok=True)
        return path if os.name != 'nt' else path.replace('\\', '/')

    def exist(self, name=None):
        current_name = name or cfg.currentProjectName.value
        if not current_name:
            return False
        return os.path.exists(self.get_work_path(current_name))

    def remove(self, name):
        if not self.exist(name):
            return True
        else:
            rmtree(self.get_work_path(name))
        return not self.exist(name)

project_manger = ProjectManager()


class ProjectsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ProjectsPage")
        self.cards_data = []

        # Enable QFluentWidgets native modern dark theme context
        self.initUI()

    def initUI(self):
        # 1. Main View Surface Configuration
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setStyleSheet("background-color: #1c1c1c;")

        # Custom high-performance scrolling layout track
        scroll_area = ScrollArea(self)
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)

        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setContentsMargins(24, 24, 24, 24)
        self.scroll_layout.setSpacing(20)  # Generous modern breathing room
        scroll_area.setWidget(scroll_content)

        # 2. Build Structured Application Cards
        self._build_project_card(scroll_content)
        self._build_partition_card(scroll_content)
        self._build_tools_card(scroll_content)

        # Push layout components to the top naturally
        self.scroll_layout.addStretch(1)

    def _build_project_card(self, parent_widget):
        """Builds the '项目' (Project Management) block."""
        card = SimpleCardWidget(parent_widget)
        card.setStyleSheet("border-radius: 12px; background-color: #272727; border: 1px solid #323232;")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header = SubtitleLabel("项目", card)
        header.setStyleSheet("color: #ffffff; font-weight: 600; font-size: 15px;")
        layout.addWidget(header)

        # Action Input Row
        row1 = QHBoxLayout()
        self.project_combo = ComboBox(card)
        self.project_combo.setPlaceholderText("选择项目...")
        self.project_combo.addItem("21212")  # Match screenshot state

        self.open_btn = PushButton("打开", card, FIF.FOLDER)
        row1.addWidget(self.project_combo, 1)
        row1.addWidget(self.open_btn)
        layout.addLayout(row1)

        # Management Control Bar Row
        row2 = QHBoxLayout()
        self.refresh_btn = PushButton("刷新", card, FIF.SYNC)
        self.new_btn = PushButton("新建", card, FIF.ADD)
        self.delete_btn = PushButton("删除", card, FIF.DELETE)
        self.delete_btn.setStyleSheet("color: #ff4d4f;")  # Red destructive style warning
        self.rename_btn = PushButton("重命名", card, FIF.EDIT)

        for btn in [self.refresh_btn, self.new_btn, self.delete_btn, self.rename_btn]:
            btn.setMinimumWidth(85)
            row2.addWidget(btn)
        row2.addStretch(1)
        layout.addLayout(row2)

        self.scroll_layout.addWidget(card)
        self.cards_data.append({"name": "project", "widget": card})

    def _build_partition_card(self, parent_widget):
        """Builds the '分区列表' (Partition Control) block."""
        card = SimpleCardWidget(parent_widget)
        card.setStyleSheet("border-radius: 12px; background-color: #272727; border: 1px solid #323232;")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header = SubtitleLabel("分区列表", card)
        header.setStyleSheet("color: #ffffff; font-weight: 600; font-size: 15px;")
        layout.addWidget(header)

        # UPGRADE: Converted ugly default box to high-performance Fluent ListWidget
        self.partition_list = ListWidget(card)
        self.partition_list.setFixedHeight(160)
        self.partition_list.setStyleSheet("""
            ListWidget {
                border: 1px solid #3a3a3a; 
                background: #1e1e1e; 
                border-radius: 8px; 
                padding: 4px;
            }
            ListWidget::item {
                color: #ffffff;
                padding: 6px 12px;
                border-radius: 4px;
            }
            ListWidget::item:hover {
                background: rgba(255, 255, 255, 0.08);
            }
            ListWidget::item:selected {
                background: #0078d4;
            }
        """)
        layout.addWidget(self.partition_list)

        # Filters and Selectors Row
        row1 = QHBoxLayout()
        self.select_all_cb = CheckBox("全选", card)
        self.select_all_cb.stateChanged.connect(self._handle_select_all)

        # UPGRADE: Transformed custom text entry into a modern real-time filter bar
        self.filter_input = SearchLineEdit(card)
        self.filter_input.setPlaceholderText("键入过滤规则进行筛选...")
        self.filter_input.setFixedWidth(240)
        self.filter_input.textChanged.connect(self._apply_list_filter)

        row1.addWidget(self.select_all_cb)
        row1.addStretch(1)
        row1.addWidget(self.filter_input)
        layout.addLayout(row1)

        # Task Modes (Radio Buttons) Row
        row2 = QHBoxLayout()
        self.unpack_rb = RadioButton("解包", card)
        self.pack_rb = RadioButton("打包", card)
        self.unpack_rb.setChecked(True)
        row2.addWidget(self.unpack_rb)
        row2.addWidget(self.pack_rb)
        row2.addStretch(1)
        layout.addLayout(row2)

        # Output Target Execution Row
        row3 = QHBoxLayout()
        self.format_combo = ComboBox(card)
        # Match all extensions present in your screenshot
        self.format_combo.addItems([
            "new.dat.br", "new.dat.xz", "new.dat",
            "img", "zst", "payload", "super", "update.app"
        ])
        self.format_combo.setCurrentText("img")  # Default snapshot match

        # Use PrimaryPushButton for the main execution call-to-action
        self.execute_btn = PrimaryPushButton("执行", card, FIF.PLAY)
        self.execute_btn.setMinimumWidth(100)

        row3.addWidget(self.format_combo, 1)
        row3.addWidget(self.execute_btn)
        layout.addLayout(row3)

        self.scroll_layout.addWidget(card)
        self.cards_data.append({"name": "partition", "widget": card})

    def _build_tools_card(self, parent_widget):
        """Builds the '其他' (Utilities) block."""
        card = SimpleCardWidget(parent_widget)
        card.setStyleSheet("border-radius: 12px; background-color: #272727; border: 1px solid #323232;")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header = SubtitleLabel("其他", card)
        header.setStyleSheet("color: #ffffff; font-weight: 600; font-size: 15px;")
        layout.addWidget(header)

        # Clean tool layout wrap structure
        tools_layout = QHBoxLayout()
        self.zip_btn = PushButton("打包ZIP", card, FIF.DELETE)
        self.super_btn = PushButton("打包Super", card, FIF.ALBUM)
        self.plugin_btn = PushButton("插件", card, FIF.APPLICATION)
        self.format_conv_btn = PushButton("格式转换", card, FIF.EMBED)
        self.apk_mgr_btn = PushButton("Apk管理器", card, FIF.DEVELOPER_TOOLS)

        for btn in [self.zip_btn, self.super_btn, self.plugin_btn, self.format_conv_btn, self.apk_mgr_btn]:
            btn.setMinimumWidth(100)
            tools_layout.addWidget(btn)

        tools_layout.addStretch(1)
        layout.addLayout(tools_layout)

        self.scroll_layout.addWidget(card)
        self.cards_data.append({"name": "other", "widget": card})

    def _apply_list_filter(self, text):
        """Fuzzy text rows parser filtering items on typing entry loop."""
        query = text.lower().strip()
        for i in range(self.partition_list.count()):
            item = self.partition_list.item(i)
            item.setHidden(query not in item.text().lower())

    def _handle_select_all(self, state):
        """Toggles check targeting visible items exclusively."""
        checked = (state == Qt.Checked or state == 2)
        for i in range(self.partition_list.count()):
            item = self.partition_list.item(i)
            if not item.isHidden():
                item.setSelected(checked)