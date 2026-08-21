import time
import tkinter as tk

from PySide6.QtCore import QTimer
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QLabel, QLineEdit)
from qfluentwidgets import InfoBar, InfoBarPosition, LineEdit
from qfluentwidgets import (MessageBoxBase, ComboBox, SwitchButton, Slider,
                            SubtitleLabel, CaptionLabel)


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
        self.f2fs_readonly_lbl = QLabel("只读", f2fs_container)
        self.f2fs_readonly_lbl.setStyleSheet("color: #ffffff; font-size: 13px;")

        self.f2fs_compress_switch = SwitchButton(f2fs_container)
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
        self.lbl_convert = QLabel("文件系统转换", other_container)
        self.lbl_convert.setStyleSheet("color: #ffffff; font-size: 13px;")

        # 💡 创建隐藏的文件系统来源与目标下拉框组合
        self.src_fs_combo = ComboBox(other_container)
        self.src_fs_combo.addItems(["f2fs", "ext4", "erofs"])
        self.src_fs_combo.setFixedWidth(85)

        self.dest_fs_combo = ComboBox(other_container)
        self.dest_fs_combo.addItems(["ext4", "f2fs", "erofs"])
        self.dest_fs_combo.setFixedWidth(85)

        # 初始默认状态必须完全隐藏
        self.src_fs_combo.hide()
        self.dest_fs_combo.hide()

        # 🔗 核心信号槽：将文件系统转换开关绑定到可见性处理器上
        self.sw_convert.checkedChanged.connect(self._on_convert_toggled)

        self.sw_vbmeta = SwitchButton(other_container)
        self.lbl_vbmeta = QLabel("处理Vbmeta", other_container)
        self.lbl_vbmeta.setStyleSheet("color: #ffffff; font-size: 13px;")

        self.sw_delete = SwitchButton(other_container)
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

