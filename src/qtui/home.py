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
import datetime
import json
import logging
import os
import random
import shutil

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import setThemeColor

from src.core.utils import prog_path
from src.qtui.settings_cfg import cfg
from src.qtui.widgets import ClickableLabel


class _SummaryWorker(QThread):
    completed = Signal(object)

    def __init__(self, project_name, project_path, working_folder):
        super().__init__()
        self.project_name = project_name
        self.project_path = project_path
        self.working_folder = working_folder

    def run(self):
        result = {
            "project_name": self.project_name,
            "working_folder": self.working_folder,
            "project_size": None,
            "item_count": 0,
            "created_time": None,
            "free_space": None,
            "project_count": 0,
            "partition_count": 0,
            "partition_names": [],
            "android_info": {},
        }
        try:
            if os.path.isdir(self.working_folder):
                result["project_count"] = sum(
                    1 for entry in os.scandir(self.working_folder)
                    if entry.is_dir(follow_symlinks=False)
                    and not entry.name.startswith(".")
                    and entry.name not in {"bin", "src", "readmes"}
                )
                result["free_space"] = shutil.disk_usage(self.working_folder).free
        except OSError:
            logging.exception("Unable to read the project workspace summary")

        try:
            if self.project_name and os.path.isdir(self.project_path):
                info = os.stat(self.project_path)
                result["created_time"] = getattr(info, "st_birthtime", info.st_ctime)
                parts_info_path = os.path.join(self.project_path, "config", "parts_info")
                if os.path.isfile(parts_info_path):
                    try:
                        with open(parts_info_path, encoding="utf-8") as parts_file:
                            parts_info = json.load(parts_file)
                        if isinstance(parts_info, dict):
                            result["partition_names"] = list(parts_info)
                            result["partition_count"] = len(parts_info)
                    except (OSError, ValueError):
                        logging.exception("Unable to read project partition summary: %s", parts_info_path)
                size = 0
                item_count = 0
                build_prop_paths = []
                for root, directories, files in os.walk(self.project_path, onerror=self._log_walk_error):
                    if self.isInterruptionRequested():
                        return
                    directories[:] = [name for name in directories if not os.path.islink(os.path.join(root, name))]
                    if "build.prop" in files:
                        build_prop_paths.append(os.path.join(root, "build.prop"))
                    for filename in files:
                        file_path = os.path.join(root, filename)
                        try:
                            if not os.path.islink(file_path):
                                size += os.path.getsize(file_path)
                                item_count += 1
                        except OSError:
                            logging.exception("Unable to read project file metadata: %s", file_path)
                result["project_size"] = size
                result["item_count"] = item_count
                if build_prop_paths:
                    build_prop_paths.sort(key=lambda path: self._build_prop_priority(path))
                    result["android_info"] = self._read_android_info(build_prop_paths[0])
        except OSError:
            logging.exception("Unable to read the current project summary: %s", self.project_path)

        if not self.isInterruptionRequested():
            self.completed.emit(result)

    @staticmethod
    def _log_walk_error(error):
        logging.error("Unable to scan project directory: %s", error)

    @staticmethod
    def _build_prop_priority(path):
        path = path.replace("\\", "/").lower()
        priorities = (
            "/system/system/build.prop",
            "/system/build.prop",
            "/vendor/build.prop",
            "/product/build.prop",
            "/system/vendor/build.prop",
            "/build.prop",
        )
        for index, suffix in enumerate(priorities):
            if path.endswith(suffix):
                return index
        return len(priorities)

    @staticmethod
    def _read_android_info(path):
        properties = {}
        try:
            with open(path, encoding="utf-8", errors="replace") as build_prop:
                for line in build_prop:
                    line = line.strip()
                    if not line or line.startswith(("#", ";")):
                        continue
                    key, separator, value = line.partition("=")
                    if separator:
                        properties[key.strip()] = value.strip()
        except OSError:
            logging.exception("Unable to read Android build properties: %s", path)
            return {}

        def first_value(*keys):
            return next((properties[key] for key in keys if properties.get(key)), "—")

        return {
            "model": first_value("ro.product.model", "ro.product.system.model", "ro.product.vendor.model"),
            "manufacturer": first_value(
                "ro.product.manufacturer", "ro.product.system.manufacturer", "ro.product.vendor.manufacturer"
            ),
            "codename": first_value("ro.product.device", "ro.product.system.device", "ro.product.vendor.device"),
            "board": first_value(
                "ro.soc.model", "ro.board.platform", "ro.product.board", "ro.hardware"
            ),
            "android": first_value("ro.build.version.release", "ro.system.build.version.release"),
            "api": first_value("ro.build.version.sdk", "ro.system.build.version.sdk"),
            "security_patch": first_value(
                "ro.build.version.security_patch", "ro.system.build.version.security_patch"
            ),
            "build": first_value(
                "ro.build.display.id", "ro.build.id", "ro.build.version.incremental"
            ),
        }


class HomePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HomePage")
        setThemeColor("#0078D4")
        self._summary_threads = set()
        self._init_ui()
        cfg.currentProjectName.valueChanged.connect(self.refresh_summary)
        cfg.workingFolder.valueChanged.connect(self.refresh_summary)
        self.refresh_summary()

    def _init_ui(self):
        self.setStyleSheet("""
            #HomePage {
                background-color: #171A24;
                color: #F1F4F8;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }
            #HomePage QFrame#Card {
                background-color: #222731;
                border: 1px solid #292F3B;
                border-radius: 14px;
            }
            #HomePage QLabel {
                border: none;
                background: transparent;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(22, 16, 22, 16)
        main_layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)
        folder_icon = QLabel("▰")
        folder_icon.setStyleSheet("color: #7799E8; font-size: 19px;")
        title = QLabel(self.tr("Workspace"))
        title.setStyleSheet("color: #F1F4F8; font-size: 18px; font-weight: 700;")
        subtitle = QLabel(self.tr("summary"))
        subtitle.setStyleSheet("color: #93A0B1; font-size: 15px;")
        header.addWidget(folder_icon)
        header.addWidget(title)
        header.addWidget(subtitle)
        header.addStretch()
        main_layout.addLayout(header)

        content = QHBoxLayout()
        content.setSpacing(16)
        companion = QVBoxLayout()
        companion.setSpacing(14)
        companion.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        companion.setContentsMargins(0, 20, 0, 0)
        self.lbl_msg = QLabel(self.tr("Hi! What can I do for you? ✨"))
        self.lbl_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_msg.setWordWrap(True)
        self.lbl_msg.setStyleSheet("""
            color: #DCC2F2;
            background-color: #222731;
            border: 1px solid #343B48;
            border-radius: 12px;
            padding: 12px;
            font-size: 13px;
        """)
        companion.addWidget(self.lbl_msg)
        avatar = ClickableLabel()
        avatar_pixmap = QPixmap(os.path.join(prog_path, "bin", "kemiaojiang.png"))
        if not avatar_pixmap.isNull():
            avatar.setPixmap(avatar_pixmap.scaled(
                274, 274, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        avatar.setFixedSize(282, 282)
        avatar.setToolTip(self.tr("Click KeMiaoJiang to chat"))
        avatar.clicked.connect(self.react)
        companion.addWidget(avatar, 0, Qt.AlignmentFlag.AlignHCenter)
        companion_name = QLabel("KeMiaoJiang")
        companion_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        companion_name.setStyleSheet("color: #77C7F4; font-size: 18px; font-weight: 700;")
        companion.addWidget(companion_name)
        companion.addStretch()
        content.addLayout(companion, 0)

        dashboard = QVBoxLayout()
        dashboard.setSpacing(10)
        content.addLayout(dashboard, 1)
        main_layout.addLayout(content, 1)

        stats = QGridLayout()
        stats.setHorizontalSpacing(12)
        self.summary_values = {}
        for index, (key, label, icon, accent) in enumerate((
            ("project_count", self.tr("Projects"), "▰", "#F1F4F8"),
            ("project_size", self.tr("Project size"), "▱", "#F1F4F8"),
            ("free_space", self.tr("Disk space left"), "◉", "#77D6A8"),
        )):
            card = QFrame()
            card.setObjectName("Card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(17, 13, 17, 13)
            card_layout.setSpacing(7)
            label_row = QHBoxLayout()
            label_row.setSpacing(9)
            icon_widget = QLabel(icon)
            icon_widget.setStyleSheet(f"color: {accent}; font-size: 17px;")
            label_widget = QLabel(label)
            label_widget.setStyleSheet("color: #98A7B8; font-size: 14px;")
            label_row.addWidget(icon_widget)
            label_row.addWidget(label_widget)
            label_row.addStretch()
            value_widget = QLabel("—")
            value_widget.setStyleSheet(f"color: {accent}; font-size: 21px; font-weight: 700;")
            value_widget.setWordWrap(True)
            card_layout.addLayout(label_row)
            card_layout.addWidget(value_widget)
            stats.addWidget(card, 0, index)
            self.summary_values[key] = value_widget
        for column in range(3):
            stats.setColumnStretch(column, 1)
        dashboard.addLayout(stats)

        self.details_card = self._create_info_card(self.tr("Project"))
        self.details_grid = QGridLayout()
        self.details_grid.setHorizontalSpacing(22)
        self.details_grid.setVerticalSpacing(10)
        self.details_grid.setColumnStretch(1, 1)
        self.details_grid.setColumnStretch(3, 1)
        self.details_card.layout().addLayout(self.details_grid)
        dashboard.addWidget(self.details_card)

        self.partitions_card = self._create_info_card(self.tr("Partitions"))
        self.partition_count_label = QLabel("—")
        self.partition_count_label.setStyleSheet("color: #F1F4F8; font-size: 17px; font-weight: 700;")
        self.partitions_card.layout().addWidget(self.partition_count_label)
        self.partition_names_label = QLabel("—")
        self.partition_names_label.setWordWrap(True)
        self.partition_names_label.setStyleSheet("color: #E7EBF1; font-size: 13px;")
        self.partitions_card.layout().addWidget(self.partition_names_label)
        dashboard.addWidget(self.partitions_card)

        self.device_card = self._create_info_card(self.tr("Android device"))
        self.device_grid = QGridLayout()
        self.device_grid.setHorizontalSpacing(22)
        self.device_grid.setVerticalSpacing(10)
        self.device_grid.setColumnStretch(1, 1)
        self.device_grid.setColumnStretch(3, 1)
        self.device_card.layout().addLayout(self.device_grid)
        dashboard.addWidget(self.device_card)

        self.project_path_label = QLabel()
        self.project_path_label.setStyleSheet("color: #778495; font-size: 11px;")
        dashboard.addWidget(self.project_path_label)

    def _create_info_card(self, title):
        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 14)
        card_layout.setSpacing(10)
        header = QHBoxLayout()
        heading = QLabel(f"▰  {title}")
        heading.setStyleSheet("color: #91AFC2; font-size: 14px; font-weight: 600;")
        header.addWidget(heading)
        header.addStretch()
        card_layout.addLayout(header)
        return card

    def refresh_summary(self, *_args):
        project_name = cfg.currentProjectName.value
        working_folder = cfg.workingFolder.value
        project_path = os.path.join(working_folder, project_name) if project_name else ""
        self.project_path_label.setText(working_folder)
        for key in ("project_size", "free_space", "project_count"):
            self.summary_values[key].setText(self.tr("Loading..."))
        self._set_detail_rows([
            (self.tr("Name"), project_name or self.tr("No project selected")),
            (self.tr("Created time"), self.tr("Loading...")),
            (self.tr("Files"), self.tr("Loading...")),
            (self.tr("Path"), project_path or "—"),
        ])
        self.partition_count_label.setText(self.tr("Loading..."))
        self.partition_names_label.setText(self.tr("Loading..."))
        self._set_device_rows({})

        for thread in tuple(self._summary_threads):
            if thread.isRunning():
                thread.requestInterruption()

        worker = _SummaryWorker(project_name, project_path, working_folder)
        worker.setParent(self)
        self._summary_threads.add(worker)
        worker.completed.connect(self._apply_summary)
        worker.finished.connect(lambda thread=worker: self._discard_summary_thread(thread))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _discard_summary_thread(self, thread):
        self._summary_threads.discard(thread)

    def _apply_summary(self, result):
        if (
            result["project_name"] != cfg.currentProjectName.value
            or result["working_folder"] != cfg.workingFolder.value
        ):
            return
        self.summary_values["project_count"].setText(str(result["project_count"]))
        self.summary_values["project_size"].setText(
            self._format_size(result["project_size"]) if result["project_size"] is not None
            else self.tr("No project")
        )
        created_time = (
            datetime.datetime.fromtimestamp(result["created_time"]).strftime("%Y-%m-%d %H:%M")
            if result["created_time"] is not None else "—"
        )
        self.summary_values["free_space"].setText(
            self._format_size(result["free_space"]) if result["free_space"] is not None else self.tr("Unavailable")
        )
        self._set_detail_rows([
            (self.tr("Name"), result["project_name"] or self.tr("No project selected")),
            (self.tr("Created time"), created_time),
            (self.tr("Files"), str(result["item_count"]) if result["project_size"] is not None else "—"),
            (self.tr("Path"), os.path.join(result["working_folder"], result["project_name"])
             if result["project_name"] else "—"),
        ])
        if result["partition_names"]:
            self.partition_count_label.setText(str(result["partition_count"]))
            self.partition_names_label.setText("  ·  ".join(result["partition_names"]))
        else:
            self.partition_count_label.setText("0")
            self.partition_names_label.setText(self.tr("No partition metadata available"))
        self._set_device_rows(result["android_info"])

    def _set_detail_rows(self, rows):
        while self.details_grid.count():
            item = self.details_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for index, (label, value) in enumerate(rows):
            row, pair = divmod(index, 2)
            label_widget = QLabel(label)
            label_widget.setStyleSheet("color: #91A6B5; font-size: 13px;")
            value_widget = QLabel(value)
            value_widget.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value_widget.setStyleSheet("color: #F1F4F8; font-size: 13px; font-weight: 600;")
            value_widget.setWordWrap(True)
            self.details_grid.addWidget(label_widget, row, pair * 2)
            self.details_grid.addWidget(value_widget, row, pair * 2 + 1)

    def _set_device_rows(self, android_info):
        labels = (
            ("model", self.tr("Model")),
            ("manufacturer", self.tr("Manufacturer")),
            ("codename", self.tr("Codename")),
            ("board", self.tr("SoC / Board")),
            ("android", self.tr("Android")),
            ("api", self.tr("API")),
            ("security_patch", self.tr("Security patch")),
            ("build", self.tr("Build")),
        )
        self._set_grid_rows(
            self.device_grid,
            [(label, android_info.get(key, "—")) for key, label in labels]
            if android_info else [(self.tr("Build.prop"), self.tr("No build.prop found"))],
        )

    @staticmethod
    def _set_grid_rows(grid, rows):
        while grid.count():
            item = grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for index, (label, value) in enumerate(rows):
            row, pair = divmod(index, 2)
            label_widget = QLabel(label)
            label_widget.setStyleSheet("color: #91A6B5; font-size: 13px;")
            value_widget = QLabel(value)
            value_widget.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value_widget.setStyleSheet("color: #F1F4F8; font-size: 13px; font-weight: 600;")
            value_widget.setWordWrap(True)
            grid.addWidget(label_widget, row, pair * 2)
            grid.addWidget(value_widget, row, pair * 2 + 1)

    @staticmethod
    def _format_size(size):
        size = float(size)
        for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
            if size < 1024 or unit == "PB":
                return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
            size /= 1024

    def react(self):
        current_time = datetime.datetime.now()
        last_click = getattr(self, "_last_react_time", None)

        if last_click and (current_time - last_click).total_seconds() < 0.6:
            return
        self._last_react_time = current_time
        self.react_click_count = getattr(self, "react_click_count", 0) + 1

        hour = current_time.hour
        time_greeting = (
            self.tr("Good morning! ~_~") if 5 <= hour < 12
            else self.tr("Good afternoon! O^O") if 12 <= hour < 18
            else self.tr("Good evening! Zzz~~")
        )

        greetings = [
            self.tr("{} Need me to unpack some partitions? :>").format(time_greeting),
            self.tr("Master, let's patch some fresh fs_config mappings! w^w"),
            self.tr("MIO-KITCHEN is active! Let's build something awesome today! Pin~"),
            self.tr("Your ROM kitchen helper KeMiaoJiang is ready for commands! OwO"),
            self.tr("What can i do for ya~ :)"),
            self.tr("QwQ, I don't recognise this format!"),
            self.tr("Unpacking roms..."),
            self.tr("My binaries are the latest (￣▽￣)~* ")
        ]

        if self.react_click_count >= 15:
            self.lbl_msg.setText(self.tr("System Overload! Going to sleep... 💤"))
            self.react_click_count = 0
        elif self.react_click_count >= 7:
            self.lbl_msg.setText(
                self.tr("Wahh! Poke limit exceeded! Stop it, it tickles too much~! ヽ(≧Д≦)ノ"))
        else:
            self.lbl_msg.setText(random.choice(greetings))
