import logging
import os
import time

from PySide6.QtCore import QTimer, QThread
from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtCore import Slot
from PySide6.QtGui import QColor
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QListWidgetItem
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGridLayout,
                               QHBoxLayout, QButtonGroup)
from qfluentwidgets import ListWidget, CheckBox, LineEdit, ComboBox, SubtitleLabel, \
    RadioButton, PushButton, BodyLabel, EditableComboBox, CardWidget, FluentIcon, ToolButton
from qfluentwidgets import (
    MessageBoxBase,
)
from qfluentwidgets import (SwitchButton, Slider,
                            CaptionLabel)

from src.core import utils
from src.core.utils import gettype


class GenericTaskWorker(QThread):
    task_finished = Signal(bool)
    send_message = Signal(str, str, int)

    def __init__(self, target_func, *args, **kwargs):
        super().__init__()
        self.target_func = target_func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            self.target_func(*self.args, **self.kwargs)
        except Exception as e:
            self.task_finished.emit(True)
            raise e
        self.task_finished.emit(True)

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
            self.errorLabel.setText(self.tr("The name contains illegal characters"))
            self.errorLabel.show()
            return False

        if project_name in self.existing_projects:
            self.errorLabel.setText(self.tr("The project name already exists"))
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
        self.nameLineEdit.setPlaceholderText(self.tr('Type'))
        self.nameLineEdit.setClearButtonEnabled(True)
        self.nameLineEdit.setText(initial_text)

        self.errorLabel = CaptionLabel(text=self.tr("invalid"))
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
            self.errorLabel.setText(self.tr("Cannot be empty."))
            self.errorLabel.show()
            return False

        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        if any(char in project_name for char in invalid_chars):
            self.errorLabel.setText(self.tr("Contain invalid chars"))
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
        self.titleLabel = SubtitleLabel(self.tr("Convert image"), self)
        self.yesButton.setText(self.tr("OK"))
        self.cancelButton.setText(self.tr("Cancel"))

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
        self.select_all_checkbox = CheckBox(self.tr("Select all"), self)
        self.search_input = LineEdit(self)
        self.search_input.setPlaceholderText(self.tr("search..."))
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
    def __init__(self, parent=None):
        super().__init__(parent)

        self.content_widget = QWidget(self)
        self.initCustomUI()
        self.viewLayout.addWidget(self.content_widget)
        self.yesButton.setText(self.tr("Pack"))
        self.cancelButton.setText(self.tr("Cancel"))
        self.widget.setMinimumWidth(700)

    def _create_section(self, title):
        card = CardWidget(self.content_widget)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)
        layout.addWidget(SubtitleLabel(title, card))
        return card, layout

    def initCustomUI(self):
        main_layout = QVBoxLayout(self.content_widget)
        main_layout.setContentsMargins(0, 0, 0, 4)
        main_layout.setSpacing(12)

        sections = QGridLayout()
        sections.setContentsMargins(0, 0, 0, 0)
        sections.setHorizontalSpacing(12)
        sections.setVerticalSpacing(12)
        main_layout.addLayout(sections)

        ext4_card, ext4_layout = self._create_section(self.tr("EXT4 Settings"))
        ext4_form = QGridLayout()
        ext4_form.setHorizontalSpacing(12)
        ext4_form.setVerticalSpacing(8)
        ext4_form.setColumnStretch(1, 1)

        self.pack_method_label = BodyLabel(self.tr("Packing with:"), ext4_card)
        self.pack_method_combo = ComboBox(ext4_card)
        self.pack_method_combo.addItems(["make_ext4fs", "mke2fs+e2fsdroid"])
        self.size_handle_label = BodyLabel(self.tr("Size Handle:"), ext4_card)
        self.size_handle_combo = ComboBox(ext4_card)
        self.size_handle_combo.addItems([self.tr("Calculate Auto"), self.tr("Origin Size")])
        ext4_form.addWidget(self.pack_method_label, 0, 0)
        ext4_form.addWidget(self.pack_method_combo, 0, 1)
        ext4_form.addWidget(self.size_handle_label, 1, 0)
        ext4_form.addWidget(self.size_handle_combo, 1, 1)
        ext4_layout.addLayout(ext4_form)

        erofs_card, erofs_layout = self._create_section(self.tr("EROFS Settings"))
        erofs_form = QGridLayout()
        erofs_form.setHorizontalSpacing(10)
        erofs_form.setVerticalSpacing(8)
        erofs_form.setColumnStretch(1, 1)
        self.compress_algo_label = BodyLabel(self.tr("Compression Method:"), erofs_card)
        self.compress_algo_combo = ComboBox(erofs_card)
        self.compress_algo_combo.addItems(["lz4", "lz4hc", "lzma", "deflate", "zstd"])
        self.compress_algo_combo.setText("lz4hc")
        self.support_old_kernel_switch = SwitchButton(parent=erofs_card)
        self.support_old_kernel_switch.setOffText("")
        self.support_old_kernel_switch.setOnText("")
        self.support_old_kernel_label = BodyLabel(self.tr("Support old kernel"), erofs_card)
        erofs_form.addWidget(self.compress_algo_label, 0, 0)
        erofs_form.addWidget(self.compress_algo_combo, 0, 1, 1, 2)

        self.erofs_level_label = BodyLabel(self.tr("EROFS Level: 8"), erofs_card)
        self.erofs_slider = Slider(Qt.Orientation.Horizontal, erofs_card)
        self.erofs_slider.setRange(0, 20)
        self.erofs_slider.setValue(8)
        self.erofs_slider.valueChanged.connect(
            lambda value: self.erofs_level_label.setText(
                self.tr("EROFS Level: {}").format(value)))
        erofs_form.addWidget(self.erofs_level_label, 1, 0)
        erofs_form.addWidget(self.erofs_slider, 1, 1, 1, 2)
        erofs_form.addWidget(self.support_old_kernel_switch, 2, 0)
        erofs_form.addWidget(self.support_old_kernel_label, 2, 1, 1, 2)
        erofs_layout.addLayout(erofs_form)

        f2fs_card, f2fs_layout = self._create_section(self.tr("F2FS Settings"))
        f2fs_options = QGridLayout()
        f2fs_options.setHorizontalSpacing(8)
        f2fs_options.setVerticalSpacing(8)
        self.f2fs_readonly_switch = SwitchButton(f2fs_card)
        self.f2fs_readonly_switch.setOnText("")
        self.f2fs_readonly_switch.setOffText("")
        self.f2fs_readonly_lbl = BodyLabel(self.tr("Readonly"), f2fs_card)
        self.f2fs_compress_switch = SwitchButton(f2fs_card)
        self.f2fs_compress_switch.setOnText("")
        self.f2fs_compress_switch.setOffText("")
        self.f2fs_compress_lbl = BodyLabel(self.tr("Compression"), f2fs_card)
        f2fs_options.addWidget(self.f2fs_readonly_switch, 0, 0)
        f2fs_options.addWidget(self.f2fs_readonly_lbl, 0, 1)
        f2fs_options.addWidget(self.f2fs_compress_switch, 1, 0)
        f2fs_options.addWidget(self.f2fs_compress_lbl, 1, 1)
        f2fs_options.setColumnStretch(2, 1)
        f2fs_layout.addLayout(f2fs_options)

        other_card, other_layout = self._create_section(self.tr("Others"))
        other_form = QGridLayout()
        other_form.setHorizontalSpacing(12)
        other_form.setVerticalSpacing(8)
        other_form.setColumnStretch(1, 1)
        other_form.setColumnStretch(3, 1)

        self.format_label = BodyLabel(self.tr("Format:"), other_card)
        self.format_combo = ComboBox(other_card)
        self.format_combo.addItems(["raw", "sparse", "br", "dat"])
        self.utc_lbl = BodyLabel("UTC:", other_card)
        self.utc_input = LineEdit(other_card)
        self.utc_input.setText(str(int(time.time())))
        other_form.addWidget(self.format_label, 0, 0)
        other_form.addWidget(self.format_combo, 0, 1)
        other_form.addWidget(self.utc_lbl, 0, 2)
        other_form.addWidget(self.utc_input, 0, 3)

        self.brotli_lbl = BodyLabel(self.tr("Brotli Level: 0"), other_card)
        self.brotli_slider = Slider(Qt.Orientation.Horizontal, other_card)
        self.brotli_slider.setRange(0, 11)
        self.brotli_slider.valueChanged.connect(
            lambda value: self.brotli_lbl.setText(
                self.tr("Brotli Level: {}").format(value)))
        other_form.addWidget(self.brotli_lbl, 1, 0)
        other_form.addWidget(self.brotli_slider, 1, 1, 1, 3)

        self.sw_convert = SwitchButton(other_card)
        self.sw_convert.setOffText("")
        self.sw_convert.setOnText('')
        self.lbl_convert = BodyLabel(self.tr("Fs Convert"), other_card)
        self.src_fs_combo = ComboBox(other_card)
        self.src_fs_combo.addItems(["ext", "f2fs", "erofs"])
        self.src_fs_combo.setFixedWidth(90)
        self.dest_fs_combo = ComboBox(other_card)
        self.dest_fs_combo.addItems(["ext", "f2fs", "erofs"])
        self.dest_fs_combo.setFixedWidth(90)
        self.src_fs_combo.hide()
        self.dest_fs_combo.hide()
        self.fs_conversion_arrow = BodyLabel("→", other_card)
        self.fs_conversion_arrow.hide()
        self.sw_convert.checkedChanged.connect(self._on_convert_toggled)

        self.sw_vbmeta = SwitchButton(other_card)
        self.sw_vbmeta.setOffText("")
        self.sw_vbmeta.setOnText("")
        self.lbl_vbmeta = BodyLabel(self.tr("Process Vbmeta"), other_card)
        self.sw_delete = SwitchButton(other_card)
        self.sw_delete.setOffText("")
        self.sw_delete.setOnText("")
        self.lbl_delete = BodyLabel(self.tr("Remove source files"), other_card)

        conversion_row = QHBoxLayout()
        conversion_row.setSpacing(8)
        conversion_row.addWidget(self.sw_convert)
        conversion_row.addWidget(self.lbl_convert)
        conversion_row.addWidget(self.src_fs_combo)
        conversion_row.addWidget(self.fs_conversion_arrow)
        conversion_row.addWidget(self.dest_fs_combo)
        conversion_row.addStretch(1)
        other_form.addLayout(conversion_row, 2, 0, 1, 4)

        other_options = QHBoxLayout()
        other_options.setSpacing(8)
        other_options.addWidget(self.sw_vbmeta)
        other_options.addWidget(self.lbl_vbmeta)
        other_options.addSpacing(16)
        other_options.addWidget(self.sw_delete)
        other_options.addWidget(self.lbl_delete)
        other_options.addStretch(1)
        other_form.addLayout(other_options, 3, 0, 1, 4)
        other_layout.addLayout(other_form)

        sections.addWidget(ext4_card, 0, 0)
        sections.addWidget(erofs_card, 0, 1)
        sections.addWidget(f2fs_card, 1, 0, 1, 2)
        sections.addWidget(other_card, 2, 0, 1, 2)
        sections.setColumnStretch(0, 1)
        sections.setColumnStretch(1, 1)

    def _on_convert_toggled(self, is_checked: bool):
        self.src_fs_combo.setVisible(is_checked)
        self.fs_conversion_arrow.setVisible(is_checked)
        self.dest_fs_combo.setVisible(is_checked)




