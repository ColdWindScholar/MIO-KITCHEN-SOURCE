import os
from multiprocessing.dummy import DummyProcess
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QGridLayout, QHBoxLayout, QVBoxLayout, QFileDialog, QScrollArea
from qfluentwidgets import (
    MessageBoxBase,
    SubtitleLabel,
    BodyLabel,
    LineEdit,
    PushButton,
    ComboBox,
    CheckBox,
    RadioButton
)

from .configs import support_chipset, support_chipset_portstep, prog_path
from .utils import portutils


class FileChooser(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(self.tr("Please choose boot, system from device and the port rom"), self)
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addSpacing(10)

        self.portzip_edit = LineEdit(self)
        self.portzip_edit.setPlaceholderText(self.tr("Select Port Rom..."))
        self.portzip_btn = PushButton(self.tr("Choose..."), self)

        self.baseboot_edit = LineEdit(self)
        self.baseboot_edit.setPlaceholderText(self.tr("Select Boot from device..."))
        self.baseboot_btn = PushButton("Choose...", self)

        self.basesys_edit = LineEdit(self)
        self.basesys_edit.setPlaceholderText(self.tr("Select System from device..."))
        self.basesys_btn = PushButton(self.tr("Choose..."), self)

        basesys = Path("base/system.img")
        baseboot = Path("base/boot.img")
        if basesys.exists():
            self.basesys_edit.setText(str(basesys.absolute()))
        if baseboot.exists():
            self.baseboot_edit.setText(str(baseboot.absolute()))

        self.portzip_btn.clicked.connect(
            lambda: self.__choose_file(self.portzip_edit, "Zip Rom (*.zip);;All Files (*)"))
        self.baseboot_btn.clicked.connect(
            lambda: self.__choose_file(self.baseboot_edit, "Boot Image (*.img);;All Files (*)"))
        self.basesys_btn.clicked.connect(
            lambda: self.__choose_file(self.basesys_edit, "System Image (*.img);;All Files (*)"))

        grid = QGridLayout()
        grid.setSpacing(10)
        grid.addWidget(BodyLabel(self.tr("Port Rom:"), self), 0, 0, Qt.AlignLeft | Qt.AlignVCenter)
        grid.addWidget(self.portzip_edit, 0, 1)
        grid.addWidget(self.portzip_btn, 0, 2)

        grid.addWidget(BodyLabel(self.tr("Boot from device:"), self), 1, 0, Qt.AlignLeft | Qt.AlignVCenter)
        grid.addWidget(self.baseboot_edit, 1, 1)
        grid.addWidget(self.baseboot_btn, 1, 2)

        grid.addWidget(BodyLabel(self.tr("System from device:"), self), 2, 0, Qt.AlignLeft | Qt.AlignVCenter)
        grid.addWidget(self.basesys_edit, 2, 1)
        grid.addWidget(self.basesys_btn, 2, 2)
        self.viewLayout.addLayout(grid)

        self.yesButton.setText(self.tr("OK"))
        self.cancelButton.setText(self.tr("Cancel"))
        self.widget.setMinimumWidth(500)

    def __choose_file(self, edit: LineEdit, file_filter: str):
        file_path, _ = QFileDialog.getOpenFileName(self, "Choose File", prog_path, file_filter)
        if file_path:
            edit.setText(file_path)

    def get(self) -> list:
        if self.exec_():
            return [
                self.baseboot_edit.text(),
                self.basesys_edit.text(),
                self.portzip_edit.text()
            ]
        return ["", "", ""]


class MyUI(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.item = []
        self.item_box = []

        self.titleLabel = SubtitleLabel(self.tr("MTK LowLevel Machines Port Tool"), self)
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addSpacing(5)

        soc_layout = QHBoxLayout()
        soc_layout.addWidget(BodyLabel(self.tr("SOC Type:"), self), 0, Qt.AlignLeft | Qt.AlignVCenter)
        self.chipset_combo = ComboBox(self)
        self.chipset_combo.addItems(support_chipset)

        default_index = support_chipset.index('mt65') if 'mt65' in support_chipset else 0
        self.chipset_combo.setCurrentIndex(default_index)
        self.chipset_combo.currentTextChanged.connect(self.__load_port_item)
        soc_layout.addWidget(self.chipset_combo, 1)
        self.viewLayout.addLayout(soc_layout)
        self.viewLayout.addSpacing(10)

        self.viewLayout.addWidget(BodyLabel(self.tr("Supported port item"), self))

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumHeight(160)
        self.scroll_area.setMaximumHeight(200)
        self.scroll_area.setStyleSheet(
            "QScrollArea { border: 1px solid #3c3c3c; border-radius: 4px; background: transparent; }")

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(10, 10, 10, 10)
        self.scroll_layout.setSpacing(8)
        self.scroll_layout.addStretch(1)
        self.scroll_area.setWidget(self.scroll_content)
        self.viewLayout.addWidget(self.scroll_area)
        self.viewLayout.addSpacing(10)

        pack_layout = QHBoxLayout()
        self.radio_zip = RadioButton(self.tr("Output to a zip rom"), self)
        self.radio_img = RadioButton(self.tr("Output to a image"), self)
        self.radio_zip.setChecked(True)
        pack_layout.addWidget(self.radio_zip)
        pack_layout.addWidget(self.radio_img)
        self.viewLayout.addLayout(pack_layout)
        self.viewLayout.addSpacing(5)

        self.magisk_check = CheckBox(self.tr("Patch magisk"), self)
        self.viewLayout.addWidget(self.magisk_check)

        self.magisk_sub_container = QWidget(self)
        sub_layout = QVBoxLayout(self.magisk_sub_container)
        sub_layout.setContentsMargins(15, 5, 0, 5)
        sub_layout.setSpacing(3)

        sub_layout.addWidget(BodyLabel(self.tr("Target Arch:"), self))
        self.magisk_arch_combo = ComboBox(self)
        self.magisk_arch_combo.addItems(["arm64-v8a", "armeabi-v7a", "x86", "x86_64"])
        self.magisk_arch_combo.setCurrentText("arm64-v8a")
        sub_layout.addWidget(self.magisk_arch_combo)

        sub_layout.addWidget(BodyLabel("Magisk APK:", self))
        apk_row = QHBoxLayout()
        self.magisk_apk_edit = LineEdit(self)
        self.magisk_apk_edit.setText("magisk.apk")

        self.magisk_apk_edit.mousePressEvent = lambda event: self.__browse_magisk_apk()
        self.magisk_browse_btn = PushButton(self.tr("Browse..."), self)
        self.magisk_browse_btn.clicked.connect(self.__browse_magisk_apk)
        apk_row.addWidget(self.magisk_apk_edit, 1)
        apk_row.addWidget(self.magisk_browse_btn, 0)
        sub_layout.addLayout(apk_row)

        self.viewLayout.addWidget(self.magisk_sub_container)

        self.magisk_sub_container.setVisible(False)
        self.magisk_check.stateChanged.connect(lambda state: self.magisk_sub_container.setVisible(state == Qt.Checked.value))
        self.viewLayout.addSpacing(5)

        self.yesButton.setText(self.tr("Port"))
        self.cancelButton.setText(self.tr("Cancel"))
        self.widget.setMinimumWidth(460)

        self.yesButton.clicked.disconnect()
        self.yesButton.clicked.connect(self.__start_port)

        self.__load_port_item(self.chipset_combo.currentText())

    def __browse_magisk_apk(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Magisk APK", prog_path,
                                                   "Android Package (*.apk);;All Files (*)")
        if file_path:
            self.magisk_apk_edit.setText(file_path)

    def __load_port_item(self, select):
        print(f"Port method:{select}...")

        for cb_widget in self.item_box:
            self.scroll_layout.removeWidget(cb_widget)
            cb_widget.deleteLater()
        self.item.clear()
        self.item_box.clear()

        item_dict = support_chipset_portstep.get(select, {}).get('flags', {})

        for index, (current_flag, default_bool) in enumerate(item_dict.items()):
            cb = CheckBox(current_flag, self.scroll_content)
            cb.setChecked(default_bool)
            self.scroll_layout.insertWidget(index, cb)

            self.item.append([current_flag, cb])
            self.item_box.append(cb)

    def __start_port(self):
        if not self.item:
            print("Error: 移植条目为0，请先加载移植条目！")
            return

        boot, system, portzip = FileChooser(self).get()
        files = [boot, system, portzip]

        for i in files:
            if not i or not os.path.exists(i):
                print(f"File {i} Not chosen or not exists")
                return

        print(f"Boot from baserom：{boot}\n"
              f"System from baserom：{system}\n"
              f"Port Rom：{portzip}")

        newdict = support_chipset_portstep[self.chipset_combo.currentText()]
        for key, cb_widget in self.item:
            newdict[key] = cb_widget.isChecked()

        newdict['patch_magisk'] = self.magisk_check.isChecked()
        newdict['magisk_apk'] = self.magisk_apk_edit.text()
        newdict['target_arch'] = self.magisk_arch_combo.currentText()

        is_img_mode = self.radio_img.isChecked()
        p = portutils(newdict, *files, is_img_mode).start
        DummyProcess(target=p).start()

        self.accept()
