import random
from PySide6.QtWidgets import QVBoxLayout, QWidget, QGridLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from qfluentwidgets import TitleLabel, BodyLabel, CardWidget, HyperlinkLabel


class ClickableTitleLabel(TitleLabel):
    """Custom TitleLabel that efficiently cycles text colors on click."""
    COLORS = ["#38B6FF", "#FF5757", "#00FF66", "#FFBD59", "#8C52FF"]

    def __init__(self, text):
        super().__init__(text)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.current_color = self.COLORS[0]
        self._update_color()

    def _update_color(self):
        self.setStyleSheet(f"color: {self.current_color}; font-weight: bold;")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Prevent choosing the same color twice in a row
            self.current_color = random.choice([c for c in self.COLORS if c != self.current_color])
            self._update_color()
        super().mousePressEvent(event)


class AboutPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AboutPage")
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(15)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # ----------------- HEADER AREA -----------------
        self.title = ClickableTitleLabel("MIO-KITCHE")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title)

        subtitle = BodyLabel("- 专注于安卓ROM修改 -")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #8A8A8F;")
        layout.addWidget(subtitle)

        # ----------------- CENTRAL CONTENT PANEL -----------------
        content_card = CardWidget(parent=self)
        content_card.setFixedWidth(420)

        card_layout = QVBoxLayout(content_card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(16)

        sys_info_text = (
            "工具版本: 4.2.1",
            "Python库版本: 3.14.6\n",
            "操作系统: Linux\n",
            "指令集: x86_64"
        )
        for sit in sys_info_text:
            sys_info = BodyLabel(sit, parent=content_card)
            sys_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(sys_info)

        # Grid Generation
        dep_grid = QGridLayout()
        dep_grid.setHorizontalSpacing(40)
        dep_grid.setVerticalSpacing(8)

        dependencies = [
            ("erofs_utils:", "v1.9.3-26080800"),
            ("apftool:", "v1.2.3"),
            ("apftool-loongarch:", "1.1.0"),
            ("ImgKit:", "v1.2.5"),
            ("android-tools:", "37.0.0")
        ]

        for row, (name, version) in enumerate(dependencies):
            name_lbl = BodyLabel(name, parent=content_card)
            name_lbl.setStyleSheet("color: #0A84FF; font-weight: 500;")

            ver_lbl = BodyLabel(version, parent=content_card)
            ver_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            dep_grid.addWidget(name_lbl, row, 0)
            dep_grid.addWidget(ver_lbl, row, 1)

        card_layout.addLayout(dep_grid)
        layout.addWidget(content_card)
        layout.addStretch()

        # ----------------- FOOTER AREA -----------------
        footer_layout = QVBoxLayout()
        footer_layout.setSpacing(6)

        credit_lbl = BodyLabel("Chinese-Simplified By 寒风居士", parent=self)
        slogan_lbl = BodyLabel("开源, 自由, 极速", parent=self)
        slogan_lbl.setStyleSheet("color: #AEAEB2; font-weight: 500;")

        github_lbl = HyperlinkLabel(parent=self)
        github_lbl.setText("GitHub: MIO-KITCHEN-SOURCE")
        github_lbl.setUrl("https://github.com")

        copyright_lbl = BodyLabel("© 2026 寒风居士版权所有.", parent=self)
        copyright_lbl.setStyleSheet("color: #636366; font-size: 11px;")

        # Set alignments only on actual BodyLabels
        for lbl in (credit_lbl, slogan_lbl, copyright_lbl):
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Add items to layout with layout-level centering alignment
        footer_layout.addWidget(credit_lbl, alignment=Qt.AlignmentFlag.AlignCenter)
        footer_layout.addWidget(slogan_lbl, alignment=Qt.AlignmentFlag.AlignCenter)
        footer_layout.addWidget(github_lbl, alignment=Qt.AlignmentFlag.AlignCenter)  # <-- Handled cleanly here
        footer_layout.addWidget(copyright_lbl, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addLayout(footer_layout)