class ClickableLabel(QLabel):
    clicked = Signal()

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMouseTracking(True)

    def enterEvent(self, event):
        """Show hand cursor when entering widget"""
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Reset cursor when leaving widget"""
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
class PackSuperMessageBox(MessageBoxBase):
    def __init__(self, work_path, parent=None):
        super().__init__(parent)
        self.work = work_path
        self.selected = []
        self._block_device_name = 'super'

        self.viewLayout.setSpacing(12)
        self.widget.setMinimumWidth(620)
        self.titleLabel = SubtitleLabel(self.tr("Pack Super"), self)
        self.viewLayout.addWidget(self.titleLabel)

        top_sections = QHBoxLayout()
        top_sections.setSpacing(12)
        type_card, type_layout = self._create_section(self.tr("Super Type"))
        self.type_group = QButtonGroup(self)
        radios = [("A-only", 1), ("Virtual-ab", 2), ("A/B", 3)]
        type_options = QHBoxLayout()
        type_options.setSpacing(12)
        for text, value in radios:
            rb = RadioButton(text, type_card)
            self.type_group.addButton(rb, value)
            type_options.addWidget(rb)
        if self.type_group.button(1):
            self.type_group.button(1).setChecked(True)
        type_options.addStretch(1)
        type_layout.addLayout(type_options)
        top_sections.addWidget(type_card, 1)

        attribute_card, attribute_layout = self._create_section(self.tr("Attribute"))
        self.attrib_group = QButtonGroup(self)
        self.rb_readonly = RadioButton(self.tr("Readonly"), attribute_card)
        self.rb_none = RadioButton(self.tr("None"), attribute_card)
        self.attrib_group.addButton(self.rb_readonly, 0)
        self.attrib_group.addButton(self.rb_none, 1)
        self.rb_readonly.setChecked(True)
        attribute_options = QHBoxLayout()
        attribute_options.setSpacing(12)
        attribute_options.addWidget(self.rb_readonly)
        attribute_options.addWidget(self.rb_none)
        attribute_options.addStretch(1)
        attribute_layout.addLayout(attribute_options)
        top_sections.addWidget(attribute_card, 1)
        self.viewLayout.addLayout(top_sections)

        settings_card, settings_layout = self._create_section(self.tr("Settings"))
        settings_form = QGridLayout()
        settings_form.setHorizontalSpacing(12)
        settings_form.setVerticalSpacing(8)
        settings_form.setColumnStretch(1, 1)
        settings_form.addWidget(BodyLabel(self.tr("Group Name"), settings_card), 0, 0)
        self.show_group_name = EditableComboBox(settings_card)
        self.show_group_name.addItems(["qti_dynamic_partitions", "main", "mot_dp_group"])
        self.show_group_name.setCurrentIndex(0)
        settings_form.addWidget(self.show_group_name, 0, 1)
        settings_form.addWidget(BodyLabel(self.tr("Super Size"), settings_card), 0, 2)
        size_row = QHBoxLayout()
        size_row.setSpacing(6)
        self.super_size_edit = LineEdit(settings_card)
        self.super_size_edit.setText("9126805504")
        self.super_size_edit.setPlaceholderText(self.tr("Size in bytes"))
        self.super_size_edit.textChanged.connect(self.validate_digits)
        size_row.addWidget(self.super_size_edit, 1)
        self.size_refresh_button = ToolButton(FluentIcon.SYNC, settings_card)
        self.size_refresh_button.setToolTip(self.tr("Recalculate size for selected partitions"))
        self.size_refresh_button.setAccessibleName(self.tr("Recalculate super size"))
        self.size_refresh_button.clicked.connect(self.verify_size)
        size_row.addWidget(self.size_refresh_button)
        settings_form.addLayout(size_row, 0, 3)
        settings_layout.addLayout(settings_form)
        self.viewLayout.addWidget(settings_card)

        partitions_card, partitions_layout = self._create_section(self.tr("Partition(s)"))
        partition_toolbar = QHBoxLayout()
        self.partition_search = LineEdit(partitions_card)
        self.partition_search.setPlaceholderText(self.tr("Search partitions..."))
        self.partition_search.setClearButtonEnabled(True)
        self.partition_search.textChanged.connect(self.filter_partitions)
        partition_toolbar.addWidget(self.partition_search, 1)
        self.select_all_checkbox = CheckBox(self.tr("Select all"), partitions_card)
        self.select_all_checkbox.setTristate(True)
        self.select_all_checkbox.stateChanged.connect(self._on_select_all_changed)
        partition_toolbar.addWidget(self.select_all_checkbox)
        self.btn_refresh = ToolButton(FluentIcon.SYNC, partitions_card)
        self.btn_refresh.setToolTip(self.tr("Refresh partitions"))
        self.btn_refresh.setAccessibleName(self.tr("Refresh partitions"))
        self.btn_refresh.clicked.connect(self.refresh)
        partition_toolbar.addWidget(self.btn_refresh)
        partitions_layout.addLayout(partition_toolbar)
        self.tl = ListWidget(partitions_card)
        self.tl.setMinimumHeight(200)
        self.tl.setMaximumHeight(280)
        self.tl.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.tl.itemChanged.connect(self._on_partition_item_changed)
        partitions_layout.addWidget(self.tl)
        self.viewLayout.addWidget(partitions_card, 1)

        options_card, options_layout = self._create_section(self.tr("Options"))
        options_row = QHBoxLayout()
        options_row.setSpacing(20)
        self.switch_sparse = SwitchButton(options_card)
        self.switch_sparse.setOffText(self.tr("Enable Sparse"))
        self.switch_sparse.setOnText(self.tr("Enable Sparse"))
        self.switch_delete = SwitchButton(options_card)
        self.switch_delete.setOffText(self.tr("Remove source files"))
        self.switch_delete.setOnText(self.tr("Remove source files"))
        options_row.addWidget(self.switch_sparse)
        options_row.addWidget(self.switch_delete)
        options_row.addStretch(1)
        options_layout.addLayout(options_row)

        actions_row = QHBoxLayout()
        actions_row.addStretch(1)
        self.g_b = PushButton(self.tr("Generate LIST"), options_card)
        self.g_b.clicked.connect(self.generate)
        actions_row.addWidget(self.g_b)
        options_layout.addLayout(actions_row)
        self.viewLayout.addWidget(options_card)

        self.yesButton.setText(self.tr("Pack"))
        self.cancelButton.setText(self.tr("Cancel"))
        self.read_list()
        self.refresh()

    def _create_section(self, title):
        card = CardWidget(self)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)
        layout.addWidget(SubtitleLabel(title, card))
        return card, layout

    def _on_select_all_changed(self, state):
        state = Qt.CheckState(state)
        check_state = Qt.Unchecked if state == Qt.Unchecked else Qt.Checked
        self.tl.blockSignals(True)
        for index in range(self.tl.count()):
            self.tl.item(index).setCheckState(check_state)
        self.tl.blockSignals(False)
        self._sync_select_all_checkbox()
        self.verify_size()

    def _on_partition_item_changed(self, _item):
        self._sync_select_all_checkbox()
        self.verify_size()

    def _sync_select_all_checkbox(self):
        count = self.tl.count()
        checked = sum(
            self.tl.item(index).checkState() == Qt.Checked
            for index in range(count)
        )
        state = (
            Qt.Unchecked if not checked else
            Qt.Checked if checked == count else
            Qt.PartiallyChecked
        )
        self.select_all_checkbox.blockSignals(True)
        self.select_all_checkbox.setCheckState(state)
        self.select_all_checkbox.blockSignals(False)

    def filter_partitions(self, query):
        query = query.strip().casefold()
        for index in range(self.tl.count()):
            item = self.tl.item(index)
            item.setHidden(query not in item.text().casefold())



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
            self._sync_select_all_checkbox()
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
        self.filter_partitions(self.partition_search.text())
        self._sync_select_all_checkbox()
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