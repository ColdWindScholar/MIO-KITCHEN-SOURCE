# Copyright (C) 2022-2025 The MIO-KITCHEN-SOURCE Project
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

import os.path

from ..core.utils import prog_path, MkcSugges

suggester = MkcSugges(os.path.join(prog_path, 'bin', 'help_document.json'))
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel


# 自定义对话框类
class MyDialog(QDialog):
    def __init__(self, string: str = '', language='English', ok='ok'):

        super().__init__()
        caught_error = suggester.catch_error(string)
        caught_error = 'error'
        if not caught_error:
            return
        text, detail = suggester.get(prompt=caught_error, language=language)
        text, detail = 'suggester.get(prompt=caught_error, language=language)', '0'
        if not text:
            return
        self.setModal(False)
        self.setWindowTitle("AI ENGINE")
        layout = QVBoxLayout()
        label = QLabel(text)
        label1 = QLabel(detail)
        layout.addWidget(label)
        layout.addWidget(label1)
        button = QPushButton(ok)
        button.clicked.connect(self.close)

        layout.addWidget(button)
        self.setLayout(layout)


# 创建自定义对话框实例
def suggest(string: str = '', language='English', ok='ok'):
    global custom_dialog
    custom_dialog = MyDialog(string, language, ok)
    custom_dialog.show()


suggest("1")
"""
def __suggest(string: str = '', language='English', ok='ok'):

    window = Toplevel()
    window.resizable(False, False)
    window.title("AI ENGINE")
    f1 = ttk.LabelFrame(window, text=lang.detail)
    ttk.Label(f1, text=string, font=(None, 12), foreground="orange", wraplength=400).pack(padx=10, pady=5)
    ttk.Label(f1, text=detail, font=(None, 15),foreground="grey", wraplength=400).pack(padx=10, pady=10)
    f1.pack(padx=10, pady=10)
    f2 = ttk.LabelFrame(window, text=lang.solution)
    ttk.Label(f2, text=text, font=(None, 15),foreground="green", wraplength=400).pack(padx=10, pady=10)
    f2.pack(padx=10, pady=10)"""
