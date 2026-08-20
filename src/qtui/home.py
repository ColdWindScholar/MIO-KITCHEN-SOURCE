import datetime
import random

from PySide6.QtGui import Qt, QPixmap
from PySide6.QtWidgets import QVBoxLayout, QWidget, QHBoxLayout, QFrame, QLabel
from qfluentwidgets import setThemeColor

from src.qtui.widgets import ClickableLabel


class HomePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HomePage")
        setThemeColor('#0078D4')
        self.initUI()

    def initUI(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #121212;
                color: #FFFFFF;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }
            QFrame {
                background-color: #1A1A1A;
                border: 1px solid #2C2C2C;
                border-radius: 8px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(40, 40, 40, 40)


        left_layout = QVBoxLayout()
        left_layout.setSpacing(15)

        dialog_box = QFrame()
        #dialog_box.setFixedSize(QSize(280))

        dialog_inner = QVBoxLayout(dialog_box)
        dialog_inner.setContentsMargins(15, 12, 15, 12)
        lbl_user = QLabel("KeMiaoJiang:")
        lbl_user.setStyleSheet("color: #888888; font-size: 12px;")
        self.lbl_msg = QLabel("Hi! What can I do for you? ✨")
        self.lbl_msg.setStyleSheet("color: #DDA0DD; font-size: 13px; font-weight: bold;")
        self.lbl_msg.setWordWrap(True)
        dialog_inner.addWidget(lbl_user)
        dialog_inner.addWidget(self.lbl_msg)

        avatar_label = ClickableLabel()
        avatar_pixmap = QPixmap("bin/kemiaojiang.png")
        if not avatar_pixmap.isNull():
            avatar_label.setPixmap(avatar_pixmap.scaledToHeight(380, Qt.TransformationMode.SmoothTransformation))
        avatar_label.clicked.connect(self.react)
        left_layout.addWidget(dialog_box, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        left_layout.addWidget(avatar_label, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        left_layout.addStretch()
        layout.addLayout(left_layout)
        layout.addStretch(1)
        right_layout = QVBoxLayout()
        right_layout.setSpacing(25)

        info_sub_layout = QVBoxLayout()
        info_sub_layout.setSpacing(5)
        lbl_amb = QLabel("Ambassador: KeMiaoJiang")
        lbl_pnt = QLabel("Painter: HY-惠")
        lbl_wlc = QLabel("Welcome To MIO-KITCHEN")
        for lbl in [lbl_amb, lbl_pnt, lbl_wlc]:
            lbl.setStyleSheet("color: #4EA6DD; font-size: 14px; font-weight: 500;")
        lbl_wlc.setStyleSheet("color: #4EA6DD; font-size: 15px; font-weight: bold;")
        info_sub_layout.addWidget(lbl_amb)
        info_sub_layout.addWidget(lbl_pnt)
        info_sub_layout.addWidget(lbl_wlc)

        campaign_box = QFrame()
        campaign_box.setFixedHeight(160)
        campaign_box.setMinimumWidth(340)
        campaign_box.setMaximumWidth(550)

        campaign_inner = QVBoxLayout(campaign_box)
        campaign_inner.setContentsMargins(18, 18, 18, 18)
        campaign_inner.setSpacing(10)

        title_lbl = QLabel("Campaign & Community")
        title_lbl.setStyleSheet("color: #888888; font-size: 12px; font-weight: bold;")

        link1_lbl = QLabel(
            "<a href='https://keepandroidopen.org' style='color: #FF4D4D; text-decoration: underline;'>Your phone is about to stop being yours.</a>")
        link1_lbl.setOpenExternalLinks(True)

        link2_lbl = QLabel("<a href='https://keepandroidopen.org' style='color: #FF4D4D; text-decoration: underline;'>Keep Android Open</a>")
        link2_lbl.setOpenExternalLinks(True)

        campaign_inner.addWidget(title_lbl)
        campaign_inner.addWidget(link1_lbl)
        campaign_inner.addWidget(link2_lbl)
        campaign_inner.addStretch()

        right_layout.addLayout(info_sub_layout)
        right_layout.addWidget(campaign_box, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        right_layout.addStretch()
        layout.addLayout(right_layout)
        self.setLayout(layout)

    def react(self):
        current_time = datetime.datetime.now()
        last_click = getattr(self, "_last_react_time", None)

        if last_click and (current_time - last_click).total_seconds() < 0.6:
            return
        self._last_react_time = current_time
        self.react_click_count = getattr(self, "react_click_count", 0) + 1

        hour = current_time.hour
        time_greeting = "Good morning! ~_~" if 5 <= hour < 12 else "Good afternoon! O^O" if 12 <= hour < 18 else "Good evening! Zzz~~"

        greetings = [
            f"{time_greeting} Need me to unpack some partitions? :>",
            "Master, let's patch some fresh fs_config mappings! w^w",
            "MIO-KITCHEN is active! Let's build something awesome today! Pin~",
            "Your ROM kitchen helper KeMiaoJiang is ready for commands! OwO",
            "What can i do for ya~ :)",
            "QwQ, I don't recognise this format!",
            "Unpacking roms...",
            "My binaries are the latest (￣▽￣)~* "
        ]

        if self.react_click_count == 7:
            self.lbl_msg.setText(
                "Wahh! Poke limit exceeded! Stop it, it tickles too much~! ヽ(≧Д≦)ノ")
        elif self.react_click_count >= 15:
            self.lbl_msg.setText("System Overload! Going to sleep... 💤")
            self.react_click_count = 0
        else:
            self.lbl_msg.setText(random.choice(greetings))



