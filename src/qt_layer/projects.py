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
        self.cards_data = []  # Track card mappings for easy filtering
        self.initUI()

    def initUI(self):
        # 1. Main Layout Setup with a fluent-style Scroll Area
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = ScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("ScrollArea { border: none; background: transparent; }")
        main_layout.addWidget(scroll_area)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(20, 20, 20, 20)
        scroll_layout.setSpacing(15)
        scroll_area.setWidget(scroll_content)

        # ---------------------------------------------------------
        # 2. Project Section (项目)
        # ---------------------------------------------------------
        project_card = SimpleCardWidget(scroll_content)
        project_layout = QVBoxLayout(project_card)

        project_layout.addWidget(BodyLabel("项目", project_card))

        proj_row1 = QHBoxLayout()
        self.project_combo = ComboBox(project_card)
        self.project_combo.setPlaceholderText("选择项目...")
        self.open_btn = PushButton("打开", project_card)
        proj_row1.addWidget(self.project_combo, 1)
        proj_row1.addWidget(self.open_btn)
        project_layout.addLayout(proj_row1)

        proj_row2 = QHBoxLayout()
        self.refresh_btn = PushButton("刷新", project_card)
        self.new_btn = PushButton("新建", project_card)
        self.delete_btn = PushButton("删除", project_card)
        self.rename_btn = PushButton("重命名", project_card)
        for btn in [self.refresh_btn, self.new_btn, self.delete_btn, self.rename_btn]:
            proj_row2.addWidget(btn)
        project_layout.addLayout(proj_row2)

        scroll_layout.addWidget(project_card)

        # Track for filtering capabilities
        self.cards_data.append({"name": "project", "widget": project_card})

        # ---------------------------------------------------------
        # 3. Partition List Section (分区列表)
        # ---------------------------------------------------------
        partition_card = SimpleCardWidget(scroll_content)
        partition_layout = QVBoxLayout(partition_card)

        partition_layout.addWidget(BodyLabel("分区列表", partition_card))

        self.partition_list = QListWidget(partition_card)
        self.partition_list.setFixedHeight(150)
        self.partition_list.setStyleSheet(
            "QListWidget { border: 1px solid rgba(0, 0, 0, 0.1); border-radius: 4px; padding: 4px; }"
        )
        partition_layout.addWidget(self.partition_list)

        part_row1 = QHBoxLayout()
        self.select_all_cb = CheckBox("全选", partition_card)
        self.filter_combo = ComboBox(partition_card)
        part_row1.addWidget(self.select_all_cb)
        part_row1.addWidget(self.filter_combo, 1)
        partition_layout.addLayout(part_row1)

        part_row2 = QHBoxLayout()
        self.unpack_rb = RadioButton("解包", partition_card)
        self.pack_rb = RadioButton("打包", partition_card)
        self.unpack_rb.setChecked(True)
        part_row2.addWidget(self.unpack_rb)
        part_row2.addWidget(self.pack_rb)
        part_row2.addStretch(1)
        partition_layout.addLayout(part_row2)

        part_row3 = QHBoxLayout()
        self.format_combo = ComboBox(partition_card)
        self.format_combo.addItem("new.dat.br")
        self.execute_btn = PushButton("执行", partition_card)
        part_row3.addWidget(self.format_combo, 1)
        part_row3.addWidget(self.execute_btn)
        partition_layout.addLayout(part_row3)

        scroll_layout.addWidget(partition_card)
        self.cards_data.append({"name": "partition", "widget": partition_card})

        # ---------------------------------------------------------
        # 4. Other Section (其他)
        # ---------------------------------------------------------
        other_card = SimpleCardWidget(scroll_content)
        other_layout = QVBoxLayout(other_card)

        other_layout.addWidget(BodyLabel("其他", other_card))

        other_row1 = QHBoxLayout()
        self.zip_btn = PushButton("打包ZIP", other_card)
        self.super_btn = PushButton("打包Super", other_card)
        self.plugin_btn = PushButton("插件", other_card)
        self.format_conv_btn = PushButton("格式转换", other_card)
        for btn in [self.zip_btn, self.super_btn, self.plugin_btn, self.format_conv_btn]:
            other_row1.addWidget(btn)
        other_layout.addLayout(other_row1)

        other_row2 = QHBoxLayout()
        self.apk_mgr_btn = PushButton("Apk管理器", other_card)
        other_row2.addWidget(self.apk_mgr_btn)
        other_row2.addStretch(1)
        other_layout.addLayout(other_row2)

        scroll_layout.addWidget(other_card)
        self.cards_data.append({"name": "other", "widget": other_card})

        # Add stretch to keep UI pushed upwards nicely
        scroll_layout.addStretch(1)