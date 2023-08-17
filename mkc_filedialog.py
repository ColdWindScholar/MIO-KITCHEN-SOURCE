# File Chose Extra Module For MIO-KITCHEN
import os
from tkinter import Toplevel, Listbox, X, BOTH, LEFT, END, StringVar
from tkinter.ttk import *


class askopenfilename(Toplevel):
    def __init__(self, title="Chose File", filetypes=(("*", "*.*"),)):
        super().__init__()
        self.title(title)
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.filetypes = filetypes
        self.type = Combobox(self, state='readonly', values=[i[1] for i in self.filetypes])
        try:
            self.type.current(0)
        finally:
            pass
        self.type.pack(fill=X, padx=5, pady=5)
        self.path = StringVar()
        self.paths = Entry(self, textvariable=self.path)
        self.paths.bind("<Return>", self.p_bind)
        self.paths.setvar("/")
        self.paths.pack(fill=X, padx=5, pady=5)
        self.show = Listbox(self, activestyle='dotbox', highlightthickness=0)
        self.show.bind("<Double-Button-1>", self.p_bind)
        self.show.pack(fill=BOTH, padx=5, pady=5)
        ff = Frame(self)
        Button(ff, text="选择|Chose", command=self.return_var).pack(fill=X, side=LEFT, padx=5, pady=5)
        Button(ff, text="刷新|Refresh", command=self.refs).pack(fill=X, side=LEFT, padx=5, pady=5)
        Button(ff, text="取消|Cancel", command=self.cancel).pack(fill=X, side=LEFT, padx=5, pady=5)
        ff.pack(padx=5, pady=5, fill=X)
        self.wait_window()

    def p_bind(self, event):
        try:
            file = self.show.get(self.show.curselection())
        except:
            file = ""
        var = os.path.join(self.path.get(), file)
        var = os.path.abspath(var)
        if os.path.isdir(var):
            self.path.set(var)
            self.refs()
        elif os.path.isfile(var):
            self.return_var()

    def refs(self):
        self.show.delete(0, END)
        if not self.path.get():
            self.path.set("/")
        f, e = self.type.get().replace("*", "").split(".")
        for f in os.listdir(self.path.get()):
            if f.startswith(f) and f.endswith(e):
                self.show.insert(END, f)

    def return_var(self):
        var = os.path.join(self.path.get(), self.show.get(self.show.curselection()))
        self.destroy()
        return var

    def cancel(self):
        self.destroy()
        return ""


class askdirectory(Toplevel):
    def __init__(self, title="Chose File"):
        super().__init__()
        self.title(title)
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.path = StringVar()
        self.paths = Entry(self, textvariable=self.path)
        self.paths.bind("<Return>", self.p_bind)
        self.paths.setvar("/")
        self.paths.pack(fill=X, padx=5, pady=5)
        self.show = Listbox(self, activestyle='dotbox', highlightthickness=0)
        self.show.bind("<Double-Button-1>", self.p_bind)
        self.show.pack(fill=BOTH, padx=5, pady=5)
        ff = Frame(self)
        Button(ff, text="选择|Chose", command=self.return_var).pack(fill=X, side=LEFT, padx=5, pady=5)
        Button(ff, text="刷新|Refresh", command=self.refs).pack(fill=X, side=LEFT, padx=5, pady=5)
        Button(ff, text="取消|Cancel", command=self.cancel).pack(fill=X, side=LEFT, padx=5, pady=5)
        ff.pack(padx=5, pady=5, fill=X)
        self.wait_window()

    def p_bind(self, event):
        try:
            file = self.show.get(self.show.curselection())
        except:
            file = ""
        var = os.path.join(self.path.get(), file)
        var = os.path.abspath(var)
        if os.path.isdir(var):
            self.path.set(var)
            self.refs()
        elif os.path.isfile(var):
            self.return_var()

    def refs(self):
        self.show.delete(0, END)
        if not self.path.get():
            self.path.set("/")
        for f in os.listdir(self.path.get()):
            if os.path.isdir(os.path.join(self.path.get(), f)):
                self.show.insert(END, f)

    def return_var(self):
        var = os.path.join(self.path.get(), self.show.get(self.show.curselection()))
        self.destroy()
        return var

    def cancel(self):
        self.destroy()
        return ""
