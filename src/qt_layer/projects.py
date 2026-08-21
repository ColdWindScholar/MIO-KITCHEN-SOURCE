import os
from shutil import rmtree

from PySide6.QtWidgets import QVBoxLayout, QListWidget, QHBoxLayout, QWidget, QListWidgetItem
from qfluentwidgets import SimpleCardWidget, BodyLabel, CheckBox, ComboBox, RadioButton, PushButton, ScrollArea, \
    SearchLineEdit,FluentIcon as FIF

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

        # Enforce unified dark aesthetic native to QFluentWidgets
        self.initUI()

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Clean surface background definition
        self.setStyleSheet("background-color: #1e1e1e;")

        scroll_area = ScrollArea(self)
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)

        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setContentsMargins(24, 24, 24, 24)
        self.scroll_layout.setSpacing(20)  # Balanced vertical breathing space
        scroll_area.setWidget(scroll_content)

        # Generate structural interface sections
        self._build_project_card(scroll_content)
        self._build_partition_card(scroll_content)
        self._build_tools_card(scroll_content)

        self.scroll_layout.addStretch(1)

        # Populate Mock Partition Items for demonstration
        self._load_mock_partitions()

    def _build_project_card(self, parent_widget):
        card = SimpleCardWidget(parent_widget)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = BodyLabel("项目管理 / Project Management", card)
        header.setStyleSheet("font-weight: 600; font-size: 14px; color: #ffffff;")
        layout.addWidget(header)

        # Main Entry Layer
        action_row = QHBoxLayout()
        self.project_combo = ComboBox(card)
        self.project_combo.setPlaceholderText("选择或搜索目标项目...")

        self.open_btn = PushButton("打开项目", card, FIF.FOLDER)
        # Deep blue accent for primary call to action

        action_row.addWidget(self.project_combo, 1)
        action_row.addWidget(self.open_btn)
        layout.addLayout(action_row)

        # Toolbar Control Strip
        mgmt_row = QHBoxLayout()
        self.new_btn = PushButton("新建", card, FIF.ADD)
        self.refresh_btn = PushButton("刷新", card, FIF.SYNC)
        self.rename_btn = PushButton("重命名", card, FIF.EDIT)
        self.delete_btn = PushButton("删除", card, FIF.DELETE)

        for btn in [self.new_btn, self.refresh_btn, self.rename_btn, self.delete_btn]:
            btn.setFixedWidth(90)
            mgmt_row.addWidget(btn)
        mgmt_row.addStretch(1)
        layout.addLayout(mgmt_row)

        self.scroll_layout.addWidget(card)
        self.cards_data.append({"name": "project", "widget": card})

    def _build_partition_card(self, parent_widget):
        card = SimpleCardWidget(parent_widget)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        header = BodyLabel("分区", card)
        layout.addWidget(header)

        # Dynamic Core List Layout
        self.partition_list = QListWidget(card)
        self.partition_list.setFixedHeight(160)
        self.partition_list.setStyleSheet(
            "border: 1px solid #2d2d2d; background: #202020; border-radius: 6px; padding: 4px;"
        )
        layout.addWidget(self.partition_list)

        # Refactored Interactive Filter / Search Controls Row
        config_form = QHBoxLayout()
        self.select_all_cb = CheckBox("全选所有", card)

        # UPGRADE: Converted ComboBox filter into a modern instant-search bar
        self.filter_input = SearchLineEdit(card)
        self.filter_input.setPlaceholderText("键入过滤规则进行筛选...")
        self.filter_input.setFixedWidth(220)
        self.filter_input.setClearButtonEnabled(True)
        # Connect typing changes instantly to the text filtering slot logic
        self.filter_input.textChanged.connect(self._filter_partition_items)

        config_form.addWidget(self.select_all_cb)
        config_form.addStretch(1)
        config_form.addWidget(self.filter_input)
        layout.addLayout(config_form)

        # Radio Operational Row
        process_row = QHBoxLayout()
        mode_layout = QHBoxLayout()
        self.unpack_rb = RadioButton("核心解包 (Unpack)", card)
        self.pack_rb = RadioButton("智能打包 (Pack)", card)
        self.unpack_rb.setChecked(True)
        mode_layout.addWidget(self.unpack_rb)
        mode_layout.addWidget(self.pack_rb)
        process_row.addLayout(mode_layout)
        process_row.addSpacing(40)

        # Extension configuration selector
        self.format_combo = ComboBox(card)
        self.format_combo.addItem("new.dat.br")
        self.format_combo.addItem("payload.bin")
        self.format_combo.setFixedWidth(130)

        self.execute_btn = PushButton("执行任务", card, FIF.PLAY)
        self.execute_btn.setFixedWidth(110)

        process_row.addWidget(self.format_combo)
        process_row.addWidget(self.execute_btn)
        layout.addLayout(process_row)

        self.scroll_layout.addWidget(card)
        self.cards_data.append({"name": "partition", "widget": card})

    def _build_tools_card(self, parent_widget):
        card = SimpleCardWidget(parent_widget)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = BodyLabel("高级工具箱 / Developer Tools", card)
        header.setStyleSheet("font-weight: 600; font-size: 14px; color: #ffffff;")
        layout.addWidget(header)

        tools_grid = QHBoxLayout()
        self.zip_btn = PushButton("打包 ZIP", card, FIF.PASTE)
        self.super_btn = PushButton("打包 Super", card, FIF.APPLICATION)
        self.format_conv_btn = PushButton("格式转换", card, FIF.APPLICATION)
        self.plugin_btn = PushButton("插件管理", card, FIF.APPLICATION)
        self.apk_mgr_btn = PushButton("APK 助手", card, FIF.APPLICATION)

        for btn in [self.zip_btn, self.super_btn, self.format_conv_btn, self.plugin_btn, self.apk_mgr_btn]:
            btn.setMinimumWidth(105)
            tools_grid.addWidget(btn)

        tools_grid.addStretch(1)
        layout.addLayout(tools_grid)

        self.scroll_layout.addWidget(card)
        self.cards_data.append({"name": "other", "widget": card})

    def _load_mock_partitions(self):
        """Fills mock target string data into the list frame."""
        partitions = ["system.img", "vendor.img", "boot.img", "product.img", "odm.img", "recovery.img"]
        for p in partitions:
            QListWidgetItem(p, self.partition_list)

    def _filter_partition_items(self, text):
        """Fuzzy filters partition list rows on real-time keystroke input changes."""
        search_term = text.lower().strip()
        for i in range(self.partition_list.count()):
            item = self.partition_list.item(i)
            # Toggle item layout rows hidden if they do not contain the search string
            should_be_visible = search_term in item.text().lower()
            item.setHidden(not should_be_visible)