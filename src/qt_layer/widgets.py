import logging
import os
import time
import tkinter as tk

from PySide6.QtCore import QTimer, Qt
from PySide6.QtCore import Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QListWidgetItem
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGridLayout,
                               QLabel, QLineEdit, QHBoxLayout, QButtonGroup)
from qfluentwidgets import InfoBar, InfoBarPosition, ListWidget, CheckBox, LineEdit, ComboBox, SubtitleLabel, \
    RadioButton, PushButton, BodyLabel
from qfluentwidgets import (
    MessageBoxBase,
)
from qfluentwidgets import (SwitchButton, Slider,
                            CaptionLabel)

import utils
from utils import gettype


class TkinterEmbeddedBox(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)

        # 1. Force Qt to create a native window handle/X11 ID for THIS specific widget
       # self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.widget = QWidget()
        self.viewLayout.addWidget(self.widget)
        # 2. Bind Tkinter root directly into the Qt Widget's handle
        # The 'use' parameter forces Tkinter to render inside the Qt boundary
        self.tk_root = tk.Tk(use=hex(self.widget.winId()))
        self.tk_root.willdispatch()
        self.timer = QTimer(self)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.tk_root.update)
        self.timer.start()


def show_info_bar(parent, title, content, bar_type: int = 3, duration=3000):
    """bar_type: 1=error 2=warning 3=info"""
    """显示提示条，根据配置决定是否显示"""
    if True:
        if bar_type == 1:
            InfoBar.error(
                title=title,
                content=content,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM,
                duration=duration,
                parent=parent
            )
        elif bar_type == 2:
            InfoBar.warning(
                title=title,
                content=content,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM,
                duration=duration,
                parent=parent
            )
        else:
            InfoBar.success(
                title=title,
                content=content,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM,
                duration=duration,
                parent=parent
            )

class NewProjectDialog(MessageBoxBase):
    """自定义对话框，用于创建或重命名项目"""
    def __init__(self, title, existing_projects, initial_text="", parent=None):
        super().__init__(parent)
        self.existing_projects = existing_projects

        self.titleLabel = SubtitleLabel(title, self)
        self.nameLineEdit = LineEdit(self)
        self.nameLineEdit.setPlaceholderText(self.tr('Enter project name'))
        self.nameLineEdit.setClearButtonEnabled(True)
        self.nameLineEdit.setText(initial_text)

        self.errorLabel = CaptionLabel(text=self.tr('Project name is invalid or already exists.'))
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
            self.errorLabel.setText(self.tr("The project name cannot be empty."))
            self.errorLabel.show()
            return False

        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        if any(char in project_name for char in invalid_chars):
            self.errorLabel.setText("名称包含非法字符")
            self.errorLabel.show()
            return False

        if project_name in self.existing_projects:
            self.errorLabel.setText("项目名称已存在")
            self.errorLabel.show()
            return False

        self.errorLabel.hide()
        return True

class InputDialog(MessageBoxBase):
    """自定义对话框，用于创建或重命名项目"""
    def __init__(self, title, initial_text="", parent=None):
        super().__init__(parent)

        self.titleLabel = SubtitleLabel(title, self)
        self.nameLineEdit = LineEdit(self)
        self.nameLineEdit.setPlaceholderText('输入')
        self.nameLineEdit.setClearButtonEnabled(True)
        self.nameLineEdit.setText(initial_text)

        self.errorLabel = CaptionLabel(text="无效")
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
            self.errorLabel.setText("不能为空")
            self.errorLabel.show()
            return False

        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        if any(char in project_name for char in invalid_chars):
            self.errorLabel.setText("包含非法字符")
            self.errorLabel.show()
            return False

        self.errorLabel.hide()
        return True
#         if dialog.exec():
#             project_name = dialog.nameLineEdit.text().strip()
#             self.create_project(project_name)





