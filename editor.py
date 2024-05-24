import logging
import os
import time
import tkinter as tk
from tkinter import ttk, END, X, LEFT
from tkinter.ttk import Button

import pygments.lexers
from chlorophyll import CodeView
from utils import cz, gettype


class PythonEditor(tk.Frame):
    def __init__(self, parent, path, file_name):
        tk.Frame.__init__(self, parent)
        self.file_name = file_name
        self.path = path
        self.parent = parent
        self.text = CodeView(self, wrap="word", undo=True, lexer=pygments.lexers.BashLexer, color_scheme="dracula")
        self.text.pack(side="left", fill="both", expand=True)
        f1 = ttk.Frame(self.parent)
        ttk.Button(f1, text="关闭 | Close", command=self.parent.destroy).pack(side=tk.LEFT, fill=tk.X, padx=5, pady=5,
                                                                              expand=1)
        self.save_b = ttk.Button(f1, text="保存 | Save", command=lambda: cz(self.save), style="Accent.TButton")
        self.save_b.pack(side=tk.LEFT, fill=tk.X, padx=5, pady=5, expand=1)
        f1.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        self.show = tk.Listbox(self, activestyle='dotbox', highlightthickness=0)
        self.show.bind("<Double-Button-1>", self.p_bind)
        self.show.pack(fill=tk.BOTH, padx=5, pady=5)
        ff = ttk.Frame(self)
        Button(ff, text="刷新|Refresh", command=self.refs).pack(fill=X, side=LEFT, padx=5, pady=5)
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
        self.save_b.configure(text='已保存 | Saved', state='disabled')
        with open(os.path.join(self.path, self.file_name), 'w+', encoding='utf-8', newline='\n') as txt:
            txt.write(self.text.get(1.0, tk.END))
        time.sleep(1)
        self.save_b.configure(text='保存 | Save', state='normal')

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


def main(file_=None, file_name=None):
    root = tk.Toplevel()
    root.title("Editor")
    editor = PythonEditor(root, file_, file_name)
    editor.pack(side="top", fill="both", expand=True)
