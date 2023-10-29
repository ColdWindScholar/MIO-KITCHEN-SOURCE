import logging
import time
import tkinter as tk
from os.path import basename
from tkinter import ttk

kwlist = ['False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue', 'def', 'del',
          'elif', 'else', 'except', 'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is', 'lambda',
          'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'try', 'while', 'with', 'yield', "msh", 'echo', 'sed',
          'find', 'cd', 'done', 'rm', 'mkdir', "mv", "cat"]


class PythonEditor(tk.Frame):
    def __init__(self, parent, file_):
        tk.Frame.__init__(self, parent)
        self.file_ = file_
        self.parent = parent
        self.text = tk.Text(self, wrap="word", undo=True, font=("Calibri", 15))
        self.scrollbar = ttk.Scrollbar(self, command=self.text.yview)
        self.text.configure(yscrollcommand=self.scrollbar.set)
        self.text.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.text.bind("<KeyRelease>", self.highlight)
        self.highlight()
        f1 = ttk.Frame(self.parent)
        self.save_b = ttk.Button(f1, text="保存 | Save", command=self.save)
        self.save_b.pack(side=tk.LEFT, fill=tk.X, padx=5, pady=5, expand=1)
        ttk.Button(f1, text="关闭 | Close", command=self.parent.destroy).pack(side=tk.LEFT, fill=tk.X, padx=5, pady=5,
                                                                              expand=1)
        f1.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        if self.file_:
            try:
                with open(self.file_, 'r+', encoding='utf-8', newline='\n') as f:
                    self.text.delete(0.0, tk.END)
                    self.text.insert(tk.END, f.read())
                    self.highlight()
            except Exception as e:
                logging.debug(e)
            self.parent.title(f"{basename(self.file_)} - Editor")

    def save(self):
        self.save_b.configure(text='已保存', state='disabled')
        with open(self.file_, 'w+', encoding='utf-8', newline='\n') as txt:
            txt.write(self.text.get(1.0, tk.END))
        time.sleep(1)
        self.save_b.configure(text='保存 | Save', state='normal')

    def highlight(self, event=None):
        if event:
            pass
        self.text.tag_remove("keyword", "1.0", "end")
        self.text.tag_remove("builtin", "1.0", "end")
        self.text.tag_remove("string", "1.0", "end")
        self.text.tag_remove("comment", "1.0", "end")

        for word in kwlist:
            start = "1.0"
            while True:
                start = self.text.search(word, start, stopindex="end")
                if not start:
                    break
                end = "{}+{}c".format(start, len(word))
                self.text.tag_add("keyword", start, end)
                start = end

        for word in dir(__builtins__):
            start = "1.0"
            while True:
                start = self.text.search(word, start, stopindex="end")
                if not start:
                    break
                end = "{}+{}c".format(start, len(word))
                self.text.tag_add("builtin", start, end)
                start = end

        start = "1.0"
        countvar = tk.StringVar()
        while True:
            start = self.text.search("@[^@]+@", start, stopindex="end", regexp=True, count=countvar)
            if not start:
                break
            end = "{}+{}c".format(start, countvar.get())
            self.text.tag_add("string", start, end)
            start = end

        start = "1.0"
        countvar = tk.StringVar()
        while True:
            start = self.text.search('"[^"]+@"', start, stopindex="end", regexp=True, count=countvar)
            if not start:
                break
            end = "{}+{}c".format(start, countvar.get())
            self.text.tag_add("string", start, end)
            start = end

        start = "1.0"
        while True:
            start = self.text.search("#", start, stopindex="end")
            if not start:
                break
            end = self.text.search("\n", start, stopindex="end")
            if not end:
                end = "end"
            self.text.tag_add("comment", start, end)
            start = end

        self.text.tag_configure("keyword", foreground="#00BFFF")
        self.text.tag_configure("builtin", foreground="purple")
        self.text.tag_configure("string", foreground="orange")
        self.text.tag_configure("comment", foreground="gray")


def main(file_=None):
    root = tk.Toplevel()
    root.title("Editor")
    editor = PythonEditor(root, file_)
    editor.pack(side="top", fill="both", expand=True)
