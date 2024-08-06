# Copyright (C) 2024 The MIO-KITCHEN-SOURCE Project
#
# Licensed under theGNU AFFERO GENERAL PUBLIC LICENSE, Version 3.0 (the "License");
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
import logging
import os
import time
import tkinter as tk
from tkinter import ttk, END, X, LEFT
from tkinter.ttk import Button

import pygments.lexers
from chlorophyll import CodeView
from utils import cz, gettype, lang


class PythonEditor(tk.Frame):
    def __init__(self, parent, path, file_name, lexer=pygments.lexers.BashLexer):
        tk.Frame.__init__(self, parent)
        self.file_name = file_name
        self.path = path
        if not os.path.exists(self.path):
            os.makedirs(self.path, exist_ok=True)
        self.parent = parent
        self.text = CodeView(self, wrap="word", undo=True, lexer=lexer, color_scheme="dracula")
        self.text.pack(side="left", fill="both", expand=True)
        f1 = ttk.Frame(self.parent)
        ttk.Button(f1, text=lang.text17, command=self.parent.destroy).pack(side=tk.LEFT, fill=tk.X, padx=5, pady=5,
                                                                              expand=1)
        self.save_b = ttk.Button(f1, text=lang.t54, command=lambda: cz(self.save), style="Accent.TButton")
        self.save_b.pack(side=tk.LEFT, fill=tk.X, padx=5, pady=5, expand=1)
        f1.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        self.show = tk.Listbox(self, activestyle='dotbox', highlightthickness=0)
        self.show.bind("<Double-Button-1>", self.p_bind)
        self.show.pack(fill=tk.BOTH, padx=5, pady=5)
        ff = ttk.Frame(self)
        Button(ff, text=lang.text23, command=self.refs).pack(fill=X, side=LEFT, padx=5, pady=5)
        ff.pack(padx=5, pady=5, fill=X)
        self.refs()

    def p_bind(self, event):
        try:
            file = self.show.get(self.show.curselection())
        except:
            file = ""
        var = os.path.abspath(os.path.join(self.path, file))
        if os.path.isfile(var):
            self.file_name = os.path.basename(var)
            self.load()

    def refs(self):
        self.show.delete(0, END)
        for f in os.listdir(self.path):
            if os.path.isfile(os.path.join(self.path, f)):
                if gettype(os.path.join(self.path, f)) == 'unknown':
                    self.show.insert(END, f)
        self.load()

    def save(self):
        self.save_b.configure(text=lang.t55, state='disabled')
        with open(os.path.join(self.path, self.file_name), 'w+', encoding='utf-8', newline='\n') as txt:
            txt.write(self.text.get(1.0, tk.END))
        time.sleep(1)
        self.save_b.configure(text=lang.t54, state='normal')

    def load(self):
        if self.file_name:
            try:
                with open(os.path.join(self.path, self.file_name), 'rb+') as f:
                    self.text.delete(0.0, tk.END)
                    try:
                        data = f.read().decode("utf-8")
                    except:
                        data = f.read().decode("gbk")
                    self.text.insert(tk.END, data)
            except Exception as e:
                logging.debug(e)
            self.parent.title(f"{self.file_name} - Editor")


def main(file_=None, file_name=None, lexer=pygments.lexers.BashLexer):
    root = tk.Toplevel()
    root.title("Editor")
    editor = PythonEditor(root, file_, file_name, lexer=lexer)
    editor.pack(side="top", fill="both", expand=True)