class ConvertImageMessageBox(MessageBoxBase):

    def __init__(self, path: str, parent=None):
        """
        :param items: 传入要在列表中显示的文件名列表，例如 ["odm.img", "vendor.img", "system.img"]
        """
        super().__init__(parent)
        self.path = path  # 保存原始完整列表，用于搜索过滤

        # 1. 设置标准对话框标题与底层按钮文本
        self.titleLabel = SubtitleLabel("Convert image", self)
        self.yesButton.setText("OK")
        self.cancelButton.setText("Cancel")

        # 2. 创建源与目标格式下拉框
        self.src_combo = ComboBox(self)
        self.src_combo.addItems(["raw", "sparse", "dat", "br", "xz"])
        self.src_combo.currentTextChanged.connect(self.refresh_list)
        self.src_combo.setFixedWidth(160)

        self.arrow_label = SubtitleLabel(">>>>>>", self)
        self.arrow_label.setStyleSheet("color: gray;")

        self.dst_combo = ComboBox(self)
        self.dst_combo.addItems(["raw", "sparse", "dat", "br", "xz"])
        self.dst_combo.setFixedWidth(160)

        # 3. 创建核心文件多选列表 (使用 Fluent 风格的 ListWidget)
        self.list_widget = ListWidget(self)
        self.list_widget.setMinimumHeight(120)
        self.list_widget.setMaximumHeight(200)

        # 4. 创建底部控制部件：全选复选框 & 搜索输入框
        self.select_all_checkbox = CheckBox("Select all", self)
        self.search_input = LineEdit(self)
        self.search_input.setPlaceholderText("search...")
        self.search_input.setClearButtonEnabled(True)

        # 5. 构建布局结构
        # 顶部的转换格式选择水平布局
        self.combo_layout = QHBoxLayout()
        self.combo_layout.setSpacing(15)
        self.combo_layout.addWidget(self.src_combo)
        self.combo_layout.addWidget(self.arrow_label, 0, Qt.AlignmentFlag.AlignCenter)
        self.combo_layout.addWidget(self.dst_combo)

        # 底部的全选与搜索框水平布局
        self.bottom_control_layout = QHBoxLayout()
        self.bottom_control_layout.setSpacing(10)
        self.bottom_control_layout.addWidget(self.select_all_checkbox)
        self.bottom_control_layout.addWidget(self.search_input, 1)

        # 将所有部件顺次组合到 MessageBoxBase 的主视图容器中
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addLayout(self.combo_layout)
        self.viewLayout.addWidget(self.list_widget)  # 插入中间的多选列表
        self.viewLayout.addLayout(self.bottom_control_layout)

        # 设置对话框的整体宽度
        self.widget.setMinimumWidth(450)

        # 6. 绑定内部交互信号槽
        self.select_all_checkbox.stateChanged.connect(self._on_select_all_changed)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.list_widget.itemChanged.connect(self._on_item_changed)
        self.refresh_list()

    def refile(self, f):
        for i in os.listdir(self.path):
            if i.endswith(f) and os.path.isfile(f'{self.path}/{i}'):
                yield i
    def refresh_list(self):
        work = self.path
        file_list = []
        if self.src_combo.currentText() == "br":
            for i in self.refile(".new.dat.br"):
                file_list.append(i)
        elif self.src_combo.currentText() == 'xz':
            for i in self.refile(".new.dat.xz"):
                file_list.append(i)
        elif self.src_combo.currentText() == 'dat':
            for i in self.refile(".new.dat"):
                file_list.append(i)
        elif self.src_combo.currentText() == 'sparse':
            for i in os.listdir(work):
                if os.path.isfile(f'{work}/{i}') and gettype(f'{work}/{i}') == 'sparse':
                    file_list.append(i)
        elif self.src_combo.currentText() == 'raw':
            for i in os.listdir(work):
                if os.path.isfile(f'{work}/{i}'):
                    if gettype(f'{work}/{i}') in ['ext', 'erofs', 'super', 'f2fs']:
                        file_list.append(i)
        self._populate_list(file_list)
    def _populate_list(self, items_to_show: list[str]):
        """根据传入的列表渲染 QListWidget 项（带复选框）"""
        self.list_widget.blockSignals(True)  # 渲染时暂时阻塞信号，防止触发频繁回调
        self.list_widget.clear()
        for item_text in items_to_show:
            item = QListWidgetItem(item_text)
            # 设置该项为可勾选状态，并默认不勾选
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.list_widget.addItem(item)
        self.list_widget.blockSignals(False)

    @Slot(int)
    def _on_select_all_changed(self, state: int):
        """处理点击 'Select all' 时的全选/全不选逻辑"""
        self.list_widget.blockSignals(True)
        # 根据 Select all 的状态决定列表中每一项的勾选状态
        check_state = Qt.CheckState.Checked if state == 2 else Qt.CheckState.Unchecked
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            # 只有在列表当前可见的情况下才受全选影响
            if not self.list_widget.isRowHidden(i):
                item.setCheckState(check_state)
        self.list_widget.blockSignals(False)

    @Slot(QListWidgetItem)
    def _on_item_changed(self, item: QListWidgetItem):
        """如果用户手动取消勾选了某一项，自动让底部的 'Select all' 变成未完全勾选状态"""
        self.select_all_checkbox.blockSignals(True)
        total_visible = 0
        total_checked = 0
        for i in range(self.list_widget.count()):
            if not self.list_widget.isRowHidden(i):
                total_visible += 1
                if self.list_widget.item(i).checkState() == Qt.CheckState.Checked:
                    total_checked += 1

        # 联动更新全选框的状态
        if total_checked == total_visible and total_visible > 0:
            self.select_all_checkbox.setCheckState(Qt.CheckState.Checked)
        elif total_checked == 0:
            self.select_all_checkbox.setCheckState(Qt.CheckState.Unchecked)
        else:
            # 部分勾选状态 (PartiallyChecked)
            self.select_all_checkbox.setCheckState(Qt.CheckState.PartiallyChecked)
        self.select_all_checkbox.blockSignals(False)

    @Slot(str)
    def _on_search_text_changed(self, text: str):
        """处理搜索框文本变化，实时过滤隐藏不匹配的项"""
        search_text = text.strip().lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            # 模糊匹配：如果文件名包含输入字符则显示，否则隐藏
            is_match = search_text in item.text().lower()
            self.list_widget.setRowHidden(i, not is_match)

    def get_result(self):
        """获取用户当前在对话框中选择和输入的最终数据"""
        selected_files = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected_files.append(item.text())

        return self.src_combo.currentText(),self.dst_combo.currentText(),selected_files



