from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import TitleLabel, BodyLabel


class AboutPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AboutPage")
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        # 标题
        title = TitleLabel("关于 SY ROM Tools", self)
        layout.addWidget(title)

        # 基本信息
        info = BodyLabel(
            "版本: 1.0.0\n"
            "开发者: Kinaxie\n"
            "描述: 一款个人开发的ROM工具\n"
            "© 2025 Kinaxie 版权所有",
            self
        )
        layout.addWidget(info)
        layout.addStretch()
        self.setLayout(layout)