import logging
import os
import time
import tkinter as tk

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGridLayout,
                               QLabel, QLineEdit)
from qfluentwidgets import InfoBar, InfoBarPosition
from qfluentwidgets import (MessageBoxBase, SwitchButton, Slider,
                            CaptionLabel)

import utils
from utils import gettype, is_empty_img


class TkinterEmbeddedPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # 1. Force Qt to create a native window handle/X11 ID for THIS specific widget
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        layout = QVBoxLayout()
        self.widget = QWidget()
        layout.addWidget(self.widget)
        self.setLayout(layout)
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


from PySide6.QtCore import Slot
from PySide6.QtWidgets import QListWidgetItem
from qfluentwidgets import (
    MessageBoxBase,
)


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
        self.yesButton.setText("打包")
        self.cancelButton.setText("取消")

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
        self.support_old_kernel_label = QLabel("支持旧内核", erofs_container)
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
        self.f2fs_readonly_lbl = QLabel("只读", f2fs_container)
        self.f2fs_readonly_lbl.setStyleSheet("color: #ffffff; font-size: 13px;")

        self.f2fs_compress_switch = SwitchButton(f2fs_container)
        self.f2fs_compress_switch.setOnText("")
        self.f2fs_compress_switch.setOffText("")
        self.f2fs_compress_lbl = QLabel("压缩", f2fs_container)
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
        self.lbl_vbmeta = QLabel("处理Vbmeta", other_container)
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


from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QListWidgetItem
from qfluentwidgets import (
    CheckBox,
    ComboBox,
    LineEdit,
    ListWidget,
    MessageBoxBase,
    PushButton,
    RadioButton,
    SubtitleLabel,
)


