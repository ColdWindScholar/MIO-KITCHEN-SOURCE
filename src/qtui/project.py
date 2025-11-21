import os
import shutil

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QVBoxLayout, QWidget, QHBoxLayout, QListWidgetItem, QAbstractItemView)
from qfluentwidgets import (TitleLabel, PushButton, FluentIcon as FIF,
                            CardWidget, MessageBox, LineEdit, ComboBox,
                            ScrollArea as FluentScrollArea, ListWidget,
                            InfoBar, InfoBarPosition, MessageBoxBase,
                            SubtitleLabel, CaptionLabel)

from .settings import cfg


class CreateRenameDialog(MessageBoxBase):
    """自定义对话框，用于创建或重命名项目"""
    def __init__(self, title, existing_projects, initial_text="", parent=None):
        super().__init__(parent)
        self.existing_projects = existing_projects

        self.titleLabel = SubtitleLabel(title, self)
        self.nameLineEdit = LineEdit(self)
        self.nameLineEdit.setPlaceholderText('输入项目名称')
        self.nameLineEdit.setClearButtonEnabled(True)
        self.nameLineEdit.setText(initial_text)

        self.errorLabel = CaptionLabel(text="项目名称无效或已存在")
        self.errorLabel.setTextColor("#cf1010", QColor(255, 28, 32))

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.nameLineEdit)
        self.viewLayout.addWidget(self.errorLabel)
        self.errorLabel.hide()

        self.widget.setMinimumWidth(350)
        self.buttonLayout.addWidget(self.yesButton)
        self.buttonLayout.addWidget(self.cancelButton)

        self.yesButton.clicked.connect(self.__onYesButtonClicked)
        self.cancelButton.clicked.connect(self.reject)
        self.nameLineEdit.returnPressed.connect(self.yesButton.click)

    def __onYesButtonClicked(self):
        if self.validate():
            self.accept()
        else:
            self.yesButton.setEnabled(True)

    def validate(self):
        project_name = self.nameLineEdit.text().strip()
        if not project_name:
            self.errorLabel.setText("项目名称不能为空")
            self.errorLabel.show()
            return False

        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        if any(char in project_name for char in invalid_chars):
            self.errorLabel.setText("名称包含非法字符")
            self.errorLabel.show()
            return False

        if (project_name in self.existing_projects and
                project_name != self.nameLineEdit.text().strip()):
            self.errorLabel.setText("项目名称已存在")
            self.errorLabel.show()
            return False

        self.errorLabel.hide()
        return True


