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
        title = TitleLabel("关于 MIO-KITCHEN", self)
        layout.addWidget(title)

        # 基本信息
        info = BodyLabel(
            "版本: 1.0.0\n"
            "Developer: ColdWindScholar\n"
            "UI Designer: Kinaxie\n"
            "© 2025 ColdWindScholar All Rights Reserved.",
            self
        )
        layout.addWidget(info)
        layout.addStretch()
        self.setLayout(layout)