class PackSettingsDialog(MessageBoxBase):
    """
    高级打包设置自定义对话框：继承自 MessageBoxBase，
    支持嵌套分组、多状态滑动条，以及随开关状态动态显示/隐藏的隐藏组合框面板。
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # 1. 创建核心自定义内容容器组件
        self.content_widget = QWidget(self)
        self.initCustomUI()

        # 2. 将自定义容器直接安装进 MessageBoxBase 核心中
        self.viewLayout.addWidget(self.content_widget)

        # 3. 配置底部的标准基础控制按钮文本
        self.yesButton.setText(self.tr("Pack"))
        self.cancelButton.setText(self.tr("Cancel"))

        # 强制约束合理的现代弹出视窗比例范围，留足横向扩展空间
        self.widget.setMinimumWidth(580)

    def _create_group_title(self, text):
        """生成分组内敛极简副标题标签"""
        label = CaptionLabel(text, self.content_widget)
        label.setStyleSheet("color: #71717a; font-weight: bold; font-size: 11px;")
        return label

    def _create_field_label(self, text):
        """生成字段主文本说明标签"""
        label = QLabel(text, self.content_widget)
        label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 500;")
        return label

    def initCustomUI(self):
        main_layout = QVBoxLayout(self.content_widget)
        main_layout.setContentsMargins(0, 0, 0, 12)
        main_layout.setSpacing(20)

        # =========================================================================
        # 📂 1. EXT4设置 分组
        # =========================================================================
        ext4_container = QWidget(self.content_widget)
        ext4_layout = QVBoxLayout(ext4_container)
        ext4_layout.setContentsMargins(0, 0, 0, 0)
        ext4_layout.setSpacing(8)

        ext4_layout.addWidget(self._create_group_title("EXT4设置"))

        ext4_grid = QHBoxLayout()
        ext4_grid.setSpacing(16)

        self.pack_method_label = self._create_field_label("打包方式：")
        self.pack_method_combo = ComboBox(ext4_container)
        self.pack_method_combo.addItems(["make_ext4fs", "mke2fs+e2fsdroid"])

        self.size_handle_label = self._create_field_label("大小处理：")
        self.size_handle_combo = ComboBox(ext4_container)
        self.size_handle_combo.addItems(["自动读取", "手动固定"])

        ext4_grid.addWidget(self.pack_method_label)
        ext4_grid.addWidget(self.pack_method_combo, 1)
        ext4_grid.addWidget(self.size_handle_label)
        ext4_grid.addWidget(self.size_handle_combo, 1)
        ext4_layout.addLayout(ext4_grid)
        main_layout.addWidget(ext4_container)

        # =========================================================================
        # 📦 2. EROFS打包 分组
        # =========================================================================
        erofs_container = QWidget(self.content_widget)
        erofs_layout = QVBoxLayout(erofs_container)
        erofs_layout.setContentsMargins(0, 0, 0, 0)
        erofs_layout.setSpacing(10)

        erofs_layout.addWidget(self._create_group_title("EROFS打包"))

        erofs_row1 = QHBoxLayout()
        self.compress_algo_label = self._create_field_label("压缩算法：")
        self.compress_algo_combo = ComboBox(erofs_container)
        self.compress_algo_combo.addItems(["lz4", "lz4hc", "lzma", "deflate", "zstd"])
        self.compress_algo_combo.setText("lz4hc")
        self.support_old_kernel_switch = SwitchButton(parent=erofs_container)
        self.support_old_kernel_switch.setOffText("")
        self.support_old_kernel_switch.setOnText("")
        self.support_old_kernel_label = QLabel(self.tr("Support old kernel"), erofs_container)
        self.support_old_kernel_label.setStyleSheet("color: #ffffff; font-size: 13px;")

        erofs_row1.addWidget(self.compress_algo_label)
        erofs_row1.addWidget(self.compress_algo_combo, 1)
        erofs_row1.addSpacing(24)
        erofs_row1.addWidget(self.support_old_kernel_switch)
        erofs_row1.addWidget(self.support_old_kernel_label)
        erofs_layout.addLayout(erofs_row1)

        erofs_row2 = QHBoxLayout()
        self.erofs_level_label = QLabel("EROFS等级: 8", erofs_container)
        self.erofs_level_label.setStyleSheet("color: #ffffff; font-size: 13px; min-width: 90px;")
        self.erofs_slider = Slider(Qt.Orientation.Horizontal, erofs_container)
        self.erofs_slider.setRange(0, 20)
        self.erofs_slider.setValue(8)
        self.erofs_slider.valueChanged.connect(lambda v: self.erofs_level_label.setText(f"EROFS等级: {v}"))

        erofs_row2.addWidget(self.erofs_level_label)
        erofs_row2.addWidget(self.erofs_slider, 1)
        erofs_layout.addLayout(erofs_row2)
        main_layout.addWidget(erofs_container)

        # =========================================================================
        # ⚙️ 3. F2FS设置 分组
        # =========================================================================
        f2fs_container = QWidget(self.content_widget)
        f2fs_layout = QVBoxLayout(f2fs_container)
        f2fs_layout.setContentsMargins(0, 0, 0, 0)
        f2fs_layout.setSpacing(8)

        f2fs_layout.addWidget(self._create_group_title("F2FS设置"))

        f2fs_row = QHBoxLayout()
        f2fs_row.setSpacing(12)

        self.f2fs_readonly_switch = SwitchButton(f2fs_container)
        self.f2fs_readonly_switch.setOnText("")
        self.f2fs_readonly_switch.setOffText("")
        self.f2fs_readonly_lbl = QLabel(self.tr("Readonly"), f2fs_container)
        self.f2fs_readonly_lbl.setStyleSheet("color: #ffffff; font-size: 13px;")

        self.f2fs_compress_switch = SwitchButton(f2fs_container)
        self.f2fs_compress_switch.setOnText("")
        self.f2fs_compress_switch.setOffText("")
        self.f2fs_compress_lbl = QLabel(self.tr("Compression"), f2fs_container)
        self.f2fs_compress_lbl.setStyleSheet("color: #ffffff; font-size: 13px;")

        f2fs_row.addWidget(self.f2fs_readonly_switch)
        f2fs_row.addWidget(self.f2fs_readonly_lbl)
        f2fs_row.addSpacing(20)
        f2fs_row.addWidget(self.f2fs_compress_switch)
        f2fs_row.addWidget(self.f2fs_compress_lbl)
        f2fs_row.addStretch(1)
        f2fs_layout.addLayout(f2fs_row)
        main_layout.addWidget(f2fs_container)

        # =========================================================================
        # 🛠️ 4. 其他设置 分组
        # =========================================================================
        other_container = QWidget(self.content_widget)
        other_layout = QVBoxLayout(other_container)
        other_layout.setContentsMargins(0, 0, 0, 0)
        other_layout.setSpacing(12)

        other_layout.addWidget(self._create_group_title("其他设置"))

        # Brotli 等级滑动条区域
        brotli_row = QHBoxLayout()
        self.brotli_lbl = QLabel("Brotli等级: 0", other_container)
        self.brotli_lbl.setStyleSheet("color: #ffffff; font-size: 15px; font-weight: 500; min-width: 100px;")
        self.brotli_slider = Slider(Qt.Orientation.Horizontal, other_container)
        self.brotli_slider.setRange(0, 11)
        self.brotli_slider.valueChanged.connect(lambda v: self.brotli_lbl.setText(f"Brotli等级: {v}"))

        brotli_row.addWidget(self.brotli_lbl)
        brotli_row.addWidget(self.brotli_slider, 1)
        other_layout.addLayout(brotli_row)

        # UTC 输入区域
        utc_row = QHBoxLayout()
        self.utc_lbl = QLabel("UTC:", other_container)
        self.utc_lbl.setStyleSheet("color: #ffffff; font-size: 15px; min-width: 45px;")
        self.utc_input = QLineEdit(str(int(time.time())), other_container)
        self.utc_input.setStyleSheet("""
            QLineEdit {
                background-color: #2a2a2e;
                border: 1px solid #3f3f46;
                border-radius: 4px;
                color: #ffffff;
                padding: 4px 8px;
                font-family: monospace;
            }
        """)
        utc_row.addWidget(self.utc_lbl)
        utc_row.addWidget(self.utc_input, 1)
        other_layout.addLayout(utc_row)

        # 底部复杂配置网格矩阵面板
        grid_matrix = QGridLayout()
        grid_matrix.setSpacing(12)

        self.format_label = self._create_field_label("打包格式：")
        self.format_combo = ComboBox(other_container)
        self.format_combo.addItems(["raw", "sparse"])

        self.sw_convert = SwitchButton(other_container)
        self.sw_convert.setOffText('')
        self.sw_convert.setOnText('')
        self.lbl_convert = QLabel("文件系统转换", other_container)
        self.lbl_convert.setStyleSheet("color: #ffffff; font-size: 13px;")

        # 💡 创建隐藏的文件系统来源与目标下拉框组合
        self.src_fs_combo = ComboBox(other_container)
        self.src_fs_combo.addItems(["ext", "f2fs", "erofs"])
        self.src_fs_combo.setFixedWidth(85)

        self.dest_fs_combo = ComboBox(other_container)
        self.dest_fs_combo.addItems(["ext", "f2fs", "erofs"])
        self.dest_fs_combo.setFixedWidth(85)

        # 初始默认状态必须完全隐藏
        self.src_fs_combo.hide()
        self.dest_fs_combo.hide()

        # 🔗 核心信号槽：将文件系统转换开关绑定到可见性处理器上
        self.sw_convert.checkedChanged.connect(self._on_convert_toggled)

        self.sw_vbmeta = SwitchButton(other_container)
        self.sw_vbmeta.setOffText("")
        self.sw_vbmeta.setOnText("")
        self.lbl_vbmeta = QLabel(self.tr("Process Vbmeta"), other_container)
        self.lbl_vbmeta.setStyleSheet("color: #ffffff; font-size: 13px;")

        self.sw_delete = SwitchButton(other_container)
        self.sw_delete.setOffText("")
        self.sw_delete.setOnText("")
        self.lbl_delete = QLabel("删除源文件", other_container)
        self.lbl_delete.setStyleSheet("color: #ffffff; font-size: 13px;")

        # 将所有控制元素对齐组装入 QGridLayout 矩阵中
        grid_matrix.addWidget(self.format_label, 0, 0)
        grid_matrix.addWidget(self.format_combo, 0, 1)
        grid_matrix.addWidget(self.sw_convert, 0, 2)
        grid_matrix.addWidget(self.lbl_convert, 0, 3)

        # 💡 将转换下拉框追加在第0行、第4和第5列上
        grid_matrix.addWidget(self.src_fs_combo, 0, 4)
        grid_matrix.addWidget(self.dest_fs_combo, 0, 5)

        grid_matrix.addWidget(self.sw_vbmeta, 1, 0)
        grid_matrix.addWidget(self.lbl_vbmeta, 1, 1)
        grid_matrix.addWidget(self.sw_delete, 1, 2)
        grid_matrix.addWidget(self.lbl_delete, 1, 3)
        other_layout.addLayout(grid_matrix)
        main_layout.addWidget(other_container)

    def _on_convert_toggled(self, is_checked: bool):
        self.src_fs_combo.setVisible(is_checked)
        self.dest_fs_combo.setVisible(is_checked)
        self.content_widget.adjustSize()
        self.widget.adjustSize()


class PackSuperMessageBox(MessageBoxBase):
    def __init__(self, work_path, parent=None):
        super().__init__(parent)
        self.work = work_path
        self.selected = []
        self._block_device_name = 'super'

        # Window styling configuration
        self.widget.setMinimumWidth(450)

        # 1. Main Header Title
        self.titleLabel = SubtitleLabel("Pack Super", self)
        self.viewLayout.addWidget(self.titleLabel)

        # 2. Partition Type Section
        self.viewLayout.addWidget(SubtitleLabel(self.tr("Super Type"), self))
        lf1_layout = QHBoxLayout()
        self.type_group = QButtonGroup(self)
        radios = [("A-only", 1), ("Virtual-ab", 2), ("A/B", 3)]
        for text, value in radios:
            rb = RadioButton(text, self)
            self.type_group.addButton(rb, value)
            lf1_layout.addWidget(rb)
        if self.type_group.button(1):
            self.type_group.button(1).setChecked(True)
        self.viewLayout.addLayout(lf1_layout)

        # 3. Attributes Section
        self.viewLayout.addWidget(SubtitleLabel(self.tr("Attribute"), self))
        lf1_r_layout = QHBoxLayout()
        self.attrib_group = QButtonGroup(self)
        self.rb_readonly = RadioButton("Readonly", self)
        self.rb_none = RadioButton("None", self)
        self.attrib_group.addButton(self.rb_readonly, 0)
        self.attrib_group.addButton(self.rb_none, 1)
        self.rb_readonly.setChecked(True)
        lf1_r_layout.addWidget(self.rb_readonly)
        lf1_r_layout.addWidget(self.rb_none)
        self.viewLayout.addLayout(lf1_r_layout)

        # 4. Settings Section
        self.viewLayout.addWidget(SubtitleLabel("设置", self))
        lf2_layout = QHBoxLayout()

        lf2_layout.addWidget(SubtitleLabel(self.tr("Group Name"), self))
        self.show_group_name = ComboBox(self)
        self.show_group_name.addItems(["qti_dynamic_partitions", "main", "mot_dp_group"])
        self.show_group_name.setCurrentIndex(0)
        lf2_layout.addWidget(self.show_group_name)

        lf2_layout.addWidget(SubtitleLabel(self.tr("Super Size"), self))
        self.super_size_edit = LineEdit(self)
        self.super_size_edit.setText("9126805504")
        self.super_size_edit.textChanged.connect(self.validate_digits)
        lf2_layout.addWidget(self.super_size_edit)
        self.viewLayout.addLayout(lf2_layout)

        # 5. Pack Partitions Section
        self.viewLayout.addWidget(SubtitleLabel("打包分区", self))
        self.tl = ListWidget(self)
        self.tl.setMinimumHeight(180)
        self.viewLayout.addWidget(self.tl)

        # 6. Checkboxes & Action Layout Configurations
        self.switch_sparse = SwitchButton(self)
        self.switch_sparse.setOffText(self.tr("Enable Sparse"))
        self.switch_sparse.setOnText(self.tr("Enable Sparse"))
        self.viewLayout.addWidget(self.switch_sparse)

        t_frame_layout = QHBoxLayout()
        self.switch_delete = SwitchButton(self)
        self.switch_delete.setOffText("删除源文件")
        self.switch_delete.setOnText("删除源文件")
        t_frame_layout.addWidget(self.switch_delete)

        self.btn_refresh = PushButton(self.tr("Refresh"), self)
        self.btn_refresh.clicked.connect(self.refresh)
        t_frame_layout.addWidget(self.btn_refresh)

        self.g_b = PushButton(self.tr("Generate LIST"), self)
        self.g_b.clicked.connect(self.generate)
        t_frame_layout.addWidget(self.g_b)
        self.viewLayout.addLayout(t_frame_layout)

        # 7. Bottom Accept/Cancel Bar configuration setups
        self.yesButton.setText(self.tr("Pack"))
        self.cancelButton.setText(self.tr("Cancel"))
        self.read_list()
        self.refresh()

    def validate_digits(self, text):
        """Sanitizes line edit inputs to keep digit formatting clean."""
        if not text.isdigit() and text != "":
            clean_text = "".join(filter(str.isdigit, text))
            self.super_size_edit.setText(clean_text)

    def get_selected_items(self):
        """Extracts current checkable choices context keys from list layout directly."""
        checked_names = []
        for i in range(self.tl.count()):
            item = self.tl.item(i)
            if item.checkState() == Qt.Checked:
                checked_names.append(item.data(Qt.UserRole))
        return checked_names

    def verify_size(self):
        selected_lbs = self.get_selected_items()
        size = sum(
            [os.path.getsize(f"{self.work}/{i}.img") for i in selected_lbs if os.path.exists(f"{self.work}/{i}.img")])

        try:
            current_size = int(self.super_size_edit.text() or "0")
        except ValueError:
            current_size = 0

        if size > current_size:
            diff_size = size
            for i in range(20):
                if not i:
                    continue
                i -= 0.25
                t = (1024 ** 3) * i - size
                if t < 0:
                    continue
                if t < diff_size:
                    diff_size = t
                else:
                    size = i * (1024 ** 3)
                    break
            self.super_size_edit.setText(str(int(size)))
            return False
        return True

    def generate(self):
        self.g_b.setText(self.tr("Running"))
        self.g_b.setEnabled(False)
        self.g_b.repaint()

        try:
            size_val = int(self.super_size_edit.text() or "0")
        except ValueError:
            size_val = 0

        utils.generate_dynamic_list(
            group_name=self.show_group_name.currentText(),
            size=size_val,
            super_type=self.type_group.checkedId(),
            part_list=self.get_selected_items(),
            work=self.work
        )
        self.g_b.setText(self.tr("Done"))
        QTimer.singleShot(1000, self._reset_generate_button)

    def _reset_generate_button(self):
        try:
            self.g_b.setText(self.tr("Generate LIST"))
            self.g_b.setEnabled(True)
        except Exception:
            logging.exception('Bugs')

    def refresh(self):
        self.tl.clear()
        if not os.path.exists(self.work):
            return

        for file_name in os.listdir(self.work):
            if file_name.endswith(".img"):
                img_path = os.path.join(self.work, file_name)
                name = file_name[:-4]
                is_checked = name in self.selected
                item_text = ""

                if utils.is_empty_img(img_path):
                    item_text = f"{name} [empty]"
                else:
                    file_type = gettype(img_path)
                    if file_type in ["ext", "erofs", 'f2fs', 'sparse']:
                        item_text = f"{name} [{file_type}]"

                if item_text:
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.UserRole, name)
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Checked if is_checked else Qt.Unchecked)
                    self.tl.addItem(item)
        self.verify_size()

    def read_list(self):
        # Read parts_config
        parts_info = f"{self.work}/config/parts_info"
        if os.path.exists(parts_info):
            try:
                data: dict = utils.JsonEdit(parts_info).read().get('super_info')
                if data is None:
                    raise AttributeError("super_info is not dict")
            except Exception:
                logging.exception('PackSupper:read_parts_info')
            else:
                # get block device name
                for i in data.get('block_devices', []):
                    self._block_device_name = i.get('name', 'super')
                    if isinstance(i.get('size'), int):
                        self.super_size_edit.setText(str(i.get('size')))

                for i in data.get('group_table', []):
                    name = i.get('name')
                    if isinstance(name, str) and name != 'default':
                        index = self.show_group_name.findText(name)
                        if index >= 0:
                            self.show_group_name.setCurrentIndex(index)
                        else:
                            self.show_group_name.addItem(name)
                            self.show_group_name.setCurrentText(name)

                selected = []
                for i in data.get('partition_table', []):
                    name = i.get('name')
                    if isinstance(name, str) and name not in selected:
                        selected.append(name)
                self.selected = selected

        # Read dynamic_partitions_op_list
        list_file = f"{self.work}/dynamic_partitions_op_list"
        if os.path.exists(list_file):
            try:
                data = utils.dynamic_list_reader(list_file)
            except Exception:
                logging.exception('Bugs')
                return

            if not isinstance(data, dict) or not data:
                return

            keys = list(data.keys())

            if len(keys) > 1:
                fir = keys[0]
                sec = keys[1]
                if fir[:-2] == sec[:-2]:
                    g_name = fir[:-2]
                    index = self.show_group_name.findText(g_name)
                    if index >= 0:
                        self.show_group_name.setCurrentIndex(index)
                    else:
                        self.show_group_name.addItem(g_name)
                        self.show_group_name.setCurrentText(g_name)

                    if self.type_group.button(2):
                        self.type_group.button(2).setChecked(True)

                    self.super_size_edit.setText(str(int(data[fir]['size'])))
                    self.selected = data[fir].get('parts', [])

                    selected_copy = self.selected.copy()
                    for i in self.selected:
                        name = i[:-2] if i.endswith('_a') or i.endswith('_b') else i
                        if name not in selected_copy:
                            selected_copy.append(name)
                    self.selected = selected_copy

            elif len(keys) == 1:
                group_name = keys[0]
                index = self.show_group_name.findText(group_name)
                if index >= 0:
                    self.show_group_name.setCurrentIndex(index)
                else:
                    self.show_group_name.addItem(group_name)
                    self.show_group_name.setCurrentText(group_name)

                self.super_size_edit.setText(str(int(data[group_name]['size'])))
                self.selected = data[group_name].get('parts', [])

                if self.type_group.button(1):
                    self.type_group.button(1).setChecked(True)


class RepackZipMessageBox(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(self.tr("Pack ZIP"))
        self.widget.setMinimumWidth(550)

        # 1. Title
        self.titleLabel = SubtitleLabel(self.tr("Repack ZIP?"), self)
        self.titleLabel.setAlignment(Qt.AlignCenter)
        self.viewLayout.addWidget(self.titleLabel)

        # 2. CheckBox & Content Text Layout
        self.checkbox_layout = QHBoxLayout()
        self.checkbox = CheckBox(self)

        msg_text = self.tr(
            "Pack Hybrid Rom?"
        )
        self.contentLabel = BodyLabel(msg_text, self)
        self.contentLabel.setWordWrap(True)

        self.checkbox_layout.addWidget(self.checkbox, 0, Qt.AlignTop)
        self.checkbox_layout.addWidget(self.contentLabel, 1)
        self.viewLayout.addLayout(self.checkbox_layout)

        # 3. Dynamic Device Code Input LineEdit
        self.device_code_edit = LineEdit(self)
        self.device_code_edit.setPlaceholderText(self.tr("Enter device code"))
        self.device_code_edit.setClearButtonEnabled(True)
        self.device_code_edit.hide()  # Hidden by default
        self.viewLayout.addWidget(self.device_code_edit)

        # Connect toggle action to state visibility switch
        self.checkbox.stateChanged.connect(self.toggle_input_visibility)

        # 4. Standard action button text overrides
        self.yesButton.setText(self.tr("OK"))
        self.cancelButton.setText(self.tr("Cancel"))

    def toggle_input_visibility(self, state):
        """Hides or reveals the LineEdit depending on the checkbox check state."""
        is_checked = (state == Qt.Checked or state == 2)  # Handles PySide6 integer/enum variants
        self.device_code_edit.setVisible(is_checked)

        # Force the Fluent MessageBox to smoothly recalculate layout sizing constraints
        self.widget.adjustSize()

    def is_add_tools_checked(self) -> bool:
        """Returns True if the check box tool integration option is selected."""
        return self.checkbox.isChecked()

    def get_device_code(self) -> str:
        """Returns the trimmed input text string from the device code line entry."""
        return self.device_code_edit.text().strip()