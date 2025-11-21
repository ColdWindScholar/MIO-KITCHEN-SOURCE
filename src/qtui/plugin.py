from PySide6.QtWidgets import QWidget, QVBoxLayout
from qfluentwidgets import TitleLabel, PushButton, FluentIcon as FIF

class PluginPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PluginPage")
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(40, 40, 40, 40)

        title = TitleLabel("插件管理", self)
        title.setStyleSheet("font-size: 24px; color: #FFFFFF;")
        layout.addWidget(title)

        install_btn = PushButton("安装插件", self, FIF.DOWNLOAD)
        install_btn.clicked.connect(self.install_plugin)
        layout.addWidget(install_btn)

        layout.addStretch()
        self.setLayout(layout)

    def install_plugin(self):
        print("没写")