class PackSuperMessageBox(MessageBoxBase):
    def __init__(self, work_path, parent=None):
        super().__init__(parent)
        self.work = work_path

        self._super_size = 9126805504
        self._is_sparse = False
        self._super_type = 1
        self._attrib = 'readonly'
        self._group_name = "qti_dynamic_partitions"
        self._delete_source_file = False
        self._block_device_name = 'super'
        self.selected = []

        self.setup_ui()
        self.read_list()

        self.refresh()

    def setup_ui(self):
        self.viewLayout.setSpacing(12)

        type_card = CaptionLabel(self)
        type_card.setText("Super Partition Type")
        type_layout = QHBoxLayout()
        type_layout.setContentsMargins(12, 12, 12, 12)
        self.radio_a = RadioButton("A-only", type_card)
        self.radio_vab = RadioButton("Virtual-ab", type_card)
        self.radio_ab = RadioButton("A/B", type_card)
        for rb in (self.radio_a, self.radio_vab, self.radio_ab):
            type_layout.addWidget(rb)
        type_card.setLayout(type_layout)
        self.viewLayout.addWidget(type_card)

        attr_card = CaptionLabel(self)
        attr_card.setText("Attribute")
        attr_layout = QHBoxLayout()
        attr_layout.setContentsMargins(12, 12, 12, 12)
        self.radio_ro = RadioButton("Readonly", attr_card)
        self.radio_none = RadioButton("None", attr_card)
        attr_layout.addWidget(self.radio_ro)
        attr_layout.addWidget(self.radio_none)
        attr_card.setLayout(attr_layout)
        self.viewLayout.addWidget(attr_card)

        settings_card = CaptionLabel(self)
        settings_card.setText("Configuration Settings")
        settings_layout = QGridLayout()
        settings_layout.setContentsMargins(12, 12, 12, 12)

        settings_layout.addWidget(CaptionLabel("Group Name:", settings_card), 0, 0)
        self.group_combo = ComboBox(settings_card)
        self.group_combo.addItems(["qti_dynamic_partitions", "main", "mot_dp_group"])
        settings_layout.addWidget(self.group_combo, 0, 1)

        settings_layout.addWidget(CaptionLabel("Super Size (Bytes):", settings_card), 1, 0)
        self.size_entry = LineEdit(settings_card)
        self.size_entry.textChanged.connect(self.validate_size_input)
        settings_layout.addWidget(self.size_entry, 1, 1)

        settings_card.setLayout(settings_layout)
        self.viewLayout.addWidget(settings_card)

        list_card = CaptionLabel(self)
        list_card.setText("Select Partitions")
        list_layout = QVBoxLayout()
        list_layout.setContentsMargins(12, 12, 12, 12)

        self.partition_listview = ListWidget(list_card)
        self.partition_listview.setSelectionMode(ListWidget.MultiSelection)
        self.partition_listview.setMinimumHeight(200)
        list_layout.addWidget(self.partition_listview)
        list_card.setLayout(list_layout)
        self.viewLayout.addWidget(list_card)

        self.sparse_check = CheckBox("Sparse Image Output", self)
        self.viewLayout.addWidget(self.sparse_check)

        tools_layout = QHBoxLayout()
        self.del_source_check = CheckBox("Delete Source Image Files", self)
        tools_layout.addWidget(self.del_source_check)
        tools_layout.addStretch()

        self.refresh_btn = PushButton("Refresh List", self)
        self.refresh_btn.clicked.connect(self.refresh)
        tools_layout.addWidget(self.refresh_btn)

        self.g_b = PushButton("Generate Script", self)
        self.g_b.clicked.connect(self.generate)
        tools_layout.addWidget(self.g_b)
        self.viewLayout.addLayout(tools_layout)

        self.yesButton.setText("Pack")
        self.cancelButton.setText("Cancel")

    def validate_size_input(self, text):
        has_error = not text.isdigit()
        self.size_entry.setProperty("hasError", has_error)
        self.size_entry.style().polish(self.size_entry)

    def sync_vars_from_ui(self):
        if self.radio_a.isChecked():
            self._super_type = 1
        elif self.radio_vab.isChecked():
            self._super_type = 2
        elif self.radio_ab.isChecked():
            self._super_type = 3

        self._attrib = 'readonly' if self.radio_ro.isChecked() else 'none'
        self._group_name = self.group_combo.currentText()

        try:
            self._super_size = int(self.size_entry.text())
        except ValueError:
            self._super_size = 0

        self._is_sparse = self.sparse_check.isChecked()
        self._delete_source_file = self.del_source_check.isChecked()

    def update_ui_from_vars(self):
        self.radio_a.setChecked(self._super_type == 1)
        self.radio_vab.setChecked(self._super_type == 2)
        self.radio_ab.setChecked(self._super_type == 3)
        self.radio_ro.setChecked(self._attrib == 'readonly')
        self.radio_none.setChecked(self._attrib == 'none')

        self.group_combo.setCurrentText(str(self._group_name))
        self.size_entry.setText(str(self._super_size))
        self.sparse_check.setChecked(self._is_sparse)
        self.del_source_check.setChecked(self._delete_source_file)

    def get_selected_partitions(self):
        return [item.data(Qt.UserRole) for item in self.partition_listview.selectedItems()]



    def verify_size(self):
        lbs = self.get_selected_partitions()
        size = sum([os.path.getsize(f"{self.work}/{i}.img") for i in lbs if os.path.exists(f"{self.work}/{i}.img")])

        if size > self._super_size:
            diff_size = size
            for i in range(1, 20):
                factor = i - 0.25
                t = (1024 ** 3) * factor - size
                if t < 0:
                    continue
                if t < diff_size:
                    diff_size = t
                else:
                    size = factor * (1024 ** 3)
                    break
            self._super_size = int(size)
            self.size_entry.setText(str(self._super_size))
            return False
        return True

    def generate(self):
        self.sync_vars_from_ui()
        self.g_b.setEnabled(False)
        self.g_b.setText("Generating...")

        utils.generate_dynamic_list(
            group_name=self._group_name, size=self._super_size,
            super_type=self._super_type, part_list=self.get_selected_partitions(), work=self.work
        )

        self.g_b.setText("Done!")
        time.sleep(1)
        self.g_b.setText("Generate Script")
        self.g_b.setEnabled(True)

    def refresh(self):
        self.partition_listview.clear()
        if not os.path.exists(self.work):
            return

        for file_name in os.listdir(self.work):
            if file_name.endswith(".img"):
                full_path = os.path.join(self.work, file_name)
                name = file_name[:-4]
                display_text = ""

                if is_empty_img(full_path):
                    display_text = f"{name} [empty]"
                elif (file_type := gettype(full_path)) in ["ext", "erofs", 'f2fs', 'sparse']:
                    display_text = f"{name} [{file_type}]"

                if display_text:
                    item = QListWidgetItem(display_text)
                    item.setData(Qt.UserRole, name)
                    self.partition_listview.addItem(item)
                    if name in self.selected:
                        item.setSelected(True)

    def read_list(self):
        parts_info = f"{self.work}/config/parts_info"
        if os.path.exists(parts_info):
            try:
                data: dict = utils.JsonEdit(parts_info).read().get('super_info')
                if data is None:
                    raise AttributeError()
            except Exception:
                logging.exception('PackSupper:read_parts_info')
            else:
                for i in data.get('block_devices', []):
                    self._block_device_name = i.get('name', 'super')
                    if isinstance(i.get('size'), int):
                        self._super_size = i.get('size', self._super_size)

                for i in data.get('group_table', []):
                    name = i.get('name')
                    if isinstance(name, str) and name != 'default':
                        self._group_name = name

                self.selected = [
                    i.get('name') for i in data.get('partition_table', [])
                    if isinstance(i.get('name'), str)
                ]

        list_file = f"{self.work}/dynamic_partitions_op_list"
        if os.path.exists(list_file):
            try:
                data = utils.dynamic_list_reader(list_file)
            except Exception:
                logging.exception('Bugs')
                self.update_ui_from_vars()
                return

            if len(data) > 1:
                keys = list(data.keys())
                fir, sec = keys[0], keys[1]
                if fir[:-2] == sec[:-2]:
                    self._group_name = fir[:-2]
                    self._super_type = 2
                    self._super_size = int(data[fir]['size'])

                    raw_parts = data[fir].get('parts', [])
                    selected = raw_parts.copy()
                    for i in raw_parts:
                        name = i[:-2] if i.endswith('_a') or i.endswith('_b') else i
                        if name not in selected:
                            selected.append(name)
                    self.selected = selected
            elif len(data) == 1:
                group_name = list(data.keys())[0]
                self._group_name = group_name
                self._super_size = int(data[group_name]['size'])
                self.selected = data[group_name].get('parts', [])
                self._super_type = 1

        self.update_ui_from_vars()
