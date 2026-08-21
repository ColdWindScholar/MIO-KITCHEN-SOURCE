import tkinter as tk

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout
from qfluentwidgets import InfoBar, InfoBarPosition, SubtitleLabel, LineEdit, MessageBoxBase, CaptionLabel


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

class InputDialog(MessageBoxBase):
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

#         if dialog.exec():
#             project_name = dialog.nameLineEdit.text().strip()
#             self.create_project(project_name)