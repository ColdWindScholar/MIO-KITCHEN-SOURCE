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
from PySide6.QtCore import Slot
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import PushButton, TextEdit

class LogMessageBoxBase(QWidget):

    def __init__(self,  parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.text_edit = TextEdit(self)
        self.text_edit.setReadOnly(True)
        self.layout.addWidget(self.text_edit)
        self.button_layout = QHBoxLayout()
        self.clear_btn = PushButton(self.tr("Clear"), self)

        self.button_layout.addStretch()
        self.button_layout.addWidget(self.clear_btn)
        self.layout.addLayout(self.button_layout)
        self.clear_btn.clicked.connect(self.text_edit.clear)

        # 预设不同日志级别的颜色格式
        self._formats = {
            "INFO": self._create_format(QColor("#2ECC71")),  # 绿色
            "WARN": self._create_format(QColor("#F1C40F")),  # 黄色
            "ERROR": self._create_format(QColor("#E74C3C")),  # 红色
            "DEBUG": self._create_format(QColor("#95A5A6")),  # 灰色
        }
        # ANSI COLOR MAP
        self.ansi_color_map = {
            "31": QColor("#CD3131"),  # 红色
            "91": QColor("#F44747"),  # 高亮红
            "32": QColor("#0DBC79"),  # 绿色
            "92": QColor("#23D18B"),  # 高亮绿
            "33": QColor("#E5C07B"),  # 黄色
            "93": QColor("#F5F543"),  # 高亮黄
            "34": QColor("#2472C8"),  # 蓝色
            "94": QColor("#3B8EEA"),  # 高亮蓝
            "36": QColor("#11A8CD"),  # 青色
            "96": QColor("#29B8DB"),  # 高亮青
            "0": None
        }

    def _create_format(self, color: QColor) -> QTextCharFormat:
        """创建特定颜色的文本格式"""
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        return fmt

    @Slot(str, str)
    def append_log(self, level: str, message: str):
        """
        核心方法：追加一条带颜色的日志
        使用 @Slot 装饰器，确保它可以安全地接收来自外部（甚至子线程）的信号
        """
        #  b'\x1b[1;91mExtract: \x1b[0mfailed to initialize ErofsNode!'
        is_ansi_color = message.startswith("\x1b")
        self.text_edit.moveCursor(QTextCursor.MoveOperation.End)

        if not is_ansi_color:
            fmt = self._formats.get(level.upper(), self._formats["INFO"])
            self.text_edit.setCurrentCharFormat(fmt)
            self.text_edit.insertPlainText(f"[{level}] ")
        else:
            all_x1b = [index for index, s in enumerate(message) if s == "\x1b"]
            all_x1b_ends = []
            for x1b in all_x1b:
                for index, s in enumerate(message[x1b:]):
                    if s == 'm':
                        all_x1b_ends.append(index + x1b)
                        break

            self.ansi_color_map["0"] = self.text_edit.textColor()

            for idx, (start, end) in enumerate(zip(all_x1b, all_x1b_ends)):
                color_code = message[start + 2:end]

                if ";" in color_code:
                    color_code = color_code.split(";")[1]

                fmt_color = self.ansi_color_map.get(color_code, self.text_edit.textColor())

                fmt = QTextCharFormat()
                if fmt_color:
                    fmt.setForeground(fmt_color)

                if idx == 0 and not len(all_x1b) % 2:
                    level_text = message[all_x1b_ends[0] + 1: all_x1b[1]].strip()

                    if level_text.endswith(":"):
                        level_text = level_text[:-1].strip()

                    self.text_edit.setCurrentCharFormat(fmt)
                    self.text_edit.insertPlainText(f"[{level_text}] ")


                next_text_end = all_x1b[idx + 1] if idx + 1 < len(all_x1b) else len(message)
                plain_text_segment = message[end + 1: next_text_end]

                if idx == 0 and not len(all_x1b) % 2:continue

                self.text_edit.setCurrentCharFormat(fmt)
                self.text_edit.insertPlainText(plain_text_segment)

            self.text_edit.setCurrentCharFormat(QTextCharFormat())
            self.text_edit.insertPlainText("\n")
            self.text_edit.moveCursor(QTextCursor.MoveOperation.End)
            return

        # 插入正文（恢复默认颜色）
        default_fmt = QTextCharFormat()
        self.text_edit.setCurrentCharFormat(default_fmt)
        self.text_edit.insertPlainText(f"{message}\n")

        # 自动滚动到最下方
        self.text_edit.moveCursor(QTextCursor.MoveOperation.End)
