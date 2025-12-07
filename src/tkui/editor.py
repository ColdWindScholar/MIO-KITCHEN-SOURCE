# Copyright (C) 2022-2025 The MIO-KITCHEN-SOURCE Project
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
import shutil
import time
import tkinter as tk
from tkinter import ttk, END, X, LEFT
from tkinter.ttk import Button
import pygments.lexers
from chlorophyll import CodeView

from ..core.utils import create_thread, lang
from ..tkui.controls import input_


class PythonEditor(tk.Frame):
    def __init__(self, parent, path, file_name, lexer=pygments.lexers.BashLexer):
        super().__init__(parent)
        self.file_name = file_name
        self.path = path
        if not os.path.exists(self.path):
            os.makedirs(self.path, exist_ok=True)
        self.parent = parent
        self.text = CodeView(self, wrap="word", undo=True, lexer=lexer, color_scheme="dracula")
        self.text.pack(side="left", fill="both", expand=True)
        self.encoding = tk.StringVar(value='utf-8')
        self.encoding.trace('w', self.load)
        f1 = ttk.Frame(self.parent)
        ttk.Button(f1, text=lang.text17, command=self.parent.destroy).pack(side=tk.LEFT, fill=tk.X, padx=5, pady=5,
                                                                           expand=1)
        self.save_b = ttk.Button(f1, text=lang.t54, command=lambda: create_thread(self.save), style="Accent.TButton")
        self.save_b.pack(side=tk.LEFT, fill=tk.X, padx=5, pady=5, expand=1)
        f1.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        self.show = tk.Listbox(self, activestyle='dotbox', highlightthickness=0)
        self.show.bind("<Double-Button-1>", lambda x: self.p_bind())
        self.show.pack(fill=tk.BOTH, padx=5, pady=5, expand=True)
        ff = ttk.Frame(self)
        Button(ff, text=lang.text23, command=self.refs).pack(fill=X, side=LEFT, padx=5, pady=5, expand=True)
        Button(ff, text=lang.text115, command=self.new).pack(fill=X, side=LEFT, padx=5, pady=5, expand=True)
        Button(ff, text=lang.text116, command=self.delete).pack(fill=X, side=LEFT, padx=5, pady=5, expand=True)
        Button(ff, text=lang.text117, command=self.rename).pack(fill=X, side=LEFT, padx=5, pady=5, expand=True)
        ff.pack(padx=5, pady=5, fill=X, expand=True)
        format_frame = ttk.Frame(self)
        ttk.Label(format_frame, text="Encoding:").pack(padx=5, pady=5, expand=True, side=LEFT, fill=X)
        encoding_comboxx = ttk.Combobox(format_frame, values=['utf-8', 'gbk', 'gb2312', 'utf-16'],
                                        textvariable=self.encoding)
        encoding_comboxx.pack(fill=X,
                              side=LEFT,
                              padx=5,
                              pady=5,
                              expand=True)
        encoding_comboxx.bind('<<ComboboxSelected>>', lambda *x: self.load())
        format_frame.pack(padx=5, pady=5, fill=X, expand=True)
        self.refs()

    def rename(self):
        try:
            file = self.show.get(self.show.curselection())
        except Exception:
            logging.exception("delete editor")
            return
        if file in ['.', '..']:
            return
        is_current_file = file == self.file_name
        if is_current_file:
            self.save()
        new_name = input_('Enter New Name', file, master=self)
        if not new_name:
            return
        if os.path.exists(os.path.join(self.path, new_name)):
            print(f"{new_name} is exists already.")
            return
        os.rename(os.path.join(self.path, file), os.path.join(self.path, new_name))
        self.file_name = new_name
        self.refs()
        self.load()

    def delete(self):
        try:
            file = self.show.get(self.show.curselection())
        except Exception:
            logging.exception("delete editor")
            return
        if file in ['.', '..']:
            return
        file_path = os.path.join(self.path, file)
        if os.path.isdir(file_path):
            shutil.rmtree(file_path)
        if os.path.isfile(file_path):
            os.remove(file_path)
        self.refs()

    def new(self):
        new_name = input_('Enter New File Name', "new.txt", master=self)
        if not new_name:
            return
        os.makedirs(self.path, exist_ok=True)
        if os.path.exists(os.path.join(self.path, new_name)):
            print(os.path.join(self.path, new_name), 'is exists already.')
            return
        with open(os.path.join(self.path, new_name), 'w', encoding='utf-8'):
            pass
        self.file_name = new_name
        self.refs()
        self.load()

    def p_bind(self):
        try:
            file = self.show.get(self.show.curselection())
        except:
            file = ""
        if file == '..':
            self.path = os.path.dirname(self.path)
            self.refs()
            return
        var = os.path.abspath(os.path.join(self.path, file))
        if os.path.isdir(var):
            self.path = var
            self.refs()
        elif os.path.isfile(var):
            self.file_name = os.path.basename(var)
            self.load()

    def refs(self):
        self.show.delete(0, END)
        self.show.insert(END, "..")
        for f in os.listdir(self.path):
            self.show.insert(END, f)
        self.load()

    def save(self):
        self.save_b.configure(text=lang.t55, state='disabled')
        with open(os.path.join(self.path, self.file_name), 'w+', encoding='utf-8', newline='\n') as txt:
            txt.write(self.text.get(1.0, tk.END))
        time.sleep(0.1)
        if self.winfo_exists():
            self.save_b.configure(text=lang.t54, state='normal')

    def load(self):
        if self.file_name:
            try:
                with open(os.path.join(self.path, self.file_name), 'rb+') as f:
                    self.text.delete(0.0, tk.END)
                    try:
                        data = f.read().decode(self.encoding.get())
                    except Exception as e:
                        logging.exception('read license')
                        self.text.insert(tk.END,
                                         f'[MIO-KITCHEN] Cannot load {os.path.join(self.path, self.file_name)}.\nDon\'t Click \'Save\' Button!\nReason:\n{e}')
                    self.text.insert(tk.END, data)
            except Exception as e:
                logging.debug(e)
            self.parent.title(f"{self.file_name}:[{self.encoding.get()}] - Editor")


def main(file_=None, file_name=None, lexer=pygments.lexers.BashLexer):
    root = tk.Toplevel()
    root.title("Editor")
    editor = PythonEditor(root, file_, file_name, lexer=lexer)
    editor.pack(side="top", fill="both", expand=True)
