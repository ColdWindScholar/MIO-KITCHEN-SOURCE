from PySide6.QtGui import QColor
from PySide6.QtWidgets import QVBoxLayout, QWidget, QGraphicsDropShadowEffect
from qfluentwidgets import TitleLabel, StrongBodyLabel, CardWidget, setThemeColor


class HomePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HomePage")
        setThemeColor('#0078D4')
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        layout.setSpacing(25)
        layout.setContentsMargins(40, 40, 40, 40)

        title_label = TitleLabel("SY ROM Tools", self)
        title_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(title_label)

        description_label = StrongBodyLabel(
            "一款ROM制作的工具，支持项目管理、插件扩展和个性化设置。",
            self
        )
        description_label.setStyleSheet("color: #B0B0B0; font-size: 14px;")
        description_label.setWordWrap(True)
        layout.addWidget(description_label)

        self.add_feature_card(layout)
        layout.addStretch()
        self.setLayout(layout)
        self.setStyleSheet("background-color: transparent;")

    def add_feature_card(self, layout):
        card = CardWidget(self)
        card.setMinimumHeight(180)
        card.setStyleSheet("CardWidget { border-radius: 8px; border: 1px solid #3A3A3A; }")
        
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(15)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 100))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(10)
        card_layout.setContentsMargins(20, 20, 20, 20)

        card_title = TitleLabel("功能概览", card)
        card_title.setStyleSheet("font-size: 20px; color: #FFFFFF;")
        card_layout.addWidget(card_title)

        features = [
            "• 项目管理：创建和管理ROM项目",
            "• 插件支持：扩展工具功能(暂未实现)",
            "• 自定义设置：个性化工具",
        ]
        for feature in features:
            feature_label = StrongBodyLabel(feature, card)
            feature_label.setStyleSheet("color: #B0B0B0; font-size: 14px;")
            card_layout.addWidget(feature_label)

        layout.addWidget(card)
