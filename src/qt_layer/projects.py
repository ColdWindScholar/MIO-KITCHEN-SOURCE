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
        # 1. Main Layout & Scroll Area Setup
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.setStyleSheet("background-color: #202020;")

        scroll_area = ScrollArea(self)
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)

        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setContentsMargins(20, 20, 20, 20)
        self.scroll_layout.setSpacing(15)
        scroll_area.setWidget(scroll_content)

        # 2. Build Sections Modularly
        self._build_project_section(scroll_content)
        self._build_partition_section(scroll_content)
        self._build_other_section(scroll_content)

        # Push everything to the top
        self.scroll_layout.addStretch(1)

    def _build_project_section(self, parent_widget):
        """Creates the '项目' (Project) management section."""
        card = SimpleCardWidget(parent_widget)
        layout = QVBoxLayout(card)

        layout.addWidget(BodyLabel("项目", card))

        # Row 1: Combo and Open
        row1 = QHBoxLayout()
        self.project_combo = ComboBox(card)
        self.project_combo.setPlaceholderText("选择项目...")
        self.open_btn = PushButton("打开", card)
        row1.addWidget(self.project_combo, 1)
        row1.addWidget(self.open_btn)
        layout.addLayout(row1)

        # Row 2: Action Buttons
        row2 = QHBoxLayout()
        self.refresh_btn = PushButton("刷新", card)
        self.new_btn = PushButton("新建", card)
        self.delete_btn = PushButton("删除", card)
        self.rename_btn = PushButton("重命名", card)

        for btn in [self.refresh_btn, self.new_btn, self.delete_btn, self.rename_btn]:
            row2.addWidget(btn)
        layout.addLayout(row2)

        self.scroll_layout.addWidget(card)
        self.cards_data.append({"name": "project", "widget": card})

    def _build_partition_section(self, parent_widget):
        """Creates the '分区列表' (Partition List) operational section."""
        card = SimpleCardWidget(parent_widget)
        layout = QVBoxLayout(card)

        layout.addWidget(BodyLabel("分区列表", card))

        self.partition_list = QListWidget(card)
        self.partition_list.setFixedHeight(150)
        layout.addWidget(self.partition_list)

        # Row 1: Selection and Filtering
        row1 = QHBoxLayout()
        self.select_all_cb = CheckBox("全选", card)
        self.filter_combo = ComboBox(card)
        row1.addWidget(self.select_all_cb)
        row1.addWidget(self.filter_combo, 1)
        layout.addLayout(row1)

        # Row 2: Mode Radio Buttons
        row2 = QHBoxLayout()
        self.unpack_rb = RadioButton("解包", card)
        self.pack_rb = RadioButton("打包", card)
        self.unpack_rb.setChecked(True)
        row2.addWidget(self.unpack_rb)
        row2.addWidget(self.pack_rb)
        row2.addStretch(1)
        layout.addLayout(row2)

        # Row 3: Format and Execution
        row3 = QHBoxLayout()
        self.format_combo = ComboBox(card)
        for i in ['new.dat.br', 'new.dat.xz', "new.dat", 'img', 'zst', 'payload', 'super',
                                   'update.app']:
            self.format_combo.addItem(i)
        self.execute_btn = PushButton("执行", card)
        row3.addWidget(self.format_combo, 1)
        row3.addWidget(self.execute_btn)
        layout.addLayout(row3)

        self.scroll_layout.addWidget(card)
        self.cards_data.append({"name": "partition", "widget": card})

    def _build_other_section(self, parent_widget):
        """Creates the '其他' (Other) tools section."""
        card = SimpleCardWidget(parent_widget)
        layout = QVBoxLayout(card)

        layout.addWidget(BodyLabel("其他", card))

        # Row 1: Main Tools
        row1 = QHBoxLayout()
        self.zip_btn = PushButton("打包ZIP", card)
        self.super_btn = PushButton("打包Super", card)
        self.plugin_btn = PushButton("插件", card)
        self.format_conv_btn = PushButton("格式转换", card)

        for btn in [self.zip_btn, self.super_btn, self.plugin_btn, self.format_conv_btn]:
            row1.addWidget(btn)
        layout.addLayout(row1)

        # Row 2: Secondary Tools
        row2 = QHBoxLayout()
        self.apk_mgr_btn = PushButton("Apk管理器", card)
        row2.addWidget(self.apk_mgr_btn)
        row2.addStretch(1)
        layout.addLayout(row2)

        self.scroll_layout.addWidget(card)
        self.cards_data.append({"name": "other", "widget": card})