class ProjectCard(CardWidget):
    """项目卡片，显示单个项目"""
    def __init__(self, project_name, project_page, parent=None):
        super().__init__(parent)
        self.project_name = project_name
        self.project_page = project_page
        self.is_selected = False
        self.setAttribute(Qt.WA_StyledBackground)
        self.setObjectName("ProjectCard")
        self.init_ui()
        self.set_selected(False)

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        self.name_label = TitleLabel(self.project_name, self)
        self.name_label.setObjectName("CardLabel")
        layout.addWidget(self.name_label)

        self.setFixedHeight(60)
        self.setCursor(Qt.PointingHandCursor)

        self.setStyleSheet("""
            #ProjectCard {
                border: 1px solid #3A3A3A;
                border-radius: 8px;
                background-color: #2A2A2A;
                transition: all 0.2s;
            }
            #ProjectCard:hover {
                background-color: #333333;
                border: 1px solid #505050;
            }
            #ProjectCard #CardLabel {
                color: #FFFFFF;
                font-size: 16px;
            }
        """)

    def set_selected(self, selected):
        self.is_selected = selected
        border_color = "#0078D4" if selected else "#3A3A3A"
        self.setStyleSheet(f"""
            #ProjectCard {{
                border: 2px solid {border_color};
                border-radius: 8px;
                background-color: #2A2A2A;
            }}
            #ProjectCard:hover {{
                background-color: #333333;
            }}
            #ProjectCard #CardLabel {{
                color: #FFFFFF;
                font-size: 16px;
            }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.project_page.select_project(self)
        super().mousePressEvent(event)


class ProjectPage(QWidget):
    """项目页面，管理项目列表和镜像操作"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ProjectPage")
        self.project_dir = "Project"
        self.current_project = None  # 跟踪当前选中的项目
        self.selected_project = None  # 当前选中的项目卡片
        self.selected_images = []  # 存储多选的镜像文件
        self.setStyleSheet("""
            QWidget#ProjectPage {
                background-color: #1E1E1E;
            }
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)

        self.projects = []
        self.project_cards = []
        self.init_project_dir()
        self.init_ui()

    def init_project_dir(self):
        """初始化项目目录"""
        if not os.path.exists(self.project_dir):
            os.makedirs(self.project_dir)
        self.refresh_projects()

    def refresh_projects(self):
        """刷新项目列表"""
        self.projects = [
            f for f in os.listdir(self.project_dir)
            if os.path.isdir(os.path.join(self.project_dir, f))
        ]

    def init_ui(self):
        """初始化界面布局"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)

        # 左侧项目列表区域
        left_widget = QWidget()
        left_widget.setObjectName("LeftWidget")
        left_widget.setStyleSheet("#LeftWidget { background-color: transparent; }")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(20, 20, 20, 20)
        left_layout.setSpacing(15)

        title = TitleLabel("项目列表", self)
        title.setStyleSheet("color: white; font-size: 18px;")
        left_layout.addWidget(title)

        self.cards_container = QWidget()
        self.cards_container.setObjectName("CardsContainer")
        self.cards_container.setStyleSheet("#CardsContainer { background-color: transparent; }")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 10, 0)
        self.cards_layout.setSpacing(10)

        for project in self.projects:
            card = ProjectCard(project, self, self.cards_container)
            self.cards_layout.addWidget(card)
            self.project_cards.append(card)
        self.cards_layout.addStretch()

        scroll_area = FluentScrollArea(self)
        scroll_area.setObjectName("MainScrollArea")
        scroll_area.setWidget(self.cards_container)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollBar:vertical {
                width: 10px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: #505050;
                min-height: 20px;
                border-radius: 5px;
            }
        """)
        left_layout.addWidget(scroll_area)

        # 右侧镜像列表区域
        right_widget = QWidget()
        right_widget.setObjectName("RightWidget")
        right_widget.setStyleSheet("#RightWidget { background-color: transparent; }")
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(15)

        image_title = TitleLabel("镜像列表", self)
        image_title.setStyleSheet("color: white; font-size: 18px;")
        right_layout.addWidget(image_title)

        self.image_list = ListWidget(self)
        self.image_list.setObjectName("ImageList")
        self.image_list.setSelectionMode(QAbstractItemView.MultiSelection)  # 启用多选
        self.image_list.setSelectRightClickedRow(True)  # 右键选中
        self.image_list.itemSelectionChanged.connect(self.select_image)  # 选择变化信号
        self.image_list.setStyleSheet("""
            #ImageList {
                background-color: #2A2A2A;
                border: 1px solid #3A3A3A;
                border-radius: 8px;
                color: white;
                font-size: 14px;
                outline: none;
                selection-background-color: transparent; /* 移除 Qt 默认选中背景 */
            }
            #ImageList::item {
                padding: 8px;
                border-bottom: 1px solid #3A3A3A;
            }
            #ImageList::item:hover {
                background-color: #333333;
            }
            #ImageList::item:selected {
                background: transparent;
            }
            #ImageList::item:last {
                border-bottom: none;
            }
            #ImageList:focus {
                outline: none;
            }
        """)

        # 初始化格式选择下拉框
        self.format_combo = ComboBox(self)
        self.format_combo.setObjectName("FormatCombo")
        formats = ['img', 'dat', 'br', 'payload.bin', 'super']
        self.format_combo.addItems(formats)
        self.format_combo.setFixedHeight(30)
        self.format_combo.setFixedWidth(120)
        self.format_combo.setCurrentIndex(0)
        self.format_combo.currentTextChanged.connect(self.update_image_list)
        self.update_image_list()

        image_scroll_area = FluentScrollArea(self)
        image_scroll_area.setObjectName("ImageScrollArea")
        image_scroll_area.setWidget(self.image_list)
        image_scroll_area.setWidgetResizable(True)
        image_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        image_scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                width: 10px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: #505050;
                min-height: 20px;
                border-radius: 5px;
            }
        """)
        right_layout.addWidget(image_scroll_area)

        top_layout.addWidget(left_widget, stretch=3)
        top_layout.addWidget(right_widget, stretch=7)
        main_layout.addLayout(top_layout)

        # 底部操作按钮
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(20, 0, 20, 20)
        bottom_layout.setSpacing(20)

        project_op_layout = QHBoxLayout()
        project_op_layout.setSpacing(15)

        buttons = [
            ("创建", FIF.ADD, self.show_create_dialog),
            ("删除", FIF.DELETE, self.delete_project),
            ("重命名", FIF.EDIT, self.show_rename_dialog)
        ]
        for text, icon, slot in buttons:
            btn = PushButton(text, self, icon)
            btn.setFixedSize(80 if text != "重命名" else 90, 30)
            btn.clicked.connect(slot)
            project_op_layout.addWidget(btn)

        bottom_layout.addLayout(project_op_layout)
        bottom_layout.addStretch()

        image_op_layout = QHBoxLayout()
        image_op_layout.setSpacing(15)

        image_buttons = [
            ("分解", FIF.ALBUM, self.extract_img),
            ("打包", FIF.SAVE, self.pack_image)
        ]
        for text, icon, slot in image_buttons:
            btn = PushButton(text, self, icon)
            btn.setFixedSize(80, 30)
            btn.clicked.connect(slot)
            image_op_layout.addWidget(btn)

        image_op_layout.addWidget(self.format_combo)
        bottom_layout.addLayout(image_op_layout)
        main_layout.addLayout(bottom_layout)

    def select_project(self, card):
        """选择项目卡片，更新选中状态和镜像列表"""
        self.selected_project = card.project_name
        self.current_project = card.project_name
        print(f"切换到项目: {self.current_project}")
        for c in self.project_cards:
            c.set_selected(c == card)
        self.update_image_list()

    def show_create_dialog(self):
        """显示创建项目对话框"""
        dialog = CreateRenameDialog(
            title="创建新项目",
            existing_projects=self.projects,
            parent=self
        )
        if dialog.exec():
            project_name = dialog.nameLineEdit.text().strip()
            self.create_project(project_name)

    def create_project(self, name):
        """创建新项目并显示提示"""
        try:
            project_path = os.path.join(self.project_dir, name)
            os.makedirs(project_path)
            self.refresh_projects()
            card = ProjectCard(name, self, self.cards_container)
            self.project_cards.append(card)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

            if name == "杨洋":
                self.show_info_bar("提示", "创建的什么啊？好难猜", is_error=False)
            else:
                self.show_info_bar("成功", f"项目 '{name}' 已创建", is_error=False)
        except Exception as e:
            self.show_info_bar("错误", f"创建项目失败: {str(e)}", is_error=True)

    def delete_project(self):
        """删除选中的项目并显示提示"""
        if not self.selected_project:
            self.show_info_bar("提示", "请先选择一个项目", is_error=True)
            return

        result = MessageBox(
            "确认删除",
            f"确定要删除项目 '{self.selected_project}' 吗?",
            self
        ).exec()

        if result != 1:
            return

        try:
            project_path = os.path.join(self.project_dir, self.selected_project)
            shutil.rmtree(project_path)
            deleted_project = self.selected_project
            self.refresh_projects()
            for card in self.project_cards[:]:
                if card.project_name == self.selected_project:
                    self.cards_layout.removeWidget(card)
                    card.deleteLater()
                    self.project_cards.remove(card)
            self.selected_project = None
            self.current_project = None
            self.update_image_list()

            if deleted_project == "杨洋":
                self.show_info_bar("提示", "删除了个超级背刺王", is_error=False)
            elif any(x in deleted_project.lower() for x in ["mio", "寒风居士"]):
                self.show_info_bar("提示", "好删兄弟好删", is_error=False)
            else:
                self.show_info_bar("成功", "项目已删除", is_error=False)
        except Exception as e:
            self.show_info_bar("错误", f"删除项目失败: {str(e)}", is_error=True)

    def show_rename_dialog(self):
        """显示重命名项目对话框"""
        if not self.selected_project:
            self.show_info_bar("提示", "请先选择一个项目", is_error=True)
            return
        dialog = CreateRenameDialog(
            title="重命名项目",
            existing_projects=self.projects,
            initial_text=self.selected_project,
            parent=self
        )
        if dialog.exec():
            new_name = dialog.nameLineEdit.text().strip()
            self.rename_project(new_name)

    def rename_project(self, new_name):
        """重命名项目并更新界面"""
        try:
            old_path = os.path.join(self.project_dir, self.selected_project)
            new_path = os.path.join(self.project_dir, new_name)
            os.rename(old_path, new_path)
            self.refresh_projects()
            for card in self.project_cards:
                if card.project_name == self.selected_project:
                    card.project_name = new_name
                    card.name_label.setText(new_name)
                    break
            self.selected_project = new_name
            self.current_project = new_name
            self.update_image_list()
            self.show_info_bar("成功", f"项目已重命名为 '{new_name}'", is_error=False)
        except Exception as e:
            self.show_info_bar("错误", f"重命名失败: {str(e)}", is_error=True)

    def update_image_list(self):
        """更新镜像列表，显示当前项目文件夹下与所选格式匹配的文件"""
        self.image_list.clear()
        self.selected_images = []
        if self.selected_project:
            project_path = os.path.join(self.project_dir, self.selected_project)
            selected_format = self.format_combo.currentText()
            if selected_format == 'payload.bin':
                images = [f for f in os.listdir(project_path) if f.lower() == 'payload.bin']
            elif selected_format == 'super':
                images = [f for f in os.listdir(project_path) if f.lower().startswith('super') and f.lower().endswith(('.img', '.bin'))]
            else:
                images = [f for f in os.listdir(project_path) if f.lower().endswith(f".{selected_format}")]
            if images:
                for image in images:
                    item = QListWidgetItem(image)
                    self.image_list.addItem(item)
            else:
                empty_item = QListWidgetItem("暂无匹配的镜像文件")
                empty_item.setFlags(Qt.NoItemFlags)
                empty_item.setForeground(QColor("#808080"))
                self.image_list.addItem(empty_item)
        else:
            empty_item = QListWidgetItem("暂无匹配的镜像文件")
            empty_item.setFlags(Qt.NoItemFlags)
            empty_item.setForeground(QColor("#808080"))
            self.image_list.addItem(empty_item)

    def select_image(self):
        selected_items = [item for item in self.image_list.selectedItems() if item.flags() != Qt.NoItemFlags]
        self.selected_images = [item.text() for item in selected_items]
        print(f"当前选中镜像: {', '.join(self.selected_images) if self.selected_images else '无'}")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            item = self.image_list.itemAt(self.image_list.mapFromGlobal(event.globalPos()))
            if item and item.flags() != Qt.NoItemFlags:
                self.image_list.setItemSelected(item, not item.isSelected())
                self.select_image()
                return
        super().mousePressEvent(event)

    def pack_image(self):
        """打包选中的镜像文件"""
        if not self.selected_project:
            self.show_info_bar("提示", "你项目都没选你干🐔🪶呢！", is_error=True)
            return
        if not self.selected_images:
            self.show_info_bar("提示", "你镜像都没选你打包🐔🪶呢！", is_error=True)
            return
        selected_format = self.format_combo.currentText()
        self.show_info_bar("提示", f"开始打包 {', '.join(self.selected_images)} 为 {selected_format} 格式", is_error=False)

    def extract_img(self):
        """打印选中的镜像文件，供后续解包逻辑"""
        if not self.selected_project:
            self.show_info_bar("提示", "你项目都没选你干🐔🪶呢！", is_error=True)
            return
        if not self.selected_images:
            self.show_info_bar("提示", "你镜像都没选你分解🐔🪶呢！", is_error=True)
            return
        print(f"准备分解的镜像文件: {', '.join(self.selected_images)}")
        self.show_info_bar("提示", f"准备分解: {', '.join(self.selected_images)}", is_error=False)

    def show_info_bar(self, title, content, is_error=False, duration=3000):
        """显示提示条，根据配置决定是否显示"""
        if cfg.enableNotifications.value:
            if is_error:
                InfoBar.error(
                    title=title,
                    content=content,
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM,
                    duration=duration,
                    parent=self
                )
            else:
                InfoBar.success(
                    title=title,
                    content=content,
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM,
                    duration=duration,
                    parent=self
                )