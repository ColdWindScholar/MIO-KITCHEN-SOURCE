# Copyright (C) 2022-2026 The MIO-KITCHEN-SOURCE Project
#
# Licensed under the GNU AFFERO GENERAL PUBLIC LICENSE, Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.gnu.org/licenses/agpl-3.0.en.html#license-text
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import json
import os.path
import platform
import random
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QVBoxLayout, QGridLayout, QHBoxLayout, QFrame
from qfluentwidgets import (
    TitleLabel, BodyLabel, CaptionLabel, HyperlinkLabel,
    CardWidget
)

from src.core.utils import JsonEdit, prog_path
from src.qtui.settings_cfg import cfg


class ClickableTitleLabel(TitleLabel):
    """Modern dark-mode TitleLabel with glow effect and color cycling."""
    COLORS = ["#38B6FF", "#FF5757", "#00FF66", "#FFBD59", "#8C52FF"]

    def __init__(self, text):
        super().__init__(text)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._original_text = text
        self.current_color = self.COLORS[0]
        self._click_count = 0
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._reset_click_count)
        self._boom_timer = QTimer(self)
        self._boom_timer.setSingleShot(True)
        self._boom_timer.timeout.connect(self._reset_title)
        self._boom_previous_color = self.current_color
        self._update_color()

    def _reset_click_count(self):
        self._click_count = 0

    def _reset_title(self):
        self.setText(self._original_text)
        self.current_color = self._boom_previous_color
        self._reset_click_count()
        self._update_color()

    def _update_color(self):
        """Update with modern glow effect using qfluentwidgets theming."""
        self.setStyleSheet(
            f"TitleLabel {{"
            f"  color: {self.current_color};"
            f"  font-size: 48px;"
            f"  font-weight: bold;"
            f"  letter-spacing: 3px;"
            f"}}"
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.current_color = random.choice(
                [c for c in self.COLORS if c != self.current_color]
            )
            self._update_color()
            self._click_count += 1
            if self._click_count == 5:
                self._click_count = 0
                self._click_timer.stop()
                self.setText("BOOM!")
                self._boom_previous_color = self.current_color
                self.current_color = "#FF5757"
                self._update_color()
                self._boom_timer.start(1400)
            else:
                self._click_timer.start(1500)
        super().mousePressEvent(event)


class AboutPage(QFrame):
    """Modern About page with left and right sections using qfluentwidgets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AboutPage")
        self._styled_widgets = []
        self.initUI()
        cfg.themeChanged.connect(self._restore_stylesheets)

    def _set_widget_style(self, widget, stylesheet):
        widget.setStyleSheet(stylesheet)
        self._styled_widgets.append((widget, stylesheet))

    def _restore_stylesheets(self, _theme):
        # Apply after qfluentwidgets has refreshed widget styles for the new theme.
        QTimer.singleShot(0, self._apply_stylesheets)

    def _apply_stylesheets(self):
        self.title._update_color()
        for widget, stylesheet in self._styled_widgets:
            widget.setStyleSheet(stylesheet)

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(48, 48, 48, 48)
        main_layout.setSpacing(32)

        # ================== HEADER ==================
        header_layout = QVBoxLayout()
        header_layout.setSpacing(8)
        header_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title = ClickableTitleLabel("MIO-KITCHEN")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.title)

        subtitle = BodyLabel(self.tr("- Focus on Android ROM modification -"))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(subtitle)

        main_layout.addLayout(header_layout)
        main_layout.addSpacing(20)

        # ================== CONTENT: LEFT & RIGHT ==================
        content_layout = QHBoxLayout()
        content_layout.setSpacing(40)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # LEFT SIDE - System Info
        left_card = CardWidget()
        left_card.setFixedWidth(320)

        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(32, 32, 32, 32)
        left_layout.setSpacing(20)

        sys_header = CaptionLabel(self.tr("System Info"))
        self._set_widget_style(sys_header, "color: #38B6FF; font-weight: 700; font-size: 14px;")
        left_layout.addWidget(sys_header)
        with open(f"{prog_path}/bin/settings.json", 'r') as f:
            ver = json.load(f)['Tool']['Version']
        sys_info_data = [
            (self.tr("Tool Version"), ver),
            (self.tr("Python Version"), f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"),
            (self.tr("Operating system"), platform.system()),
            (self.tr("Architecture"), platform.machine())
        ]

        sys_grid = QGridLayout()
        sys_grid.setHorizontalSpacing(20)
        sys_grid.setVerticalSpacing(14)
        sys_grid.setColumnStretch(0, 1)
        sys_grid.setColumnStretch(1, 1)

        for row, (label, value) in enumerate(sys_info_data):
            lbl = BodyLabel(label)
            self._set_widget_style(lbl, "color: #A0A0A0; font-size: 13px;")
            val_lbl = BodyLabel(value)
            self._set_widget_style(val_lbl, "color: #38B6FF; font-weight: 700; font-size: 12px;")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

            sys_grid.addWidget(lbl, row, 0)
            sys_grid.addWidget(val_lbl, row, 1)

        left_layout.addLayout(sys_grid)
        content_layout.addWidget(left_card)

        # RIGHT SIDE - Dependencies
        right_card = CardWidget()
        right_card.setFixedWidth(320)

        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(32, 32, 32, 32)
        right_layout.setSpacing(20)

        dep_header = CaptionLabel(self.tr("Dependencies"))
        self._set_widget_style(dep_header, "color: #38B6FF; font-weight: 700; font-size: 14px;")
        right_layout.addWidget(dep_header)

        dep_grid = QGridLayout()
        dep_grid.setHorizontalSpacing(20)
        dep_grid.setVerticalSpacing(12)
        dep_grid.setColumnStretch(0, 1)
        dep_grid.setColumnStretch(1, 1)
        dependencies_version = JsonEdit(os.path.join(prog_path, "bin", "update.json")).read()


        for row, (name, version) in enumerate(dependencies_version.items()):
            name_lbl = BodyLabel(name)
            self._set_widget_style(name_lbl, "color: #A0A0A0; font-size: 11px;")

            ver_lbl = BodyLabel(version)
            self._set_widget_style(ver_lbl, "color: #FF5757; font-weight: 700; font-size: 11px;")
            ver_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

            dep_grid.addWidget(name_lbl, row, 0)
            dep_grid.addWidget(ver_lbl, row, 1)

        right_layout.addLayout(dep_grid)
        content_layout.addWidget(right_card)

        main_layout.addLayout(content_layout)
        main_layout.addStretch()

        # ================== FOOTER ==================
        footer_layout = QVBoxLayout()
        footer_layout.setSpacing(10)
        footer_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        credit_lbl = BodyLabel(self.tr("Chinese-Simplified By ColdWindScholar"))
        credit_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        slogan_lbl = BodyLabel(self.tr("Open Source / Free / faster"))
        slogan_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_widget_style(slogan_lbl, "color: #38B6FF; font-weight: 700; font-size: 13px;")

        github_lbl = HyperlinkLabel()
        github_lbl.setText(self.tr("GitHub: MIO-KITCHEN-SOURCE"))
        github_lbl.setUrl("https://github.com/ColdWindScholar/MIO-KITCHEN-SOURCE")

        copyright_lbl = CaptionLabel(self.tr("© 2026 ColdWindScholar All Rights Reserved."))
        copyright_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        footer_layout.addWidget(credit_lbl)
        footer_layout.addWidget(slogan_lbl)
        footer_layout.addWidget(github_lbl)
        footer_layout.addWidget(copyright_lbl)

        main_layout.addLayout(footer_layout)