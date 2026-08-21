import os
from shutil import rmtree

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QListWidget, QHBoxLayout, QWidget, QListWidgetItem, QTableWidgetItem, QLabel, \
    QHeaderView
from qfluentwidgets import SimpleCardWidget, BodyLabel, CheckBox, ComboBox, RadioButton, PushButton, ScrollArea, \
    SearchLineEdit, FluentIcon as FIF, ListWidget, PrimaryPushButton, SubtitleLabel, TableWidget

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
        self.initUI()

    def initUI(self):
        # 1. 基础布局与极简深色背景
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setStyleSheet("background-color: #00202020; color: #ffffff;")

        # 使用 QFluentWidgets 原生滚动区域
        scroll_area = ScrollArea(self)
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)

        # 核心滚动容器
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)

        # 【关键优化：增加顶部与四周间距】把原本紧凑的区域整体下调，留出透气的空间
        self.scroll_layout.setContentsMargins(32, 40, 32, 32)
        self.scroll_layout.setSpacing(35)  # 模块与模块之间拉开足够的高级感间距
        scroll_area.setWidget(scroll_content)

        # 2. 依次构建去背景、去卡片的扁平化模块
        self._build_project_section(scroll_content)
        self._build_partition_section(scroll_content)
        self._build_tools_section(scroll_content)

        # 底层弹性推力
        self.scroll_layout.addStretch(1)
        self._load_mock_partitions_table()

    def _create_section_title(self, text):
        """统一生成无边框、无背景的纯文本全局大标题"""
        title = BodyLabel(text)
        title.setStyleSheet("""
            font-size: 15px; 
            font-weight: 600; 
            color: #ffffff; 
            background: transparent; 
            border: none;
            padding-bottom: 4px;
        """)
        return title

    def _build_project_section(self, parent_widget):
        """项目管理模块：去掉 Card 容器，直接将控件平铺在主背景上"""
        container = QWidget(parent_widget)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # 标题放外面
        layout.addWidget(self._create_section_title("项目管理"))

        # 下半部分控件区域
        row1 = QHBoxLayout()
        self.project_combo = ComboBox(container)
        self.project_combo.setPlaceholderText("选择或搜索目标项目...")
        self.project_combo.addItem("21212")
        self.open_btn = PushButton("打开", container, FIF.FOLDER)
        row1.addWidget(self.project_combo, 1)
        row1.addWidget(self.open_btn)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.new_btn = PushButton("新建", container, FIF.ADD)
        self.refresh_btn = PushButton("刷新", container, FIF.SYNC)
        self.rename_btn = PushButton("重命名", container, FIF.EDIT)
        self.delete_btn = PushButton("删除", container, FIF.DELETE)

        for btn in [self.new_btn, self.refresh_btn, self.rename_btn, self.delete_btn]:
            btn.setMinimumWidth(90)
            row2.addWidget(btn)
        row2.addStretch(1)
        layout.addLayout(row2)

        self.scroll_layout.addWidget(container)

    def _build_partition_section(self, parent_widget):
        """分区控制模块：标题完全独立，仅保留核心高级列表的内部深色背板"""
        container = QWidget(parent_widget)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # 标题放外面
        frame = QHBoxLayout()
        frame.addWidget(self._create_section_title("分区"))
        self.execute_btn = PrimaryPushButton("执行", container, FIF.PLAY)
        self.execute_btn.setFixedWidth(80)
        frame.addWidget(self.execute_btn)
        layout.addLayout(frame)

        # 高级现代列数据集表格（参照上一轮设计的现代化 List 样式）
        self.partition_table = TableWidget(container)
        self.partition_table.setColumnCount(5)
        self.partition_table.setHorizontalHeaderLabels(["NAME", "SIZE", "FS", "IMAGE", "ATTRIBUTES"])
        self.partition_table.setFixedHeight(240)


        self.partition_table.verticalHeader().setVisible(False)
        self.partition_table.setSelectionBehavior(TableWidget.SelectRows)
        self.partition_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, 5):
            self.partition_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        layout.addWidget(self.partition_table)

        # 全选与搜索框
        row1 = QHBoxLayout()
        self.select_all_cb = CheckBox("全选所有", container)
        self.filter_input = SearchLineEdit(container)
        self.filter_input.setPlaceholderText("根据名称快速检索...")
        self.filter_input.setFixedWidth(240)
        self.format_combo = ComboBox(container)
        self.format_combo.addItems(["img", "new.dat.br", "new.dat.xz", "payload"])

        row1.addWidget(self.select_all_cb)
        row1.addWidget(self.format_combo)
        row1.addWidget(self.filter_input)
        layout.addLayout(row1)

        # 单选切换
        row2 = QHBoxLayout()
        self.unpack_rb = RadioButton("解包", container)
        self.pack_rb = RadioButton("打包", container)
        self.unpack_rb.setChecked(True)

        row2.addWidget(self.unpack_rb)
        row2.addWidget(self.pack_rb)

        row2.addStretch(1)
        layout.addLayout(row2)


        self.scroll_layout.addWidget(container)

    def _build_tools_section(self, parent_widget):
        """高级工具箱：纯扁平化工具栏，取消卡片框"""
        container = QWidget(parent_widget)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # 标题放外面
        layout.addWidget(self._create_section_title("高级工具箱"))

        # 工具按钮行
        tools_layout = QHBoxLayout()
        self.zip_btn = PushButton("打包ZIP", container, FIF.APPLICATION)
        self.super_btn = PushButton("打包Super", container, FIF.ALBUM)
        self.format_conv_btn = PushButton("格式转换", container, FIF.EMBED)
        self.plugin_btn = PushButton("插件管理", container, FIF.APPLICATION)
        self.apk_mgr_btn = PushButton("APK 助手", container, FIF.DEVELOPER_TOOLS)

        for btn in [self.zip_btn, self.super_btn, self.format_conv_btn, self.plugin_btn, self.apk_mgr_btn]:
            btn.setMinimumWidth(105)
            tools_layout.addWidget(btn)

        tools_layout.addStretch(1)
        layout.addLayout(tools_layout)

        self.scroll_layout.addWidget(container)

    def _load_mock_partitions_table(self):
        """装载高质感的数据集行数据（带彩色胶囊Badge标签）"""
        mock_data = [
            ("boot", "64.0 MB", "Raw", "Source", "read-write"),
            ("product", "877 MB", "EroFS", "Build", "read-only"),
            ("odm", "1.0 MB", "EroFS", "Source", "read-only"),
            ("recovery", "128 MB", "Raw", "Build", "read-write"),
            ("recovery", "128 MB", "Raw", "Build", "read-write"),
            ("recovery", "128 MB", "Raw", "Build", "read-write"),
            ("recovery", "128 MB", "Raw", "Build", "read-write"),
            ("recovery", "128 MB", "Raw", "Build", "read-write"),
            ("recovery", "128 MB", "Raw", "Build", "read-write"),
            ("recovery", "128 MB", "Raw", "Build", "read-write"),
            ("recovery", "128 MB", "Raw", "Build", "read-write"),
            ("recovery", "128 MB", "Raw", "Build", "read-write"),
            ("recovery", "128 MB", "Raw", "Build", "read-write"),
            ("recovery", "128 MB", "Raw", "Build", "read-write"),
            ("recovery", "128 MB", "Raw", "Build", "read-write"),
            ("recovery", "128 MB", "Raw", "Build", "read-write"),
            ("recovery", "128 MB", "Raw", "Build", "read-write"),
            ("recovery", "128 MB", "Raw", "Build", "read-write"),
            ("recovery", "128 MB", "Raw", "Build", "read-write"),
            ("recovery", "128 MB", "Raw", "Build", "read-write"),
            ("recovery", "128 MB", "Raw", "Build", "read-write"),
            ("recovery", "128 MB", "Raw", "Build", "read-write"),
            ("recovery", "128 MB", "Raw", "Build", "read-write"),
            ("recovery", "128 MB", "Raw", "Build", "read-write"),
            ("recovery", "128 MB", "Raw", "Build", "read-write"),
            ("recovery", "128 MB", "Raw", "Build", "read-write"),
            ("recovery", "128 MB", "Raw", "Build", "read-write"),
            ("recovery", "128 MB", "Raw", "Build", "read-write"),
        ]
        self.partition_table.setRowCount(len(mock_data))
        for row_idx, (name, size, fs, img_type, attrs) in enumerate(mock_data):
            name_item = QTableWidgetItem(name)
            name_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            name_item.setCheckState(Qt.Unchecked)
            self.partition_table.setItem(row_idx, 0, name_item)
            self.partition_table.setItem(row_idx, 1, QTableWidgetItem(size))
            self.partition_table.setItem(row_idx, 2, QTableWidgetItem(fs))

            # 高级彩色高亮标签
            badge = QLabel(img_type)
            badge.setAlignment(Qt.AlignCenter)
            if img_type == "Build":
                badge.setStyleSheet(
                    "color: #a78bfa; border-radius: 6px; font-weight: bold; font-size: 11px; margin: 3px;")
            else:
                badge.setStyleSheet(
                    "color: #f59e0b; border-radius: 6px; font-weight: bold; font-size: 11px; margin: 3px;")
            self.partition_table.setCellWidget(row_idx, 3, badge)

            attr_item = QTableWidgetItem(attrs)
            self.partition_table.setItem(row_idx, 4, attr_item)
