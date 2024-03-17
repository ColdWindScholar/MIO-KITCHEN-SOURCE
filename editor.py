import logging
import time
import tkinter as tk
from os.path import basename
from tkinter import ttk
import pygments.lexers
from chlorophyll import CodeView
from utils import cz


class PythonEditor(tk.Frame):
    def __init__(self, parent, file_):
        tk.Frame.__init__(self, parent)
        self.file_ = file_
        self.parent = parent
        self.text = CodeView(self, wrap="word", undo=True, lexer=pygments.lexers.BashLexer, color_scheme="monokai")
        self.text.pack(side="left", fill="both", expand=True)
        f1 = ttk.Frame(self.parent)
        self.save_b = ttk.Button(f1, text="保存 | Save", command=lambda: cz(self.save))
        self.save_b.pack(side=tk.LEFT, fill=tk.X, padx=5, pady=5, expand=1)
        ttk.Button(f1, text="关闭 | Close", command=self.parent.destroy).pack(side=tk.LEFT, fill=tk.X, padx=5, pady=5,
                                                                              expand=1)
        f1.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        if self.file_:
            try:
                with open(self.file_, 'r+', encoding='utf-8', newline='\n') as f:
                    self.text.delete(0.0, tk.END)
                    self.text.insert(tk.END, f.read())
            except Exception as e:
                logging.debug(e)
            self.parent.title(f"{basename(self.file_)} - Editor")

    def save(self):
        self.save_b.configure(text='已保存 | Saved', state='disabled')
        with open(self.file_, 'w+', encoding='utf-8', newline='\n') as txt:
            txt.write(self.text.get(1.0, tk.END))
        time.sleep(1)
        self.save_b.configure(text='保存 | Save', state='normal')


def main(file_=None):
    root = tk.Toplevel()
    root.title("Editor")
    editor = PythonEditor(root, file_)
    editor.pack(side="top", fill="both", expand=True)
