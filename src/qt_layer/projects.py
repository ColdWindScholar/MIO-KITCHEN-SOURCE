import os
from shutil import rmtree

from PySide6.QtWidgets import QVBoxLayout, QListWidget, QHBoxLayout, QWidget
from qfluentwidgets import SimpleCardWidget, BodyLabel, CheckBox, ComboBox, RadioButton, PushButton, ScrollArea

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
        self.initUI()

    def initUI(self):
        # Base setup with seamless background color
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setStyleSheet("background-color: #1e1e1e; color: #e0e0e0;")

        # Custom high-performance scroll wrapper
        scroll_area = ScrollArea(self)
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)

        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setContentsMargins(24, 24, 24, 24)
        self.scroll_layout.setSpacing(20)  # Generous modern breathing space
        scroll_area.setWidget(scroll_content)

        # Build clean visual card modules
        self._build_project_card(scroll_content)
        self._build_partition_card(scroll_content)
        self._build_tools_card(scroll_content)

        # Push elements upward cleanly
        self.scroll_layout.addStretch(1)

    def _build_project_card(self, parent_widget):
        card = SimpleCardWidget(parent_widget)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Clean Typography Header
        header = BodyLabel("项目管理 / Projects", card)
        header.setStyleSheet("font-weight: bold; color: #ffffff;")
        layout.addWidget(header)

        # Core Action Row (Integrated Form Design)
        action_row = QHBoxLayout()
        self.project_combo = ComboBox(card)
        self.project_combo.setPlaceholderText("请选择或输入目标项目...")
        self.open_btn = PushButton("打开项目", card)
        self.open_btn.setStyleSheet("background-color: #0078d4; color: white;")  # Tech blue accent

        action_row.addWidget(self.project_combo, 1)
        action_row.addWidget(self.open_btn)
        layout.addLayout(action_row)

        # Clean Grid-Aligned Operations Bar
        mgmt_row = QHBoxLayout()
        self.new_btn = PushButton("新建", card)
        self.refresh_btn = PushButton("刷新", card)
        self.rename_btn = PushButton("重命名", card)
        self.delete_btn = PushButton("删除", card)

        # Style destructive action subtly
        self.delete_btn.setStyleSheet("color: #ff4d4f;")

        for btn in [self.new_btn, self.refresh_btn, self.rename_btn, self.delete_btn]:
            btn.setFixedWidth(85)
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

        header = BodyLabel("分区控制 / Partitions", card)
        header.setStyleSheet("font-weight: bold; color: #ffffff;")
        layout.addWidget(header)

        # Main List Widget with modern clean spacing styles
        self.partition_list = QListWidget(card)
        self.partition_list.setFixedHeight(160)
        self.partition_list.setStyleSheet("border: 1px solid #333333; background: #252526; border-radius: 4px;")
        layout.addWidget(self.partition_list)

        # Structured configuration panel utilizing modern layout pairs
        config_form = QHBoxLayout()

        self.select_all_cb = CheckBox("全选所有", card)
        self.filter_combo = ComboBox(card)
        self.filter_combo.setPlaceholderText("过滤规则...")
        self.filter_combo.setFixedWidth(150)

        config_form.addWidget(self.select_all_cb)
        config_form.addSpacing(20)
        config_form.addWidget(self.filter_combo)
        config_form.addStretch(1)
        layout.addLayout(config_form)

        # Process Block: Actions + Output Format Selection
        process_row = QHBoxLayout()

        # Operational Mode Switches Toggle Group
        mode_layout = QHBoxLayout()
        self.unpack_rb = RadioButton("核心解包", card)
        self.pack_rb = RadioButton("智能打包", card)
        self.unpack_rb.setChecked(True)
        mode_layout.addWidget(self.unpack_rb)
        mode_layout.addWidget(self.pack_rb)
        process_row.addLayout(mode_layout)
        process_row.addSpacing(40)

        # Target Extension selection config
        self.format_combo = ComboBox(card)
        self.format_combo.addItem("new.dat.br")
        self.format_combo.setFixedWidth(130)

        self.execute_btn = PushButton("开始执行", card)
        self.execute_btn.setFixedWidth(100)
        self.execute_btn.setStyleSheet(
            "background-color: #25855a; color: white; font-weight: bold;")  # Cyber green success color

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

        header = BodyLabel("扩展工具箱", card)
        header.setStyleSheet("font-weight: bold; color: #ffffff;")
        layout.addWidget(header)

        # Wrap everything inside a unified responsive wrapping system
        tools_grid = QHBoxLayout()

        self.zip_btn = PushButton("打包 ZIP", card)
        self.super_btn = PushButton("打包 Super", card)
        self.format_conv_btn = PushButton("格式转换", card)
        self.apk_mgr_btn = PushButton("Apk 管理器", card)

        for btn in [self.zip_btn, self.super_btn, self.format_conv_btn, self.apk_mgr_btn]:
            btn.setMinimumWidth(100)
            tools_grid.addWidget(btn)

        tools_grid.addStretch(1)
        layout.addLayout(tools_grid)

        self.scroll_layout.addWidget(card)
        self.cards_data.append({"name": "other", "widget": card})